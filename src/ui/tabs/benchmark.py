"""Aba 4: Benchmark Empírico Consolidado (10 Editais Reais do BNDES)."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.extractor_llm import carregar_resumo_benchmark
from src.ui.components import (
    estilizar_coluna_status,
    estilizar_matriz_benchmark,
    limpar_emojis_ui,
    render_divergence_spotlight,
    render_kpi_strip,
    render_nota_discreta,
    render_section_header,
    render_status_badge_html,
)


def _estilo_tipo_limitacao(_: object) -> str:
    return "background-color: #F5F3FF; color: #6D28D9; font-weight: 600;"


def render_tab_benchmark(benchmark_dir: Path) -> None:
    """Renderiza o painel consolidado do benchmark dos 10 editais."""
    render_section_header(
        titulo="Benchmark Empírico: 10 Editais Reais do BNDES",
        subtitulo="Avaliação consolidada de 90 verificações deônticas sob a Lei nº 13.303/2016.",
        overline="DADOS EXPERIMENTAIS",
    )

    resumo_bench = carregar_resumo_benchmark(benchmark_dir)
    if not resumo_bench:
        render_nota_discreta(
            "Os resultados consolidados do benchmark dos 10 editais ainda não foram gerados. "
            "Execute `python scripts/executar_benchmark_10_editais.py` para popular `dados/benchmark_10_editais/`.",
            tone="warning",
        )
        return

    render_kpi_strip(
        [
            {
                "label": "Editais Avaliados",
                "value": str(resumo_bench["total_editais"]),
                "detail": "PDFs reais BNDES (Lei 13.303/2016)",
                "tone": "neutral",
            },
            {
                "label": "Verificações Deônticas",
                "value": str(resumo_bench["total_verificacoes"]),
                "detail": f"{resumo_bench['total_regras_por_edital']} regras × {resumo_bench['total_editais']} editais",
                "tone": "primary",
            },
            {
                "label": "Divergências (LLM vs. NeSy)",
                "value": f"{resumo_bench['total_divergencias']} casos",
                "detail": f"{resumo_bench['taxa_divergencia_pct']}% das verificações",
                "tone": "divergence",
            },
            {
                "label": "Latência Simbólica Média",
                "value": f"{resumo_bench['tempo_medio_prolog_ms']:.2f} ms",
                "detail": f"vs. {resumo_bench['tempo_medio_extracao_nesy_s']}s na extração LLM",
                "tone": "success",
            },
        ]
    )

    if "total_hipoteses_independentes" in resumo_bench:
        st.caption(
            f"Recorte sem dupla contagem de R01/R02 (Art. 47, I): "
            f"**{resumo_bench['total_divergencias_sem_dupla_contagem_r01_r02']}** divergência(s) em "
            f"**{resumo_bench['total_hipoteses_independentes']}** hipóteses independentes "
            f"(**{resumo_bench['taxa_divergencia_sem_dupla_contagem_pct']}%**)."
        )

    render_section_header(
        titulo="Matriz Consolidada (10 Editais × 9 Regras)",
        subtitulo="Resultados do motor Neuro-Simbólico (Gemini + Prolog/UFO-L).",
    )
    df_matriz_raw = pd.DataFrame(resumo_bench.get("matriz_editais", []))
    if not df_matriz_raw.empty:
        _, styler_matriz = estilizar_matriz_benchmark(df_matriz_raw)
        st.dataframe(styler_matriz, use_container_width=True, hide_index=True)

    col_inc1, col_inc2 = st.columns([3, 2], gap="medium")
    df_inc = pd.DataFrame(resumo_bench.get("incidencia_por_regra", []))

    with col_inc1:
        render_section_header(
            titulo="Incidência e Divergências por Regra",
            subtitulo="Comparação quantitativa por dispositivo avaliado.",
        )
        if not df_inc.empty:
            df_melt = df_inc[["regra_id", "nesy_inconformes", "neural_inconformes", "divergencias"]].rename(
                columns={
                    "nesy_inconformes": "Neuro-Simbólico",
                    "neural_inconformes": "Somente Neural",
                    "divergencias": "Divergências",
                }
            ).melt(id_vars="regra_id", var_name="Série", value_name="Ocorrências")

            chart = (
                alt.Chart(df_melt)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("regra_id:N", title="Regra", axis=alt.Axis(labelAngle=0, grid=False)),
                    xOffset=alt.XOffset("Série:N"),
                    y=alt.Y("Ocorrências:Q", title="Editais", axis=alt.Axis(tickMinStep=1, gridColor="#E2E5EC")),
                    color=alt.Color(
                        "Série:N",
                        scale=alt.Scale(
                            domain=["Neuro-Simbólico", "Somente Neural", "Divergências"],
                            range=["#1D4ED8", "#94A3B8", "#7C3AED"],
                        ),
                        legend=alt.Legend(orient="top", title=None),
                    ),
                    tooltip=["regra_id", "Série", "Ocorrências"],
                )
                .properties(height=300, background="transparent")
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart, use_container_width=True)

    with col_inc2:
        render_section_header(
            titulo="Tabela Quantitativa",
            subtitulo="Resumo numérico por regra.",
        )
        if not df_inc.empty:
            df_inc_clean = df_inc[
                ["regra_id", "dispositivo_legal", "nesy_inconformes", "neural_inconformes", "divergencias"]
            ].rename(
                columns={
                    "regra_id": "Regra",
                    "dispositivo_legal": "Dispositivo",
                    "nesy_inconformes": "NeSy",
                    "neural_inconformes": "Neural",
                    "divergencias": "Diverg.",
                }
            )
            st.dataframe(df_inc_clean, use_container_width=True, hide_index=True)

    render_section_header(
        titulo="Divergências Reais Encontradas",
        subtitulo="Casos em que o julgamento Somente Neural divergiu da inferência Prolog/UFO-L.",
    )
    divs_list = resumo_bench.get("divergencias_detalhadas", [])
    if not divs_list:
        render_nota_discreta("Nenhuma divergência de veredito registrada nos 90 casos.", tone="success")
    else:
        df_divs = pd.DataFrame(divs_list)[
            [
                "edital",
                "regra_id",
                "dispositivo_legal",
                "status_somente_neural",
                "status_neuro_simbolico",
                "tipo_limitacao",
                "item_evidencia_nesy",
            ]
        ].copy()
        df_divs["tipo_limitacao"] = df_divs["tipo_limitacao"].map(limpar_emojis_ui)
        df_divs.columns = [
            "Edital",
            "Regra",
            "Dispositivo",
            "Somente Neural",
            "Neuro-Simbólico",
            "Tipo de Limitação",
            "Evidência (NeSy)",
        ]
        styler_divs = (
            df_divs.style
            .map(estilizar_coluna_status, subset=["Somente Neural", "Neuro-Simbólico"])
            .map(_estilo_tipo_limitacao, subset=["Tipo de Limitação"])
        )
        st.dataframe(styler_divs, use_container_width=True, hide_index=True)

        for d_item in divs_list:
            titulo_div = (
                f"{d_item['edital']} · {d_item['regra_id']} ({d_item['dispositivo_legal']})  "
                f":violet-badge[Divergência]"
            )
            with st.expander(titulo_div, expanded=False, icon=":material/bolt:"):
                render_divergence_spotlight(
                    titulo=limpar_emojis_ui(d_item["tipo_limitacao"]),
                    status_neural=d_item["status_somente_neural"],
                    status_nesy=d_item["status_neuro_simbolico"],
                )
                c_dn, c_ds = st.columns(2, gap="medium")
                with c_dn:
                    with st.container(border=True):
                        tone_n = "error" if d_item["status_somente_neural"] == "Indício de Inconformidade" else "success"
                        st.markdown(
                            f"**Somente Neural (LLM Puro)** &nbsp; {render_status_badge_html(d_item['status_somente_neural'], tone_n)}",
                            unsafe_allow_html=True,
                        )
                        st.markdown(d_item["justificativa_somente_neural"])
                with c_ds:
                    with st.container(border=True):
                        tone_s = "error" if d_item["status_neuro_simbolico"] == "Indício de Inconformidade" else "success"
                        st.markdown(
                            f"**Neuro-Simbólico (Prolog + UFO-L)** &nbsp; {render_status_badge_html(d_item['status_neuro_simbolico'], tone_s)}",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"- **Evidência:** `{d_item['item_evidencia_nesy']}`\n"
                            f"- **Trecho:** {d_item['trecho_evidencia_nesy']}\n"
                            f"- **Posição UFO-L:** `{d_item['momento_edital_ufol']}` vs. `{d_item['momento_lei_ufol']}`"
                        )
                st.markdown(f"**Análise:** {d_item['analise_diferenca']}")

    csv_gabarito = benchmark_dir / "revisao_gabarito_90_casos.csv"
    if csv_gabarito.exists():
        st.download_button(
            "Baixar Planilha para Revisão de Gabarito (90 Casos · CSV)",
            data=csv_gabarito.read_bytes(),
            file_name="revisao_gabarito_90_casos.csv",
            mime="text/csv",
            icon=":material/download:",
        )
