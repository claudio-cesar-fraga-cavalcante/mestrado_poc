"""
Módulo de segmentação e indexação estrutural de Editais (.txt e .pdf) e da Lei 13.303/2016.
Preserva a numeração exata de páginas e linhas para rastreabilidade e auditoria jurídica.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union


POC_RULE_IDS = ["R01", "R02", "R03", "R09", "R11", "R29", "R38", "R41", "R43"]


@dataclass
class EditalSegmentado:
    nome_arquivo: str
    caminho: str
    linhas_originais: List[str]
    texto_numerado: str
    secoes: Dict[str, str] = field(default_factory=dict)
    resumo_secoes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    texto_auditoria: str = ""
    total_paginas: int = 0


def _limpar_linha_pdf(raw: str) -> str:
    """Normaliza espaços e remove cabeçalhos/rodapés repetitivos de PDFs do BNDES."""
    s = re.sub(r"\s+", " ", raw).strip()
    if not s:
        return ""
    if re.match(r"^PREG\s*[ÃA]O\s+ELETR", s, re.IGNORECASE) and len(s) > 40 and "Nº" not in s and "OBJETO" not in s:
        return ""
    if re.match(r"^\d{1,3}\s*/\s*\d{1,3}$", s):
        return ""
    return s


def carregar_edital(caminho: Union[str, Path]) -> EditalSegmentado:
    """Despacha automaticamente o carregamento para .pdf ou .txt."""
    path = Path(caminho)
    if path.suffix.lower() == ".pdf":
        return carregar_edital_pdf(path, nome_arquivo=path.name)
    return carregar_edital_txt(path)


def carregar_edital_txt(caminho: Union[str, Path]) -> EditalSegmentado:
    """Lê um arquivo de edital .txt, indexa todas as linhas e segmenta em seções lógicas."""
    path = Path(caminho)
    conteudo = path.read_text(encoding="utf-8", errors="replace")
    return processar_texto_edital(conteudo, nome_arquivo=path.name, caminho=str(path))


def carregar_edital_pdf(
    fonte: Union[str, Path, bytes],
    nome_arquivo: str = "",
) -> EditalSegmentado:
    """
    Lê um arquivo de edital em PDF (via PyMuPDF) a partir de caminho ou bytes,
    indexa cada linha com tag canônica `[Pxx|Lxxxx]` e segmenta em:
    - corpo_edital
    - termo_referencia (Anexo I)
    - minuta_contrato (Anexo III / Contrato OCS + Anexo IV Matriz de Riscos)
    """
    import pymupdf

    if isinstance(fonte, (bytes, bytearray)):
        doc = pymupdf.open(stream=bytes(fonte), filetype="pdf")
        caminho_str = nome_arquivo or "upload.pdf"
        nome_final = nome_arquivo or "upload.pdf"
    else:
        path = Path(fonte)
        doc = pymupdf.open(path)
        caminho_str = str(path)
        nome_final = nome_arquivo or path.name

    try:
        total_paginas = len(doc)
        registros: List[tuple[int, str]] = []
        for pg_idx, page in enumerate(doc, start=1):
            txt = page.get_text("text") or ""
            for raw in txt.splitlines():
                limpa = _limpar_linha_pdf(raw)
                if limpa:
                    registros.append((pg_idx, limpa))
    finally:
        doc.close()

    linhas_originais = [texto for _, texto in registros]
    linhas_numeradas = [
        f"[P{pg:02d}|L{idx:04d}] {texto}"
        for idx, (pg, texto) in enumerate(registros, start=1)
    ]
    texto_numerado = "\n".join(linhas_numeradas)

    idx_tr: Optional[int] = None
    idx_contrato: Optional[int] = None
    idx_fim_minuta: Optional[int] = None

    rx_tr_strict = re.compile(
        r"^ANEXO\s+I\s*[–—-]\s*(?:ESPECIFICA|TERMO\s+DE\s+REFER)",
        re.IGNORECASE,
    )
    rx_contrato_strict = re.compile(
        r"^(?:ANEXO\s+[IVX]+\s*[–—-]\s*MINUTA\s+D[OE]\s+CONTRATO|CONTRATO\s+OCS\s+N[º°]\s*___)",
        re.IGNORECASE,
    )
    rx_pos_matriz = re.compile(
        r"^ANEXO\s+V\s*[–—-]\s*MODELOS?\s+DE\s+DECLARA",
        re.IGNORECASE,
    )
    rx_tr_fallback = re.compile(
        r"^(ANEXO\s+I\b.*(?:ESPECIFICA|TERMO\s+DE\s+REFER)|TERMO\s+DE\s+REFER[ÊE]NCIA)",
        re.IGNORECASE,
    )
    rx_contrato_fallback = re.compile(
        r"^(CONTRATO\s+(?:OCS|SAP|DE\s+PRESTA|N[º°])|MINUTA\s+D[EO]\s+CONTRATO|ANEXO\s+[IVX]+\s*[–—-]\s*MINUTA\s+D[EO]\s+CONTRATO)",
        re.IGNORECASE,
    )

    for idx, (pg, s) in enumerate(registros):
        if idx_tr is None and pg >= 10 and rx_tr_strict.search(s):
            idx_tr = idx
        if idx_contrato is None and pg >= 25 and rx_contrato_strict.search(s):
            idx_contrato = idx
        if idx_contrato is not None and idx_fim_minuta is None and idx > idx_contrato + 100 and rx_pos_matriz.search(s):
            idx_fim_minuta = idx

    # Fallbacks caso um PDF customizado possua menos páginas
    if idx_tr is None or idx_contrato is None:
        for idx, (_, s) in enumerate(registros):
            if idx_tr is None and idx > 20 and rx_tr_fallback.search(s):
                idx_tr = idx
            elif idx_contrato is None and idx > 50 and rx_contrato_fallback.search(s):
                idx_contrato = idx

    if idx_tr is None and idx_contrato is None:
        secoes = {
            "corpo_edital": texto_numerado,
            "termo_referencia": texto_numerado,
            "minuta_contrato": texto_numerado,
        }
        resumo = {
            "Documento Completo": {
                "inicio": 1,
                "fim": len(linhas_originais),
                "total_linhas": len(linhas_originais),
                "total_paginas": total_paginas,
            }
        }
        texto_auditoria = texto_numerado
    else:
        fim_corpo = idx_tr if idx_tr is not None else (idx_contrato or len(linhas_originais))
        inicio_tr = idx_tr if idx_tr is not None else 0
        fim_tr = idx_contrato if idx_contrato is not None else len(linhas_originais)
        inicio_contrato = idx_contrato if idx_contrato is not None else fim_tr
        fim_contrato = idx_fim_minuta if idx_fim_minuta is not None else len(linhas_originais)

        bloco_corpo = "\n".join(linhas_numeradas[:fim_corpo])
        bloco_tr = "\n".join(linhas_numeradas[inicio_tr:fim_tr])
        bloco_minuta = "\n".join(linhas_numeradas[inicio_contrato:fim_contrato])

        secoes = {
            "corpo_edital": bloco_corpo,
            "termo_referencia": bloco_tr,
            "minuta_contrato": bloco_minuta,
        }

        def _pg(idx_pos: int) -> int:
            if not registros:
                return 0
            pos = max(0, min(idx_pos, len(registros) - 1))
            return registros[pos][0]

        resumo = {
            "Corpo do Edital": {
                "inicio": 1,
                "fim": fim_corpo,
                "total_linhas": fim_corpo,
                "pagina_inicio": _pg(0),
                "pagina_fim": _pg(max(0, fim_corpo - 1)),
            },
            "Anexo I / Termo de Referência": {
                "inicio": inicio_tr + 1,
                "fim": fim_tr,
                "total_linhas": max(0, fim_tr - inicio_tr),
                "pagina_inicio": _pg(inicio_tr),
                "pagina_fim": _pg(max(inicio_tr, fim_tr - 1)),
            },
            "Minuta de Contrato (+ Matriz de Riscos)": {
                "inicio": inicio_contrato + 1,
                "fim": fim_contrato,
                "total_linhas": max(0, fim_contrato - inicio_contrato),
                "pagina_inicio": _pg(inicio_contrato),
                "pagina_fim": _pg(max(inicio_contrato, fim_contrato - 1)),
            },
        }
        texto_auditoria = (
            "=== SEÇÃO 1: CORPO DO EDITAL ===\n"
            + bloco_corpo
            + "\n\n=== SEÇÃO 2: ANEXO I / TERMO DE REFERÊNCIA ===\n"
            + bloco_tr
            + "\n\n=== SEÇÃO 3: MINUTA DE CONTRATO E MATRIZ DE RISCOS ===\n"
            + bloco_minuta
        )

    return EditalSegmentado(
        nome_arquivo=nome_final,
        caminho=caminho_str,
        linhas_originais=linhas_originais,
        texto_numerado=texto_numerado,
        secoes=secoes,
        resumo_secoes=resumo,
        texto_auditoria=texto_auditoria,
        total_paginas=total_paginas,
    )


def processar_texto_edital(
    conteudo: str,
    nome_arquivo: str = "edital_customizado.txt",
    caminho: str = "",
) -> EditalSegmentado:
    """Indexa as linhas de um texto de edital (.txt) e separa Corpo, Termo de Referência e Minuta de Contrato."""
    linhas = conteudo.splitlines()
    linhas_numeradas = [f"[L{i:04d}] {linha}" for i, linha in enumerate(linhas, start=1)]
    texto_numerado = "\n".join(linhas_numeradas)

    idx_tr = None
    idx_contrato = None

    padrao_tr = re.compile(
        r"^(ANEXO\s+I\b.*(?:ESPECIFICA|TERMO\s+DE\s+REFER)|TERMO\s+DE\s+REFER[ÊE]NCIA)",
        re.IGNORECASE,
    )
    padrao_contrato = re.compile(
        r"^(CONTRATO\s+(?:OCS|SAP|DE\s+PRESTA|N[º°])|MINUTA\s+DE\s+CONTRATO|ANEXO\s+(?:II|III)\s*[–-]\s*MINUTA\s+DE\s+CONTRATO)",
        re.IGNORECASE,
    )

    for idx, linha in enumerate(linhas):
        limpa = linha.strip()
        if idx_tr is None and padrao_tr.search(limpa):
            idx_tr = idx
        elif idx_contrato is None and idx > 50 and padrao_contrato.search(limpa):
            idx_contrato = idx

    if idx_tr is None and idx_contrato is None:
        secoes = {
            "corpo_edital": texto_numerado,
            "termo_referencia": texto_numerado,
            "minuta_contrato": texto_numerado,
        }
        resumo = {
            "Documento Completo": {"inicio": 1, "fim": len(linhas), "total_linhas": len(linhas)}
        }
        texto_auditoria = texto_numerado
    else:
        fim_corpo = idx_tr if idx_tr is not None else (idx_contrato or len(linhas))
        inicio_tr = idx_tr if idx_tr is not None else 0
        fim_tr = idx_contrato if idx_contrato is not None else len(linhas)
        inicio_contrato = idx_contrato if idx_contrato is not None else fim_tr

        bloco_corpo = "\n".join(linhas_numeradas[:fim_corpo])
        bloco_tr = "\n".join(linhas_numeradas[inicio_tr:fim_tr])
        bloco_minuta = "\n".join(linhas_numeradas[inicio_contrato:])

        secoes = {
            "corpo_edital": bloco_corpo,
            "termo_referencia": bloco_tr,
            "minuta_contrato": bloco_minuta,
        }
        resumo = {
            "Corpo do Edital": {
                "inicio": 1,
                "fim": fim_corpo,
                "total_linhas": fim_corpo,
            },
            "Anexo I / Termo de Referência": {
                "inicio": inicio_tr + 1,
                "fim": fim_tr,
                "total_linhas": max(0, fim_tr - inicio_tr),
            },
            "Minuta de Contrato": {
                "inicio": inicio_contrato + 1,
                "fim": len(linhas),
                "total_linhas": max(0, len(linhas) - inicio_contrato),
            },
        }
        texto_auditoria = texto_numerado

    return EditalSegmentado(
        nome_arquivo=nome_arquivo,
        caminho=caminho,
        linhas_originais=linhas,
        texto_numerado=texto_numerado,
        secoes=secoes,
        resumo_secoes=resumo,
        texto_auditoria=texto_auditoria,
        total_paginas=0,
    )


def carregar_regras_validador(caminho_json: str | Path) -> Dict[str, dict]:
    """Carrega o catálogo de regras extraídas da Lei 13.303 (regras_validador.json)."""
    path = Path(caminho_json)
    dados = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: item for item in dados}


def carregar_artigos_lei13303(caminho_lei: str | Path) -> Dict[int, str]:
    """Indexa todos os artigos de L13303.txt pelo número do artigo (1 a 97)."""
    path = Path(caminho_lei)
    linhas = path.read_text(encoding="utf-8", errors="replace").splitlines()

    artigos: Dict[int, List[str]] = {}
    artigo_atual: Optional[int] = None
    padrao_art = re.compile(r"^\s*Art\.\s*(\d+)[º°.]?\s+(.*)")
    padrao_cabecalho = re.compile(r"^\s*(?:={10,}|-{10,}|TÍTULO\s+|CAPÍTULO\s+|Seção\s+)")

    for linha in linhas:
        m = padrao_art.match(linha)
        if m:
            artigo_atual = int(m.group(1))
            artigos[artigo_atual] = [linha.strip()]
        elif artigo_atual is not None:
            if padrao_cabecalho.match(linha):
                continue
            if linha.strip():
                artigos[artigo_atual].append(linha.rstrip())

    return {num: "\n".join(blocos) for num, blocos in artigos.items()}


def buscar_texto_dispositivo_legal(dispositivo_str: str, mapa_artigos: Dict[int, str]) -> str:
    """Dado um campo 'dispositivo_legal' (ex: 'Art. 47, I, c' ou 'Art. 42, X / Art. 69, X'),
    retorna o texto oficial correspondente extraído de L13303.txt."""
    numeros = [int(n) for n in re.findall(r"Art(?:igo)?\.?\s*(\d+)", dispositivo_str, re.IGNORECASE)]
    if not numeros:
        return "Dispositivo legal não mapeado numericamente."

    trechos = []
    vistos = set()
    for num in numeros:
        if num not in vistos and num in mapa_artigos:
            vistos.add(num)
            trechos.append(mapa_artigos[num])

    return "\n\n".join(trechos) if trechos else f"Artigo(s) {numeros} não localizado(s) em L13303.txt."
