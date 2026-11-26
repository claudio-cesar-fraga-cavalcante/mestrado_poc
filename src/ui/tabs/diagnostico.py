"""Aba 1: Diagnóstico de Conformidade Neuro-Simbólica."""

from __future__ import annotations

from typing import List

import streamlit as st

from src.explainer import ParecerRegraEdital
from src.extractor_llm import FatosExtraidosEdital
from src.ui.components import (
    render_accent_banner,
    render_kv_list,
    render_nota_discreta,
    render_section_header,
)


def render_tab_diagnostico(
    fatos: FatosExtraidosEdital,
    pareceres: List[ParecerRegraEdital],
    inconformes: List[ParecerRegraEdital],
    conformes: List[ParecerRegraEdital],
) -> None:
    """Renderiza a aba de diagnóstico de conformidade no padrão minimalista M3."""
    with st.container(border=True):
        render_section_header(
            titulo="Objeto Extraído do Edital",
            subtitulo=fatos.resumo_objeto,
            overline="RESUMO SEMÂNTICO",
        )

    opcoes_filtro = ["Todas", "Inconformes", "Conformes"]
    rotulos_filtro = {
        "Todas": f"Todas ({len(pareceres)})",
        "Inconformes": f"Inconformes ({len(inconformes)})",
        "Conformes": f"Conformes ({len(conformes)})",
    }
    filtro_sel = (
        st.segmented_control(
            "Filtrar regras avaliadas",
            options=opcoes_filtro,
            default="Todas",
            format_func=lambda op: rotulos_filtro[op],
            key="diag_filtro_status",
            label_visibility="collapsed",
        )
        or "Todas"
    )

    if filtro_sel == "Inconformes":
        lista_exibicao = inconformes
    elif filtro_sel == "Conformes":
        lista_exibicao = conformes
    else:
        lista_exibicao = pareceres

    if not lista_exibicao:
        render_nota_discreta(
            "Nenhum item encontrado para o filtro selecionado.",
            tone="success",
        )
        return

    for p in lista_exibicao:
        eh_inconforme = p.status_verificacao == "Indício de Inconformidade"
        icone = ":material/error_outline:" if eh_inconforme else ":material/check_circle:"
        badge_status = (
            f":red-badge[Inconforme · Risco {p.classificacao_risco}]"
            if eh_inconforme
            else ":green-badge[Conforme]"
        )
        titulo_card = f"{p.regra_id} · {p.categoria} — {p.dispositivo_legal}  {badge_status}"

        with st.expander(titulo_card, expanded=eh_inconforme, icon=icone):
            c_esq, c_dir = st.columns([3, 2], gap="medium")

            with c_esq:
                with st.container(border=True):
                    titulo_banner = (
                        f"Indício de Inconformidade · Risco {p.classificacao_risco} · {p.criterio_validacao}"
                        if eh_inconforme
                        else f"Conformidade Verificada · {p.criterio_validacao}"
                    )
                    render_accent_banner(
                        titulo_banner,
                        tone="error" if eh_inconforme else "success",
                    )
                    st.markdown(p.explicacao_neuro_simbolica)
                    st.caption("Trecho identificado no edital")
                    st.code(
                        f"Localização: {p.item_identificado}\n\n{p.trecho_identificado}",
                        language="text",
                    )

            with c_dir:
                with st.container(border=True):
                    render_accent_banner(
                        "Formalização na Ontologia UFO-L",
                        tone="primary",
                    )
                    st.markdown(p.explicacao_ontologica_ufol)
                    render_kv_list(
                        [
                            ("Relação Jurídica", p.inferencia_bruta.relacao_juridica_ufol, True),
                            ("Papel Afetado", p.inferencia_bruta.papel_afetado, True),
                            (
                                "Posição na Lei 13.303",
                                f"{p.inferencia_bruta.momento_esperado_lei} (correlato: {p.inferencia_bruta.momento_correlato_lei})",
                                True,
                            ),
                            ("Posição no Edital", p.inferencia_bruta.momento_edital, True),
                            ("Resultado Prolog", p.inferencia_bruta.tipo_inferencia_ufol, True),
                        ]
                    )
                    with st.popover(
                        f"Texto oficial ({p.dispositivo_legal})",
                        icon=":material/gavel:",
                    ):
                        st.text(p.texto_lei_13303)
