"""Aba 3: Avaliação Comparativa (Somente Neural vs. Neuro-Simbólico)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

from src.explainer import ParecerRegraEdital
from src.extractor_llm import (
    JulgamentoNeuralRegra,
    carregar_cache_benchmark_edital,
    executar_avaliacao_somente_neural_gemini,
    obter_avaliacao_somente_neural_demo,
)
from src.parser_edital import EditalSegmentado
from src.ui.components import (
    estilizar_coluna_status,
    limpar_emojis_ui,
    render_accent_banner,
    render_divergence_spotlight,
    render_kpi_strip,
    render_kv_list,
    render_nota_discreta,
    render_section_header,
    render_status_badge_html,
)


def _estilizar_linha_comparativo(row: pd.Series) -> List[str]:
    if row.get("Somente Neural") != row.get("Neuro-Simbólico"):
        return [
            "background-color: #F5F3FF; color: #6D28D9; font-weight: 600;"
            if col == "Diagnóstico da Diferença"
            else "background-color: #F5F3FF;"
            for col in row.index
        ]
    return [""] * len(row)


def render_tab_comparativo(
    edital_seg: EditalSegmentado,
    pareceres: List[ParecerRegraEdital],
    catalogo: Dict[str, dict],
    regras_selecionadas: List[str],
    modo_execucao: str,
    api_key: str,
    modelo_gemini: str,
    benchmark_dir: Path,
) -> None:
    """Renderiza a comparação lado a lado entre LLM puro e motor Neuro-Simbólico."""
    render_section_header(
        titulo="Somente Neural (LLM Puro) vs. Neuro-Simbólico (Prolog + UFO-L)",
        subtitulo="Confronto entre julgamento direto em texto livre e inferência deôntica formal.",
        overline="AVALIAÇÃO COMPARATIVA",
    )

    with st.expander("Sobre a metodologia comparativa", expanded=False, icon=":material/info:"):
        st.markdown(
            "Esta visão coloca lado a lado as respostas de um **Mecanismo Somente Neural** "
            "(onde o LLM julga diretamente a conformidade do edital em texto livre, sem ABox formal e sem Prolog) "
            "e o **Mecanismo Neuro-Simbólico** (onde o LLM apenas extrai fatos observáveis e o motor Prolog/UFO-L "
            "executa a Resolução SLD sob a Hipótese do Mundo Fechado)."
        )

    chave_cache_neural = f"baseline_neural_{edital_seg.nome_arquivo}"
    cache_ed_atual = carregar_cache_benchmark_edital(edital_seg.nome_arquivo, benchmark_dir)
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
        render_nota_discreta(
            f"Baseline Somente Neural: execução real registrada via {cache_ed_atual.get('modelo_gemini', 'gemini-2.5-flash')} (temperature=0.0).",
            tone="primary",
        )
    else:
        render_nota_discreta(
            "Cenário sintético/offline sem execução Gemini pré-gravada: exibindo respostas ilustrativas de demonstração. "
            "Para dados experimentais reais, selecione um dos 10 PDFs do BNDES ou execute ao vivo no Modo Live.",
            tone="warning",
        )

    if modo_execucao.startswith("Modo Live") and api_key:
        if st.button(
            "Executar julgamento Somente Neural ao vivo",
            icon=":material/refresh:",
            key="btn_live_somente_neural",
        ):
            with st.spinner("Executando julgamento Somente Neural no Google Gemini..."):
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

    total_comp = len(pareceres)
    divergencias_veredito: List[str] = []
    ruidos_ou_divergencias: List[str] = []
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

    render_kpi_strip(
        [
            {
                "label": "Concordância",
                "value": f"{pct_conc}%",
                "detail": f"{concordancias} de {total_comp} vereditos iguais",
                "tone": "primary",
            },
            {
                "label": "Divergências",
                "value": str(len(divergencias_veredito)),
                "detail": ", ".join(divergencias_veredito) if divergencias_veredito else "Convergência total",
                "tone": "divergence" if divergencias_veredito else "success",
            },
            {
                "label": "Consistência Cruzada",
                "value": f"{cruzada_ok}/{total_comp}",
                "detail": "SWI-Prolog vs. SLD Trace",
                "tone": "success" if cruzada_ok == total_comp else "warning",
            },
            {
                "label": "Prova Formal Auditável",
                "value": "0% vs. 100%",
                "detail": "Caixa-preta vs. SLD + Hohfeld",
                "tone": "neutral",
            },
        ]
    )

    linhas_tab_comp = []
    for p in pareceres:
        jn = mapa_neural.get(p.regra_id)
        if not jn:
            continue
        linhas_tab_comp.append(
            {
                "Regra": p.regra_id,
                "Categoria / Dispositivo": f"{p.categoria} ({p.dispositivo_legal})",
                "Somente Neural": jn.status_verificacao,
                "Neuro-Simbólico": p.status_verificacao,
                "Diagnóstico da Diferença": limpar_emojis_ui(jn.tipo_limitacao_observada),
                "Hohfeld (Edital vs. Lei)": f"{p.inferencia_bruta.momento_edital} vs. {p.inferencia_bruta.momento_esperado_lei}",
            }
        )

    df_comp = pd.DataFrame(linhas_tab_comp)
    styler_comp = (
        df_comp.style.apply(_estilizar_linha_comparativo, axis=1)
        .map(estilizar_coluna_status, subset=["Somente Neural", "Neuro-Simbólico"])
    )
    st.dataframe(
        styler_comp,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Regra": st.column_config.TextColumn("Regra", width="small"),
        },
    )

    opcoes_comp = ["Divergências e Diferenças", "Todas as Regras"]
    rotulos_comp = {
        "Divergências e Diferenças": f"Divergências e diferenças ({len(ruidos_ou_divergencias)})",
        "Todas as Regras": f"Todas as regras ({total_comp})",
    }
    filtro_comp = (
        st.segmented_control(
            "Filtrar comparativos detalhados",
            options=opcoes_comp,
            default="Divergências e Diferenças" if ruidos_ou_divergencias else "Todas as Regras",
            format_func=lambda op: rotulos_comp[op],
            key="comp_filtro_cards",
            label_visibility="collapsed",
        )
        or "Todas as Regras"
    )

    pareceres_comp = (
        [p for p in pareceres if p.regra_id in ruidos_ou_divergencias]
        if filtro_comp == "Divergências e Diferenças" and ruidos_ou_divergencias
        else pareceres
    )

    for p in pareceres_comp:
        jn = mapa_neural.get(p.regra_id)
        if not jn:
            continue
        divergiu = jn.status_verificacao != p.status_verificacao
        tem_diff_critica = p.regra_id in ruidos_ou_divergencias
        if divergiu:
            icone_exp = ":material/bolt:"
            badge_exp = ":violet-badge[Divergência de Veredito]"
        elif tem_diff_critica:
            icone_exp = ":material/compare_arrows:"
            badge_exp = ":orange-badge[Diferença de Fundamentação]"
        else:
            icone_exp = ":material/check_circle:"
            badge_exp = ":green-badge[Convergente]"

        titulo_exp = f"{p.regra_id} · {p.categoria} ({p.dispositivo_legal})  {badge_exp}"

        with st.expander(titulo_exp, expanded=tem_diff_critica, icon=icone_exp):
            if divergiu:
                render_divergence_spotlight(
                    titulo=limpar_emojis_ui(jn.tipo_limitacao_observada),
                    status_neural=jn.status_verificacao,
                    status_nesy=p.status_verificacao,
                )

            col_n, col_s = st.columns(2, gap="medium")

            with col_n:
                with st.container(border=True):
                    tone_n = "error" if jn.status_verificacao == "Indício de Inconformidade" else "success"
                    st.markdown(
                        f"**Somente Neural (LLM Puro)** &nbsp; {render_status_badge_html(jn.status_verificacao, tone_n)}",
                        unsafe_allow_html=True,
                    )
                    st.caption("Justificativa em texto livre (caixa-preta)")
                    st.markdown(f"> {jn.justificativa_livre_llm}")
                    render_kv_list(
                        [
                            ("Trecho citado", jn.trecho_citado_llm, True),
                            ("Árvore de prova (SLD)", "Ausente (geração autoregressiva)", False),
                            ("Posição UFO-L (Hohfeld)", "Não modelada", False),
                            ("Mundo Fechado (NAF)", "Ausente", False),
                        ]
                    )

            with col_s:
                with st.container(border=True):
                    tone_s = "error" if p.status_verificacao == "Indício de Inconformidade" else "success"
                    st.markdown(
                        f"**Neuro-Simbólico (Prolog + UFO-L)** &nbsp; {render_status_badge_html(p.status_verificacao, tone_s)}",
                        unsafe_allow_html=True,
                    )
                    st.caption("Parecer fundamentado na UFO-L")
                    st.markdown(p.explicacao_neuro_simbolica)
                    render_kv_list(
                        [
                            ("Evidência rastreável", p.item_identificado, True),
                            ("Papel afetado", p.inferencia_bruta.papel_afetado, True),
                            (
                                "Confronto Hohfeldiano",
                                f"{p.inferencia_bruta.momento_edital} vs. {p.inferencia_bruta.momento_esperado_lei}",
                                True,
                            ),
                            ("Resolução SLD", p.inferencia_bruta.tipo_inferencia_ufol, True),
                        ]
                    )
                    with st.popover(
                        f"Árvore SLD ({p.regra_id})",
                        icon=":material/account_tree:",
                    ):
                        st.code("\n".join(p.inferencia_bruta.passos_prova_prolog), language="prolog")

            render_accent_banner(
                limpar_emojis_ui(jn.tipo_limitacao_observada),
                tone="divergence" if divergiu else ("warning" if tem_diff_critica else "neutral"),
            )
            st.markdown(f"**Análise comparativa:** {jn.analise_diferenca_nesy}")
