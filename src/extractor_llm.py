"""
Camada Neural (Instanciação Ontológica):
Extrai fatos observáveis do texto do Edital (.txt) usando Google Gemini (Structured Outputs)
ou Modo Demonstração / Analisador Local, e converte para fatos Prolog (ABox da UFO-L).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field


class MencaoMarcaFato(BaseModel):
    marca_ou_produto: str = Field(
        description="Nome da marca, fabricante ou produto específico mencionado como requisito técnico."
    )
    contexto_mencao: Literal[
        "objeto_licitado",
        "interoperabilidade_ambiente_legado",
        "manutencao_parque_existente",
        "referencia_exemplificativa",
    ] = Field(
        default="objeto_licitado",
        description=(
            "Papel da menção à marca/produto no edital: "
            "'objeto_licitado' quando define o próprio bem/software/serviço a ser fornecido/contratado; "
            "'interoperabilidade_ambiente_legado' quando se refere apenas a sistemas/infraestrutura já existentes no órgão com os quais o objeto novo deve se integrar; "
            "'manutencao_parque_existente' quando o objeto da licitação é suporte técnico, manutenção, garantia ou atualização de ativo proprietário já pertencente ao órgão; "
            "'referencia_exemplificativa' quando aparece apenas como exemplo ilustrativo ('ex.: ...') ou descrição informativa do ambiente atual."
        ),
    )
    possui_clausula_similaridade: bool = Field(
        description="True se acompanhado de 'ou similar', 'ou equivalente', 'ou de melhor qualidade' ou usado apenas como exemplo ('ex.:')."
    )
    possui_justificativa_padronizacao: bool = Field(
        description="True se o edital mencionar expressamente processo formal de padronização ou exclusividade técnica aprovada."
    )
    item_edital: str = Field(description="Referência do item e número da linha no edital (ex: 'Anexo I, Item 5 (Linha 294)').")
    trecho_literal: str = Field(description="Citação literal do trecho do edital onde a marca/produto aparece.")


class FatosExtraidosEdital(BaseModel):
    """Contrato estruturado (Pydantic) entre a Camada Neural (Gemini) e a Camada Simbólica (SWI-Prolog + UFO-L)."""

    identificador_edital: str = Field(description="Identificador curto em snake_case do edital (ex: pe_29_2026).")
    resumo_objeto: str = Field(description="Resumo conciso do objeto da licitação.")

    # R01 e R02 - Direcionamento de Marca
    mencoes_marca: List[MencaoMarcaFato] = Field(
        default_factory=list,
        description="Lista de menções a marcas, fabricantes ou softwares proprietários nas especificações técnicas.",
    )

    # R03 e R38 - Matriz de Riscos e Vedação de Aditivos por Riscos Alocados
    matriz_riscos_presente: bool = Field(
        description="True se o edital/minuta de contrato contiver cláusula ou anexo de Matriz de Riscos."
    )
    matriz_riscos_item: str = Field(description="Item/Cláusula e linha onde consta a Matriz de Riscos (ou onde deveria constar).")
    matriz_riscos_trecho: str = Field(description="Trecho literal sobre a Matriz de Riscos ou indicação de omissão.")

    vedacao_aditivo_risco_presente: bool = Field(
        description="True se houver cláusula vedando celebração de aditivos decorrentes de eventos supervenientes alocados como risco da contratada."
    )
    vedacao_aditivo_risco_item: str = Field(description="Item/Cláusula e linha sobre vedação de aditivos da Matriz de Riscos.")
    vedacao_aditivo_risco_trecho: str = Field(description="Trecho literal sobre vedação de aditivos por riscos alocados.")

    # R09 - Subcontratação
    subcontratacao_definida: bool = Field(
        description="True se o edital/contrato definir expressamente se é permitida (com limites) ou vedada a subcontratação."
    )
    subcontratacao_item: str = Field(description="Item/Cláusula e linha que trata da subcontratação.")
    subcontratacao_trecho: str = Field(description="Trecho literal sobre subcontratação ou indicação de omissão.")

    # R11 - Amostra / Prova de Conceito
    escopo_exigencia_amostra: Literal[
        "apenas_primeiro_colocado", "todos_licitantes_fase_proposta", "nao_exigida"
    ] = Field(
        description="Momento/escopo de exigência de amostra: 'apenas_primeiro_colocado', 'todos_licitantes_fase_proposta' ou 'nao_exigida'."
    )
    amostra_item: str = Field(description="Item e linha do edital que disciplina a amostra/PoC.")
    amostra_trecho: str = Field(description="Trecho literal sobre exigência de amostra.")

    # R29 - Qualificação Técnica (Quantitativo de Atestado e Somatório)
    percentual_minimo_atestado: int = Field(
        description="Percentual mínimo exigido nos atestados de capacidade técnica em relação ao total do objeto (0 se não exigir percentual)."
    )
    veda_somatorio_atestados: bool = Field(
        description="True se o edital proibir o somatório de quantitativos em diferentes atestados de capacidade técnica."
    )
    possui_justificativa_vedacao_somatorio: bool = Field(
        description="True se houver justificativa técnica expressa no edital demonstrando por que o somatório de atestados é inviável."
    )
    atestado_item: str = Field(description="Item e linha do edital sobre atestados de capacidade técnica.")
    atestado_trecho: str = Field(description="Trecho literal sobre percentual e somatório de atestados.")

    # R41 - Credenciamento / Revenda Autorizada / Carta de Solidariedade do Fabricante
    exige_credenciamento_ou_carta_fabricante: bool = Field(
        description=(
            "True SOMENTE se exigir que a licitante declare fazer parte de rede de revendas autorizadas/parceiro "
            "credenciado pelo fabricante ou apresente carta de solidariedade/anuência emitida pelo fabricante. "
            "Marque False se for apenas compromisso próprio da licitante de prestar ou contratar a garantia do produto "
            "sem exigir credenciamento prévio ou carta do fabricante."
        )
    )
    credenciamento_item: str = Field(description="Item e linha onde consta a exigência de credenciamento/carta do fabricante.")
    credenciamento_trecho: str = Field(description="Trecho literal sobre exigência de revenda autorizada/carta do fabricante.")

    # R43 - Participação em Consórcio
    veda_participacao_consorcio: bool = Field(
        description="True se o edital impedir a participação de empresas reunidas em consórcio."
    )
    possui_justificativa_vedacao_consorcio: bool = Field(
        description="True se o edital apresentar justificativa técnica/mercadológica formal para a proibição de consórcio."
    )
    consorcio_item: str = Field(description="Item e linha que trata da participação de consórcio.")
    consorcio_trecho: str = Field(description="Trecho literal sobre participação de consórcio.")


def sanitizar_atom_prolog(texto: str) -> str:
    """Escapa aspas simples para uso seguro em átomos/strings do SWI-Prolog."""
    if not texto:
        return "''"
    limpo = texto.replace("\\", "/").replace("'", "\\'").replace("\r", " ").replace("\n", " ").strip()
    return f"'{limpo}'"


def converter_fatos_para_prolog(fatos: FatosExtraidosEdital) -> str:
    """
    Converte o objeto FatosExtraidosEdital (saída da Camada Neural) em cláusulas Prolog (ABox UFO-L).
    Emite apenas fatos positivos observados no documento para que o motor Prolog infira omissões
    genuinamente sob a Hipótese do Mundo Fechado via Negação por Falha (\\+).
    """
    edital_id = re.sub(r"[^a-z0-9_]", "_", fatos.identificador_edital.lower()).strip("_") or "edital_analisado"
    linhas_pl = [
        "% ==============================================================================",
        f"% Fatos Positivos Extraídos do Edital (ABox UFO-L) - Instância: {edital_id}",
        "% (Ausência de fato é tratada via Closed-World Assumption / NAF '\\+')",
        "% ==============================================================================",
        f"edital_instancia({edital_id}).",
        "",
        "% --- R01 & R02: Menções de Marca / Produto Específico ---",
    ]

    marcas_restritivas = []
    for m in fatos.mencoes_marca:
        sim_atom = "com_clausula_similaridade" if m.possui_clausula_similaridade else "sem_clausula_similaridade"
        pad_atom = "com_justificativa_padronizacao" if m.possui_justificativa_padronizacao else "sem_justificativa_padronizacao"
        ctx_atom = m.contexto_mencao
        linhas_pl.append(
            f"mencao_marca_exigida({edital_id}, {sanitizar_atom_prolog(m.marca_ou_produto)}, "
            f"{ctx_atom}, {sim_atom}, {pad_atom}, {sanitizar_atom_prolog(m.item_edital)}, {sanitizar_atom_prolog(m.trecho_literal)})."
        )
        if m.contexto_mencao == "objeto_licitado" and not m.possui_clausula_similaridade and not m.possui_justificativa_padronizacao:
            marcas_restritivas.append(m)

    if marcas_restritivas:
        itens_agg = " | ".join(dict.fromkeys(m.item_edital for m in marcas_restritivas))
        trechos_agg = "\n".join(dict.fromkeys(f"[{m.marca_ou_produto}] {m.trecho_literal}" for m in marcas_restritivas))
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R01', {sanitizar_atom_prolog(itens_agg)}, {sanitizar_atom_prolog(trechos_agg)})."
        )
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R02', {sanitizar_atom_prolog(itens_agg)}, {sanitizar_atom_prolog(trechos_agg)})."
        )
    elif fatos.mencoes_marca:
        itens_agg = " | ".join(dict.fromkeys(m.item_edital for m in fatos.mencoes_marca))
        trechos_agg = "\n".join(dict.fromkeys(f"[{m.marca_ou_produto} | {m.contexto_mencao}] {m.trecho_literal}" for m in fatos.mencoes_marca))
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R01', {sanitizar_atom_prolog(itens_agg)}, {sanitizar_atom_prolog(trechos_agg)})."
        )
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R02', {sanitizar_atom_prolog(itens_agg)}, {sanitizar_atom_prolog(trechos_agg)})."
        )
    else:
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R01', 'Especificações Técnicas', 'Nenhuma marca restritiva sem cláusula de similaridade identificada.')."
        )
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R02', 'Especificações Técnicas', 'Nenhuma indicação exclusiva de marca sem padronização identificada.')."
        )

    # R03 - Matriz de Riscos (fato emitido SOMENTE se presente)
    linhas_pl.extend(["", "% --- R03 & R38: Matriz de Riscos e Vedação de Aditivos ---"])
    if fatos.matriz_riscos_presente:
        linhas_pl.append(
            f"fato_matriz_riscos({edital_id}, {sanitizar_atom_prolog(fatos.matriz_riscos_item)}, {sanitizar_atom_prolog(fatos.matriz_riscos_trecho)})."
        )
    else:
        linhas_pl.append("% fato_matriz_riscos omitido -> NAF (\\+) detectará violação em R03")
    linhas_pl.append(
        f"evidencia_regra({edital_id}, 'R03', {sanitizar_atom_prolog(fatos.matriz_riscos_item)}, {sanitizar_atom_prolog(fatos.matriz_riscos_trecho)})."
    )

    # R38 - Vedação de Aditivo por Risco Alocado (fato emitido SOMENTE se presente)
    if fatos.vedacao_aditivo_risco_presente:
        linhas_pl.append(
            f"fato_vedacao_aditivo_risco({edital_id}, {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_item)}, {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_trecho)})."
        )
    else:
        linhas_pl.append("% fato_vedacao_aditivo_risco omitido -> NAF (\\+) detectará violação em R38")
    linhas_pl.append(
        f"evidencia_regra({edital_id}, 'R38', {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_item)}, {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_trecho)})."
    )

    # R09 - Subcontratação (fato emitido SOMENTE se definida expressamente)
    linhas_pl.extend(["", "% --- R09: Regra de Subcontratação ---"])
    if fatos.subcontratacao_definida:
        linhas_pl.append(
            f"fato_subcontratacao_definida({edital_id}, {sanitizar_atom_prolog(fatos.subcontratacao_item)}, {sanitizar_atom_prolog(fatos.subcontratacao_trecho)})."
        )
    else:
        linhas_pl.append("% fato_subcontratacao_definida omitido -> NAF (\\+) detectará omissão em R09")
    linhas_pl.append(
        f"evidencia_regra({edital_id}, 'R09', {sanitizar_atom_prolog(fatos.subcontratacao_item)}, {sanitizar_atom_prolog(fatos.subcontratacao_trecho)})."
    )

    # R11 - Amostra
    linhas_pl.extend([
        "",
        "% --- R11: Exigência de Amostra / PoC ---",
        f"fato_amostra({edital_id}, {fatos.escopo_exigencia_amostra}, {sanitizar_atom_prolog(fatos.amostra_item)}, {sanitizar_atom_prolog(fatos.amostra_trecho)}).",
        f"evidencia_regra({edital_id}, 'R11', {sanitizar_atom_prolog(fatos.amostra_item)}, {sanitizar_atom_prolog(fatos.amostra_trecho)}).",
    ])

    # R29 - Atestado de Capacidade Técnica e Somatório
    linhas_pl.extend([
        "",
        "% --- R29: Qualificação Técnica (Quantitativo e Somatório de Atestados) ---",
        f"fato_atestado_percentual({edital_id}, {fatos.percentual_minimo_atestado}, {sanitizar_atom_prolog(fatos.atestado_item)}, {sanitizar_atom_prolog(fatos.atestado_trecho)}).",
    ])
    if fatos.veda_somatorio_atestados:
        linhas_pl.append(
            f"fato_veda_somatorio({edital_id}, {sanitizar_atom_prolog(fatos.atestado_item)}, {sanitizar_atom_prolog(fatos.atestado_trecho)})."
        )
    if fatos.possui_justificativa_vedacao_somatorio:
        linhas_pl.append(
            f"fato_justificativa_vedacao_somatorio({edital_id}, {sanitizar_atom_prolog(fatos.atestado_item)}, {sanitizar_atom_prolog(fatos.atestado_trecho)})."
        )
    linhas_pl.append(
        f"evidencia_regra({edital_id}, 'R29', {sanitizar_atom_prolog(fatos.atestado_item)}, {sanitizar_atom_prolog(fatos.atestado_trecho)})."
    )

    # R41 - Credenciamento / Carta do Fabricante (emitido SOMENTE se exigido)
    linhas_pl.extend(["", "% --- R41: Credenciamento / Revenda Autorizada do Fabricante ---"])
    if fatos.exige_credenciamento_ou_carta_fabricante:
        linhas_pl.append(
            f"fato_credenciamento_exigido({edital_id}, {sanitizar_atom_prolog(fatos.credenciamento_item)}, {sanitizar_atom_prolog(fatos.credenciamento_trecho)})."
        )
    else:
        linhas_pl.append("% fato_credenciamento_exigido ausente -> NAF (\\+) confirmará conformidade em R41")
    linhas_pl.append(
        f"evidencia_regra({edital_id}, 'R41', {sanitizar_atom_prolog(fatos.credenciamento_item)}, {sanitizar_atom_prolog(fatos.credenciamento_trecho)})."
    )

    # R43 - Consórcio (vedação e justificativa emitidas apenas se presentes)
    linhas_pl.extend(["", "% --- R43: Participação em Consórcio ---"])
    if fatos.veda_participacao_consorcio:
        linhas_pl.append(
            f"fato_veda_consorcio({edital_id}, {sanitizar_atom_prolog(fatos.consorcio_item)}, {sanitizar_atom_prolog(fatos.consorcio_trecho)})."
        )
    if fatos.possui_justificativa_vedacao_consorcio:
        linhas_pl.append(
            f"fato_justificativa_vedacao_consorcio({edital_id}, {sanitizar_atom_prolog(fatos.consorcio_item)}, {sanitizar_atom_prolog(fatos.consorcio_trecho)})."
        )
    linhas_pl.append(
        f"evidencia_regra({edital_id}, 'R43', {sanitizar_atom_prolog(fatos.consorcio_item)}, {sanitizar_atom_prolog(fatos.consorcio_trecho)})."
    )

    return "\n".join(linhas_pl)


def obter_fatos_demo_pe_29_2026() -> FatosExtraidosEdital:
    """Retorna os fatos auditados do Edital_PE_29-2026.txt (BNDES - Contratação DaaS) para o Modo Demonstração."""
    return FatosExtraidosEdital(
        identificador_edital="pe_29_2026",
        resumo_objeto=(
            "Pregão Eletrônico nº 29/2026 - BNDES: Contratação de até 246 estações de trabalho virtuais em nuvem "
            "(Desktop as a Service - DaaS), incluindo infraestrutura de rede, implantação, suporte e gerenciamento."
        ),
        mencoes_marca=[
            MencaoMarcaFato(
                marca_ou_produto="Windows 11 Professional / Microsoft 365 E5 / Active Directory / Microsoft Entra ID",
                contexto_mencao="objeto_licitado",
                possui_clausula_similaridade=False,
                possui_justificativa_padronizacao=False,
                item_edital="Anexo I, Itens 5, 18, 20 e 78 (Linhas 294, 334, 340 e 488)",
                trecho_literal=(
                    "[L0294] Sistema operacional Windows 11 Professional | "
                    "[L0340] 20. A solução deve possibilitar o provisionamento de estações virtuais com ingresso ao Active Directory do BNDES | "
                    "[L0488] 78. A solução deve permitir a utilização de autenticação e autorização federadas, integradas com o repositório corporativo de credenciais de acesso da contratante (Microsoft Entra ID)"
                ),
            ),
            MencaoMarcaFato(
                marca_ou_produto="Yubikey (Chave USB 2FA)",
                contexto_mencao="referencia_exemplificativa",
                possui_clausula_similaridade=True,
                possui_justificativa_padronizacao=False,
                item_edital="Anexo I, Item 49.f (Linha 409)",
                trecho_literal="[L0409] f. Chave de segurança USB / 2FA resistente a fishing (ex.: yubikey);",
            ),
        ],
        matriz_riscos_presente=True,
        matriz_riscos_item="Minuta de Contrato, Cláusula Nona e Anexo III (Linhas 841-843 e 1095)",
        matriz_riscos_trecho=(
            "[L0841] CLÁUSULA NONA – MATRIZ DE RISCOS: O BNDES e o CONTRATADO, tendo como premissa a obtenção do melhor custo contratual "
            "mediante a alocação do risco à parte com maior capacidade para geri-lo e absorvê-lo, identificam os riscos decorrentes da relação contratual "
            "e, sem prejuízo de outras previsões contratuais, estabelecem os respectivos responsáveis na Matriz de Riscos constante do Anexo III deste Contrato."
        ),
        vedacao_aditivo_risco_presente=True,
        vedacao_aditivo_risco_item="Minuta de Contrato, Cláusula Nona, Parágrafo Segundo (Linha 848)",
        vedacao_aditivo_risco_trecho=(
            "[L0848] É vedada a celebração de aditivos decorrentes de eventos supervenientes alocados, na Matriz de Riscos, como de responsabilidade do CONTRATADO."
        ),
        subcontratacao_definida=True,
        subcontratacao_item="Minuta de Contrato, Cláusula Décima Sétima, Parágrafo Terceiro (Linha 1018)",
        subcontratacao_trecho="[L1018] Parágrafo Terceiro: É vedada a subcontratação para a execução do objeto deste Contrato.",
        escopo_exigencia_amostra="apenas_primeiro_colocado",
        amostra_item="Corpo do Edital, Item 4.11.4 (Linha 140) e Anexo I, Item 119 (Linha 639)",
        amostra_trecho=(
            "[L0140] 4.11.4 Verificado o atendimento dos requisitos de habilitação do licitante, o Pregoeiro suspenderá a sessão pública para a apresentação de amostra, "
            "observadas as condições e o procedimento descrito no item 119 do Anexo I (Termo de Referência) deste Edital."
        ),
        percentual_minimo_atestado=50,
        veda_somatorio_atestados=True,
        possui_justificativa_vedacao_somatorio=False,
        atestado_item="Anexo I, Itens 116 e 117 (Linhas 628-630)",
        atestado_trecho=(
            "[L0628] 116. Atestado de Capacidade Técnica, emitido por pessoa jurídica de direito público ou privado, que comprove que a Licitante forneceu estações virtuais, "
            "em quantidade igual ou superior a 50% (cinquenta por cento) da quantidade total prevista para esta contratação, por período não inferior a 12 (doze) meses. "
            "[L0630] 117. Não será aceito o somatório da quantidade de estações virtuais disponibilizadas em diferentes atestados de capacidade técnica."
        ),
        exige_credenciamento_ou_carta_fabricante=True,
        credenciamento_item="Anexo I, Item 114.c (Linha 624)",
        credenciamento_trecho=(
            "[L0621] 114. Serão exigidos, para aceitação da proposta, os seguintes requisitos: ... "
            "[L0624] c. Declaração de que faz parte da rede de revendas autorizadas pelo provedor da solução para comercialização dos serviços ofertados."
        ),
        veda_participacao_consorcio=True,
        possui_justificativa_vedacao_consorcio=False,
        consorcio_item="Corpo do Edital, Item 2.3, VIII (Linhas 15 e 23)",
        consorcio_trecho="[L0015] 2.3 Estará impedido de participar deste Pregão o interessado que: ... [L0023] VIII. esteja organizado sob a forma de consórcio.",
    )


def extrair_fatos_heuristico_texto(texto_numerado: str, nome_arquivo: str = "edital_customizado.txt") -> FatosExtraidosEdital:
    """
    Analisador semântico-heurístico local que inspeciona o texto numerado (.txt)
    para atualizar dinamicamente os fatos quando o usuário edita cláusulas no Laboratório What-If
    ou carrega outro arquivo .txt em Modo Demonstração (sem precisar de chave de API).
    """
    base = obter_fatos_demo_pe_29_2026()
    edital_id = re.sub(r"[^a-z0-9_]", "_", os.path.splitext(nome_arquivo)[0].lower()).strip("_") or "edital_custom"
    base.identificador_edital = edital_id

    linhas = texto_numerado.splitlines()

    def buscar_linha(padrao: str) -> Optional[str]:
        rx = re.compile(padrao, re.IGNORECASE)
        for l in linhas:
            if rx.search(l):
                return l.strip()
        return None

    # 1. Verificar R01 / R02 (Marca Windows 11 / Switch Catalyst / similaridade / padronização)
    linha_win = buscar_linha(r"Windows\s+11|Catalyst\s+9300|marca\s+exclusiva")
    if linha_win:
        tem_similar = bool(re.search(r"ou\s+similar|ou\s+equivalente|ou\s+de\s+melhor\s+qualidade", texto_numerado, re.IGNORECASE))
        tem_padronizacao = bool(re.search(r"processo\s+de\s+padroniza[çc][ãa]o|estudo\s+t[ée]cnico\s+de\s+padroniza[çc][ãa]o|justificativa\s+de\s+padroniza[çc][ãa]o", texto_numerado, re.IGNORECASE))
        base.mencoes_marca = [
            MencaoMarcaFato(
                marca_ou_produto="Marca/Produto Nominal Identificado nas Especificações",
                contexto_mencao="objeto_licitado",
                possui_clausula_similaridade=tem_similar,
                possui_justificativa_padronizacao=tem_padronizacao,
                item_edital="Especificações Técnicas",
                trecho_literal=linha_win,
            )
        ]
    else:
        base.mencoes_marca = []

    # 2. Verificar R41 (Revenda autorizada / carta de solidariedade / credenciamento do fabricante)
    linha_cred = buscar_linha(r"revendas?\s+autorizadas?|carta\s+de\s+solidariedade|parceiro\s+(?:gold|platinum|exclusivo)|credenciamento.*fabricante")
    if linha_cred and not re.search(r"n[ãa]o\s+ser[áa]\s+exigid[ao].*(?:revenda|carta|credenciamento)", linha_cred, re.IGNORECASE):
        base.exige_credenciamento_ou_carta_fabricante = True
        base.credenciamento_item = "Requisitos de Proposta / Habilitação"
        base.credenciamento_trecho = linha_cred
    else:
        base.exige_credenciamento_ou_carta_fabricante = False
        base.credenciamento_item = "Requisitos de Proposta / Habilitação"
        base.credenciamento_trecho = "Ausência de exigência de carta de solidariedade ou declaração de revenda autorizada do fabricante."

    # 3. Verificar R43 (Consórcio e justificativa)
    linha_cons_vedado = buscar_linha(r"impedido.*cons[óo]rcio|vedad[ao].*participa[çc][ãa]o.*cons[óo]rcio|esteja\s+organizado\s+sob\s+a\s+forma\s+de\s+cons[óo]rcio")
    linha_cons_just = buscar_linha(r"justifica-se\s+a\s+veda[çc][ãa]o\s+de\s+cons[óo]rcio|justificativa.*cons[óo]rcio|estudo\s+t[ée]cnico.*cons[óo]rcio")
    if linha_cons_vedado:
        base.veda_participacao_consorcio = True
        base.possui_justificativa_vedacao_consorcio = bool(linha_cons_just)
        base.consorcio_item = "Condições de Participação"
        base.consorcio_trecho = linha_cons_vedado + (f" | {linha_cons_just}" if linha_cons_just else "")
    else:
        base.veda_participacao_consorcio = False
        base.possui_justificativa_vedacao_consorcio = True
        base.consorcio_item = "Condições de Participação"
        base.consorcio_trecho = buscar_linha(r"cons[óo]rcio") or "Participação em consórcio permitida ou sem vedação restritiva."

    # 4. Verificar R29 (Atestado % e somatório)
    linha_atestado_pct = buscar_linha(r"quantidade\s+igual\s+ou\s+superior\s+a\s+\d+\s*%")
    pct = 50
    if linha_atestado_pct:
        m_pct = re.search(r"(\d+)\s*%", linha_atestado_pct)
        if m_pct:
            pct = int(m_pct.group(1))
    linha_veda_som = buscar_linha(r"n[ãa]o\s+ser[áa]\s+aceito\s+o\s+somat[óo]rio|vedado\s+o\s+somat[óo]rio\s+de\s+atestados")
    linha_just_som = buscar_linha(r"justifica-se\s+a\s+veda[çc][ãa]o\s+ao\s+somat[óo]rio|complexidade\s+indivis[íi]vel\s+que\s+impede\s+o\s+somat[óo]rio")
    base.percentual_minimo_atestado = pct
    base.veda_somatorio_atestados = bool(linha_veda_som)
    base.possui_justificativa_vedacao_somatorio = bool(linha_just_som)
    if linha_atestado_pct or linha_veda_som:
        base.atestado_item = "Habilitação Técnica / Atestados"
        base.atestado_trecho = " ".join(x for x in [linha_atestado_pct, linha_veda_som, linha_just_som] if x)

    # 5. Verificar R03 e R38 (Matriz de Riscos e Vedação de Aditivos)
    linha_mr = buscar_linha(r"MATRIZ\s+DE\s+RISCOS")
    base.matriz_riscos_presente = bool(linha_mr)
    base.matriz_riscos_item = "Minuta de Contrato / Anexo IV" if linha_mr else "Minuta de Contrato (Omissão)"
    base.matriz_riscos_trecho = linha_mr or "Omissão: Não foi localizada cláusula ou seção de Matriz de Riscos no edital/contrato."

    linha_vad = buscar_linha(r"vedada\s+a\s+celebra[çc][ãa]o\s+de\s+aditivos\s+decorrentes\s+de\s+eventos\s+supervenientes\s+alocados")
    base.vedacao_aditivo_risco_presente = bool(linha_vad)
    base.vedacao_aditivo_risco_item = "Minuta de Contrato (Cláusula de Riscos)" if linha_vad else "Minuta de Contrato (Omissão)"
    base.vedacao_aditivo_risco_trecho = linha_vad or "Omissão: Não consta cláusula vedando aditivos decorrentes de riscos alocados à contratada."

    # 6. Verificar R09 (Subcontratação)
    linha_sub = buscar_linha(r"subcontrata[çc][ãa]o")
    base.subcontratacao_definida = bool(linha_sub)
    base.subcontratacao_item = "Minuta de Contrato (Subcontratação)" if linha_sub else "Minuta de Contrato (Omissão)"
    base.subcontratacao_trecho = linha_sub or "Omissão: O edital e a minuta de contrato são silentes quanto à permissão ou vedação de subcontratação."

    # 7. Verificar R11 (Amostra)
    linha_amostra_todos = buscar_linha(r"todos\s+os\s+licitantes\s+dever[ãa]o\s+apresentar\s+amostra|amostra\s+juntamente\s+com\s+a\s+proposta\s+inicial")
    linha_amostra_1 = buscar_linha(r"suspender[áa]\s+a\s+sess[ãa]o\s+p[úu]blica\s+para\s+a\s+apresenta[çc][ãa]o\s+de\s+amostra|amostra.*primeiro\s+colocado|amostra.*melhor\s+lance")
    if linha_amostra_todos:
        base.escopo_exigencia_amostra = "todos_licitantes_fase_proposta"
        base.amostra_item = "Requisitos de Proposta / Amostra"
        base.amostra_trecho = linha_amostra_todos
    elif linha_amostra_1:
        base.escopo_exigencia_amostra = "apenas_primeiro_colocado"
        base.amostra_item = "Fase de Aceitação / Amostra"
        base.amostra_trecho = linha_amostra_1
    else:
        base.escopo_exigencia_amostra = "nao_exigida"
        base.amostra_item = "Procedimento Licitatório"
        base.amostra_trecho = "Não há exigência de amostra no certame."

    return base


_ERROS_TRANSITORIOS_GEMINI = (
    "429",
    "503",
    "500",
    "502",
    "504",
    "resource_exhausted",
    "unavailable",
    "timeout",
    "timed out",
    "readtimeout",
    "10053",
    "10054",
    "connection",
    "reset",
    "eof",
    "broken pipe",
    "remoteprotocolerror",
)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log_api(verbose: bool, msg: str) -> None:
    if verbose:
        print(f"[{_ts()}] {msg}", flush=True)


class _HeartbeatGemini:
    """Emite logs periódicos enquanto a requisição síncrona à API Gemini aguarda resposta."""

    def __init__(self, verbose: bool, label: str, timeout_s: int, intervalo_s: int = 15):
        self.verbose = verbose
        self.label = label
        self.timeout_s = timeout_s
        self.intervalo_s = intervalo_s
        self._stop = threading.Event()
        self._t0 = 0.0
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        while not self._stop.wait(self.intervalo_s):
            decorrido = int(time.perf_counter() - self._t0)
            print(
                f"[{_ts()}]   ... [{self.label}] aguardando resposta da API Gemini "
                f"({decorrido}s decorridos | timeout={self.timeout_s}s)...",
                flush=True,
            )

    def __enter__(self) -> "_HeartbeatGemini":
        self._t0 = time.perf_counter()
        if self.verbose:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


def _extrair_usage_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return {}
    return {
        "prompt_token_count": getattr(usage, "prompt_token_count", None),
        "thoughts_token_count": getattr(usage, "thoughts_token_count", None),
        "candidates_token_count": getattr(usage, "candidates_token_count", None),
        "total_token_count": getattr(usage, "total_token_count", None),
    }


def _formatar_usage_gemini(response: Any) -> str:
    d = _extrair_usage_dict(response)
    if not d:
        return "tokens=indisponível"
    prompt_tk = d["prompt_token_count"]
    thoughts_tk = d["thoughts_token_count"]
    output_tk = d["candidates_token_count"]
    total_tk = d["total_token_count"]
    return (
        f"prompt={prompt_tk if prompt_tk is not None else '?'} | "
        f"thoughts={thoughts_tk if thoughts_tk is not None else 0} | "
        f"output={output_tk if output_tk is not None else '?'} | "
        f"total={total_tk if total_tk is not None else '?'}"
    )


def _executar_generate_content_gemini(
    api_key: str,
    modelos_tentativa: list[str],
    prompt: str,
    response_schema: Any,
    label: str,
    timeout_s: int,
    verbose: bool,
    erro_prefixo: str,
    thinking_budget: int = 4096,
    usage_out: Optional[dict[str, Any]] = None,
) -> tuple[Any, str]:
    """Executa chamada Structured Output à API Gemini com timeout HTTP explícito, heartbeat e retry."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_s * 1000),
    )

    ultimo_erro = None
    for mod in modelos_tentativa:
        for tentativa in range(3):
            t_req = time.perf_counter()
            _log_api(
                verbose,
                f"  -> [{label}] Tentativa {tentativa + 1}/3 | modelo={mod} | "
                f"prompt={len(prompt)} chars | T=0.0 | thinking_budget={thinking_budget} | timeout={timeout_s}s",
            )
            try:
                with _HeartbeatGemini(verbose, label, timeout_s):
                    response = client.models.generate_content(
                        model=mod,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json",
                            response_schema=response_schema,
                            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                        ),
                    )
                decorrido = time.perf_counter() - t_req
                if usage_out is not None:
                    usage_out.clear()
                    usage_out.update(_extrair_usage_dict(response))
                _log_api(
                    verbose,
                    f"  <- [{label}] Resposta recebida em {decorrido:.1f}s | {_formatar_usage_gemini(response)}",
                )
                return response, mod
            except Exception as exc:
                decorrido = time.perf_counter() - t_req
                ultimo_erro = exc
                msg = str(exc).lower()
                _log_api(
                    verbose,
                    f"  !! [{label}] Erro após {decorrido:.1f}s ({type(exc).__name__}): {exc}",
                )
                if tentativa < 2 and any(k in msg for k in _ERROS_TRANSITORIOS_GEMINI):
                    espera = 2 ** (tentativa + 1)
                    _log_api(verbose, f"  .. [{label}] Aguardando {espera}s para retry...")
                    time.sleep(espera)
                    continue
                break

    raise RuntimeError(f"{erro_prefixo}: {ultimo_erro}")


