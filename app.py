"""
Interface Web (Streamlit) da PoC de Mestrado:
Validador Neuro-Simbólico de Editais de Licitação (Lei nº 13.303/2016 + Ontologia UFO-L).
Versão minimalista inspirada no Material Design 3 (M3).
"""

from __future__ import annotations

import importlib
import os
import re
from pathlib import Path
from typing import Dict, List

import streamlit as st
from dotenv import load_dotenv

import src.extractor_llm as _ext_mod
import src.parser_edital as _parser_mod
import src.reasoner_prolog as _reas_mod
import src.ui.components as _ui_comp_mod
import src.ui.tabs as _ui_tabs_mod
import src.ui.tabs.benchmark as _ui_tab_bench_mod
import src.ui.tabs.comparativo as _ui_tab_comp_mod
import src.ui.tabs.diagnostico as _ui_tab_diag_mod
import src.ui.tabs.edital as _ui_tab_ed_mod
import src.ui.tabs.prova_prolog as _ui_tab_prolog_mod
import src.ui.tabs.whatif as _ui_tab_whatif_mod
import src.ui.theme as _ui_theme_mod
from src import __version__

importlib.reload(_parser_mod)
importlib.reload(_ext_mod)
importlib.reload(_reas_mod)
importlib.reload(_ui_theme_mod)
importlib.reload(_ui_comp_mod)
importlib.reload(_ui_tab_diag_mod)
importlib.reload(_ui_tab_prolog_mod)
importlib.reload(_ui_tab_comp_mod)
importlib.reload(_ui_tab_bench_mod)
importlib.reload(_ui_tab_whatif_mod)
importlib.reload(_ui_tab_ed_mod)
importlib.reload(_ui_tabs_mod)

from src.explainer import gerar_pareceres_edital
from src.extractor_llm import (
    FatosExtraidosEdital,
    carregar_cache_benchmark_edital,
    converter_fatos_para_prolog,
    extrair_fatos_heuristico_texto,
    extrair_fatos_via_gemini,
    obter_fatos_demo_pe_29_2026,
)
from src.parser_edital import (
    POC_RULE_IDS,
    EditalSegmentado,
    carregar_artigos_lei13303,
    carregar_edital,
    carregar_edital_pdf,
    carregar_regras_validador,
    processar_texto_edital,
)
from src.reasoner_prolog import AvaliadorSimbolicoUfoL
from src.ui.components import (
    render_kpi_strip,
    render_nota_discreta,
    render_sidebar_overline,
    render_top_bar,
)
from src.ui.tabs import (
    render_tab_benchmark,
    render_tab_comparativo,
    render_tab_diagnostico,
    render_tab_edital,
    render_tab_prova_prolog,
    render_tab_whatif,
)
from src.ui.theme import aplicar_tema_material_m3

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"
BNDES_PDF_DIR = DADOS_DIR / "editais_bndes_pdf"
BENCHMARK_DIR = DADOS_DIR / "benchmark_10_editais"
TESTE_DIR = DADOS_DIR / "editais_teste"
SRC_DIR = BASE_DIR / "src"

_OPCAO_UPLOAD = "Enviar outro arquivo (.pdf / .txt)..."

st.set_page_config(
    page_title="Validador Neuro-Simbólico | Lei 13.303 + UFO-L",
    page_icon=":material/balance:",
    layout="wide",
)


@st.cache_resource
def inicializar_recursos():
    catalogo = carregar_regras_validador(DADOS_DIR / "regras_validador.json")
    artigos_lei = carregar_artigos_lei13303(DADOS_DIR / "L13303.txt")
    avaliador = AvaliadorSimbolicoUfoL(
        caminho_ufol_pl=DADOS_DIR / "UFO_L.pl",
        caminho_regras_pl=SRC_DIR / "ufo_l_rules.pl",
    )
    return catalogo, artigos_lei, avaliador


def _chave_ordenacao_pe(arq: Path) -> tuple[int, str]:
    m = re.search(r"PE_(\d+)", arq.name, re.IGNORECASE)
    return (int(m.group(1)) if m else 9999, arq.name)


