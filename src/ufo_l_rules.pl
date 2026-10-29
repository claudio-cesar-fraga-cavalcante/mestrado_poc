% ==============================================================================
% Regras Deônticas e Normativas da Lei 13.303/2016 fundamentadas na UFO-L
% ==============================================================================
% Este módulo estende dados/UFO_L.pl conectando as normas da Lei das Estatais
% (Lei 13.303/2016) às posições jurídicas de Hohfeld/Alexy (UFO-L) e aos fatos
% extraídos de cada Edital pela Camada Neural.
% ==============================================================================

:- discontiguous norma_legal/6.
:- discontiguous avaliar_regra/8.

% ------------------------------------------------------------------------------
% 1. Catálogo Formal de Normas da Lei 13.303 na UFO-L (Dever-Ser Legal)
% ------------------------------------------------------------------------------
% norma_legal(RegraID, RelacaoJuridica, PapelTitular, MomentoEsperadoLei, AcaoJuridica, DispositivoLegal)

norma_legal('R01', administrative_tender_relation, bidder_role, permission_to_act,
    ofertar_produto_similar_ou_melhor_qualidade, 'Art. 47, I, "c"').

norma_legal('R02', administrative_tender_relation, bidding_authority_role, disability,
    exigir_marca_especifica_sem_padronizacao, 'Art. 47, I, "a" e "b"').

norma_legal('R03', administrative_tender_relation, bidding_authority_role, duty_to_act,
    incluir_clausula_matriz_de_riscos, 'Art. 42, X e Art. 69, X').

norma_legal('R09', legal_service_agreement, bidding_authority_role, duty_to_act,
    definir_regra_expressa_subcontratacao, 'Art. 78').

norma_legal('R11', administrative_tender_relation, bidding_authority_role, disability,
    exigir_amostra_de_todos_licitantes_na_proposta, 'Art. 47, II').

norma_legal('R29', administrative_tender_relation, bidder_role, permission_to_act,
    comprovar_capacidade_ate_50_porcento_com_somatorio, 'Art. 58, II (Súmula 263 TCU)').

norma_legal('R38', legal_service_agreement, contracted_party_role, disability,
    celebrar_aditivo_por_risco_alocado_contratada, 'Art. 81, § 8º').

norma_legal('R41', administrative_tender_relation, bidder_role, permission_to_omit,
    apresentar_credenciamento_ou_carta_fabricante, 'Art. 31 (Competitividade)').

norma_legal('R43', administrative_tender_relation, bidding_authority_role, duty_to_act,
    motivar_formalmente_vedacao_a_consorcio, 'Art. 31 (Competitividade)').


% ------------------------------------------------------------------------------
% 2. Predicados de Inferência UFO-L (Detecção de Conflitos e Omissões)
% ------------------------------------------------------------------------------

% Verifica se o momento jurídico instanciado pelo Edital é o Oposto Hohfeldiano
% do momento assegurado pela Lei 13.303 (ex: duty_to_act vs permission_to_omit)
conflito_hohfeldiano(MomentoEdital, MomentoLei, PoloCorrelatoLei) :-
    opposite_moment(MomentoEdital, MomentoLei),
    correlative_moment(MomentoLei, PoloCorrelatoLei).

% ------------------------------------------------------------------------------
% 3. Regras de Avaliação Deôntica por Regra da Lei 13.303
% ------------------------------------------------------------------------------
% avaliar_regra(Edital, RegraID, Status, TipoInferenciaUfoL, PapelAfetado,
%               MomentoEdital, MomentoLei, EvidenciaId)

% --- R01: Menção de marca nominal sem cláusula "ou similar" ---
avaliar_regra(Edital, 'R01', 'Indício de Inconformidade',
              conflito_hohfeldiano(duty_to_omit, permission_to_act, no_right_to_omission),
              bidder_role, duty_to_omit, permission_to_act, Item) :-
    mencao_marca_exigida(Edital, _Marca, sem_clausula_similaridade, sem_justificativa_padronizacao, Item, _Trecho),
    opposite_moment(duty_to_omit, permission_to_act).

