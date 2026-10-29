"""
Interface Web (Streamlit) da PoC de Mestrado:
Validador Neuro-Simbólico de Editais de Licitação (Lei nº 13.303/2016 + Ontologia UFO-L).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.explainer import (
    ParecerRegraEdital,
    exportar_relatorio_json_validado,
    gerar_pareceres_edital,
)
from src.extractor_llm import (
    FatosExtraidosEdital,
    converter_fatos_para_prolog,
    extrair_fatos_heuristico_texto,
    extrair_fatos_via_gemini,
    obter_fatos_demo_pe_29_2026,
)
from src.parser_edital import (
    POC_RULE_IDS,
    EditalSegmentado,
    carregar_artigos_lei13303,
    carregar_edital_txt,
    carregar_regras_validador,
    processar_texto_edital,
)
from src.reasoner_prolog import AvaliadorSimbolicoUfoL

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"
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


def listar_editais_disponiveis() -> Dict[str, Path]:
    opcoes: Dict[str, Path] = {}
    edital_principal = DADOS_DIR / "Edital_PE_29-2026.txt"
    if edital_principal.exists():
        opcoes["📄 Edital_PE_29-2026.txt (BNDES - Contratação DaaS - Original)"] = edital_principal

    if TESTE_DIR.exists():
        for arq in sorted(TESTE_DIR.glob("*.txt")):
            if "Critico" in arq.name:
                label = f"🚨 {arq.name} (Cenário de Alto Direcionamento / Restrição)"
            elif "Saneado" in arq.name:
                label = f"✅ {arq.name} (Cenário Saneado 100% Conforme)"
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
    if modo_execucao.startswith("Modo Live"):
        if not api_key:
            st.error("Informe a chave `GEMINI_API_KEY` na barra lateral para usar o Modo Live, ou alterne para o Modo Demonstração.")
            st.stop()
        with st.spinner(f"Camada Neural: Extraindo fatos ontológicos via Google Gemini (`{modelo_gemini}`)..."):
            fatos, mod_usado = extrair_fatos_via_gemini(
                texto_numerado=edital_seg.texto_numerado,
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
        if edital_seg.nome_arquivo == "Edital_PE_29-2026.txt" and not forcar_heuristico_texto:
            fatos = obter_fatos_demo_pe_29_2026()
        else:
            fatos = extrair_fatos_heuristico_texto(
                edital_seg.texto_numerado, nome_arquivo=edital_seg.nome_arquivo
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

    st.title("⚖️ Validador Neuro-Simbólico de Editais (Lei 13.303/2016 + UFO-L)")
    st.caption(
        "PoC de Mestrado — Instanciação Semântica via LLM (Google Gemini) + Raciocínio Deôntico/Relacional em Prolog fundamentado na Ontologia Jurídica UFO-L"
    )

    # ==========================================================================
    # Barra Lateral
    # ==========================================================================
    with st.sidebar:
        st.header("⚙️ Configuração da Auditoria")

        editais_map = listar_editais_disponiveis()
        escolha_edital = st.selectbox(
            "1. Selecione o Edital (.txt):",
            options=list(editais_map.keys()) + ["📤 Enviar outro arquivo .txt..."],
        )

        arquivo_upload = None
        if escolha_edital == "📤 Enviar outro arquivo .txt...":
            arquivo_upload = st.file_uploader("Carregar Edital (.txt)", type=["txt"])

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
    if escolha_edital == "📤 Enviar outro arquivo .txt...":
        if arquivo_upload is None:
            st.info("Envie um arquivo `.txt` na barra lateral para iniciar a análise.")
            st.stop()
        conteudo_up = arquivo_upload.read().decode("utf-8", errors="replace")
        edital_seg = processar_texto_edital(conteudo_up, nome_arquivo=arquivo_upload.name)
    else:
        caminho_edital = editais_map[escolha_edital]
        edital_seg = carregar_edital_txt(caminho_edital)

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
    col1.metric("Arquivo Analisado", edital_seg.nome_arquivo, f"{len(edital_seg.linhas_originais)} linhas")
    col2.metric("Regras Avaliadas (PoC)", len(pareceres), "Lei nº 13.303/2016")
    col3.metric(
        "Indícios de Inconformidade",
        len(inconformes),
        f"{len(criticos_altos)} de risco Crítico/Alto" if inconformes else "Nenhuma violação",
        delta_color="inverse" if inconformes else "normal",
    )
    col4.metric("Regras Conformes", len(conformes), f"{int(len(conformes)/max(1, len(pareceres))*100)}% de aderência")

    # ==========================================================================
    # Abas Principais
    # ==========================================================================
    aba_parecer, aba_ontologia, aba_whatif, aba_edital = st.tabs([
        "📋 1. Diagnóstico de Conformidade e Explicação",
        "🧠 2. Raciocínio Neuro-Simbólico & Prova UFO-L (Prolog)",
        "🧪 3. Laboratório 'What-If' (Testar Mudanças no Edital)",
        "📄 4. Explorador do Edital (.txt Numerado)",
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
    # ABA 3: Laboratório What-If
    # --------------------------------------------------------------------------
    with aba_whatif:
        st.subheader("🧪 Laboratório 'What-If': Teste de Sensibilidade do Motor Simbólico")
        st.markdown(
            "Altere qualquer texto das cláusulas abaixo (por exemplo, adicione **'ou similar ou de melhor qualidade'** "
            "ao Windows 11, remova a exigência de **rede de revendas autorizadas**, ou inclua **justificativa para vedação de consórcio**) "
            "e veja como a nova extração altera os fatos em Prolog e a prova formal na UFO-L!"
        )

        trecho_default_whatif = (
            "[L0023] 2.3 Estará impedido de participar deste Pregão o interessado que: VIII. esteja organizado sob a forma de consórcio.\n"
            "[L0140] 4.11.4 Verificado o atendimento dos requisitos de habilitação do licitante, o Pregoeiro suspenderá a sessão pública para a apresentação de amostra pelo primeiro colocado.\n"
            "[L0294] 5. Sistema operacional Windows 11 Professional\n"
            "[L0624] 114.c Declaração de que faz parte da rede de revendas autorizadas pelo provedor da solução para comercialização dos serviços ofertados.\n"
            "[L0628] 116. Atestado de Capacidade Técnica em quantidade igual ou superior a 50% da quantidade total prevista.\n"
            "[L0630] 117. Não será aceito o somatório da quantidade de estações virtuais disponibilizadas em diferentes atestados de capacidade técnica.\n"
            "[L0841] CLÁUSULA NONA – MATRIZ DE RISCOS: estabelecem os respectivos responsáveis na Matriz de Riscos constante do Anexo III.\n"
            "[L0848] Parágrafo Segundo: É vedada a celebração de aditivos decorrentes de eventos supervenientes alocados, na Matriz de Riscos, como de responsabilidade do CONTRATADO.\n"
            "[L1018] CLÁUSULA DÉCIMA SÉTIMA - Parágrafo Terceiro: É vedada a subcontratação para a execução do objeto deste Contrato."
        )

        texto_whatif = st.text_area(
            "Cláusulas em Teste (edite livremente):",
            value=trecho_default_whatif,
            height=240,
        )

        if st.button("▶️ Executar Revalidação Simbólica sobre o Texto Editado", type="primary"):
            edital_custom = processar_texto_edital(texto_whatif, nome_arquivo="simulacao_what_if.txt")
            _, abox_wi, _, _, pareceres_wi, _ = executar_pipeline(
                edital_seg=edital_custom,
                modo_execucao=modo_execucao,
                api_key=api_key,
                modelo_gemini=modelo_gemini,
                regras_selecionadas=regras_selecionadas,
                forcar_heuristico_texto=True,
            )
            inc_wi = [p for p in pareceres_wi if p.status_verificacao == "Indício de Inconformidade"]
            st.markdown(
                f"### Resultado da Simulação: **{len(pareceres_wi) - len(inc_wi)} Conformes** | **{len(inc_wi)} Indícios de Inconformidade**"
            )
            df_wi = pd.DataFrame([
                {
                    "Regra": p.regra_id,
                    "Categoria": p.categoria,
                    "Status Pós-Edição": p.status_verificacao,
                    "Momento no Edital (UFO-L)": p.inferencia_bruta.momento_edital,
                    "Momento na Lei (UFO-L)": p.inferencia_bruta.momento_esperado_lei,
                    "Inferência Prolog": p.inferencia_bruta.tipo_inferencia_ufol,
                }
                for p in pareceres_wi
            ])
            st.dataframe(df_wi, use_container_width=True, hide_index=True)
            with st.expander("Ver Fatos Prolog Gerados na Simulação"):
                st.code(abox_wi, language="prolog")

    # --------------------------------------------------------------------------
    # ABA 4: Explorador do Edital (.txt Numerado)
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
                "minuta_contrato": "3. Minuta de Contrato",
            }[s],
        )
        st.text_area(
            "Texto Numerado ([Lxxxx]):",
            value=edital_seg.secoes[secao_escolhida],
            height=450,
        )


if __name__ == "__main__":
    main()

