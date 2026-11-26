"""Aba 2: Prova Formal em Prolog (UFO-L) e Exportação de Artefatos."""

from __future__ import annotations

import json
from typing import Dict, List

import pandas as pd
import streamlit as st

from src.explainer import ParecerRegraEdital, exportar_relatorio_json_validado
from src.extractor_llm import FatosExtraidosEdital
from src.ui.components import render_section_header


def _estilizar_linha_ufol(row: pd.Series) -> List[str]:
    """Destaca linhas com indício de inconformidade na tabela resumo UFO-L."""
    diagnostico = str(row.get("Diagnóstico", "")).strip()
    if diagnostico == "Indício de Inconformidade":
        estilos = []
        for col in row.index:
            if col == "Diagnóstico":
                estilos.append("background-color: #FEE2E2; color: #B91C1C; font-weight: 700;")
            elif col in {"Regra", "Fato no Edital"}:
                estilos.append("background-color: #FEF2F2; color: #B91C1C; font-weight: 600;")
            else:
                estilos.append("background-color: #FEF2F2; color: #7F1D1D;")
        return estilos
    if diagnostico == "Conforme":
        return [
            "background-color: #F0FDF4; color: #15803D; font-weight: 600;"
            if col == "Diagnóstico"
            else ""
            for col in row.index
        ]
    return [""] * len(row)


def render_tab_prova_prolog(
    fatos: FatosExtraidosEdital,
    abox_pl: str,
    codigo_pl_completo: str,
    motor_label: str,
    pareceres: List[ParecerRegraEdital],
    catalogo: Dict[str, dict],
) -> None:
    """Renderiza o inspetor da camada simbólica, tabela UFO-L e exportações."""
    render_section_header(
        titulo="Extração Neural para Prova Deôntica em Prolog (UFO-L)",
        subtitulo=f"Motor simbólico ativo: {motor_label}",
        overline="ARQUITETURA EM DUAS CAMADAS",
    )

    tabela_resumo_ufol = [
        {
            "Regra": p.regra_id,
            "Dispositivo": p.dispositivo_legal,
            "Relação UFO-L": p.inferencia_bruta.relacao_juridica_ufol,
            "Papel (Role)": p.inferencia_bruta.papel_afetado,
            "Deve-Ser (Lei)": p.inferencia_bruta.momento_esperado_lei,
            "Correlato Hohfeld": p.inferencia_bruta.momento_correlato_lei,
            "Fato no Edital": p.inferencia_bruta.momento_edital,
            "Diagnóstico": p.status_verificacao,
        }
        for p in pareceres
    ]
    df_ufol = pd.DataFrame(tabela_resumo_ufol)
    st.dataframe(
        df_ufol.style.apply(_estilizar_linha_ufol, axis=1),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Regra": st.column_config.TextColumn("Regra", width="small"),
            "Dispositivo": st.column_config.TextColumn("Dispositivo", width="medium"),
            "Diagnóstico": st.column_config.TextColumn("Diagnóstico", width="large"),
        },
    )

    opcoes_visao = [
        "Árvore de Derivação (SLD)",
        "ABox Prolog (UFO-L)",
        "JSON Extraído (Neural)",
    ]
    visao = (
        st.segmented_control(
            "Inspecionar artefato formal",
            options=opcoes_visao,
            default="Árvore de Derivação (SLD)",
            key="prolog_visao_artefato",
        )
        or "Árvore de Derivação (SLD)"
    )

    with st.container(border=True):
        if visao == "Árvore de Derivação (SLD)":
            regra_trace_sel = st.selectbox(
                "Regra para inspeção da prova passo a passo:",
                options=[p.regra_id for p in pareceres],
                format_func=lambda r: f"{r} · {catalogo[r]['criterio_validacao']}",
                key="prolog_trace_regra",
            )
            parecer_sel = next(p for p in pareceres if p.regra_id == regra_trace_sel)
            st.code(
                "\n".join(parecer_sel.inferencia_bruta.passos_prova_prolog),
                language="prolog",
            )
        elif visao == "ABox Prolog (UFO-L)":
            st.caption("Fatos positivos traduzidos para predicados da ontologia UFO-L.")
            st.code(abox_pl, language="prolog")
        else:
            st.caption("Estrutura Pydantic extraída pela camada neural (`FatosExtraidosEdital`).")
            st.json(fatos.model_dump())

    st.caption("Exportar artefatos auditáveis da sessão")
    col_dl1, col_dl2, _ = st.columns([1, 1, 1.5])
    with col_dl1:
        st.download_button(
            "Baixar Base Prolog (.pl)",
            data=codigo_pl_completo,
            file_name=f"sessao_{fatos.identificador_edital}.pl",
            mime="text/plain",
            icon=":material/download:",
            use_container_width=True,
        )
    with col_dl2:
        relatorio_json = exportar_relatorio_json_validado(pareceres, catalogo)
        st.download_button(
            "Baixar Relatório Validado (.json)",
            data=json.dumps(relatorio_json, ensure_ascii=False, indent=2),
            file_name=f"relatorio_{fatos.identificador_edital}.json",
            mime="application/json",
            icon=":material/download:",
            use_container_width=True,
        )
