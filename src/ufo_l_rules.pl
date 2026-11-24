% ==============================================================================
% Regras Deônticas e Normativas da Lei 13.303/2016 fundamentadas na UFO-L
% ==============================================================================
% Este módulo estende dados/UFO_L.pl conectando as normas da Lei das Estatais
% (Lei 13.303/2016) às posições jurídicas de Hohfeld/Alexy (UFO-L) e aos fatos
% positivos extraídos de cada Edital (ABox). Omissões são inferidas sob a
% Hipótese do Mundo Fechado (Closed-World Assumption) via Negação por Falha (\+).
% ==============================================================================

:- discontiguous norma_legal/6.
:- discontiguous posicao_edital/6.
:- discontiguous avaliar_regra/8.
:- discontiguous evidencia_regra/4.

:- dynamic mencao_marca_exigida/7.
:- dynamic fato_matriz_riscos/3.
:- dynamic fato_vedacao_aditivo_risco/3.
:- dynamic fato_subcontratacao_definida/3.
:- dynamic fato_amostra/4.
:- dynamic fato_atestado_percentual/4.
:- dynamic fato_veda_somatorio/3.
:- dynamic fato_justificativa_vedacao_somatorio/3.
:- dynamic fato_credenciamento_exigido/3.
:- dynamic fato_veda_consorcio/3.
:- dynamic fato_justificativa_vedacao_consorcio/3.
:- dynamic evidencia_regra/4.

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

