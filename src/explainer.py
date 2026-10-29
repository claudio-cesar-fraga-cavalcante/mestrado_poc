"""
Camada de Explicabilidade Auditável (Neuro-Simbólica):
Combina o rastro de prova lógica do Prolog (UFO-L), os fatos extraídos do Edital,
o catálogo `regras_validador.json` e o texto oficial de `L13303.txt` para gerar
explicações jurídicas fundamentadas e auditáveis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from src.parser_edital import buscar_texto_dispositivo_legal
from src.reasoner_prolog import ResultadoInferenciaRegra


TRADUCAO_MOMENTOS_UFOL = {
    "right_to_action": "Direito a uma Ação (Right to Action / Pretensão)",
    "duty_to_act": "Dever de Agir (Duty to Act / Obrigação Positiva)",
    "right_to_omission": "Direito a uma Omissão (Right to Omission / Abstenção)",
    "duty_to_omit": "Dever de Omitir-se (Duty to Omit / Proibição)",
    "permission_to_act": "Permissão para Agir (Permission to Act / Liberdade Positiva)",
    "no_right_to_omission": "Não-Direito à Omissão (No-Right to Omission)",
    "permission_to_omit": "Permissão para Omitir-se (Permission to Omit / Liberdade de Abstenção)",
    "no_right_to_action": "Não-Direito à Ação (No-Right to Action)",
    "power": "Poder Jurídico Formativo (Power / Competência)",
    "subjection": "Sujeição Jurídica (Subjection)",
    "immunity": "Imunidade Jurídica (Immunity)",
    "disability": "Incompetência / Não-Poder (Disability)",
}

TRADUCAO_PAPEIS_UFOL = {
    "bidding_authority_role": "Estatal Licitante (bidding_authority_role)",
    "bidder_role": "Licitante / Proponente (bidder_role)",
    "contracting_party_role": "Estatal Contratante (contracting_party_role)",
    "contracted_party_role": "Empresa Contratada (contracted_party_role)",
}

TRADUCAO_RELACOES_UFOL = {
    "administrative_tender_relation": "Relação Jurídica Licitatória (administrative_tender_relation)",
    "legal_service_agreement": "Relação Contratual Administrativa (legal_service_agreement)",
}


@dataclass
class ParecerRegraEdital:
    regra_id: str
    categoria: str
    dispositivo_legal: str
    criterio_validacao: str
    classificacao_risco: str
    status_verificacao: str
    item_identificado: str
    trecho_identificado: str
    acao_recomendacao: str
    explicacao_neuro_simbolica: str
    explicacao_ontologica_ufol: str
    texto_lei_13303: str
    inferencia_bruta: ResultadoInferenciaRegra


def gerar_pareceres_edital(
    resultados_prolog: Dict[str, ResultadoInferenciaRegra],
    catalogo_regras: Dict[str, dict],
    mapa_artigos_lei: Dict[int, str],
) -> List[ParecerRegraEdital]:
    """Gera a lista de pareceres fundamentados para todas as regras avaliadas."""
    pareceres: List[ParecerRegraEdital] = []

    for r_id, inf in resultados_prolog.items():
        meta = catalogo_regras.get(r_id, {})
        categoria = meta.get("categoria", "Geral")
        dispositivo = meta.get("dispositivo_legal", inf.dispositivo_legal_ufol)
        criterio = meta.get("criterio_validacao", "")
        risco = meta.get("classificacao_risco", "Médio")
        recomendacao = meta.get("acao_recomendacao", "") or meta.get("trecho_identificado", "")

        papel_pt = TRADUCAO_PAPEIS_UFOL.get(inf.papel_afetado, inf.papel_afetado)
        relacao_pt = TRADUCAO_RELACOES_UFOL.get(inf.relacao_juridica_ufol, inf.relacao_juridica_ufol)
        mom_edital_pt = TRADUCAO_MOMENTOS_UFOL.get(inf.momento_edital, inf.momento_edital)
        mom_lei_pt = TRADUCAO_MOMENTOS_UFOL.get(inf.momento_esperado_lei, inf.momento_esperado_lei)
        mom_corr_pt = TRADUCAO_MOMENTOS_UFOL.get(inf.momento_correlato_lei, inf.momento_correlato_lei)

        texto_lei = buscar_texto_dispositivo_legal(dispositivo, mapa_artigos_lei)

        if inf.status == "Indício de Inconformidade":
            explicacao_ufol = (
                f"Na **{relacao_pt}**, a norma da Lei 13.303 ({dispositivo}) estabelece para o papel "
                f"**{papel_pt}** a posição jurídica de **{mom_lei_pt}** sobre `{inf.acao_juridica_ufol}` "
                f"(cujo correlato hohfeldiano no polo oposto é **{mom_corr_pt}**). "
                f"Contudo, a cláusula extraída do Edital ({inf.item_evidencia}) instancia a posição oposta "
                f"**{mom_edital_pt}**, configurando uma **oposição formal na ontologia UFO-L** "
                f"(`hohfeldian_opposite({inf.momento_edital}, {inf.momento_esperado_lei})`)."
            )
            explicacao_ns = _construir_explicacao_inconformidade(
                r_id, criterio, dispositivo, inf, recomendacao
            )
        else:
            explicacao_ufol = (
                f"Na **{relacao_pt}**, a posição jurídica instanciada pelo Edital ({inf.item_evidencia}) "
                f"para o papel **{papel_pt}** é **{mom_edital_pt}** sobre `{inf.acao_juridica_ufol}`, "
                f"em plena harmonia deôntica com a posição exigida pela Lei 13.303 (**{mom_lei_pt}**) e seu "
                f"correlato hohfeldiano (**{mom_corr_pt}**)."
            )
            explicacao_ns = (
                f"**Conformidade Verificada ({dispositivo}):** O edital atende ao critério de validação "
                f"(*\"{criterio}\"*). A evidência localizada em **{inf.item_evidencia}** preserva o equilíbrio "
                f"da relação jurídica na ontologia UFO-L, não havendo indício de violação normativa para esta regra."
            )

        pareceres.append(
            ParecerRegraEdital(
                regra_id=r_id,
                categoria=categoria,
                dispositivo_legal=dispositivo,
                criterio_validacao=criterio,
                classificacao_risco=risco,
                status_verificacao=inf.status,
                item_identificado=inf.item_evidencia,
                trecho_identificado=inf.trecho_evidencia,
                acao_recomendacao=recomendacao if inf.status == "Indício de Inconformidade" else "Nenhuma ação corretiva necessária (cláusula em conformidade).",
                explicacao_neuro_simbolica=explicacao_ns,
                explicacao_ontologica_ufol=explicacao_ufol,
                texto_lei_13303=texto_lei,
                inferencia_bruta=inf,
            )
        )

    return pareceres


def _construir_explicacao_inconformidade(
    r_id: str,
    criterio: str,
    dispositivo: str,
    inf: ResultadoInferenciaRegra,
    recomendacao: str,
) -> str:
    """Gera explicação detalhada em linguagem natural conectando o trecho, a lei e a prova UFO-L."""
    detalhes_especificos = {
        "R01": (
            "O edital faz menção nominal a marca/software específico como requisito obrigatório "
            "sem acrescentar a cláusula permissiva **'ou similar ou de melhor qualidade'**. "
            "Pelo Art. 47, I, 'c' da Lei 13.303/2016, quando uma marca ou produto é utilizado como referência técnica, "
            "o licitante (`bidder_role`) detém a liberdade jurídica (`permission_to_act`) de ofertar solução equivalente."
        ),
        "R02": (
            "O edital exige tecnologia/marca nominal específica sem demonstrar ou referenciar processo formal "
            "de padronização prévia ou comprovação de exclusividade técnica (Art. 47, I, 'a' e 'b' da Lei 13.303/2016). "
            "Na ontologia UFO-L, a Estatal encontra-se em posição de incompetência (`disability`) para restringir "
            "a marca sem o ato formal de padronização que lhe conferiria tal poder (`power`)."
        ),
        "R03": (
            "Foi constatada a omissão da cláusula ou anexo de **Matriz de Riscos** no instrumento convocatório/minuta contratual, "
            "descumprindo o dever legal (`duty_to_act`) imposto pelos Arts. 42, X e 69, X da Lei 13.303/2016."
        ),
        "R38": (
            "A minuta contratual omite a vedação expressa à celebração de termos aditivos decorrentes de eventos supervenientes "
            "alocados na Matriz de Riscos como de responsabilidade da contratada, violando o Art. 81, § 8º da Lei 13.303/2016."
        ),
        "R09": (
            "O instrumento convocatório/contrato é omisso quanto à autorização ou vedação de subcontratação e seus limites, "
            "descumprindo o dever de definição clara imposto pelo Art. 78 da Lei 13.303/2016."
        ),
        "R11": (
            "O edital exige apresentação de amostra ou prova de conceito de todos os licitantes já na fase de propostas iniciais, "
            "e não apenas do licitante provisoriamente classificado em primeiro lugar (Art. 47, II da Lei 13.303/2016)."
        ),
        "R29": (
            "Embora o quantitativo exigido possa respeitar o teto de 50%, o edital **proíbe sumariamente o somatório de atestados** "
            "de capacidade técnica sem apresentar justificativa técnica formal que demonstre a indivisibilidade operacional do objeto "
            "(Art. 58, II da Lei 13.303/2016 e jurisprudência consolidada do TCU). Isso restringe indevidamente a permissão jurídica (`permission_to_act`) de competição."
        ),
        "R41": (
            "O edital exige como condição de aceitação da proposta/habilitação que a licitante apresente **declaração de que faz parte da "
            "rede de revendas autorizadas pelo fabricante/provedor da solução** (ou carta de solidariedade). "
            "Essa exigência subordina a participação do licitante à vontade de um terceiro privado (o fabricante), violando o princípio da "
            "competitividade (Art. 31 da Lei 13.303/2016) e impondo um dever de agir (`duty_to_act`) diametralmente oposto à permissão de abstenção (`permission_to_omit`) assegurada pela norma."
        ),
        "R43": (
            "O edital veda expressamente a participação de empresas reunidas em **consórcio**, impondo uma incapacidade (`disability`) "
            "aos licitantes sem apresentar, no texto convocatório ou termo de referência, a justificativa técnica/econômica formal exigida "
            "pelo princípio da competitividade (Art. 31 da Lei 13.303/2016)."
        ),
    }

    corpo = detalhes_especificos.get(
        r_id,
        f"Foi detectado indício de inconformidade em relação ao critério '{criterio}' ({dispositivo}).",
    )
    return (
        f"**Por que não está conforme ({dispositivo}):** {corpo}\n\n"
        f"**Localização no Edital:** `{inf.item_evidencia}`\n\n"
        f"**Como corrigir:** {recomendacao}"
    )


def exportar_relatorio_json_validado(
    pareceres: List[ParecerRegraEdital],
    catalogo_completo: Dict[str, dict],
) -> List[dict]:
    """Retorna a lista de regras no mesmo formato de `regras_validador.json`,
    preenchendo os campos `status_verificacao`, `trecho_identificado` e `prova_ufol`."""
    mapa_pareceres = {p.regra_id: p for p in pareceres}
    saida = []
    for r_id, regra_orig in catalogo_completo.items():
        copia = dict(regra_orig)
        if r_id in mapa_pareceres:
            p = mapa_pareceres[r_id]
            copia["se_aplica"] = "Sim"
            copia["status_verificacao"] = p.status_verificacao
            copia["item_identificado"] = p.item_identificado
            copia["trecho_identificado"] = p.trecho_identificado
            copia["acao_recomendacao"] = p.acao_recomendacao
            copia["prova_ontologica_ufol"] = {
                "relacao_juridica": p.inferencia_bruta.relacao_juridica_ufol,
                "papel_afetado": p.inferencia_bruta.papel_afetado,
                "momento_instanciado_edital": p.inferencia_bruta.momento_edital,
                "momento_esperado_lei": p.inferencia_bruta.momento_esperado_lei,
                "momento_correlato_lei": p.inferencia_bruta.momento_correlato_lei,
                "inferencia_prolog": p.inferencia_bruta.tipo_inferencia_ufol,
                "passos_sld": p.inferencia_bruta.passos_prova_prolog,
            }
            copia["explicacao_fundamentada"] = p.explicacao_neuro_simbolica
        saida.append(copia)
    return saida

