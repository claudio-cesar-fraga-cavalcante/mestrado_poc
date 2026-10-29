% ==============================================================================
% UFO-L: Legal Core Ontology (Axiomatized in ISO/SWI-Prolog)
% ==============================================================================
% Theoretical Foundation:
% - Griffo, C., Almeida, J. P. A., & Guizzardi, G. (2015, 2017, 2018).
%   "UFO-L: Uma Ontologia Núcleo de Aspectos Jurídicos Construída sob a
%   Perspectiva das Relações Jurídicas" (Ph.D. Thesis, UFES / NEMO).
% - Wesley Newcomb Hohfeld (1913, 1917): Fundamental Legal Conceptions.
% - Robert Alexy (1985): A Theory of Constitutional Rights (Relational Model).
% ==============================================================================

% ------------------------------------------------------------------------------
% 1. Class Declarations (UFO Foundational & UFO-L Core Categories)
% ------------------------------------------------------------------------------

% Top-Level / Foundational (UFO-A / UFO-C)
class(entity).
class(endurant).
class(agent).
class(physical_agent).
class(social_agent).
class(collective_social_agent).
class(juridical_person).
class(role).
class(relator).
class(moment).
class(extrinsic_moment).
class(action).
class(action_type).

% Legal Core Entities (UFO-L)
class(legal_subject).
class(legal_role).
class(legal_relator).
class(legal_relation).
class(bilateral_legal_relation).
class(administrative_legal_relation).
class(legal_service_agreement).
class(administrative_tender_relation).
class(normative_description).
class(legal_norm).
class(legal_object).

% Legal Roles
class(contracting_party_role).
class(contracted_party_role).
class(service_customer_role).
class(hired_service_provider_role).
class(bidding_authority_role).
class(bidder_role).
class(contract_manager_role).
class(contract_inspector_role).

% Legal Moment Taxonomy (Hohfeld / Alexy / UFO-L)
class(legal_moment).
class(legal_entitlement).
class(legal_burden).

% The 12 Hohfeldian Legal Moments admitted by UFO-L:
% 1. Claim-Duty Positions (Ação e Omissão)
class(right_to_action).
class(duty_to_act).
class(right_to_omission).
class(duty_to_omit).

% 2. Liberty-NoRight Positions (Permissões e Não-Direitos)
class(permission_to_act).
class(no_right_to_omission).
class(permission_to_omit).
class(no_right_to_action).

% 3. Power-Subjection Positions (Poderes Formativos e Sujeições)
class(power).
class(subjection).

% 4. Immunity-Disability Positions (Imunidades e Incompetências)
class(immunity).
class(disability).


% ------------------------------------------------------------------------------
% 2. Taxonomic Axioms (subclass_of/2)
% ------------------------------------------------------------------------------

% Agents and Subjects
subclass_of(agent, entity).
subclass_of(physical_agent, agent).
subclass_of(social_agent, agent).
subclass_of(collective_social_agent, social_agent).
subclass_of(juridical_person, collective_social_agent).
subclass_of(legal_subject, agent).

% Roles
subclass_of(role, entity).
subclass_of(legal_role, role).
subclass_of(contracting_party_role, legal_role).
subclass_of(contracted_party_role, legal_role).
subclass_of(service_customer_role, contracting_party_role).
subclass_of(hired_service_provider_role, contracted_party_role).
subclass_of(bidding_authority_role, legal_role).
subclass_of(bidder_role, legal_role).
subclass_of(contract_manager_role, legal_role).
subclass_of(contract_inspector_role, legal_role).

% Relators and Relations
subclass_of(relator, endurant).
subclass_of(legal_relator, relator).
subclass_of(legal_relation, entity).
subclass_of(bilateral_legal_relation, legal_relation).
subclass_of(administrative_legal_relation, legal_relation).
subclass_of(legal_service_agreement, legal_relator).
subclass_of(administrative_tender_relation, legal_relator).

% Legal Moments
subclass_of(moment, entity).
subclass_of(extrinsic_moment, moment).
subclass_of(legal_moment, extrinsic_moment).

% Entitlements (Polo Ativo / Vantagem Jurídica)
subclass_of(legal_entitlement, legal_moment).
subclass_of(right_to_action, legal_entitlement).
subclass_of(right_to_omission, legal_entitlement).
subclass_of(permission_to_act, legal_entitlement).
subclass_of(permission_to_omit, legal_entitlement).
subclass_of(power, legal_entitlement).
subclass_of(immunity, legal_entitlement).

% Burdens (Polo Passivo / Encargo Jurídico)
subclass_of(legal_burden, legal_moment).
subclass_of(duty_to_act, legal_burden).
subclass_of(duty_to_omit, legal_burden).
subclass_of(no_right_to_action, legal_burden).
subclass_of(no_right_to_omission, legal_burden).
subclass_of(subjection, legal_burden).
subclass_of(disability, legal_burden).


% ------------------------------------------------------------------------------
% 3. Hohfeldian Correlatives (hohfeldian_correlative/2)
% ------------------------------------------------------------------------------
% In UFO-L, legal relations are strictly relational: every entitlement in party A
% has an inherent, legally correlative burden in party B.

% Claim <-> Duty
hohfeldian_correlative(right_to_action, duty_to_act).
hohfeldian_correlative(right_to_omission, duty_to_omit).

% Liberty/Permission <-> No-Right
hohfeldian_correlative(permission_to_act, no_right_to_omission).
hohfeldian_correlative(permission_to_omit, no_right_to_action).

% Power <-> Subjection
hohfeldian_correlative(power, subjection).

% Immunity <-> Disability
hohfeldian_correlative(immunity, disability).


% ------------------------------------------------------------------------------
% 4. Hohfeldian Opposites (hohfeldian_opposite/2)
% ------------------------------------------------------------------------------
% A single party cannot hold mutually contradictory legal positions regarding
% the same action at the same time.

hohfeldian_opposite(right_to_action, no_right_to_action).
hohfeldian_opposite(right_to_omission, no_right_to_omission).
hohfeldian_opposite(duty_to_act, permission_to_omit).
hohfeldian_opposite(duty_to_omit, permission_to_act).
hohfeldian_opposite(power, disability).
hohfeldian_opposite(subjection, immunity).


% ------------------------------------------------------------------------------
% 5. Relational Consistency & Inference Rules
% ------------------------------------------------------------------------------

% Transitive subclass reasoning
is_subclass(X, X).
is_subclass(X, Y) :- subclass_of(X, Z), is_subclass(Z, Y).

% Check if a given class is a valid UFO-L Legal Moment
is_legal_moment(Class) :- is_subclass(Class, legal_moment), Class \= legal_moment, Class \= legal_entitlement, Class \= legal_burden.

% Check if a given class is an entitlement
is_entitlement(Class) :- is_subclass(Class, legal_entitlement), Class \= legal_entitlement.

% Check if a given class is a burden
is_burden(Class) :- is_subclass(Class, legal_burden), Class \= legal_burden.

% Bidirectional correlative query
correlative_moment(M1, M2) :- hohfeldian_correlative(M1, M2).
correlative_moment(M1, M2) :- hohfeldian_correlative(M2, M1).

% Bidirectional opposite query
opposite_moment(M1, M2) :- hohfeldian_opposite(M1, M2).
opposite_moment(M1, M2) :- hohfeldian_opposite(M2, M1).