norma_legal('R09', legal_service_agreement, contracting_party_role, duty_to_act,
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
% 2. Instanciação das Posições Jurídicas Efetivas do Edital (com Mundo Fechado \+)
% ------------------------------------------------------------------------------
% posicao_edital(Edital, RegraID, PapelAfetado, MomentoEdital, MotivoFactual, EvidenciaId)

% --- R01: Proteção de 1ª Ordem ao Licitante (cláusula "ou similar" sobre o objeto licitado) ---
posicao_edital(Edital, 'R01', bidder_role, duty_to_omit, marca_sem_similaridade, Item) :-
    mencao_marca_exigida(Edital, _Marca, objeto_licitado, sem_clausula_similaridade, sem_justificativa_padronizacao, Item, _Trecho).

posicao_edital(Edital, 'R01', bidder_role, permission_to_act, equivalencia_ou_contexto_legitimo, Item) :-
    \+ mencao_marca_exigida(Edital, _, objeto_licitado, sem_clausula_similaridade, sem_justificativa_padronizacao, _, _),
    evidencia_regra(Edital, 'R01', Item, _Trecho).

% --- R02: Incompetência da Estatal para exigir marca do objeto sem processo de padronização ---
posicao_edital(Edital, 'R02', bidding_authority_role, power, marca_sem_padronizacao, Item) :-
    mencao_marca_exigida(Edital, _Marca, objeto_licitado, sem_clausula_similaridade, sem_justificativa_padronizacao, Item, _Trecho).

posicao_edital(Edital, 'R02', bidding_authority_role, disability, padronizacao_ou_contexto_legitimo, Item) :-
    \+ mencao_marca_exigida(Edital, _, objeto_licitado, sem_clausula_similaridade, sem_justificativa_padronizacao, _, _),
    evidencia_regra(Edital, 'R02', Item, _Trecho).

% --- R03: Matriz de Riscos Obrigatória (Omissão detectada via NAF \+) ---
posicao_edital(Edital, 'R03', bidding_authority_role, permission_to_omit, omissao_matriz_riscos, Item) :-
    \+ fato_matriz_riscos(Edital, _, _),
    evidencia_regra(Edital, 'R03', Item, _Trecho).

posicao_edital(Edital, 'R03', bidding_authority_role, duty_to_act, matriz_riscos_presente, Item) :-
    fato_matriz_riscos(Edital, Item, _Trecho).

% --- R38: Vedação de Aditivos por riscos alocados à Contratada (Omissão via NAF \+) ---
posicao_edital(Edital, 'R38', contracted_party_role, power, omissao_vedacao_aditivo, Item) :-
    \+ fato_vedacao_aditivo_risco(Edital, _, _),
    evidencia_regra(Edital, 'R38', Item, _Trecho).

posicao_edital(Edital, 'R38', contracted_party_role, disability, vedacao_aditivo_presente, Item) :-
    fato_vedacao_aditivo_risco(Edital, Item, _Trecho).

% --- R09: Definição expressa sobre Subcontratação (Omissão via NAF \+) ---
posicao_edital(Edital, 'R09', contracting_party_role, permission_to_omit, omissao_subcontratacao, Item) :-
    \+ fato_subcontratacao_definida(Edital, _, _),
    evidencia_regra(Edital, 'R09', Item, _Trecho).

posicao_edital(Edital, 'R09', contracting_party_role, duty_to_act, subcontratacao_definida, Item) :-
    fato_subcontratacao_definida(Edital, Item, _Trecho).

% --- R11: Momento de exigência de Amostra / Prova de Conceito ---
posicao_edital(Edital, 'R11', bidding_authority_role, power, amostra_todos_proposta, Item) :-
    fato_amostra(Edital, todos_licitantes_fase_proposta, Item, _Trecho).

posicao_edital(Edital, 'R11', bidding_authority_role, disability, amostra_restrita_primeiro_colocado, Item) :-
    fato_amostra(Edital, apenas_primeiro_colocado, Item, _Trecho).

posicao_edital(Edital, 'R11', bidding_authority_role, disability, amostra_nao_exigida, Item) :-
    fato_amostra(Edital, nao_exigida, Item, _Trecho).

% --- R29: Quantitativo de Atestado (>50%) ou Vedação ao Somatório sem Justificativa ---
posicao_edital(Edital, 'R29', bidder_role, duty_to_omit, percentual_acima_50, Item) :-
    fato_atestado_percentual(Edital, Percentual, Item, _Trecho),
    Percentual > 50.

posicao_edital(Edital, 'R29', bidder_role, duty_to_omit, veda_somatorio_sem_justificativa, Item) :-
    fato_atestado_percentual(Edital, Percentual, _ItemPct, _TrechoPct),
    Percentual =< 50,
    fato_veda_somatorio(Edital, Item, _TrechoSom),
    \+ fato_justificativa_vedacao_somatorio(Edital, _, _).

posicao_edital(Edital, 'R29', bidder_role, permission_to_act, atestado_conforme, Item) :-
    fato_atestado_percentual(Edital, Percentual, Item, _Trecho),
    Percentual =< 50,
    \+ fato_veda_somatorio(Edital, _, _).

posicao_edital(Edital, 'R29', bidder_role, permission_to_act, vedacao_somatorio_justificada, Item) :-
    fato_atestado_percentual(Edital, Percentual, Item, _Trecho),
    Percentual =< 50,
    fato_veda_somatorio(Edital, _, _),
    fato_justificativa_vedacao_somatorio(Edital, _, _).

% --- R41: Credenciamento / Revenda Autorizada / Carta do Fabricante ---
posicao_edital(Edital, 'R41', bidder_role, duty_to_act, credenciamento_fabricante_exigido, Item) :-
    fato_credenciamento_exigido(Edital, Item, _Trecho).

posicao_edital(Edital, 'R41', bidder_role, permission_to_omit, sem_exigencia_credenciamento, Item) :-
    \+ fato_credenciamento_exigido(Edital, _, _),
    evidencia_regra(Edital, 'R41', Item, _Trecho).

% --- R43: Participação em Consórcio e Dever de Motivação (via NAF \+) ---
posicao_edital(Edital, 'R43', bidding_authority_role, permission_to_omit, veda_consorcio_sem_justificativa, Item) :-
    fato_veda_consorcio(Edital, Item, _Trecho),
    \+ fato_justificativa_vedacao_consorcio(Edital, _, _).

posicao_edital(Edital, 'R43', bidding_authority_role, duty_to_act, veda_consorcio_justificada, Item) :-
    fato_veda_consorcio(Edital, Item, _Trecho),
    fato_justificativa_vedacao_consorcio(Edital, _, _).

posicao_edital(Edital, 'R43', bidding_authority_role, duty_to_act, consorcio_permitido, Item) :-
    \+ fato_veda_consorcio(Edital, _, _),
    evidencia_regra(Edital, 'R43', Item, _Trecho).


% ------------------------------------------------------------------------------
% 3. Predicados Gerais de Inferência Deôntica sobre a Ontologia UFO-L
% ------------------------------------------------------------------------------

% Deriva conflito hohfeldiano verificando oposição contraditória e correlato bilateral
conflito_hohfeldiano(MomentoEdital, MomentoLei, PoloCorrelatoLei) :-
    opposite_moment(MomentoEdital, MomentoLei),
    correlative_moment(MomentoLei, PoloCorrelatoLei).

% Deriva harmonia normativa verificando identidade de posição e correlato bilateral
harmonia_normativa_ufol(MomentoEdital, MomentoLei, PoloCorrelatoLei) :-
    MomentoEdital = MomentoLei,
    correlative_moment(MomentoLei, PoloCorrelatoLei).


% ------------------------------------------------------------------------------
% 4. Avaliador Genérico Unificado UFO-L (sem constantes chumbadas)
% ------------------------------------------------------------------------------
% avaliar_regra(Edital, RegraID, Status, TipoInferenciaUfoL, PapelAfetado,
%               MomentoEdital, MomentoLei, EvidenciaId)

avaliar_regra(Edital, RegraID, 'Indício de Inconformidade',
              conflito_hohfeldiano(Motivo, MomEdital, MomLei, CorrelatoLei),
              Papel, MomEdital, MomLei, Item) :-
    norma_legal(RegraID, _Relacao, Papel, MomLei, _Acao, _Dispositivo),
    posicao_edital(Edital, RegraID, Papel, MomEdital, Motivo, Item),
    is_subclass(Papel, legal_role),
    is_legal_moment(MomEdital),
    is_legal_moment(MomLei),
    conflito_hohfeldiano(MomEdital, MomLei, CorrelatoLei).

avaliar_regra(Edital, RegraID, 'Conforme',
              harmonia_normativa(Motivo, MomEdital, CorrelatoLei),
              Papel, MomEdital, MomLei, Item) :-
    norma_legal(RegraID, _Relacao, Papel, MomLei, _Acao, _Dispositivo),
    posicao_edital(Edital, RegraID, Papel, MomEdital, Motivo, Item),
    is_subclass(Papel, legal_role),
    is_legal_moment(MomEdital),
    is_legal_moment(MomLei),
    harmonia_normativa_ufol(MomEdital, MomLei, CorrelatoLei).