avaliar_regra(Edital, 'R01', 'Conforme',
              harmonia_normativa(permission_to_act, no_right_to_omission),
              bidder_role, permission_to_act, permission_to_act, Item) :-
    \+ mencao_marca_exigida(Edital, _, sem_clausula_similaridade, sem_justificativa_padronizacao, _, _),
    evidencia_regra(Edital, 'R01', Item, _Trecho).

% --- R02: Indicação de marca/modelo sem justificativa formal de padronização ---
avaliar_regra(Edital, 'R02', 'Indício de Inconformidade',
              conflito_hohfeldiano(power, disability, immunity),
              bidding_authority_role, power, disability, Item) :-
    mencao_marca_exigida(Edital, _Marca, sem_clausula_similaridade, sem_justificativa_padronizacao, Item, _Trecho),
    opposite_moment(power, disability).

avaliar_regra(Edital, 'R02', 'Conforme',
              harmonia_normativa(disability, immunity),
              bidding_authority_role, disability, disability, Item) :-
    \+ mencao_marca_exigida(Edital, _, sem_clausula_similaridade, sem_justificativa_padronizacao, _, _),
    evidencia_regra(Edital, 'R02', Item, _Trecho).

% --- R03: Matriz de Riscos Obrigatória ---
avaliar_regra(Edital, 'R03', 'Indício de Inconformidade',
              violacao_dever_legal(bidding_authority_role, duty_to_act, permission_to_omit),
              bidding_authority_role, permission_to_omit, duty_to_act, Item) :-
    fato_matriz_riscos(Edital, ausente, Item, _Trecho),
    opposite_moment(duty_to_act, permission_to_omit).

avaliar_regra(Edital, 'R03', 'Conforme',
              cumprimento_dever_legal(bidding_authority_role, duty_to_act, right_to_action),
              bidding_authority_role, duty_to_act, duty_to_act, Item) :-
    fato_matriz_riscos(Edital, presente, Item, _Trecho),
    correlative_moment(right_to_action, duty_to_act).

% --- R38: Vedação de Aditivos decorrentes de riscos alocados ao Contratado ---
avaliar_regra(Edital, 'R38', 'Indício de Inconformidade',
              conflito_hohfeldiano(power, disability, immunity),
              contracted_party_role, power, disability, Item) :-
    fato_vedacao_aditivo_risco(Edital, ausente, Item, _Trecho),
    opposite_moment(power, disability).

avaliar_regra(Edital, 'R38', 'Conforme',
              harmonia_normativa(disability, immunity),
              contracted_party_role, disability, disability, Item) :-
    fato_vedacao_aditivo_risco(Edital, presente, Item, _Trecho),
    correlative_moment(immunity, disability).

% --- R09: Definição expressa sobre Subcontratação ---
avaliar_regra(Edital, 'R09', 'Indício de Inconformidade',
              violacao_dever_legal(bidding_authority_role, duty_to_act, permission_to_omit),
              bidding_authority_role, permission_to_omit, duty_to_act, Item) :-
    fato_subcontratacao(Edital, omissa, Item, _Trecho),
    opposite_moment(duty_to_act, permission_to_omit).

avaliar_regra(Edital, 'R09', 'Conforme',
              cumprimento_dever_legal(bidding_authority_role, duty_to_act, right_to_action),
              bidding_authority_role, duty_to_act, duty_to_act, Item) :-
    fato_subcontratacao(Edital, definida, Item, _Trecho),
    correlative_moment(right_to_action, duty_to_act).

% --- R11: Momento de exigência de Amostra / Prova de Conceito ---
avaliar_regra(Edital, 'R11', 'Indício de Inconformidade',
              conflito_hohfeldiano(power, disability, immunity),
              bidding_authority_role, power, disability, Item) :-
    fato_amostra(Edital, todos_licitantes_fase_proposta, Item, _Trecho),
    opposite_moment(power, disability).

avaliar_regra(Edital, 'R11', 'Conforme',
              harmonia_normativa(disability, immunity),
              bidding_authority_role, disability, disability, Item) :-
    fato_amostra(Edital, apenas_primeiro_colocado, Item, _Trecho),
    correlative_moment(immunity, disability).

