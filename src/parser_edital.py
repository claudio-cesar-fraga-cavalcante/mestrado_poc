"""
Módulo de segmentação e indexação estrutural de Editais (.txt) e da Lei 13.303/2016.
Preserva a numeração exata de linhas para rastreabilidade e auditoria jurídica.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


POC_RULE_IDS = ["R01", "R02", "R03", "R09", "R11", "R29", "R38", "R41", "R43"]


@dataclass
class EditalSegmentado:
    nome_arquivo: str
    caminho: str
    linhas_originais: List[str]
    texto_numerado: str
    secoes: Dict[str, str] = field(default_factory=dict)
    resumo_secoes: Dict[str, Dict[str, int]] = field(default_factory=dict)


def carregar_edital_txt(caminho: str | Path) -> EditalSegmentado:
    """Lê um arquivo de edital .txt, indexa todas as linhas e segmenta em seções lógicas."""
    path = Path(caminho)
    conteudo = path.read_text(encoding="utf-8", errors="replace")
    return processar_texto_edital(conteudo, nome_arquivo=path.name, caminho=str(path))


def processar_texto_edital(
    conteudo: str,
    nome_arquivo: str = "edital_customizado.txt",
    caminho: str = "",
) -> EditalSegmentado:
    """Indexa as linhas de um texto de edital e separa Corpo, Termo de Referência e Minuta de Contrato."""
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
    else:
        fim_corpo = idx_tr if idx_tr is not None else (idx_contrato or len(linhas))
        inicio_tr = idx_tr if idx_tr is not None else 0
        fim_tr = idx_contrato if idx_contrato is not None else len(linhas)
        inicio_contrato = idx_contrato if idx_contrato is not None else fim_tr

        secoes = {
            "corpo_edital": "\n".join(linhas_numeradas[:fim_corpo]),
            "termo_referencia": "\n".join(linhas_numeradas[inicio_tr:fim_tr]),
            "minuta_contrato": "\n".join(linhas_numeradas[inicio_contrato:]),
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

    return EditalSegmentado(
        nome_arquivo=nome_arquivo,
        caminho=caminho,
        linhas_originais=linhas,
        texto_numerado=texto_numerado,
        secoes=secoes,
        resumo_secoes=resumo,
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