def extrair_fatos_via_gemini(
    texto_numerado: str,
    nome_arquivo: str,
    api_key: str,
    modelo: str = "gemini-2.5-flash",
    timeout_s: int = 240,
    verbose: bool = False,
    thinking_budget: int = 4096,
    usage_out: Optional[dict[str, Any]] = None,
) -> tuple[FatosExtraidosEdital, str]:
    """
    Chama a API Google Gemini usando o SDK oficial `google-genai` com Structured Outputs
    para instanciar os fatos ontológicos (FatosExtraidosEdital) a partir do texto do Edital.
    Inclui timeout HTTP explícito, heartbeat opcional e retry com backoff para tolerância a falhas transitórias.
    Retorna (fatos, modelo_efetivamente_utilizado).
    """
    prompt = f"""Você é um extrator semântico jurídico-ontológico especializado na Lei das Estatais (Lei nº 13.303/2016) e na ontologia jurídica UFO-L.
Sua tarefa é ler as seções estruturadas do Edital abaixo (arquivo: {nome_arquivo}) e extrair EXCLUSIVAMENTE os fatos observáveis no documento para alimentar um motor simbólico em SWI-Prolog. NÃO emita opiniões jurídicas sobre ilegalidade; apenas registre o que está escrito ou omitido.

Orientações de busca por seção (confira sempre o documento inteiro antes de afirmar omissão):
- SEÇÃO 1 (Corpo do Edital): verifique consórcios (`R43`), exigência/momento de amostras (`R11`), regras gerais de aceitação/habilitação (`R29`, `R41`).
- SEÇÃO 2 (Anexo I / Termo de Referência): verifique menções nominais a marcas/produtos/softwares proprietários (`R01`/`R02`, incluindo se há cláusula "ou similar / ou equivalente / ou de melhor qualidade", se é apenas exemplo "ex.:", ou se cita processo formal de padronização), exigência de credenciamento/revenda autorizada/carta de solidariedade (`R41`), atestados de capacidade técnica (`R29`: percentual exigido e se veda somatório de atestados com ou sem justificativa técnica), e amostra/PoC (`R11`).
- SEÇÃO 3 (Minuta de Contrato e Matriz de Riscos): verifique presença de Matriz de Riscos (`R03`), cláusula vedando celebração de aditivos decorrentes de eventos alocados como risco da contratada (`R38`), e definição expressa de permissão ou vedação à subcontratação (`R09`).

Instruções de rigor:
1. Cite sempre a seção/item/cláusula e a tag exata de página/linha (ex: `[P18|L0650]` ou `[L0624]`) nos campos `*_item` e `*_trecho`.
2. Para cada item em `mencoes_marca`, classifique `contexto_mencao` com rigor:
   - `'objeto_licitado'`: quando a marca/produto/software define o próprio bem, hardware, licença ou serviço principal que a contratada deve fornecer (ex.: sistema operacional exigido para o DaaS, modelo de equipamento ou software objeto da compra).
   - `'interoperabilidade_ambiente_legado'`: quando a marca se refere apenas a um sistema, SGBD, diretório ou infraestrutura já existente no BNDES com o qual a solução contratada precisa integrar ou se comunicar.
   - `'manutencao_parque_existente'`: quando o objeto da licitação em si é suporte técnico, garantia ou atualização de equipamentos/licenças proprietárias já pertencentes ao órgão.
   - `'referencia_exemplificativa'`: quando a marca aparece apenas como exemplo ilustrativo ('ex.: ...') ou descrição informativa do ambiente atual sem impor fornecimento daquela marca.
3. Se uma marca/produto aparecer apenas como exemplo ('ex.: ...') ou acompanhada de 'ou similar / equivalente / de melhor qualidade', marque `possui_clausula_similaridade = True`. Só marque `False` quando a marca/produto for exigido de forma fechada/obrigatória sem cláusula de equivalência.
4. Em `R41` (`exige_credenciamento_ou_carta_fabricante`), marque `True` SOMENTE quando o edital exigir declaração de revenda autorizada, credenciamento pelo fabricante ou carta de solidariedade/anuência emitida pelo fabricante (não marque `True` para mero compromisso próprio da licitante de prestar ou contratar garantia).
5. Em `percentual_minimo_atestado`, informe o percentual inteiro exigido (0 se não exigir percentual mínimo).

TEXTO DO EDITAL ESTRUTURADO E NUMERADO:
{texto_numerado}
"""

    modelos_tentativa = [modelo]
    if modelo != "gemini-2.5-flash":
        modelos_tentativa.append("gemini-2.5-flash")

    response, mod = _executar_generate_content_gemini(
        api_key=api_key,
        modelos_tentativa=modelos_tentativa,
        prompt=prompt,
        response_schema=FatosExtraidosEdital,
        label=f"Extração {nome_arquivo}",
        timeout_s=timeout_s,
        verbose=verbose,
        erro_prefixo=f"Falha ao chamar API Gemini ({modelo})",
        thinking_budget=thinking_budget,
        usage_out=usage_out,
    )
    if response.parsed is not None:
        return response.parsed, mod
    fatos = FatosExtraidosEdital.model_validate_json(response.text)
    return fatos, mod


