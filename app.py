"""
Interface Web (Streamlit) da PoC de Mestrado:
Validador Neuro-Simbólico de Editais de Licitação (Lei nº 13.303/2016 + Ontologia UFO-L).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src import __version__
import importlib
import src.parser_edital as _parser_mod
import src.extractor_llm as _ext_mod
import src.reasoner_prolog as _reas_mod
importlib.reload(_parser_mod)
importlib.reload(_ext_mod)
importlib.reload(_reas_mod)

from src.explainer import (
    ParecerRegraEdital,
    exportar_relatorio_json_validado,
    gerar_pareceres_edital,
)
from src.extractor_llm import (
    FatosExtraidosEdital,
    JulgamentoNeuralRegra,
    MencaoMarcaFato,
    carregar_cache_benchmark_edital,
    carregar_resumo_benchmark,
    converter_fatos_para_prolog,
    executar_avaliacao_somente_neural_gemini,
    extrair_fatos_heuristico_texto,
    extrair_fatos_via_gemini,
    obter_avaliacao_somente_neural_demo,
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

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"
BNDES_PDF_DIR = DADOS_DIR / "editais_bndes_pdf"
BENCHMARK_DIR = DADOS_DIR / "benchmark_10_editais"
TESTE_DIR = DADOS_DIR / "editais_teste"
SRC_DIR = BASE_DIR / "src"

st.set_page_config(
    page_title="Validador Neuro-Simbólico | Lei 13.303 + UFO-L",
    page_icon="⚖️",
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
        # Coloca Edital_PE_29-2026.pdf em primeiro lugar como referência principal se existir
        pe29 = [p for p in pdfs if "PE_29-2026" in p.name]
        outros = [p for p in pdfs if "PE_29-2026" not in p.name]
        for arq in pe29 + outros:
            tag_destaque = " (Calibração DaaS)" if "PE_29-2026" in arq.name else ""
            opcoes[f"📄 [BNDES Real] {arq.name}{tag_destaque}"] = arq

    edital_principal = DADOS_DIR / "Edital_PE_29-2026.txt"
    if edital_principal.exists():
        opcoes["📝 [Texto Base] Edital_PE_29-2026.txt (BNDES DaaS)"] = edital_principal

    if TESTE_DIR.exists():
        for arq in sorted(TESTE_DIR.glob("*.txt")):
            if "Critico" in arq.name:
                label = f"🚨 [Sintético] {arq.name} (Alto Direcionamento)"
            elif "Saneado" in arq.name:
                label = f"✅ [Sintético] {arq.name} (Saneado 100% Conforme)"
            else:
                label = f"📑 {arq.name}"
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
                f"Fatos extraídos previamente via **{cache_edital.get('modelo_gemini', 'gemini-2.5-flash')}** "
                f"(cache auditado de benchmark) + inferência **Prolog/UFO-L executada em tempo real**."
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
    catalogo, _, _ = inicializar_recursos()

    st.title(f"⚖️ Validador Neuro-Simbólico de Editais (Lei 13.303/2016 + UFO-L)")
    st.caption(
        f"Versão {__version__} | Instanciação Semântica via LLM + Raciocínio Deôntico/Relacional em Prolog fundamentado na Ontologia Jurídica UFO-L"
    )

    # ==========================================================================
    # Barra Lateral
    # ==========================================================================
    with st.sidebar:
        st.header("⚙️ Configuração da Auditoria")

        editais_map = listar_editais_disponiveis()
        escolha_edital = st.selectbox(
            "1. Selecione o Edital (.pdf ou .txt):",
            options=list(editais_map.keys()) + ["📤 Enviar outro arquivo (.pdf / .txt)..."],
        )

        arquivo_upload = None
        if escolha_edital == "📤 Enviar outro arquivo (.pdf / .txt)...":
            arquivo_upload = st.file_uploader("Carregar Edital (.pdf ou .txt)", type=["pdf", "txt"])

        st.divider()
        modo_execucao = st.radio(
            "2. Modo da Camada Neural:",
            options=[
                "Modo Demonstração (Instantâneo + Motor Prolog Real)",
                "Modo Live (Google Gemini API + Motor Prolog Real)",
            ],
            index=0,
            help=(
                "No Modo Demonstração, a extração neural usa cache auditado / analisador semântico local "
                "e executa a inferência formal no Prolog (UFO-L) em tempo real sem custo de API."
            ),
        )

        api_key = os.environ.get("GEMINI_API_KEY", "")
        modelo_gemini = "gemini-2.5-flash"

        if modo_execucao.startswith("Modo Live"):
            opcoes_modelo = ["gemini-2.5-flash", "gemini-2.8-flash", "gemini-2.5-pro", "Outro (digitar)"]
            sel_mod = st.selectbox("Modelo Gemini:", options=opcoes_modelo, index=0)
            if sel_mod == "Outro (digitar)":
                modelo_gemini = st.text_input("Identificador do modelo:", value="gemini-2.5-flash")
            else:
                modelo_gemini = sel_mod

            api_key = st.text_input(
                "GEMINI_API_KEY:",
                value=api_key,
                type="password",
                help="Chave da API Google AI Studio / Gemini.",
            )

        st.divider()
        opcoes_regras_Formatadas = {
            r_id: f"{r_id} - {catalogo[r_id]['categoria']} ({catalogo[r_id]['dispositivo_legal']})"
            for r_id in POC_RULE_IDS
            if r_id in catalogo
        }
        regras_selecionadas = st.multiselect(
            "3. Regras da Lei 13.303 para avaliar:",
            options=list(opcoes_regras_Formatadas.keys()),
            default=list(opcoes_regras_Formatadas.keys()),
            format_func=lambda k: opcoes_regras_Formatadas[k],
        )

    # Carregar o Edital selecionado
    if escolha_edital == "📤 Enviar outro arquivo (.pdf / .txt)...":
        if arquivo_upload is None:
            st.info("Envie um arquivo `.pdf` ou `.txt` na barra lateral para iniciar a análise.")
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

    if aviso_modelo:
        st.info(aviso_modelo)

    # ==========================================================================
    # Métricas Resumo
    # ==========================================================================
    inconformes = [p for p in pareceres if p.status_verificacao == "Indício de Inconformidade"]
    conformes = [p for p in pareceres if p.status_verificacao == "Conforme"]
    criticos_altos = [
        p
        for p in inconformes
        if any(k in p.classificacao_risco.lower() for k in ["crítico", "critico", "alto"])
    ]

    col1, col2, col3, col4 = st.columns(4)
    detalhe_doc = (
        f"{edital_seg.total_paginas} págs | {len(edital_seg.linhas_originais)} linhas"
        if edital_seg.total_paginas > 0
        else f"{len(edital_seg.linhas_originais)} linhas"
    )
    col1.metric("Arquivo Analisado", edital_seg.nome_arquivo, detalhe_doc)
    col2.metric("Regras Avaliadas (PoC)", len(pareceres), "Lei nº 13.303/2016")
    col3.metric(
        "Indícios de Inconformidade",
        len(inconformes),
        f"{len(criticos_altos)} de risco Crítico/Alto" if inconformes else "Nenhuma violação",
        delta_color="inverse" if inconformes else "normal",
    )
    col4.metric("Regras Conformes", len(conformes), f"{int(len(conformes)/max(1, len(pareceres))*100)}% de aderência")

    # ==========================================================================
    # Abas Principais (Títulos compactos + CSS responsivo sem seta de scroll)
    # ==========================================================================
    st.markdown(
        """
        <style>
        div[data-baseweb="tab-list"] {
            gap: 8px;
            flex-wrap: wrap;
        }
        button[data-baseweb="tab"] {
            padding-left: 12px !important;
            padding-right: 12px !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    aba_parecer, aba_ontologia, aba_comparativo, aba_benchmark, aba_whatif, aba_edital = st.tabs([
        "📋 1. Diagnóstico",
        "🧠 2. Prova Prolog (UFO-L)",
        "⚖️ 3. Neural vs. Neuro-Simbólico",
        "📊 4. Benchmark (10 Editais)",
        "🧪 5. Laboratório What-If",
        "📄 6. Texto do Edital",
    ])

    # --------------------------------------------------------------------------
    # ABA 1: Diagnóstico de Conformidade
    # --------------------------------------------------------------------------
    with aba_parecer:
        st.markdown(f"**Resumo do Objeto Extraído:** {fatos.resumo_objeto}")

        filtro_status = st.radio(
            "Filtrar visualização:",
            options=["Todas as Regras Avaliadas", "Apenas Indícios de Inconformidade (🚨)", "Apenas Conformes (✅)"],
            horizontal=True,
        )

        lista_exibicao = pareceres
        if "Inconformidade" in filtro_status:
            lista_exibicao = inconformes
        elif "Conformes" in filtro_status:
            lista_exibicao = conformes

        if not lista_exibicao:
            st.success("Nenhum item encontrado para o filtro selecionado.")
        else:
            for p in lista_exibicao:
                icone = "🚨" if p.status_verificacao == "Indício de Inconformidade" else "✅"
                titulo_card = (
                    f"{icone} [{p.regra_id}] {p.categoria} — {p.criterio_validacao} "
                    f"| Status: {p.status_verificacao} (Risco: {p.classificacao_risco})"
                )
                with st.expander(titulo_card, expanded=(p.status_verificacao == "Indício de Inconformidade")):
                    c_esq, c_dir = st.columns([3, 2])
                    with c_esq:
                        st.markdown("#### 🔍 Explicação Jurídica e Técnica")
                        if p.status_verificacao == "Indício de Inconformidade":
                            st.error(p.explicacao_neuro_simbolica)
                        else:
                            st.success(p.explicacao_neuro_simbolica)

                        st.markdown("#### 📌 Trecho Identificado no Edital")
                        st.code(f"Localização: {p.item_identificado}\n\n{p.trecho_identificado}", language="text")

                    with c_dir:
                        st.markdown("#### 🏛️ Formalização na Ontologia UFO-L")
                        st.info(p.explicacao_ontologica_ufol)
                        st.markdown(
                            f"- **Relação Jurídica:** `{p.inferencia_bruta.relacao_juridica_ufol}`\n"
                            f"- **Papel Afetado:** `{p.inferencia_bruta.papel_afetado}`\n"
                            f"- **Posição na Lei 13.303:** `{p.inferencia_bruta.momento_esperado_lei}` (Correlato: `{p.inferencia_bruta.momento_correlato_lei}`)\n"
                            f"- **Posição Instanciada no Edital:** `{p.inferencia_bruta.momento_edital}`\n"
                            f"- **Resultado Formal Prolog:** `{p.inferencia_bruta.tipo_inferencia_ufol}`"
                        )
                        with st.popover(f"📖 Ver Texto Oficial ({p.dispositivo_legal} - Lei 13.303)"):
                            st.text(p.texto_lei_13303)

    # --------------------------------------------------------------------------
    # ABA 2: Inspetor Neuro-Simbólico & Prova UFO-L
    # --------------------------------------------------------------------------
    with aba_ontologia:
        st.subheader("Arquitetura em Duas Camadas: Extração Neural (JSON) ➡️ Prova Deôntica Simbólica (Prolog + UFO-L)")
        st.caption(f"Motor Simbólico Ativo: **{motor_label}**")

        tabela_resumo_ufol = []
        for p in pareceres:
            tabela_resumo_ufol.append({
                "Regra": p.regra_id,
                "Dispositivo": p.dispositivo_legal,
                "Relação UFO-L": p.inferencia_bruta.relacao_juridica_ufol,
                "Papel (Role)": p.inferencia_bruta.papel_afetado,
                "Deve-Ser (Lei 13.303)": p.inferencia_bruta.momento_esperado_lei,
                "Correlato Hohfeld": p.inferencia_bruta.momento_correlato_lei,
                "Fato no Edital": p.inferencia_bruta.momento_edital,
                "Diagnóstico": p.status_verificacao,
            })
        st.dataframe(pd.DataFrame(tabela_resumo_ufol), use_container_width=True, hide_index=True)

        col_neural, col_simb = st.columns(2)
        with col_neural:
            st.markdown("#### 1️⃣ Saída da Camada Neural (`FatosExtraidosEdital` JSON)")
            st.json(fatos.model_dump())

        with col_simb:
            st.markdown("#### 2️⃣ Fatos Traduzidos para a ABox Prolog (`UFO-L`)")
            st.code(abox_pl, language="prolog")

        st.markdown("#### 3️⃣ Árvore de Derivação Formal (SLD-Resolution Trace no Prolog)")
        regra_trace_sel = st.selectbox(
            "Inspecionar prova passo a passo da regra:",
            options=[p.regra_id for p in pareceres],
            format_func=lambda r: f"{r} - {catalogo[r]['criterio_validacao']}",
        )
        parecer_sel = next(p for p in pareceres if p.regra_id == regra_trace_sel)
        st.code("\n".join(parecer_sel.inferencia_bruta.passos_prova_prolog), language="prolog")

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "⬇️ Baixar Base Prolog Completa da Sessão (sessao_validacao.pl)",
                data=codigo_pl_completo,
                file_name=f"sessao_{fatos.identificador_edital}.pl",
                mime="text/plain",
            )
        with col_dl2:
            relatorio_json = exportar_relatorio_json_validado(pareceres, catalogo)
            st.download_button(
                "⬇️ Baixar Relatório Validado (regras_validador_resultado.json)",
                data=json.dumps(relatorio_json, ensure_ascii=False, indent=2),
                file_name=f"relatorio_{fatos.identificador_edital}.json",
                mime="application/json",
            )

    # --------------------------------------------------------------------------
    # ABA 3: Comparativo Somente Neural (LLM Puro) vs. Neuro-Simbólico (Prolog + UFO-L)
    # --------------------------------------------------------------------------
    with aba_comparativo:
        st.subheader("⚖️ Avaliação Comparativa: Mecanismo Somente Neural (LLM Puro) vs. Neuro-Simbólico (LLM + Prolog + UFO-L)")
        st.markdown(
            "Esta visão coloca lado a lado as respostas de um **Mecanismo Somente Neural** "
            "(onde o LLM julga diretamente a conformidade do edital em texto livre, sem ABox formal e sem Prolog) "
            "e o nosso **Mecanismo Neuro-Simbólico** (onde o LLM apenas extrai fatos observáveis e o motor Prolog/UFO-L "
            "executa a Resolução SLD sob a Hipótese do Mundo Fechado)."
        )

        # Obter baseline Somente Neural (Cache real Gemini -> Demo determinístico -> Live sob demanda)
        chave_cache_neural = f"baseline_neural_{edital_seg.nome_arquivo}"
        cache_ed_atual = carregar_cache_benchmark_edital(edital_seg.nome_arquivo, BENCHMARK_DIR)
        if chave_cache_neural not in st.session_state:
            if cache_ed_atual and "julgamentos_somente_neural" in cache_ed_atual:
                st.session_state[chave_cache_neural] = {
                    rid: JulgamentoNeuralRegra.model_validate(payload_j)
                    for rid, payload_j in cache_ed_atual["julgamentos_somente_neural"].items()
                }
            else:
                st.session_state[chave_cache_neural] = obter_avaliacao_somente_neural_demo(
                    nome_arquivo=edital_seg.nome_arquivo,
                    pareceres_nesy=pareceres,
                )

        if cache_ed_atual and "julgamentos_somente_neural" in cache_ed_atual:
            st.caption(
                f"Fonte do Baseline Somente Neural: **Execução real registrada via `{cache_ed_atual.get('modelo_gemini', 'gemini-2.5-flash')}` (`temperature=0.0`)**."
            )
        else:
            st.warning(
                "Aviso: Para cenários sintéticos/offline sem execução Gemini pré-gravada, o comparativo abaixo usa "
                "respostas ilustrativas de demonstração. Para resultados experimentais reais (`temperature=0.0`), "
                "selecione qualquer um dos **10 PDFs reais do BNDES** ou clique em **Executar Ao Vivo** no Modo Live."
            )

        if modo_execucao.startswith("Modo Live") and api_key:
            if st.button("🔄 Executar Julgamento 'Somente Neural' Ao Vivo na API Gemini para Comparar"):
                with st.spinner("Executando prompt Somente Neural (End-to-End) no Google Gemini..."):
                    st.session_state[chave_cache_neural] = executar_avaliacao_somente_neural_gemini(
                        texto_numerado=edital_seg.texto_auditoria or edital_seg.texto_numerado,
                        nome_arquivo=edital_seg.nome_arquivo,
                        catalogo_regras=catalogo,
                        regras_selecionadas=regras_selecionadas,
                        pareceres_nesy=pareceres,
                        api_key=api_key,
                        modelo=modelo_gemini,
                    )

        mapa_neural = st.session_state[chave_cache_neural]

        # Cálculo de métricas comparativas
        total_comp = len(pareceres)
        divergencias_veredito = []
        ruidos_ou_divergencias = []
        for p in pareceres:
            jn = mapa_neural.get(p.regra_id)
            if not jn:
                continue
            if jn.status_verificacao != p.status_verificacao:
                divergencias_veredito.append(p.regra_id)
                ruidos_ou_divergencias.append(p.regra_id)
            elif "Ruído" in jn.tipo_limitacao_observada:
                ruidos_ou_divergencias.append(p.regra_id)

        concordancias = total_comp - len(divergencias_veredito)
        pct_conc = int(round((concordancias / max(1, total_comp)) * 100))
        cruzada_ok = sum(1 for p in pareceres if getattr(p.inferencia_bruta, "validacao_cruzada_ok", True))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "Concordância entre Vereditos",
            f"{pct_conc}% ({concordancias}/{total_comp})",
            f"{len(divergencias_veredito)} divergência(s) a auditar" if divergencias_veredito else "Convergência total",
            delta_color="off",
        )
        m2.metric(
            "Divergências a Auditar",
            f"{len(divergencias_veredito)} regras",
            ", ".join(divergencias_veredito) if divergencias_veredito else "Nenhuma",
            delta_color="off",
        )
        m3.metric(
            "Consistência Cruzada (Prolog)",
            f"{cruzada_ok}/{total_comp}",
            "SWI-Prolog == SLD Trace",
        )
        m4.metric(
            "Prova Formal Auditável (SLD)",
            "0% vs. 100%",
            "Caixa-Preta vs. Árvore SLD + Hohfeld",
        )

        # Tabela Resumo Comparativa
        linhas_tab_comp = []
        for p in pareceres:
            jn = mapa_neural.get(p.regra_id)
            if not jn:
                continue
            ic_n = "🚨" if jn.status_verificacao == "Indício de Inconformidade" else "✅"
            ic_s = "🚨" if p.status_verificacao == "Indício de Inconformidade" else "✅"
            linhas_tab_comp.append({
                "Regra": p.regra_id,
                "Categoria / Dispositivo": f"{p.categoria} ({p.dispositivo_legal})",
                "🧠 Somente Neural (LLM Puro)": f"{ic_n} {jn.status_verificacao}",
                "🏛️ Neuro-Simbólico (Prolog + UFO-L)": f"{ic_s} {p.status_verificacao}",
                "Diagnóstico da Diferença": jn.tipo_limitacao_observada,
                "Relação Hohfeld (UFO-L)": f"{p.inferencia_bruta.momento_edital} vs. {p.inferencia_bruta.momento_esperado_lei}",
            })

        st.markdown("#### 📊 Matriz Resumo: Resposta Somente Neural vs. Resposta Neuro-Simbólica")
        st.dataframe(pd.DataFrame(linhas_tab_comp), use_container_width=True, hide_index=True)

        filtro_comp = st.radio(
            "Filtrar cards comparativos detalhados:",
            options=[
                f"🔍 Destacar Divergências e Diferenças Críticas ({len(ruidos_ou_divergencias)} regras)",
                f"📋 Mostrar Todas as Regras Avaliadas ({total_comp} regras)",
            ],
            horizontal=True,
        )

        pareceres_comp = (
            [p for p in pareceres if p.regra_id in ruidos_ou_divergencias]
            if filtro_comp.startswith("🔍") and ruidos_ou_divergencias
            else pareceres
        )

        for p in pareceres_comp:
            jn = mapa_neural.get(p.regra_id)
            if not jn:
                continue
            tem_diff_critica = p.regra_id in ruidos_ou_divergencias
            badge = "🔴 DIVERGÊNCIA / DIFERENÇA CRÍTICA" if tem_diff_critica else "🟢 VEREDITOS CONVERGENTES (DIFERENÇA NA PROVA FORMAL)"
            titulo_exp = f"{badge} | [{p.regra_id}] {p.categoria} ({p.dispositivo_legal}) — {p.criterio_validacao}"

            with st.expander(titulo_exp, expanded=tem_diff_critica):
                col_n, col_s = st.columns(2)

                with col_n:
                    st.markdown("### 🧠 Mecanismo Somente Neural (LLM Puro)")
                    cor_n = "🔴" if jn.status_verificacao == "Indício de Inconformidade" else "🟢"
                    st.markdown(f"**Veredito do LLM Puro:** {cor_n} `{jn.status_verificacao}`")
                    st.warning(f"**Justificativa em Texto Livre (Caixa-Preta):**\n\n\"{jn.justificativa_livre_llm}\"")
                    st.markdown(
                        f"- **Trecho Citado pelo LLM:** `{jn.trecho_citado_llm}`\n"
                        f"- **Árvore de Prova Formal (SLD):** ❌ *Inexistente (geração autoregressiva de tokens)*\n"
                        f"- **Posição Jurídica UFO-L (Hohfeld):** ❌ *Não modelada*\n"
                        f"- **Garantia de Mundo Fechado (NAF `\\+`):** ❌ *Não possui*"
                    )

                with col_s:
                    st.markdown("### 🏛️ Mecanismo Neuro-Simbólico (LLM + Prolog + UFO-L)")
                    cor_s = "🔴" if p.status_verificacao == "Indício de Inconformidade" else "🟢"
                    st.markdown(f"**Veredito Simbólico Formal:** {cor_s} `{p.status_verificacao}`")
                    if p.status_verificacao == "Indício de Inconformidade":
                        st.error(f"**Parecer Desempacotado da UFO-L:**\n\n{p.explicacao_neuro_simbolica}")
                    else:
                        st.success(f"**Parecer Desempacotado da UFO-L:**\n\n{p.explicacao_neuro_simbolica}")
                    st.markdown(
                        f"- **Evidência Rastreável Exata:** `{p.item_identificado}`\n"
                        f"- **Papel Jurídico Afetado:** `{p.inferencia_bruta.papel_afetado}`\n"
                        f"- **Confronto Hohfeldiano (UFO-L):** `{p.inferencia_bruta.momento_edital}` (Edital) vs. `{p.inferencia_bruta.momento_esperado_lei}` (Lei 13.303)\n"
                        f"- **Resultado da Resolução SLD:** `{p.inferencia_bruta.tipo_inferencia_ufol}`"
                    )
                    with st.popover(f"🌲 Ver Árvore de Prova Prolog (SLD Trace - {p.regra_id})"):
                        st.code("\n".join(p.inferencia_bruta.passos_prova_prolog), language="prolog")

                st.info(
                    f"**💡 {jn.tipo_limitacao_observada}**\n\n"
                    f"**Análise Comparativa (requer conferência humana nas divergências):** {jn.analise_diferenca_nesy}"
                )

    # --------------------------------------------------------------------------
    # ABA 4: Benchmark Consolidado (10 Editais Reais BNDES = 90 Verificações)
    # --------------------------------------------------------------------------
    with aba_benchmark:
        st.subheader("📊 Benchmark Empírico Consolidado: 10 Editais Reais do BNDES (90 Verificações Deônticas)")
        resumo_bench = carregar_resumo_benchmark(BENCHMARK_DIR)
        if not resumo_bench:
            st.info(
                "Os resultados consolidados do benchmark dos 10 editais ainda não foram gerados. "
                "Execute `python scripts/executar_benchmark_10_editais.py` para popular `dados/benchmark_10_editais/`."
            )
        else:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Editais Reais Avaliados", resumo_bench["total_editais"], "BNDES (Lei 13.303/2016)")
            b2.metric("Verificações Deônticas", resumo_bench["total_verificacoes"], f"{resumo_bench['total_regras_por_edital']} regras × {resumo_bench['total_editais']} PDFs")
            b3.metric(
                "Divergências (LLM Puro vs. NeSy)",
                f"{resumo_bench['total_divergencias']} casos",
                f"{resumo_bench['taxa_divergencia_pct']}% das verificações",
            )
            b4.metric(
                "Latência Média Simbólica",
                f"{resumo_bench['tempo_medio_prolog_ms']:.2f} ms",
                f"vs. {resumo_bench['tempo_medio_extracao_nesy_s']}s LLM extração",
            )
            if "total_hipoteses_independentes" in resumo_bench:
                st.caption(
                    f"Recorte sem dupla contagem de R01/R02 (Art. 47, I): "
                    f"**{resumo_bench['total_divergencias_sem_dupla_contagem_r01_r02']}** divergência(s) em "
                    f"**{resumo_bench['total_hipoteses_independentes']}** hipóteses independentes "
                    f"(**{resumo_bench['taxa_divergencia_sem_dupla_contagem_pct']}%**)."
                )

            st.markdown("#### 1️⃣ Matriz Consolidada `10 Editais × 9 Regras` (Motor Neuro-Simbólico: Gemini + Prolog/UFO-L)")
            df_matriz = pd.DataFrame(resumo_bench.get("matriz_editais", []))
            st.dataframe(df_matriz, use_container_width=True, hide_index=True)

            col_inc1, col_inc2 = st.columns([3, 2])
            with col_inc1:
                st.markdown("#### 2️⃣ Incidência de Inconformidades e Divergências por Regra")
                df_inc = pd.DataFrame(resumo_bench.get("incidencia_por_regra", []))
                if not df_inc.empty:
                    df_chart = df_inc.set_index("regra_id")[["nesy_inconformes", "neural_inconformes", "divergencias"]]
                    df_chart.columns = ["Inconformes (Neuro-Simbólico)", "Inconformes (Somente Neural)", "Divergências de Veredito"]
                    st.bar_chart(df_chart)
            with col_inc2:
                st.markdown("#### 3️⃣ Tabela Quantitativa por Regra")
                if not df_inc.empty:
                    st.dataframe(
                        df_inc[["regra_id", "dispositivo_legal", "nesy_inconformes", "neural_inconformes", "divergencias"]],
                        use_container_width=True,
                        hide_index=True,
                    )

            st.markdown("#### 4️⃣ Divergências Reais Encontradas (Somente Neural vs. Neuro-Simbólico)")
            divs_list = resumo_bench.get("divergencias_detalhadas", [])
            if not divs_list:
                st.success("Nenhuma divergência de veredito registrada nos 90 casos.")
            else:
                df_divs = pd.DataFrame(divs_list)[
                    ["edital", "regra_id", "dispositivo_legal", "status_somente_neural", "status_neuro_simbolico", "tipo_limitacao", "item_evidencia_nesy"]
                ]
                st.dataframe(df_divs, use_container_width=True, hide_index=True)
                for idx_d, d_item in enumerate(divs_list):
                    titulo_div = (
                        f"🔴 [{d_item['edital']}] Regra {d_item['regra_id']} ({d_item['dispositivo_legal']}) — "
                        f"LLM Puro: {d_item['status_somente_neural']} vs. Prolog/UFO-L: {d_item['status_neuro_simbolico']}"
                    )
                    with st.expander(titulo_div, expanded=(idx_d < 3)):
                        c_dn, c_ds = st.columns(2)
                        with c_dn:
                            st.warning(f"**🧠 Somente Neural (LLM Puro):** {d_item['status_somente_neural']}\n\n{d_item['justificativa_somente_neural']}")
                        with c_ds:
                            st.info(
                                f"**🏛️ Neuro-Simbólico (Prolog + UFO-L):** {d_item['status_neuro_simbolico']}\n\n"
                                f"- **Evidência:** `{d_item['item_evidencia_nesy']}`\n"
                                f"- **Trecho:** {d_item['trecho_evidencia_nesy']}\n"
                                f"- **Posição UFO-L:** `{d_item['momento_edital_ufol']}` vs `{d_item['momento_lei_ufol']}`"
                            )
                        st.markdown(f"**Análise:** {d_item['analise_diferenca']}")

            csv_gabarito = BENCHMARK_DIR / "revisao_gabarito_90_casos.csv"
            if csv_gabarito.exists():
                st.download_button(
                    "⬇️ Baixar Planilha para Revisão de Gabarito (90 Casos - CSV)",
                    data=csv_gabarito.read_bytes(),
                    file_name="revisao_gabarito_90_casos.csv",
                    mime="text/csv",
                )

    # --------------------------------------------------------------------------
    # ABA 5: Laboratório What-If (Manipulação Direta da ABox + SWI-Prolog)
    # --------------------------------------------------------------------------
    with aba_whatif:
        st.subheader("🧪 Laboratório 'What-If': Perturbação Direta da ABox sobre o Motor Simbólico")
        st.markdown(
            "Os controles abaixo carregam diretamente os **fatos reais da ABox** extraídos de "
            f"`{edital_seg.nome_arquivo}`. Altere qualquer premissa factual (sem usar regex) "
            "e observe o **SWI-Prolog / UFO-L** recalcular os vereditos e as negações por falha (`\\+`) em tempo real."
        )

        fatos_wi = fatos.model_copy(deep=True)
        key_prefix = f"wi_{edital_seg.nome_arquivo}"

        with st.form(key=f"form_whatif_{key_prefix}"):
            st.markdown("#### 1. Especificação de Marcas (`R01` e `R02`)")
            novas_marcas: List[MencaoMarcaFato] = []
            if fatos_wi.mencoes_marca:
                opcoes_ctx = [
                    "objeto_licitado",
                    "interoperabilidade_ambiente_legado",
                    "manutencao_parque_existente",
                    "referencia_exemplificativa",
                ]
                for idx_m, m_orig in enumerate(fatos_wi.mencoes_marca):
                    cm1, cm2, cm3, cm4 = st.columns([2.0, 1.8, 1.1, 1.1])
                    cm1.markdown(f"**{m_orig.marca_ou_produto}**  \n_{m_orig.item_edital}_")
                    idx_ctx = opcoes_ctx.index(m_orig.contexto_mencao) if m_orig.contexto_mencao in opcoes_ctx else 0
                    ctx_val = cm2.selectbox(
                        "Contexto da menção",
                        options=opcoes_ctx,
                        index=idx_ctx,
                        key=f"{key_prefix}_ctx_{idx_m}",
                    )
                    sim_val = cm3.checkbox(
                        "Cláusula 'ou similar'",
                        value=m_orig.possui_clausula_similaridade,
                        key=f"{key_prefix}_sim_{idx_m}",
                    )
                    pad_val = cm4.checkbox(
                        "Padronização formal",
                        value=m_orig.possui_justificativa_padronizacao,
                        key=f"{key_prefix}_pad_{idx_m}",
                    )
                    m_copy = m_orig.model_copy(deep=True)
                    m_copy.contexto_mencao = ctx_val  # type: ignore[assignment]
                    m_copy.possui_clausula_similaridade = sim_val
                    m_copy.possui_justificativa_padronizacao = pad_val
                    novas_marcas.append(m_copy)
            else:
                st.caption("Nenhuma marca específica extraída neste edital.")

            incluir_marca_teste = st.checkbox(
                "➕ Injetar marca proprietária hipotética sem 'ou similar' (para testar R01/R02)",
                value=False,
                key=f"{key_prefix}_inj_marca",
            )
            if incluir_marca_teste:
                novas_marcas.append(
                    MencaoMarcaFato(
                        marca_ou_produto="Switch Marca Hipotética XYZ",
                        contexto_mencao="objeto_licitado",
                        possui_clausula_similaridade=False,
                        possui_justificativa_padronizacao=False,
                        item_edital="Simulação What-If (ABox Direta)",
                        trecho_literal="Cláusula hipotética injetada no Laboratório What-If exigindo marca sem similaridade.",
                    )
                )

            st.markdown("#### 2. Habilitação, Amostras e Participação (`R11`, `R29`, `R41`, `R43`)")
            cw1, cw2 = st.columns(2)
            with cw1:
                pct_atestado_wi = st.number_input(
                    "Percentual mínimo exigido em atestado (`R29`)",
                    min_value=0,
                    max_value=100,
                    value=int(fatos_wi.percentual_minimo_atestado),
                    step=5,
                    key=f"{key_prefix}_pct",
                )
                veda_som_wi = st.checkbox(
                    "Veda somatório de atestados (`R29`)",
                    value=fatos_wi.veda_somatorio_atestados,
                    key=f"{key_prefix}_vedasom",
                )
                just_som_wi = st.checkbox(
                    "Possui justificativa técnica para vedar somatório (`R29`)",
                    value=fatos_wi.possui_justificativa_vedacao_somatorio,
                    key=f"{key_prefix}_justsom",
                )
                exige_cred_wi = st.checkbox(
                    "Exige credenciamento / revenda autorizada / carta do fabricante (`R41`)",
                    value=fatos_wi.exige_credenciamento_ou_carta_fabricante,
                    key=f"{key_prefix}_cred",
                )

            with cw2:
                opcoes_amostra = ["nao_exigida", "apenas_primeiro_colocado", "todos_licitantes_fase_proposta"]
                idx_amo = opcoes_amostra.index(fatos_wi.escopo_exigencia_amostra) if fatos_wi.escopo_exigencia_amostra in opcoes_amostra else 0
                amostra_wi = st.selectbox(
                    "Escopo de exigência de amostra (`R11`)",
                    options=opcoes_amostra,
                    index=idx_amo,
                    key=f"{key_prefix}_amostra",
                )
                veda_cons_wi = st.checkbox(
                    "Veda participação em consórcio (`R43`)",
                    value=fatos_wi.veda_participacao_consorcio,
                    key=f"{key_prefix}_cons",
                )
                just_cons_wi = st.checkbox(
                    "Possui justificativa formal para vedar consórcio (`R43`)",
                    value=fatos_wi.possui_justificativa_vedacao_consorcio,
                    key=f"{key_prefix}_justcons",
                )

            st.markdown("#### 3. Cláusulas Contratuais e Gestão de Riscos (`R03`, `R09`, `R38`)")
            cc1, cc2, cc3 = st.columns(3)
            mr_wi = cc1.checkbox("Matriz de Riscos presente (`R03`)", value=fatos_wi.matriz_riscos_presente, key=f"{key_prefix}_mr")
            vad_wi = cc2.checkbox("Vedação a aditivos de risco presente (`R38`)", value=fatos_wi.vedacao_aditivo_risco_presente, key=f"{key_prefix}_vad")
            sub_wi = cc3.checkbox("Subcontratação definida (`R09`)", value=fatos_wi.subcontratacao_definida, key=f"{key_prefix}_sub")

            submeteu_wi = st.form_submit_button("▶️ Recalcular ABox no SWI-Prolog / UFO-L", type="primary")

        if submeteu_wi:
            fatos_wi.mencoes_marca = novas_marcas
            fatos_wi.percentual_minimo_atestado = int(pct_atestado_wi)
            fatos_wi.veda_somatorio_atestados = veda_som_wi
            fatos_wi.possui_justificativa_vedacao_somatorio = just_som_wi
            fatos_wi.exige_credenciamento_ou_carta_fabricante = exige_cred_wi
            fatos_wi.escopo_exigencia_amostra = amostra_wi  # type: ignore[assignment]
            fatos_wi.veda_participacao_consorcio = veda_cons_wi
            fatos_wi.possui_justificativa_vedacao_consorcio = just_cons_wi
            fatos_wi.matriz_riscos_presente = mr_wi
            fatos_wi.vedacao_aditivo_risco_presente = vad_wi
            fatos_wi.subcontratacao_definida = sub_wi

            abox_wi = converter_fatos_para_prolog(fatos_wi)
            catalogo_res, artigos_res, avaliador_res = inicializar_recursos()
            res_pl_wi, _, motor_wi = avaliador_res.executar_avaliacao(
                edital_id=fatos_wi.identificador_edital,
                abox_prolog=abox_wi,
                regras_selecionadas=regras_selecionadas,
            )
            pareceres_wi = gerar_pareceres_edital(res_pl_wi, catalogo_res, artigos_res)
            inc_wi = [p for p in pareceres_wi if p.status_verificacao == "Indício de Inconformidade"]

            st.caption(f"Motor executado: **{motor_wi}**")
            st.markdown(
                f"### Resultado Pós-Perturbação da ABox: **{len(pareceres_wi) - len(inc_wi)} Conformes** | **{len(inc_wi)} Indícios de Inconformidade**"
            )
            mapa_antes = {p.regra_id: p.status_verificacao for p in pareceres}
            df_wi = pd.DataFrame([
                {
                    "Regra": p.regra_id,
                    "Categoria": p.categoria,
                    "Status Original": mapa_antes.get(p.regra_id, "-"),
                    "Status Pós-Edição ABox": p.status_verificacao,
                    "Mudou?": "🔄 SIM" if mapa_antes.get(p.regra_id) != p.status_verificacao else "—",
                    "Momento no Edital (UFO-L)": p.inferencia_bruta.momento_edital,
                    "Momento na Lei (UFO-L)": p.inferencia_bruta.momento_esperado_lei,
                    "Inferência Prolog": p.inferencia_bruta.tipo_inferencia_ufol,
                }
                for p in pareceres_wi
            ])
            st.dataframe(df_wi, use_container_width=True, hide_index=True)
            with st.expander("Ver Nova ABox Prolog Gerada (apenas fatos positivos)"):
                st.code(abox_wi, language="prolog")

    # --------------------------------------------------------------------------
    # ABA 6: Explorador do Edital (.pdf/.txt Numerado)
    # --------------------------------------------------------------------------
    with aba_edital:
        st.subheader(f"Estrutura Segmentada de `{edital_seg.nome_arquivo}`")
        st.json(edital_seg.resumo_secoes)
        secao_escolhida = st.selectbox(
            "Visualizar seção:",
            options=["corpo_edital", "termo_referencia", "minuta_contrato"],
            format_func=lambda s: {
                "corpo_edital": "1. Corpo do Edital",
                "termo_referencia": "2. Anexo I – Especificações Técnicas / Termo de Referência",
                "minuta_contrato": "3. Minuta de Contrato (+ Matriz de Riscos)",
            }[s],
        )
        st.text_area(
            "Texto Numerado ([Pxx|Lxxxx] / [Lxxxx]):",
            value=edital_seg.secoes[secao_escolhida],
            height=450,
        )


if __name__ == "__main__":
    main()