def listar_editais_disponiveis() -> Dict[str, Path]:
    opcoes: Dict[str, Path] = {}

    if BNDES_PDF_DIR.exists():
        pdfs = sorted(BNDES_PDF_DIR.glob("*.pdf"), key=_chave_ordenacao_pe)
        pe29 = [p for p in pdfs if "PE_29-2026" in p.name]
        outros = [p for p in pdfs if "PE_29-2026" not in p.name]
        for arq in pe29 + outros:
            tag_destaque = " (Calibração DaaS)" if "PE_29-2026" in arq.name else ""
            opcoes[f"{arq.name} · BNDES Real{tag_destaque}"] = arq

    edital_principal = DADOS_DIR / "Edital_PE_29-2026.txt"
    if edital_principal.exists():
        opcoes["Edital_PE_29-2026.txt · Texto Base (BNDES DaaS)"] = edital_principal

    if TESTE_DIR.exists():
        for arq in sorted(TESTE_DIR.glob("*.txt")):
            if "Critico" in arq.name:
                label = f"{arq.name} · Sintético (Alto Direcionamento)"
            elif "Saneado" in arq.name:
                label = f"{arq.name} · Sintético (Saneado 100% Conforme)"
            else:
                label = f"{arq.name} · Teste"
            opcoes[label] = arq
    return opcoes


def executar_pipeline(
    edital_seg: EditalSegmentado,
    modo_execucao: str,
    api_key: str,
    modelo_gemini: str,
    regras_selecionadas: List[str],
    forcar_heuristico_texto: bool = False,
):
    catalogo, artigos_lei, avaliador = inicializar_recursos()

    aviso_modelo = None
    texto_para_extracao = edital_seg.texto_auditoria or edital_seg.texto_numerado
    if modo_execucao.startswith("Modo Live"):
        if not api_key:
            st.error("Informe a chave `GEMINI_API_KEY` na barra lateral para usar o Modo Live, ou alterne para o Modo Demonstração.")
            st.stop()
        with st.spinner(f"Camada Neural: Extraindo fatos ontológicos via Google Gemini (`{modelo_gemini}`)..."):
            fatos, mod_usado = extrair_fatos_via_gemini(
                texto_numerado=texto_para_extracao,
                nome_arquivo=edital_seg.nome_arquivo,
                api_key=api_key,
                modelo=modelo_gemini,
            )
            if mod_usado != modelo_gemini:
                aviso_modelo = (
                    f"Nota: O identificador `{modelo_gemini}` não respondeu no endpoint público; "
                    f"a extração utilizou automaticamente `{mod_usado}`."
                )
    else:
        cache_edital = None if forcar_heuristico_texto else carregar_cache_benchmark_edital(edital_seg.nome_arquivo, BENCHMARK_DIR)
        if cache_edital is not None and "fatos" in cache_edital:
            fatos = FatosExtraidosEdital.model_validate(cache_edital["fatos"])
            aviso_modelo = (
                f"Fatos extraídos previamente via {cache_edital.get('modelo_gemini', 'gemini-2.5-flash')} "
                f"(cache auditado de benchmark) + inferência Prolog/UFO-L executada em tempo real."
            )
        elif edital_seg.nome_arquivo == "Edital_PE_29-2026.txt" and not forcar_heuristico_texto:
            fatos = obter_fatos_demo_pe_29_2026()
        else:
            fatos = extrair_fatos_heuristico_texto(
                texto_para_extracao, nome_arquivo=edital_seg.nome_arquivo
            )

    abox_pl = converter_fatos_para_prolog(fatos)
    caminho_sessao = DADOS_DIR / "ultima_sessao_validacao.pl"

    resultados_prolog, codigo_pl_completo, motor_label = avaliador.executar_avaliacao(
        edital_id=fatos.identificador_edital,
        abox_prolog=abox_pl,
        regras_selecionadas=regras_selecionadas,
        salvar_sessao_em=caminho_sessao,
    )

    pareceres = gerar_pareceres_edital(
        resultados_prolog=resultados_prolog,
        catalogo_regras=catalogo,
        mapa_artigos_lei=artigos_lei,
    )

    return fatos, abox_pl, codigo_pl_completo, motor_label, pareceres, aviso_modelo