# ==============================================================================
# Baseline "Somente Neural" (LLM Puro End-to-End sem Prolog e sem UFO-L)
# ==============================================================================


class JulgamentoNeuralRegra(BaseModel):
    """Representa o julgamento direto (end-to-end) feito por um LLM puro sem camada simbólica."""

    regra_id: str = Field(description="Código da regra avaliada (ex: R01, R29).")
    status_verificacao: Literal["Conforme", "Indício de Inconformidade"] = Field(
        description="Veredito emitido diretamente pelo LLM puro."
    )
    justificativa_livre_llm: str = Field(
        description="Argumentação textual gerada livremente pelo LLM puro (caixa-preta)."
    )
    trecho_citado_llm: str = Field(
        description="Referência textual ou trecho citado pelo LLM puro (frequentemente incompleto ou sem linha exata)."
    )
    tipo_limitacao_observada: str = Field(
        default="",
        description="Classificação técnica da diferença entre a resposta Somente Neural e a Neuro-Simbólica.",
    )
    analise_diferenca_nesy: str = Field(
        default="",
        description="Explicação detalhada de por que a abordagem Neuro-Simbólica (Prolog + UFO-L) é superior neste caso.",
    )


class ListaJulgamentosNeurais(BaseModel):
    julgamentos: List[JulgamentoNeuralRegra]


