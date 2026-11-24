"""
Script de Benchmark em Lote sobre os 10 Editais Reais do BNDES (PDF).
Executa para cada edital:
1. Segmentação tripartite (corpo_edital, termo_referencia, minuta_contrato) com tags [Pxx|Lxxxx].
2. Pipeline Neuro-Simbólico: Extração estruturada Gemini (Structured Outputs, T=0.0) -> Prolog + UFO-L.
3. Baseline Somente Neural: Julgamento direto end-to-end via Gemini (T=0.0) sem Prolog e sem UFO-L.
4. Persistência em `dados/benchmark_10_editais/<stem>.json`, `resumo_consolidado.json` e `revisao_gabarito_90_casos.csv`.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.explainer import gerar_pareceres_edital
from src.extractor_llm import (
    FatosExtraidosEdital,
    converter_fatos_para_prolog,
    executar_avaliacao_somente_neural_gemini,
    extrair_fatos_via_gemini,
)
from src.parser_edital import (
    POC_RULE_IDS,
    carregar_artigos_lei13303,
    carregar_edital_pdf,
    carregar_regras_validador,
)
from src.reasoner_prolog import AvaliadorSimbolicoUfoL


def _chave_ordenacao_pe(path: Path) -> tuple[int, str]:
    m = re.search(r"PE_(\d+)", path.name, re.IGNORECASE)
    return (int(m.group(1)) if m else 9999, path.name)


def consolidar_benchmark(cache_dir: Path, catalogo_regras: dict) -> dict:
    """Lê os JSONs individuais em `cache_dir` e gera `resumo_consolidado.json` e `revisao_gabarito_90_casos.csv`."""
    arquivos = sorted(
        [p for p in cache_dir.glob("Edital_*.json")],
        key=_chave_ordenacao_pe,
    )

    editais_resumo = []
    divergencias_reais = []
    incidencia_por_regra = {
        rid: {
            "regra_id": rid,
            "categoria": catalogo_regras[rid]["categoria"],
            "dispositivo_legal": catalogo_regras[rid]["dispositivo_legal"],
            "nesy_inconformes": 0,
            "nesy_conformes": 0,
            "neural_inconformes": 0,
            "neural_conformes": 0,
            "divergencias": 0,
        }
        for rid in POC_RULE_IDS
    }

    csv_rows = []
    total_verificacoes = 0
    total_divergencias = 0
    total_divergencias_indep = 0
    tempos_extracao = []
    tempos_prolog_ms = []
    tempos_neural = []
    tokens_extracao = []
    tokens_neural = []
    homog_itens = []

    for arq in arquivos:
        dados = json.loads(arq.read_text(encoding="utf-8"))
        nome = dados["nome_arquivo"]
        resumo_regras = dados["resumo_regras_nesy"]
        julg_neural = dados["julgamentos_somente_neural"]

        nesy_inc = 0
        nesy_conf = 0
        divs_edital = []

        linha_matriz = {
            "Edital": nome,
            "Páginas": dados["total_paginas"],
            "Objeto": (dados["fatos"].get("resumo_objeto") or "")[:110],
        }

        for rid in POC_RULE_IDS:
            r_nesy = resumo_regras[rid]
            r_neur = julg_neural.get(rid, {})
            st_nesy = r_nesy["status_verificacao"]
            st_neur = r_neur.get("status_verificacao", "N/A")
            div = st_nesy != st_neur

            total_verificacoes += 1
            if st_nesy == "Indício de Inconformidade":
                nesy_inc += 1
                incidencia_por_regra[rid]["nesy_inconformes"] += 1
                linha_matriz[rid] = "🚨 Inconforme"
            else:
                nesy_conf += 1
                incidencia_por_regra[rid]["nesy_conformes"] += 1
                linha_matriz[rid] = "✅ Conforme"

            if st_neur == "Indício de Inconformidade":
                incidencia_por_regra[rid]["neural_inconformes"] += 1
            elif st_neur == "Conforme":
                incidencia_por_regra[rid]["neural_conformes"] += 1

            if div:
                total_divergencias += 1
                incidencia_por_regra[rid]["divergencias"] += 1
                divs_edital.append(rid)
                tipo_div_neutro = (
                    f"🔀 Divergência (LLM Puro: {st_neur} vs. Prolog/UFO-L: {st_nesy} — requer auditoria)"
                )
                divergencias_reais.append({
                    "edital": nome,
                    "regra_id": rid,
                    "dispositivo_legal": catalogo_regras[rid]["dispositivo_legal"],
                    "status_neuro_simbolico": st_nesy,
                    "status_somente_neural": st_neur,
                    "tipo_limitacao": tipo_div_neutro,
                    "item_evidencia_nesy": r_nesy["item_identificado"],
                    "trecho_evidencia_nesy": r_nesy["trecho_identificado"],
                    "momento_edital_ufol": r_nesy["momento_edital"],
                    "momento_lei_ufol": r_nesy["momento_esperado_lei"],
                    "justificativa_somente_neural": r_neur.get("justificativa_livre_llm", ""),
                    "analise_diferenca": r_neur.get("analise_diferenca_nesy", ""),
                })

            csv_rows.append({
                "edital": nome,
                "regra_id": rid,
                "dispositivo_legal": catalogo_regras[rid]["dispositivo_legal"],
                "status_neuro_simbolico": st_nesy,
                "status_somente_neural": st_neur,
                "divergencia": "SIM" if div else "NAO",
                "momento_edital_ufol": r_nesy["momento_edital"],
                "momento_lei_ufol": r_nesy["momento_esperado_lei"],
                "item_evidencia_nesy": r_nesy["item_identificado"],
                "trecho_evidencia_nesy": r_nesy["trecho_identificado"],
                "justificativa_somente_neural": r_neur.get("justificativa_livre_llm", ""),
                "gabarito_humano_revisao": "",
            })

        # Recorte sem dupla contagem de R01/R02 (agrupa R01 e R02 em 1 hipótese fática do Art. 47, I)
        divs_set = set(divs_edital)
        total_divergencias_indep += (1 if ("R01" in divs_set or "R02" in divs_set) else 0) + sum(
            1 for r in divs_set if r not in ("R01", "R02")
        )

        linha_matriz["Conformes (NeSy)"] = f"{nesy_conf}/{len(POC_RULE_IDS)}"
        linha_matriz["Inconformes (NeSy)"] = nesy_inc
        linha_matriz["Divergências (LLM vs NeSy)"] = ", ".join(divs_edital) if divs_edital else "Nenhuma"
        editais_resumo.append(linha_matriz)

        tempos_extracao.append(dados.get("tempo_extracao_nesy_s", 0.0))
        tempos_prolog_ms.append(dados.get("tempo_prolog_ms", 0.0))
        tempos_neural.append(dados.get("tempo_somente_neural_s", 0.0))
        tk_ext = (dados.get("usage_extracao_nesy") or {}).get("total_token_count")
        tk_neu = (dados.get("usage_somente_neural") or {}).get("total_token_count")
        if isinstance(tk_ext, int) and tk_ext > 0:
            tokens_extracao.append(tk_ext)
        if isinstance(tk_neu, int) and tk_neu > 0:
            tokens_neural.append(tk_neu)
        homog_itens.append({
            "t_ext": dados.get("temperatura_extrator"),
            "t_neu": dados.get("temperatura_somente_neural"),
            "tb": dados.get("thinking_budget"),
            "swipl": "SWI-Prolog" in dados.get("motor_simbolico", ""),
            "cruzada": bool(dados.get("validacao_cruzada_prolog_ok")),
            "ts": bool(dados.get("timestamp_execucao")),
        })

    total_hipoteses_indep = len(arquivos) * 8
    budgets_unicos = sorted({h["tb"] for h in homog_itens if h["tb"] is not None})
    homog_ok = bool(homog_itens) and all(
        h["t_ext"] == 0.0 and h["t_neu"] == 0.0 and h["tb"] is not None and h["swipl"] and h["cruzada"] and h["ts"]
        for h in homog_itens
    ) and len(budgets_unicos) == 1
    resumo = {
        "total_editais": len(arquivos),
        "total_regras_por_edital": len(POC_RULE_IDS),
        "total_verificacoes": total_verificacoes,
        "total_divergencias": total_divergencias,
        "taxa_divergencia_pct": round((total_divergencias / max(1, total_verificacoes)) * 100, 1),
        "total_hipoteses_independentes": total_hipoteses_indep,
        "total_divergencias_sem_dupla_contagem_r01_r02": total_divergencias_indep,
        "taxa_divergencia_sem_dupla_contagem_pct": round((total_divergencias_indep / max(1, total_hipoteses_indep)) * 100, 1),
        "nota_metodologica_r01_r02": (
            "R01 (1ª ordem, bidder_role) e R02 (2ª ordem, bidding_authority_role) representam projeções hohfeldianas "
            "complementares da mesma hipótese fática do Art. 47, I; o recorte sem dupla contagem agrupa R01/R02 em "
            "8 hipóteses independentes por edital."
        ),
        "tempo_medio_extracao_nesy_s": round(sum(tempos_extracao) / max(1, len(tempos_extracao)), 2),
        "tempo_medio_prolog_ms": round(sum(tempos_prolog_ms) / max(1, len(tempos_prolog_ms)), 3),
        "tempo_medio_somente_neural_s": round(sum(tempos_neural) / max(1, len(tempos_neural)), 2),
        "tokens_medios_extracao_nesy": round(sum(tokens_extracao) / len(tokens_extracao), 1) if tokens_extracao else None,
        "tokens_medios_somente_neural": round(sum(tokens_neural) / len(tokens_neural), 1) if tokens_neural else None,
        "homogeneidade_experimental": {
            "homogeneo_100pct": homog_ok,
            "temperatura_extrator_esperada": 0.0,
            "temperatura_somente_neural_esperada": 0.0,
            "thinking_budgets_observados": budgets_unicos,
            "editais_com_swipl": sum(1 for h in homog_itens if h["swipl"]),
            "editais_com_validacao_cruzada_ok": sum(1 for h in homog_itens if h["cruzada"]),
            "editais_com_timestamp": sum(1 for h in homog_itens if h["ts"]),
        },
        "matriz_editais": editais_resumo,
        "incidencia_por_regra": list(incidencia_por_regra.values()),
        "divergencias_detalhadas": divergencias_reais,
    }

    (cache_dir / "resumo_consolidado.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = cache_dir / "revisao_gabarito_90_casos.csv"
    if csv_rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(csv_rows)

    return resumo


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Executa benchmark dos 10 editais PDF do BNDES.")
    parser.add_argument("--force", action="store_true", help="Reprocessa extração + baseline em todos os editais.")
    parser.add_argument(
        "--reavaliar-t0",
        action="store_true",
        help="Reaproveita os fatos já extraídos (T=0.0), reexecuta o novo SWI-Prolog (NAF \\+ + findall) e reexecuta o baseline Somente Neural com temperature=0.0.",
    )
    parser.add_argument("--modelo", default="gemini-2.5-flash", help="Modelo Gemini a utilizar.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout HTTP em segundos por chamada à API Gemini (padrão: 180s).",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=4096,
        help="Teto de tokens de raciocínio interno (thoughts) por chamada Gemini (padrão: 4096).",
    )
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não encontrada no arquivo .env.")

    pdf_dir = BASE_DIR / "dados" / "editais_bndes_pdf"
    cache_dir = BASE_DIR / "dados" / "benchmark_10_editais"
    cache_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pdf_dir.glob("*.pdf"), key=_chave_ordenacao_pe)
    if not pdfs:
        raise RuntimeError(f"Nenhum PDF encontrado em {pdf_dir}")

    catalogo = carregar_regras_validador(BASE_DIR / "dados" / "regras_validador.json")
    artigos_lei = carregar_artigos_lei13303(BASE_DIR / "dados" / "L13303.txt")
    avaliador = AvaliadorSimbolicoUfoL(
        caminho_ufol_pl=BASE_DIR / "dados" / "UFO_L.pl",
        caminho_regras_pl=BASE_DIR / "src" / "ufo_l_rules.pl",
    )

    _log(
        f"Iniciando benchmark em {len(pdfs)} editais PDF do BNDES "
        f"(modelo: {args.modelo} | T=0.0 | thinking_budget={args.thinking_budget} | timeout={args.timeout}s)..."
    )
    for idx, pdf_path in enumerate(pdfs, start=1):
        out_json = cache_dir / f"{pdf_path.stem}.json"
        if out_json.exists() and not args.force and not args.reavaliar_t0:
            _log(f"[{idx}/{len(pdfs)}] {pdf_path.name} -> Cache já existe, pulando (use --force para reexecutar).")
            continue
        if args.reavaliar_t0 and not args.force and out_json.exists():
            prev_check = json.loads(out_json.read_text(encoding="utf-8"))
            if (
                "SWI-Prolog" in prev_check.get("motor_simbolico", "")
                and prev_check.get("thinking_budget") == args.thinking_budget
                and prev_check.get("temperatura_somente_neural") == 0.0
                and prev_check.get("timestamp_execucao")
            ):
                _log(f"[{idx}/{len(pdfs)}] {pdf_path.name} -> Já reavaliado homogeneamente (SWI-Prolog + T=0.0 + budget={args.thinking_budget}), pulando.")
                continue

        _log(f"\n[{idx}/{len(pdfs)}] Processando {pdf_path.name}...")
        _log(f"  [1/5] Carregando e segmentando PDF {pdf_path.name}...")
        ts0 = time.perf_counter()
        edital_seg = carregar_edital_pdf(pdf_path, nome_arquivo=pdf_path.name)
        texto_para_llm = edital_seg.texto_auditoria or edital_seg.texto_numerado
        _log(
            f"  [1/5] Segmentado em {time.perf_counter() - ts0:.2f}s: "
            f"{edital_seg.total_paginas} págs | {len(edital_seg.linhas_originais)} linhas | "
            f"{len(texto_para_llm)} chars para auditoria"
        )

        # 1. Pipeline Neuro-Simbólico: Extração Neural (T=0.0) + Inferência SWI-Prolog/UFO-L
        usage_ext: dict = {}
        if args.reavaliar_t0 and out_json.exists():
            prev = json.loads(out_json.read_text(encoding="utf-8"))
            fatos = FatosExtraidosEdital.model_validate(prev["fatos"])
            modelo_usado = prev.get("modelo_gemini", args.modelo)
            t_extracao = prev.get("tempo_extracao_nesy_s", 0.0)
            usage_ext = prev.get("usage_extracao_nesy") or {}
            _log(f"  [2/5] Reaproveitando fatos em cache (T=0.0 | {t_extracao:.2f}s originais | modelo={modelo_usado}).")
        else:
            _log(f"  [2/5] Extraindo fatos via Gemini (T=0.0, timeout={args.timeout}s)...")
            t0 = time.perf_counter()
            fatos, modelo_usado = extrair_fatos_via_gemini(
                texto_numerado=texto_para_llm,
                nome_arquivo=edital_seg.nome_arquivo,
                api_key=api_key,
                modelo=args.modelo,
                timeout_s=args.timeout,
                verbose=True,
                thinking_budget=args.thinking_budget,
                usage_out=usage_ext,
            )
            t_extracao = time.perf_counter() - t0
            _log(f"  [2/5] Extração concluída em {t_extracao:.2f}s.")

        _log("  [3/5] Gerando ABox Prolog e executando SWI-Prolog...")
        abox_pl = converter_fatos_para_prolog(fatos)
        tp0 = time.perf_counter()
        resultados_prolog, _, motor_label = avaliador.executar_avaliacao(
            edital_id=fatos.identificador_edital,
            abox_prolog=abox_pl,
            regras_selecionadas=POC_RULE_IDS,
        )
        t_prolog_ms = (time.perf_counter() - tp0) * 1000.0

        pareceres_nesy = gerar_pareceres_edital(
            resultados_prolog=resultados_prolog,
            catalogo_regras=catalogo,
            mapa_artigos_lei=artigos_lei,
        )
        conf = sum(1 for p in pareceres_nesy if p.status_verificacao == "Conforme")
        _log(f"  [3/5] SWI-Prolog concluído em {t_prolog_ms:.2f}ms ({conf}/9 conformes | motor: {motor_label}).")

        # 2. Baseline Somente Neural: LLM Puro End-to-End (T=0.0)
        usage_neural: dict = {}
        _log(f"  [4/5] Executando Baseline Somente Neural via Gemini (T=0.0, timeout={args.timeout}s)...")
        t1 = time.perf_counter()
        julgamentos_neural = executar_avaliacao_somente_neural_gemini(
            texto_numerado=texto_para_llm,
            nome_arquivo=edital_seg.nome_arquivo,
            catalogo_regras=catalogo,
            regras_selecionadas=POC_RULE_IDS,
            pareceres_nesy=pareceres_nesy,
            api_key=api_key,
            modelo=modelo_usado,
            timeout_s=args.timeout,
            verbose=True,
            thinking_budget=args.thinking_budget,
            usage_out=usage_neural,
        )
        t_neural = time.perf_counter() - t1
        _log(f"  [4/5] Somente Neural concluído em {t_neural:.2f}s.")

        resumo_regras_nesy = {
            p.regra_id: {
                "status_verificacao": p.status_verificacao,
                "classificacao_risco": p.classificacao_risco,
                "item_identificado": p.item_identificado,
                "trecho_identificado": p.trecho_identificado,
                "momento_edital": p.inferencia_bruta.momento_edital,
                "momento_esperado_lei": p.inferencia_bruta.momento_esperado_lei,
                "tipo_inferencia_ufol": p.inferencia_bruta.tipo_inferencia_ufol,
            }
            for p in pareceres_nesy
        }

        payload = {
            "timestamp_execucao": datetime.now().isoformat(timespec="seconds"),
            "nome_arquivo": edital_seg.nome_arquivo,
            "identificador_edital": fatos.identificador_edital,
            "total_paginas": edital_seg.total_paginas,
            "total_linhas": len(edital_seg.linhas_originais),
            "resumo_secoes": edital_seg.resumo_secoes,
            "modelo_gemini": modelo_usado,
            "temperatura_extrator": 0.0,
            "temperatura_somente_neural": 0.0,
            "thinking_budget": args.thinking_budget,
            "motor_simbolico": motor_label,
            "validacao_cruzada_prolog_ok": all(r.validacao_cruzada_ok for r in resultados_prolog.values()),
            "tempo_extracao_nesy_s": round(t_extracao, 2),
            "tempo_prolog_ms": round(t_prolog_ms, 3),
            "tempo_somente_neural_s": round(t_neural, 2),
            "usage_extracao_nesy": usage_ext,
            "usage_somente_neural": usage_neural,
            "fatos": fatos.model_dump(),
            "abox_prolog": abox_pl,
            "resumo_regras_nesy": resumo_regras_nesy,
            "julgamentos_somente_neural": {k: v.model_dump() for k, v in julgamentos_neural.items()},
        }
        _log(f"  [5/5] Salvando JSON em {out_json.name}...")
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        divs = [
            rid
            for rid in POC_RULE_IDS
            if rid in julgamentos_neural
            and julgamentos_neural[rid].status_verificacao != resumo_regras_nesy[rid]["status_verificacao"]
        ]
        _log(
            f"  -> OK ({modelo_usado}) | NeSy: {conf}/9 conformes ({t_extracao:.1f}s LLM + {t_prolog_ms:.2f}ms Prolog) | "
            f"Somente Neural: {t_neural:.1f}s | Divergências: {divs}"
        )
        time.sleep(2)

    resumo = consolidar_benchmark(cache_dir, catalogo)
    print("\n" + "=" * 75)
    _log(f"BENCHMARK CONSOLIDADO: {resumo['total_editais']} Editais | {resumo['total_verificacoes']} Verificações")
    _log(f"Divergências Totais (Somente Neural vs. Neuro-Simbólico): {resumo['total_divergencias']} ({resumo['taxa_divergencia_pct']}%)")
    _log(f"Tempo Médio Extração Neural: {resumo['tempo_medio_extracao_nesy_s']}s | Prolog: {resumo['tempo_medio_prolog_ms']}ms")
    _log(f"Arquivos gerados em: {cache_dir}")


if __name__ == "__main__":
    main()
