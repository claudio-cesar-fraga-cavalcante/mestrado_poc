"""Aba 5: Laboratório What-If (Perturbação Direta da ABox + SWI-Prolog)."""

from __future__ import annotations

from typing import Callable, List

import pandas as pd
import streamlit as st

from src.explainer import ParecerRegraEdital, gerar_pareceres_edital
from src.extractor_llm import (
    FatosExtraidosEdital,
    MencaoMarcaFato,
    converter_fatos_para_prolog,
)
from src.parser_edital import EditalSegmentado
from src.ui.components import render_kpi_strip, render_section_header

_LABELS_CONTEXTO_MARCA = {
    "objeto_licitado": "Objeto licitado",
    "interoperabilidade_ambiente_legado": "Interoperabilidade com ambiente legado",
    "manutencao_parque_existente": "Manutenção de parque existente",
    "referencia_exemplificativa": "Referência exemplificativa",
}

_LABELS_ESCOPO_AMOSTRA = {
    "nao_exigida": "Não exigida",
    "apenas_primeiro_colocado": "Apenas 1º colocado",
    "todos_licitantes_fase_proposta": "Todos os licitantes na fase de proposta",
}


def _destacar_mudanca_linha(row: pd.Series) -> List[str]:
    if row.get("Mudou?") == "Sim":
        return ["background-color: #F5F3FF; color: #5B21B6; font-weight: 600;"] * len(row)
    return [""] * len(row)