def obter_avaliacao_somente_neural_demo(
    nome_arquivo: str,
    pareceres_nesy: list,
) -> dict[str, JulgamentoNeuralRegra]:
    """
    Retorna as respostas de referência do mecanismo 'Somente Neural (LLM Puro End-to-End)'
    no modo demonstração para comparação lado a lado com 'Neuro-Simbólico (LLM + Prolog + UFO-L)'.
    Ilustra cenários didáticos em disjunção lógica, Mundo Fechado (CWA), ruído léxico e ausência de prova SLD.
    """
    res: dict[str, JulgamentoNeuralRegra] = {}

    if "Saneado" in nome_arquivo:
        for p in pareceres_nesy:
            rid = p.regra_id
            if rid == "R43":
                res[rid] = JulgamentoNeuralRegra(
                    regra_id=rid,
                    status_verificacao="Indício de Inconformidade",
                    justificativa_livre_llm=(
                        "O item 2.3, inciso VIII, do edital estabelece que estará impedido de participar o interessado "
                        "que esteja organizado sob a forma de consórcio, o que configura restrição à competitividade."
                    ),
                    trecho_citado_llm="Item 2.3, VIII - impedido de participar consórcio.",
                    tipo_limitacao_observada="🔀 Divergência (Modo Demo — Resolução de Exceção Justificada)",
                    analise_diferenca_nesy=(
                        "Ao encontrar a cláusula proibitiva no item 2.3, VIII, o baseline demo disparou inconformidade "
                        "por viés de superfície léxica, deixando de encadear logicamente o subitem 2.3.1 [L0010] que "
                        "trouxe a motivação técnica formal. Já o motor Prolog unificou `fato_veda_consorcio/3` + "
                        "`fato_justificativa_vedacao_consorcio/3` e provou que o dever de motivar (`duty_to_act`) da Estatal foi cumprido."
                    ),
                )
            else:
                res[rid] = JulgamentoNeuralRegra(
                    regra_id=rid,
                    status_verificacao="Conforme",
                    justificativa_livre_llm=(
                        f"Pela leitura geral do documento saneado, a exigência referente à regra {rid} ({p.dispositivo_legal}) "
                        "aparenta estar atendida no texto convocatório."
                    ),
                    trecho_citado_llm="Menção geral no texto do edital (sem árvore de derivação).",
                    tipo_limitacao_observada="⚖️ Convergente no Veredito (Sem Prova Formal SLD / UFO-L no LLM Puro)",
                    analise_diferenca_nesy=(
                        "Embora o LLM puro chegue ao mesmo veredito ('Conforme'), ele entrega apenas uma impressão "
                        "textual probabilística. O mecanismo Neuro-Simbólico comprova matematicamente a ausência de "
                        f"oposição hohfeldiana (`{p.inferencia_bruta.momento_edital}` == `{p.inferencia_bruta.momento_esperado_lei}`) "
                        "via Resolução SLD sob Mundo Fechado."
                    ),
                )
        return res

    if "Critico" in nome_arquivo or "Switches" in nome_arquivo:
        for p in pareceres_nesy:
            rid = p.regra_id
            if rid == "R38":
                res[rid] = JulgamentoNeuralRegra(
                    regra_id=rid,
                    status_verificacao="Conforme",
                    justificativa_livre_llm=(
                        "Como o edital não possui cláusula de Matriz de Riscos, não há que se falar em aditivos "
                        "sobre riscos alocados na matriz, não havendo violação direta neste ponto específico."
                    ),
                    trecho_citado_llm="Não aplicável (ausência de matriz).",
                    tipo_limitacao_observada="🔀 Divergência (Modo Demo — Raciocínio Deôntico Relacional)",
                    analise_diferenca_nesy=(
                        "O baseline demo presume que omitir a Matriz de Riscos isenta o contrato da regra do Art. 81, § 8º. "
                        "No motor Prolog + UFO-L, a ausência do fato positivo (`\\+ fato_vedacao_aditivo_risco/3`) via Negação por Falha "
                        "prova que o contrato deixou de impor a incompetência legal (`disability`) à contratada, mantendo um `power` indevido de pleitear aditivos."
                    ),
                )
            elif rid == "R09":
                res[rid] = JulgamentoNeuralRegra(
                    regra_id=rid,
                    status_verificacao="Conforme",
                    justificativa_livre_llm=(
                        "O edital não proíbe expressamente a subcontratação, o que indica que ela seguirá as regras "
                        "gerais da legislação aplicável durante a execução do contrato."
                    ),
                    trecho_citado_llm="Silêncio contratual interpretado como regular.",
                    tipo_limitacao_observada="🔀 Divergência (Modo Demo — Hipótese do Mundo Fechado / CWA)",
                    analise_diferenca_nesy=(
                        "O LLM puro opera sob pensamento de 'Mundo Aberto': interpreta o silêncio do edital como "
                        "conformidade tácita. No sistema Neuro-Simbólico, o Prolog aplica Negação por Falha (`\\+`) sob "
                        "Mundo Fechado: se a cláusula de subcontratação não está definida no edital, a Estatal violou seu "
                        "dever positivo de clareza (`duty_to_act` vs `permission_to_omit`, Art. 78)."
                    ),
                )
            else:
                res[rid] = JulgamentoNeuralRegra(
                    regra_id=rid,
                    status_verificacao="Indício de Inconformidade",
                    justificativa_livre_llm=(
                        f"O edital apresenta exigência restritiva relacionada a {p.categoria} ({p.dispositivo_legal}), "
                        "contrariando os princípios da Lei nº 13.303/2016."
                    ),
                    trecho_citado_llm="Trecho restritivo identificado no Termo de Referência.",
                    tipo_limitacao_observada="⚖️ Convergente no Veredito (Sem Enquadramento Hohfeldiano nem Prova SLD)",
                    analise_diferenca_nesy=(
                        "Em violações óbvias, o LLM puro acerta o alerta, mas não especifica qual posição jurídica fundamental "
                        f"foi quebrada. O motor Neuro-Simbólico explicita o par hohfeldiano violado (`{p.inferencia_bruta.momento_edital}` "
                        f"vs `{p.inferencia_bruta.momento_esperado_lei}`) sobre o papel `{p.inferencia_bruta.papel_afetado}`."
                    ),
                )
        return res

    # Caso Principal: Edital Real PE 29/2026 (BNDES) ou editais customizados (Modo Demo offline)
    mapa_pe29: dict[str, JulgamentoNeuralRegra] = {
        "R01": JulgamentoNeuralRegra(
            regra_id="R01",
            status_verificacao="Indício de Inconformidade",
            justificativa_livre_llm=(
                "O Termo de Referência menciona marcas específicas como 'Windows 11', 'Microsoft 365' e também "
                "exige chave física 'YubiKey' no item 49.f, configurando citação de marcas no caderno técnico."
            ),
            trecho_citado_llm="Itens 5, 18 e 49.f (Windows 11, Microsoft 365 e Yubikey).",
            tipo_limitacao_observada="🟠 Ruído Semântico (Modo Demo — Não isolou a cláusula exemplificativa)",
            analise_diferenca_nesy=(
                "Embora aponte problema de marca no edital, o texto demo mistura a exigência fechada "
                "de `Windows 11 Professional` e a menção meramente exemplificativa `(ex.: yubikey)`. "
                "No motor Neuro-Simbólico, o Prolog filtra a ABox pela condição estrita `sem_clausula_similaridade`, "
                "absolvendo automaticamente a `YubiKey` e incriminando apenas as exigências sem equivalência."
            ),
        ),
        "R02": JulgamentoNeuralRegra(
            regra_id="R02",
            status_verificacao="Conforme",
            justificativa_livre_llm=(
                "Por se tratar de contratação de solução corporativa de Desktop as a Service (DaaS) integrada ao "
                "ambiente já existente do BNDES, a exigência de softwares da plataforma Microsoft decorre da "
                "padronização tecnológica natural da instituição, estando conforme o Art. 47, I."
            ),
            trecho_citado_llm="Anexo I - Especificações de integração com ambiente Microsoft do BNDES.",
            tipo_limitacao_observada="🔀 Divergência (Modo Demo — Presunção de Premissa / Mundo Aberto)",
            analise_diferenca_nesy=(
                "O baseline demo presume que existe um processo administrativo formal de padronização apenas pelo contexto de TI do edital. Na arquitetura "
                "Neuro-Simbólica, sob a Hipótese do Mundo Fechado, como não há menção a processo formal de padronização "
                "no texto (`sem_justificativa_padronizacao`), o Prolog prova o conflito de 2ª ordem: a Estatal exerceu "
                "um `power` onde a Lei 13.303 impõe uma incompetência (`disability`) na ausência de padronização formal."
            ),
        ),
        "R03": JulgamentoNeuralRegra(
            regra_id="R03",
            status_verificacao="Conforme",
            justificativa_livre_llm=(
                "O edital e a minuta contratual preveem a Matriz de Riscos na Cláusula Nona e no Anexo III."
            ),
            trecho_citado_llm="Cláusula Nona da Minuta de Contrato e Anexo III.",
            tipo_limitacao_observada="⚖️ Convergente no Veredito (Sem Prova Formal SLD / UFO-L no LLM Puro)",
            analise_diferenca_nesy=(
                "Ambos convergem na presença da Matriz de Riscos. A diferença está na garantia formal: o motor "
                "Neuro-Simbólico ancora a prova no fato `fato_matriz_riscos/3` e demonstra na UFO-L o adimplemento do "
                "dever positivo (`duty_to_act`) da Estatal perante o direito (`right_to_action`) dos licitantes."
            ),
        ),
        "R09": JulgamentoNeuralRegra(
            regra_id="R09",
            status_verificacao="Conforme",
            justificativa_livre_llm=(
                "A minuta do contrato define na Cláusula Décima Sétima que é vedada a subcontratação do objeto."
            ),
            trecho_citado_llm="Cláusula Décima Sétima, Parágrafo Terceiro.",
            tipo_limitacao_observada="⚖️ Convergente no Veredito (Sem Prova Formal SLD / UFO-L no LLM Puro)",
            analise_diferenca_nesy=(
                "Enquanto o LLM puro apenas resume a cláusula, o motor Prolog unifica `fato_subcontratacao_definida(pe_29_2026, ...)` "
                "e comprova formalmente a harmonia normativa no relator `legal_service_agreement`."
            ),
        ),
        "R11": JulgamentoNeuralRegra(
            regra_id="R11",
            status_verificacao="Conforme",
            justificativa_livre_llm=(
                "O item 4.11.4 estabelece que a amostra será exigida apenas após a fase de lances e verificação de "
                "habilitação do licitante classificado em primeiro lugar."
            ),
            trecho_citado_llm="Item 4.11.4 do Edital e Item 119 do Anexo I.",
            tipo_limitacao_observada="⚖️ Convergente no Veredito (Sem Prova Formal SLD / UFO-L no LLM Puro)",
            analise_diferenca_nesy=(
                "O mecanismo Neuro-Simbólico vai além da constatação textual: prova formalmente que a Estatal respeitou "
                "sua incompetência (`disability`) de exigir amostra na fase inicial, preservando a imunidade (`immunity`) "
                "dos demais licitantes."
            ),
        ),
        "R29": JulgamentoNeuralRegra(
            regra_id="R29",
            status_verificacao="Conforme",
            justificativa_livre_llm=(
                "O item 116 do Termo de Referência exige comprovação de fornecimento de 50% (cinquenta por cento) "
                "do quantitativo total previsto (123 de 246 estações virtuais). Como 50% está dentro do limite máximo "
                "de 50% consolidado pela jurisprudência do TCU (Súmula 263), a exigência de qualificação técnica está conforme."
            ),
            trecho_citado_llm="Anexo I, Item 116 (percentual de 50% do quantitativo).",
            tipo_limitacao_observada="🔀 Divergência (Modo Demo — Regra Composta / Disjunção Lógica)",
            analise_diferenca_nesy=(
                "A regra R29 possui duas condições "
                "disjuntivas de violação: (1) exigir percentual > 50% OU (2) vedar o somatório de atestados sem "
                "justificativa técnica. O baseline demo sofreu viés de ancoragem numérica: verificou que 50% <= 50% no "
                "item 116 e encerrou a análise como 'Conforme', ignorando a proibição ao somatório no item 117. "
                "No motor Prolog, a Resolução SLD testou a 1ª cláusula (50 > 50 -> Falso), fez backtracking automático "
                "para a 2ª cláusula (`fato_veda_somatorio/3` + `\\+ fato_justificativa_vedacao_somatorio/3` -> Verdadeiro) e detectou a divergência!"
            ),
        ),
        "R38": JulgamentoNeuralRegra(
            regra_id="R38",
            status_verificacao="Conforme",
            justificativa_livre_llm=(
                "O Parágrafo Segundo da Cláusula Nona veda aditivos decorrentes de eventos alocados como risco do contratado."
            ),
            trecho_citado_llm="Minuta de Contrato, Cláusula Nona, Parágrafo Segundo.",
            tipo_limitacao_observada="⚖️ Convergente no Veredito (Sem Prova Formal SLD / UFO-L no LLM Puro)",
            analise_diferenca_nesy=(
                "O motor Neuro-Simbólico comprova na árvore SLD via `fato_vedacao_aditivo_risco/3` que o contrato institui corretamente a posição "
                "hohfeldiana `disability` sobre o `contracted_party_role`, em harmonia com o Art. 81, § 8º."
            ),
        ),
        "R41": JulgamentoNeuralRegra(
            regra_id="R41",
            status_verificacao="Indício de Inconformidade",
            justificativa_livre_llm=(
                "O item 114, alínea 'c', do Anexo I exige declaração de que a licitante faz parte da rede de revendas "
                "autorizadas pelo provedor da solução, o que pode restringir a competitividade do certame."
            ),
            trecho_citado_llm="Anexo I, Item 114, alínea 'c'.",
            tipo_limitacao_observada="⚖️ Convergente no Veredito (Texto Opinativo vs. Oposição Hohfeldiana Formal)",
            analise_diferenca_nesy=(
                "O LLM puro usa linguagem hesitante ('pode restringir a competitividade'). O motor Neuro-Simbólico "
                "entrega uma prova deôntica baseada em `fato_credenciamento_exigido/3`: o edital impôs um `duty_to_act` ao "
                "`bidder_role` que é o oposto contraditório (`hohfeldian_opposite`) da liberdade `permission_to_omit` "
                "garantida pelo Art. 31 da Lei 13.303/2016."
            ),
        ),
        "R43": JulgamentoNeuralRegra(
            regra_id="R43",
            status_verificacao="Conforme",
            justificativa_livre_llm=(
                "O item 2.3, inciso VIII, veda a participação de empresas em consórcio. Como a decisão sobre "
                "admitir ou vedar consórcios insere-se no poder discricionário da empresa estatal, a cláusula é válida."
            ),
            trecho_citado_llm="Item 2.3, inciso VIII do Edital.",
            tipo_limitacao_observada="🔀 Divergência (Modo Demo — Omissão de Motivação Obrigatória / Mundo Fechado)",
            analise_diferenca_nesy=(
                "O baseline demo lembra que vedar consórcio é permitido em tese, mas ignora a exigência de justificativa técnica expressa. O motor Prolog, "
                "operando sob Mundo Fechado, verifica `fato_veda_consorcio/3` combinada a `\\+ fato_justificativa_vedacao_consorcio/3` (NAF) "
                "e prova que a Estatal violou seu dever legal (`duty_to_act`) de motivar a restrição."
            ),
        ),
    }

    for p in pareceres_nesy:
        rid = p.regra_id
        if rid in mapa_pe29:
            res[rid] = mapa_pe29[rid]
    return res


