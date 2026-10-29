"""
Camada Neural (Instanciação Ontológica):
Extrai fatos observáveis do texto do Edital (.txt) usando Google Gemini (Structured Outputs)
ou Modo Demonstração / Analisador Local, e converte para fatos Prolog (ABox da UFO-L).
"""

from __future__ import annotations

import os
import re
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class MencaoMarcaFato(BaseModel):
    marca_ou_produto: str = Field(
        description="Nome da marca, fabricante ou produto específico mencionado como requisito técnico."
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
        description="True se exigir declaração de que faz parte de rede de revendas autorizadas, parceiro credenciado ou carta de solidariedade do fabricante/provedor."
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
    limpo = texto.replace("\\", "/").replace("'", "\\'").replace("\n", " ").strip()
    return f"'{limpo}'"


def converter_fatos_para_prolog(fatos: FatosExtraidosEdital) -> str:
    """Converte o objeto FatosExtraidosEdital (saída da Camada Neural) em cláusulas Prolog (ABox UFO-L)."""
    edital_id = re.sub(r"[^a-z0-9_]", "_", fatos.identificador_edital.lower()).strip("_") or "edital_analisado"
    linhas_pl = [
        "% ==============================================================================",
        f"% Fatos Extraídos do Edital (ABox UFO-L) - Instância: {edital_id}",
        "% ==============================================================================",
        f"edital_instancia({edital_id}).",
        "",
        "% --- R01 & R02: Menções de Marca / Produto Específico ---",
    ]

    marcas_sem_similaridade = []
    for m in fatos.mencoes_marca:
        sim_atom = "com_clausula_similaridade" if m.possui_clausula_similaridade else "sem_clausula_similaridade"
        pad_atom = "com_justificativa_padronizacao" if m.possui_justificativa_padronizacao else "sem_justificativa_padronizacao"
        linhas_pl.append(
            f"mencao_marca_exigida({edital_id}, {sanitizar_atom_prolog(m.marca_ou_produto)}, "
            f"{sim_atom}, {pad_atom}, {sanitizar_atom_prolog(m.item_edital)}, {sanitizar_atom_prolog(m.trecho_literal)})."
        )
        if not m.possui_clausula_similaridade and not m.possui_justificativa_padronizacao:
            marcas_sem_similaridade.append(m)

    if marcas_sem_similaridade:
        m0 = marcas_sem_similaridade[0]
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R01', {sanitizar_atom_prolog(m0.item_edital)}, {sanitizar_atom_prolog(m0.trecho_literal)})."
        )
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R02', {sanitizar_atom_prolog(m0.item_edital)}, {sanitizar_atom_prolog(m0.trecho_literal)})."
        )
    elif fatos.mencoes_marca:
        m0 = fatos.mencoes_marca[0]
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R01', {sanitizar_atom_prolog(m0.item_edital)}, {sanitizar_atom_prolog(m0.trecho_literal)})."
        )
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R02', {sanitizar_atom_prolog(m0.item_edital)}, {sanitizar_atom_prolog(m0.trecho_literal)})."
        )
    else:
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R01', 'Especificações Técnicas', 'Nenhuma marca restritiva sem cláusula de similaridade identificada.')."
        )
        linhas_pl.append(
            f"evidencia_regra({edital_id}, 'R02', 'Especificações Técnicas', 'Nenhuma indicação exclusiva de marca sem padronização identificada.')."
        )

    # R03 e R38
    status_mr = "presente" if fatos.matriz_riscos_presente else "ausente"
    linhas_pl.extend([
        "",
        "% --- R03 & R38: Matriz de Riscos e Vedação de Aditivos ---",
        f"fato_matriz_riscos({edital_id}, {status_mr}, {sanitizar_atom_prolog(fatos.matriz_riscos_item)}, {sanitizar_atom_prolog(fatos.matriz_riscos_trecho)}).",
        f"evidencia_regra({edital_id}, 'R03', {sanitizar_atom_prolog(fatos.matriz_riscos_item)}, {sanitizar_atom_prolog(fatos.matriz_riscos_trecho)}).",
    ])

    status_vad = "presente" if fatos.vedacao_aditivo_risco_presente else "ausente"
    linhas_pl.extend([
        f"fato_vedacao_aditivo_risco({edital_id}, {status_vad}, {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_item)}, {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_trecho)}).",
        f"evidencia_regra({edital_id}, 'R38', {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_item)}, {sanitizar_atom_prolog(fatos.vedacao_aditivo_risco_trecho)}).",
    ])

    # R09 - Subcontratação
    status_sub = "definida" if fatos.subcontratacao_definida else "omissa"
    linhas_pl.extend([
        "",
        "% --- R09: Regra de Subcontratação ---",
        f"fato_subcontratacao({edital_id}, {status_sub}, {sanitizar_atom_prolog(fatos.subcontratacao_item)}, {sanitizar_atom_prolog(fatos.subcontratacao_trecho)}).",
        f"evidencia_regra({edital_id}, 'R09', {sanitizar_atom_prolog(fatos.subcontratacao_item)}, {sanitizar_atom_prolog(fatos.subcontratacao_trecho)}).",
    ])

    # R11 - Amostra
    linhas_pl.extend([
        "",
        "% --- R11: Exigência de Amostra / PoC ---",
        f"fato_amostra({edital_id}, {fatos.escopo_exigencia_amostra}, {sanitizar_atom_prolog(fatos.amostra_item)}, {sanitizar_atom_prolog(fatos.amostra_trecho)}).",
        f"evidencia_regra({edital_id}, 'R11', {sanitizar_atom_prolog(fatos.amostra_item)}, {sanitizar_atom_prolog(fatos.amostra_trecho)}).",
    ])

    # R29 - Atestado de Capacidade Técnica e Somatório
    som_atom = "veda_somatorio" if fatos.veda_somatorio_atestados else "permite_somatorio"
    just_som_atom = "com_justificativa" if fatos.possui_justificativa_vedacao_somatorio else "sem_justificativa"
    linhas_pl.extend([
        "",
        "% --- R29: Qualificação Técnica (Quantitativo e Somatório de Atestados) ---",
        f"fato_atestado_capacidade({edital_id}, {fatos.percentual_minimo_atestado}, {som_atom}, {just_som_atom}, {sanitizar_atom_prolog(fatos.atestado_item)}, {sanitizar_atom_prolog(fatos.atestado_trecho)}).",
        f"evidencia_regra({edital_id}, 'R29', {sanitizar_atom_prolog(fatos.atestado_item)}, {sanitizar_atom_prolog(fatos.atestado_trecho)}).",
    ])

    # R41 - Credenciamento / Carta do Fabricante
    cred_atom = "exigido" if fatos.exige_credenciamento_ou_carta_fabricante else "nao_exigido"
    linhas_pl.extend([
        "",
        "% --- R41: Credenciamento / Revenda Autorizada do Fabricante ---",
        f"fato_credenciamento_fabricante({edital_id}, {cred_atom}, {sanitizar_atom_prolog(fatos.credenciamento_item)}, {sanitizar_atom_prolog(fatos.credenciamento_trecho)}).",
        f"evidencia_regra({edital_id}, 'R41', {sanitizar_atom_prolog(fatos.credenciamento_item)}, {sanitizar_atom_prolog(fatos.credenciamento_trecho)}).",
    ])

    # R43 - Consórcio
    cons_atom = "vedado" if fatos.veda_participacao_consorcio else "permitido"
    just_cons_atom = "com_justificativa" if fatos.possui_justificativa_vedacao_consorcio else "sem_justificativa"
    linhas_pl.extend([
        "",
        "% --- R43: Participação em Consórcio ---",
        f"fato_consorcio({edital_id}, {cons_atom}, {just_cons_atom}, {sanitizar_atom_prolog(fatos.consorcio_item)}, {sanitizar_atom_prolog(fatos.consorcio_trecho)}).",
        f"evidencia_regra({edital_id}, 'R43', {sanitizar_atom_prolog(fatos.consorcio_item)}, {sanitizar_atom_prolog(fatos.consorcio_trecho)}).",
    ])

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
        base.atestado_trecho = " ".join(x for x in [linha_atestado_pct, linha_veda_som, linha_just_som] if x)

    # 5. Verificar R03 e R38 (Matriz de Riscos e Vedação de Aditivos)
    linha_mr = buscar_linha(r"MATRIZ\s+DE\s+RISCOS")
    base.matriz_riscos_presente = bool(linha_mr)
    base.matriz_riscos_trecho = linha_mr or "Omissão: Não foi localizada cláusula ou seção de Matriz de Riscos no edital/contrato."

    linha_vad = buscar_linha(r"vedada\s+a\s+celebra[çc][ãa]o\s+de\s+aditivos\s+decorrentes\s+de\s+eventos\s+supervenientes\s+alocados")
    base.vedacao_aditivo_risco_presente = bool(linha_vad)
    base.vedacao_aditivo_risco_trecho = linha_vad or "Omissão: Não consta cláusula vedando aditivos decorrentes de riscos alocados à contratada."

    # 6. Verificar R09 (Subcontratação)
    linha_sub = buscar_linha(r"subcontrata[çc][ãa]o")
    base.subcontratacao_definida = bool(linha_sub)
    base.subcontratacao_trecho = linha_sub or "Omissão: O edital e a minuta de contrato são silentes quanto à permissão ou vedação de subcontratação."

    # 7. Verificar R11 (Amostra)
    linha_amostra_todos = buscar_linha(r"todos\s+os\s+licitantes\s+dever[ãa]o\s+apresentar\s+amostra|amostra\s+juntamente\s+com\s+a\s+proposta\s+inicial")
    linha_amostra_1 = buscar_linha(r"suspender[áa]\s+a\s+sess[ãa]o\s+p[úu]blica\s+para\s+a\s+apresenta[çc][ãa]o\s+de\s+amostra|amostra.*primeiro\s+colocado|amostra.*melhor\s+lance")
    if linha_amostra_todos:
        base.escopo_exigencia_amostra = "todos_licitantes_fase_proposta"
        base.amostra_trecho = linha_amostra_todos
    elif linha_amostra_1:
        base.escopo_exigencia_amostra = "apenas_primeiro_colocado"
        base.amostra_trecho = linha_amostra_1
    else:
        base.escopo_exigencia_amostra = "nao_exigida"
        base.amostra_trecho = "Não há exigência de amostra no certame."

    return base