def render_tab_whatif(
    edital_seg: EditalSegmentado,
    fatos: FatosExtraidosEdital,
    pareceres: List[ParecerRegraEdital],
    regras_selecionadas: List[str],
    inicializar_recursos_fn: Callable,
) -> None:
    """Renderiza o laboratório What-If com controles M3 (toggles e Outlined Cards)."""
    render_section_header(
        titulo="Laboratório What-If: Perturbação Direta da ABox",
        subtitulo=(
            f"Carrega os fatos reais extraídos de {edital_seg.nome_arquivo}. "
            "Altere qualquer premissa factual e observe o SWI-Prolog / UFO-L recalcular os vereditos."
        ),
        overline="SIMULAÇÃO SIMBÓLICA",
    )

    fatos_wi = fatos.model_copy(deep=True)
    key_prefix = f"wi_{edital_seg.nome_arquivo}"

    with st.form(key=f"form_whatif_{key_prefix}"):
        with st.container(border=True):
            render_section_header(
                titulo="1. Especificação de Marcas (R01 e R02)",
                subtitulo="Controle de menções nominais, similaridade e padronização formal.",
            )
            novas_marcas: List[MencaoMarcaFato] = []
            if fatos_wi.mencoes_marca:
                opcoes_ctx = list(_LABELS_CONTEXTO_MARCA.keys())
                for idx_m, m_orig in enumerate(fatos_wi.mencoes_marca):
                    cm1, cm2, cm3, cm4 = st.columns([2.0, 1.9, 1.05, 1.05], vertical_alignment="center")
                    cm1.markdown(f"**{m_orig.marca_ou_produto}**  \n_{m_orig.item_edital}_")
                    idx_ctx = opcoes_ctx.index(m_orig.contexto_mencao) if m_orig.contexto_mencao in opcoes_ctx else 0
                    ctx_val = cm2.selectbox(
                        "Contexto da menção",
                        options=opcoes_ctx,
                        index=idx_ctx,
                        format_func=lambda k: _LABELS_CONTEXTO_MARCA.get(k, k),
                        key=f"{key_prefix}_ctx_{idx_m}",
                    )
                    sim_val = cm3.toggle(
                        "Cláusula 'ou similar'",
                        value=m_orig.possui_clausula_similaridade,
                        key=f"{key_prefix}_sim_{idx_m}",
                    )
                    pad_val = cm4.toggle(
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

            incluir_marca_teste = st.toggle(
                "Injetar marca proprietária hipotética sem 'ou similar' (para testar R01/R02)",
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

        with st.container(border=True):
            render_section_header(
                titulo="2. Habilitação, Amostras e Participação (R11, R29, R41, R43)",
                subtitulo="Requisitos de qualificação técnica, amostras e restrições à competitividade.",
            )
            cw1, cw2 = st.columns(2, gap="large")
            with cw1:
                pct_atestado_wi = st.number_input(
                    "Percentual mínimo exigido em atestado (R29)",
                    min_value=0,
                    max_value=100,
                    value=int(fatos_wi.percentual_minimo_atestado),
                    step=5,
                    key=f"{key_prefix}_pct",
                )
                veda_som_wi = st.toggle(
                    "Veda somatório de atestados (R29)",
                    value=fatos_wi.veda_somatorio_atestados,
                    key=f"{key_prefix}_vedasom",
                )
                just_som_wi = st.toggle(
                    "Possui justificativa técnica para vedar somatório (R29)",
                    value=fatos_wi.possui_justificativa_vedacao_somatorio,
                    key=f"{key_prefix}_justsom",
                )
                exige_cred_wi = st.toggle(
                    "Exige credenciamento / carta do fabricante (R41)",
                    value=fatos_wi.exige_credenciamento_ou_carta_fabricante,
                    key=f"{key_prefix}_cred",
                )

            with cw2:
                opcoes_amostra = list(_LABELS_ESCOPO_AMOSTRA.keys())
                idx_amo = (
                    opcoes_amostra.index(fatos_wi.escopo_exigencia_amostra)
                    if fatos_wi.escopo_exigencia_amostra in opcoes_amostra
                    else 0
                )
                amostra_wi = st.selectbox(
                    "Escopo de exigência de amostra (R11)",
                    options=opcoes_amostra,
                    index=idx_amo,
                    format_func=lambda k: _LABELS_ESCOPO_AMOSTRA.get(k, k),
                    key=f"{key_prefix}_amostra",
                )
                veda_cons_wi = st.toggle(
                    "Veda participação em consórcio (R43)",
                    value=fatos_wi.veda_participacao_consorcio,
                    key=f"{key_prefix}_cons",
                )
                just_cons_wi = st.toggle(
                    "Possui justificativa formal para vedar consórcio (R43)",
                    value=fatos_wi.possui_justificativa_vedacao_consorcio,
                    key=f"{key_prefix}_justcons",
                )

        with st.container(border=True):
            render_section_header(
                titulo="3. Cláusulas Contratuais e Gestão de Riscos (R03, R09, R38)",
                subtitulo="Elementos obrigatórios da minuta de contrato e matriz de alocação de riscos.",
            )
            cc1, cc2, cc3 = st.columns(3)
            mr_wi = cc1.toggle(
                "Matriz de Riscos presente (R03)",
                value=fatos_wi.matriz_riscos_presente,
                key=f"{key_prefix}_mr",
            )
            vad_wi = cc2.toggle(
                "Vedação a aditivos de risco (R38)",
                value=fatos_wi.vedacao_aditivo_risco_presente,
                key=f"{key_prefix}_vad",
            )
            sub_wi = cc3.toggle(
                "Subcontratação definida (R09)",
                value=fatos_wi.subcontratacao_definida,
                key=f"{key_prefix}_sub",
            )

        submeteu_wi = st.form_submit_button(
            "Recalcular ABox no Prolog",
            type="primary",
            icon=":material/play_arrow:",
        )

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
        catalogo_res, artigos_res, avaliador_res = inicializar_recursos_fn()
        res_pl_wi, _, motor_wi = avaliador_res.executar_avaliacao(
            edital_id=fatos_wi.identificador_edital,
            abox_prolog=abox_wi,
            regras_selecionadas=regras_selecionadas,
        )
        pareceres_wi = gerar_pareceres_edital(res_pl_wi, catalogo_res, artigos_res)
        inc_wi = [p for p in pareceres_wi if p.status_verificacao == "Indício de Inconformidade"]
        conf_wi = len(pareceres_wi) - len(inc_wi)

        mapa_antes = {p.regra_id: p.status_verificacao for p in pareceres}
        qtd_mudancas = sum(
            1 for p in pareceres_wi if mapa_antes.get(p.regra_id) != p.status_verificacao
        )

        render_section_header(
            titulo="Resultado Pós-Perturbação da ABox",
            subtitulo=f"Motor executado: {motor_wi}",
            overline="SAÍDA SIMBÓLICA",
        )
        render_kpi_strip(
            [
                {
                    "label": "Regras Conformes",
                    "value": str(conf_wi),
                    "detail": f"de {len(pareceres_wi)} avaliadas",
                    "tone": "success",
                },
                {
                    "label": "Inconformidades",
                    "value": str(len(inc_wi)),
                    "detail": "após perturbação",
                    "tone": "error" if inc_wi else "success",
                },
                {
                    "label": "Regras Alteradas",
                    "value": str(qtd_mudancas),
                    "detail": "mudanças de veredito",
                    "tone": "divergence" if qtd_mudancas else "neutral",
                },
                {
                    "label": "Motor Ativo",
                    "value": "Prolog",
                    "detail": motor_wi,
                    "tone": "neutral",
                },
            ]
        )

        df_wi = pd.DataFrame(
            [
                {
                    "Regra": p.regra_id,
                    "Categoria": p.categoria,
                    "Status Original": mapa_antes.get(p.regra_id, "-"),
                    "Status Pós-Edição": p.status_verificacao,
                    "Mudou?": "Sim" if mapa_antes.get(p.regra_id) != p.status_verificacao else "—",
                    "Momento no Edital": p.inferencia_bruta.momento_edital,
                    "Momento na Lei": p.inferencia_bruta.momento_esperado_lei,
                    "Inferência Prolog": p.inferencia_bruta.tipo_inferencia_ufol,
                }
                for p in pareceres_wi
            ]
        )
        st.dataframe(
            df_wi.style.apply(_destacar_mudanca_linha, axis=1),
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Ver Nova ABox Prolog Gerada (fatos positivos)", icon=":material/code:"):
            st.code(abox_wi, language="prolog")
