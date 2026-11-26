"""Aba 6: Explorador do Texto Segmentado do Edital."""

from __future__ import annotations

import streamlit as st

from src.parser_edital import EditalSegmentado
from src.ui.components import render_kv_list, render_section_header


def render_tab_edital(edital_seg: EditalSegmentado) -> None:
    """Renderiza o explorador minimalista do edital segmentado e numerado."""
    render_section_header(
        titulo=f"Estrutura Segmentada: {edital_seg.nome_arquivo}",
        subtitulo="Visualização das seções indexadas por página e linha.",
        overline="DOCUMENTO FONTE",
    )

    resumo = edital_seg.resumo_secoes or {}
    c1, c2, c3 = st.columns(3, gap="medium")
    itens_resumo = list(resumo.items())
    if len(itens_resumo) >= 3:
        for col, (k, v) in zip([c1, c2, c3], itens_resumo[:3]):
            with col:
                with st.container(border=True):
                    render_kv_list([(str(k).replace("_", " ").capitalize(), str(v), False)])
    if len(itens_resumo) > 3 or not itens_resumo:
        with st.expander("Metadados técnicos das seções (JSON)", expanded=False, icon=":material/data_object:"):
            st.json(resumo)
    else:
        with st.expander("Metadados técnicos (JSON)", expanded=False, icon=":material/data_object:"):
            st.json(resumo)

    opcoes_secoes = {
        "corpo_edital": "Corpo do Edital",
        "termo_referencia": "Termo de Referência",
        "minuta_contrato": "Minuta de Contrato",
    }
    secao_escolhida = (
        st.segmented_control(
            "Seção do documento",
            options=list(opcoes_secoes.keys()),
            default="corpo_edital",
            format_func=lambda s: opcoes_secoes[s],
            key="edital_secao_sel",
        )
        or "corpo_edital"
    )

    texto_secao = edital_seg.secoes.get(secao_escolhida, "")
    termo_busca = st.text_input(
        "Filtrar linhas por termo",
        placeholder="Ex.: marca, amostra, atestado, consórcio, matriz de riscos...",
        key="edital_filtro_termo",
    ).strip()

    if termo_busca:
        linhas_filtradas = [
            ln for ln in texto_secao.splitlines() if termo_busca.lower() in ln.lower()
        ]
        st.caption(f"{len(linhas_filtradas)} linha(s) correspondente(s) a `{termo_busca}`.")
        texto_exibicao = "\n".join(linhas_filtradas) if linhas_filtradas else "Nenhuma linha encontrada para o termo informado."
    else:
        texto_exibicao = texto_secao

    st.text_area(
        "Texto Numerado ([Pxx|Lxxxx] / [Lxxxx]):",
        value=texto_exibicao,
        height=450,
    )