def extrair_fatos_via_gemini(
    texto_numerado: str,
    nome_arquivo: str,
    api_key: str,
    modelo: str = "gemini-2.5-flash",
) -> tuple[FatosExtraidosEdital, str]:
    """
    Chama a API Google Gemini usando o SDK oficial `google-genai` com Structured Outputs
    para instanciar os fatos ontológicos (FatosExtraidosEdital) a partir do texto do Edital.
    Retorna (fatos, modelo_efetivamente_utilizado).
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    prompt = f"""Você é um extrator semântico jurídico-ontológico especializado na Lei das Estatais (Lei nº 13.303/2016) e na ontologia jurídica UFO-L.
Sua tarefa é ler o Edital numerado linha a linha abaixo (arquivo: {nome_arquivo}) e extrair EXCLUSIVAMENTE os fatos observáveis no documento para alimentar um motor simbólico em SWI-Prolog.

Instruções de rigor:
1. Cite sempre o item/cláusula e o número exato da linha (ex: [L0624]) nos campos `*_item` e `*_trecho`.
2. Em `mencoes_marca`, identifique se há exigência de marcas/produtos específicos (ex: Windows 11, Catalyst, etc.) e verifique se estão acompanhadas da expressão "ou similar / ou equivalente / ou de melhor qualidade" ou de justificativa expressa de padronização.
3. Em `veda_somatorio_atestados`, verifique se há cláusula proibindo somar atestados de capacidade técnica e se há justificativa técnica expressa para tal proibição.
4. Em `exige_credenciamento_ou_carta_fabricante`, verifique se o edital exige declaração de que a licitante faz parte da rede de revendas autorizadas, parceiro credenciado ou carta de solidariedade do fabricante/provedor.

TEXTO DO EDITAL NUMERADO:
{texto_numerado}
"""

    modelos_tentativa = [modelo]
    if modelo != "gemini-2.5-flash":
        modelos_tentativa.append("gemini-2.5-flash")

    ultimo_erro = None
    for mod in modelos_tentativa:
        try:
            response = client.models.generate_content(
                model=mod,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=FatosExtraidosEdital,
                ),
            )
            if response.parsed is not None:
                return response.parsed, mod
            fatos = FatosExtraidosEdital.model_validate_json(response.text)
            return fatos, mod
        except Exception as exc:
            ultimo_erro = exc
            continue

    raise RuntimeError(f"Falha ao chamar API Gemini ({modelo}): {ultimo_erro}")