avaliar_regra(Edital, 'R11', 'Conforme',
              harmonia_normativa(disability, immunity),
              bidding_authority_role, disability, disability, Item) :-
    fato_amostra(Edital, nao_exigida, Item, _Trecho),
    correlative_moment(immunity, disability).

% --- R29: Quantitativo de Atestado (>50%) ou Vedação ao Somatório sem Justificativa ---
avaliar_regra(Edital, 'R29', 'Indício de Inconformidade',
              conflito_hohfeldiano(duty_to_omit, permission_to_act, no_right_to_omission),
              bidder_role, duty_to_omit, permission_to_act, Item) :-
    fato_atestado_capacidade(Edital, Percentual, _VedaSomatorio, _JustificativaSomatorio, Item, _Trecho),
    Percentual > 50,
    opposite_moment(duty_to_omit, permission_to_act).

avaliar_regra(Edital, 'R29', 'Indício de Inconformidade',
              conflito_hohfeldiano(duty_to_omit, permission_to_act, no_right_to_omission),
              bidder_role, duty_to_omit, permission_to_act, Item) :-
    fato_atestado_capacidade(Edital, Percentual, veda_somatorio, sem_justificativa, Item, _Trecho),
    Percentual =< 50,
    opposite_moment(duty_to_omit, permission_to_act).

avaliar_regra(Edital, 'R29', 'Conforme',
              harmonia_normativa(permission_to_act, no_right_to_omission),
              bidder_role, permission_to_act, permission_to_act, Item) :-
    fato_atestado_capacidade(Edital, Percentual, permite_somatorio, _, Item, _Trecho),
    Percentual =< 50,
    correlative_moment(permission_to_act, no_right_to_omission).

avaliar_regra(Edital, 'R29', 'Conforme',
              harmonia_normativa(permission_to_act, no_right_to_omission),
              bidder_role, permission_to_act, permission_to_act, Item) :-
    fato_atestado_capacidade(Edital, Percentual, veda_somatorio, com_justificativa, Item, _Trecho),
    Percentual =< 50,
    correlative_moment(permission_to_act, no_right_to_omission).

% --- R41: Exigência de Credenciamento / Revenda Autorizada / Carta do Fabricante ---
avaliar_regra(Edital, 'R41', 'Indício de Inconformidade',
              conflito_hohfeldiano(duty_to_act, permission_to_omit, no_right_to_action),
              bidder_role, duty_to_act, permission_to_omit, Item) :-
    fato_credenciamento_fabricante(Edital, exigido, Item, _Trecho),
    opposite_moment(duty_to_act, permission_to_omit).

avaliar_regra(Edital, 'R41', 'Conforme',
              harmonia_normativa(permission_to_omit, no_right_to_action),
              bidder_role, permission_to_omit, permission_to_omit, Item) :-
    fato_credenciamento_fabricante(Edital, nao_exigido, Item, _Trecho),
    correlative_moment(permission_to_omit, no_right_to_action).

% --- R43: Vedação à participação de Consórcio sem justificativa formal ---
avaliar_regra(Edital, 'R43', 'Indício de Inconformidade',
              violacao_dever_legal(bidding_authority_role, duty_to_act, permission_to_omit),
              bidding_authority_role, permission_to_omit, duty_to_act, Item) :-
    fato_consorcio(Edital, vedado, sem_justificativa, Item, _Trecho),
    opposite_moment(duty_to_act, permission_to_omit).

avaliar_regra(Edital, 'R43', 'Conforme',
              cumprimento_dever_legal(bidding_authority_role, duty_to_act, right_to_action),
              bidding_authority_role, duty_to_act, duty_to_act, Item) :-
    fato_consorcio(Edital, vedado, com_justificativa, Item, _Trecho),
    correlative_moment(right_to_action, duty_to_act).

avaliar_regra(Edital, 'R43', 'Conforme',
              harmonia_normativa(permission_to_act, no_right_to_omission),
              bidder_role, permission_to_act, permission_to_act, Item) :-
    fato_consorcio(Edital, permitido, _, Item, _Trecho),
    correlative_moment(permission_to_act, no_right_to_omission).