def main():
    aplicar_tema_material_m3()
    catalogo, _, _ = inicializar_recursos()

    # ==========================================================================
    # Barra Lateral (Navigation Drawer M3)
    # ==========================================================================
    with st.sidebar:
        st.markdown("### Auditoria de Editais")
        st.caption("Lei nº 13.303/2016 · Ontologia UFO-L")

        render_sidebar_overline("DOCUMENTO")
        editais_map = listar_editais_disponiveis()
        escolha_edital = st.selectbox(
            "Edital (.pdf ou .txt)",
            options=list(editais_map.keys()) + [_OPCAO_UPLOAD],
            label_visibility="collapsed",
        )

        arquivo_upload = None
        if escolha_edital == _OPCAO_UPLOAD:
            arquivo_upload = st.file_uploader(
                "Carregar Edital (.pdf ou .txt)",
                type=["pdf", "txt"],
            )

        render_sidebar_overline("CAMADA NEURAL")
        modo_ui = (
            st.segmented_control(
                "Modo de execução",
                options=["Demonstração", "Live API"],
                default="Demonstração",
                key="sidebar_modo_exec",
                help=(
                    "Em Demonstração, a extração neural usa cache auditado / analisador local "
                    "e executa a inferência formal no Prolog (UFO-L) em tempo real."
                ),
                label_visibility="collapsed",
            )
            or "Demonstração"
        )

        modo_execucao = (
            "Modo Live (Google Gemini API + Motor Prolog Real)"
            if modo_ui == "Live API"
            else "Modo Demonstração (Instantâneo + Motor Prolog Real)"
        )

        api_key = os.environ.get("GEMINI_API_KEY", "")
        modelo_gemini = "gemini-2.5-flash"

        if modo_ui == "Live API":
            opcoes_modelo = ["gemini-2.5-flash", "gemini-2.8-flash", "gemini-2.5-pro", "Outro (digitar)"]
            sel_mod = st.selectbox("Modelo Gemini", options=opcoes_modelo, index=0)
            if sel_mod == "Outro (digitar)":
                modelo_gemini = st.text_input("Identificador do modelo", value="gemini-2.5-flash")
            else:
                modelo_gemini = sel_mod

            api_key = st.text_input(
                "GEMINI_API_KEY",
                value=api_key,
                type="password",
                help="Chave da API Google AI Studio / Gemini.",
            )

        render_sidebar_overline("ESCOPO DE REGRAS")
        opcoes_regras_formatadas = {
            r_id: f"{r_id} · {catalogo[r_id]['categoria']} ({catalogo[r_id]['dispositivo_legal']})"
            for r_id in POC_RULE_IDS
            if r_id in catalogo
        }
        todas_regras = list(opcoes_regras_formatadas.keys())
        qtd_regras = len(st.session_state.get("sidebar_regras_sel", todas_regras))

        with st.expander(
            f"Regras selecionadas ({qtd_regras}/{len(todas_regras)})",
            expanded=False,
            icon=":material/tune:",
        ):
            regras_selecionadas = st.multiselect(
                "Regras da Lei 13.303 para avaliar",
                options=todas_regras,
                default=todas_regras,
                format_func=lambda k: opcoes_regras_formatadas[k],
                key="sidebar_regras_sel",
                label_visibility="collapsed",
            )

    # ==========================================================================
    # Carregamento do Edital e Execução do Pipeline
    # ==========================================================================
    if escolha_edital == _OPCAO_UPLOAD:
        if arquivo_upload is None:
            render_top_bar(
                titulo="Validador Neuro-Simbólico de Editais",
                subtitulo="Instanciação Semântica via LLM + Raciocínio Deôntico/Relacional em Prolog (UFO-L)",
                chips=[(f"v{__version__}", "primary"), ("Aguardando documento", "neutral")],
            )
            render_nota_discreta(
                "Envie um arquivo .pdf ou .txt na barra lateral para iniciar a análise.",
                tone="primary",
            )
            st.stop()
        if arquivo_upload.name.lower().endswith(".pdf"):
            edital_seg = carregar_edital_pdf(arquivo_upload.getvalue(), nome_arquivo=arquivo_upload.name)
        else:
            conteudo_up = arquivo_upload.read().decode("utf-8", errors="replace")
            edital_seg = processar_texto_edital(conteudo_up, nome_arquivo=arquivo_upload.name)
    else:
        caminho_edital = editais_map[escolha_edital]
        edital_seg = carregar_edital(caminho_edital)

    if not regras_selecionadas:
        st.warning("Selecione ao menos uma regra na barra lateral.")
        st.stop()

    fatos, abox_pl, codigo_pl_completo, motor_label, pareceres, aviso_modelo = executar_pipeline(
        edital_seg=edital_seg,
        modo_execucao=modo_execucao,
        api_key=api_key,
        modelo_gemini=modelo_gemini,
        regras_selecionadas=regras_selecionadas,
    )

    # ==========================================================================
    # Top App Bar & Faixa de KPIs
    # ==========================================================================
    inconformes = [p for p in pareceres if p.status_verificacao == "Indício de Inconformidade"]
    conformes = [p for p in pareceres if p.status_verificacao == "Conforme"]
    criticos_altos = [
        p
        for p in inconformes
        if any(k in p.classificacao_risco.lower() for k in ["crítico", "critico", "alto"])
    ]
    detalhe_doc = (
        f"{edital_seg.total_paginas} págs · {len(edital_seg.linhas_originais)} linhas"
        if edital_seg.total_paginas > 0
        else f"{len(edital_seg.linhas_originais)} linhas"
    )

    render_top_bar(
        titulo="Validador Neuro-Simbólico de Editais",
        subtitulo="Instanciação Semântica via LLM + Raciocínio Deôntico/Relacional em Prolog fundamentado na Ontologia Jurídica UFO-L",
        chips=[
            (f"v{__version__}", "primary"),
            (edital_seg.nome_arquivo, "neutral"),
            (detalhe_doc, "neutral"),
            (f"Modo {modo_ui}", "success" if modo_ui == "Demonstração" else "warning"),
            (motor_label, "neutral"),
        ],
    )

    if aviso_modelo:
        render_nota_discreta(aviso_modelo, tone="primary")

    taxa_aderencia = int(len(conformes) / max(1, len(pareceres)) * 100)
    render_kpi_strip(
        [
            {
                "label": "Regras Avaliadas",
                "value": str(len(pareceres)),
                "detail": "Lei nº 13.303/2016 (PoC)",
                "tone": "neutral",
            },
            {
                "label": "Inconformidades",
                "value": str(len(inconformes)),
                "detail": "indício(s) detectado(s)" if inconformes else "nenhuma violação",
                "tone": "error" if inconformes else "success",
            },
            {
                "label": "Risco Crítico / Alto",
                "value": str(len(criticos_altos)),
                "detail": "prioridade de saneamento" if criticos_altos else "sem risco crítico/alto",
                "tone": "warning" if criticos_altos else "success",
            },
            {
                "label": "Taxa de Aderência",
                "value": f"{taxa_aderencia}%",
                "detail": f"{len(conformes)} de {len(pareceres)} regras conformes",
                "tone": "success" if len(conformes) == len(pareceres) else "primary",
            },
        ]
    )

    # ==========================================================================
    # Abas Principais (Material Primary Tabs + Material Symbols)
    # ==========================================================================
    aba_parecer, aba_ontologia, aba_comparativo, aba_benchmark, aba_whatif, aba_edital = st.tabs(
        [
            ":material/fact_check: Diagnóstico",
            ":material/account_tree: Prova Prolog",
            ":material/compare_arrows: Neural vs. NeSy",
            ":material/bar_chart: Benchmark",
            ":material/science: What-If",
            ":material/description: Edital",
        ]
    )

    with aba_parecer:
        render_tab_diagnostico(fatos, pareceres, inconformes, conformes)

    with aba_ontologia:
        render_tab_prova_prolog(fatos, abox_pl, codigo_pl_completo, motor_label, pareceres, catalogo)

    with aba_comparativo:
        render_tab_comparativo(
            edital_seg=edital_seg,
            pareceres=pareceres,
            catalogo=catalogo,
            regras_selecionadas=regras_selecionadas,
            modo_execucao=modo_execucao,
            api_key=api_key,
            modelo_gemini=modelo_gemini,
            benchmark_dir=BENCHMARK_DIR,
        )

    with aba_benchmark:
        render_tab_benchmark(BENCHMARK_DIR)

    with aba_whatif:
        render_tab_whatif(
            edital_seg=edital_seg,
            fatos=fatos,
            pareceres=pareceres,
            regras_selecionadas=regras_selecionadas,
            inicializar_recursos_fn=inicializar_recursos,
        )

    with aba_edital:
        render_tab_edital(edital_seg)


if __name__ == "__main__":
    main()