def executar_avaliacao_somente_neural_gemini(
    texto_numerado: str,
    nome_arquivo: str,
    catalogo_regras: dict,
    regras_selecionadas: list[str],
    pareceres_nesy: list,
    api_key: str,
    modelo: str = "gemini-2.5-flash",
    timeout_s: int = 240,
    verbose: bool = False,
    thinking_budget: int = 4096,
    usage_out: Optional[dict[str, Any]] = None,
) -> dict[str, JulgamentoNeuralRegra]:
    """
    Executa uma avaliação puramente neural (LLM Puro End-to-End) ao vivo na API Gemini,
    pedindo que o próprio LLM julgue diretamente as regras sem Prolog e sem UFO-L,
    e anota automaticamente as diferenças frente ao diagnóstico Neuro-Simbólico.
    """
    regras_desc = "\n".join(
        f"- {rid}: {catalogo_regras[rid]['categoria']} ({catalogo_regras[rid]['dispositivo_legal']}) -> {catalogo_regras[rid]['criterio_validacao']}"
        for rid in regras_selecionadas
        if rid in catalogo_regras
    )

    prompt = f"""Você é um auditor jurídico avaliando diretamente a conformidade de um edital de licitação.
Analise o edital abaixo ({nome_arquivo}) e dê seu parecer direto sobre cada uma das seguintes regras da Lei nº 13.303/2016:
{regras_desc}

Para cada regra, informe:
- `regra_id`: código da regra (ex: R01, R02, ..., R43)
- `status_verificacao`: "Conforme" ou "Indício de Inconformidade"
- `justificativa_livre_llm`: sua explicação direta
- `trecho_citado_llm`: trecho ou item do edital considerado

TEXTO DO EDITAL:
{texto_numerado}
"""

    modelos_tentativa = [modelo]
    if modelo != "gemini-2.5-flash":
        modelos_tentativa.append("gemini-2.5-flash")

    response, _ = _executar_generate_content_gemini(
        api_key=api_key,
        modelos_tentativa=modelos_tentativa,
        prompt=prompt,
        response_schema=ListaJulgamentosNeurais,
        label=f"Somente Neural {nome_arquivo}",
        timeout_s=timeout_s,
        verbose=verbose,
        erro_prefixo=f"Falha ao chamar API Gemini Somente Neural ({modelo})",
        thinking_budget=thinking_budget,
        usage_out=usage_out,
    )

    parsed = response.parsed or ListaJulgamentosNeurais.model_validate_json(response.text)
    mapa_live = {j.regra_id: j for j in parsed.julgamentos}

    # Enriquece cada julgamento live com a comparação frente ao motor Neuro-Simbólico
    mapa_nesy = {p.regra_id: p for p in pareceres_nesy}
    for rid, j in mapa_live.items():
        p = mapa_nesy.get(rid)
        if not p:
            continue
        if j.status_verificacao != p.status_verificacao:
            j.tipo_limitacao_observada = (
                f"🔀 Divergência (LLM Puro: {j.status_verificacao} vs. Prolog/UFO-L: {p.status_verificacao} — requer auditoria)"
            )
            j.analise_diferenca_nesy = (
                f"Divergência que requer conferência frente ao gabarito humano: no julgamento direto (end-to-end), "
                f"o LLM puro concluiu '{j.status_verificacao}', enquanto o motor Prolog + UFO-L derivou "
                f"'{p.status_verificacao}' via Resolução SLD (`{p.inferencia_bruta.momento_edital}` "
                f"vs `{p.inferencia_bruta.momento_esperado_lei}`) com base em {p.item_identificado}."
            )
        else:
            j.tipo_limitacao_observada = "⚖️ Convergente no Veredito (Sem Prova Formal SLD / UFO-L no LLM Puro)"
            j.analise_diferenca_nesy = (
                "Embora o veredito final tenha coincidido, o LLM puro produziu apenas texto opinativo sem garantia de "
                f"consistência axiomática. O motor Neuro-Simbólico entrega a árvore de Resolução SLD completa e o par "
                f"hohfeldiano (`{p.inferencia_bruta.momento_edital}` / `{p.inferencia_bruta.momento_esperado_lei}`)."
            )
    return mapa_live


def carregar_cache_benchmark_edital(
    nome_arquivo: str,
    cache_dir: str | Path | None = None,
) -> Optional[dict[str, Any]]:
    """Carrega o cache auditado (fatos + baseline neural) de um edital do benchmark, se existir."""
    base_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent.parent / "dados" / "benchmark_10_editais"
    if not base_dir.exists():
        return None
    stem = Path(nome_arquivo).stem
    arq = base_dir / f"{stem}.json"
    if not arq.exists():
        return None
    return json.loads(arq.read_text(encoding="utf-8"))


def carregar_resumo_benchmark(
    cache_dir: str | Path | None = None,
) -> Optional[dict[str, Any]]:
    """Carrega o resumo consolidado dos 10 editais reais em dados/benchmark_10_editais/resumo_consolidado.json."""
    base_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent.parent / "dados" / "benchmark_10_editais"
    arq = base_dir / "resumo_consolidado.json"
    if not arq.exists():
        return None
    return json.loads(arq.read_text(encoding="utf-8"))


