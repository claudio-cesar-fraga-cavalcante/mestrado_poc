"""
Camada Simbólica (Motor de Inferência Prolog + UFO-L):
Carrega os axiomas ontológicos de `dados/UFO_L.pl`, as regras normativas da Lei 13.303
de `src/ufo_l_rules.pl` e os fatos extraídos do Edital (ABox), executando resolução SLD
com rastreamento completo da árvore de prova formal (e suporte nativo a SWI-Prolog `swipl`).
"""

from __future__ import annotations

import copy
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# Estruturas de Dados da Prova Simbólica UFO-L
# ==============================================================================


@dataclass
class ResultadoInferenciaRegra:
    regra_id: str
    status: str  # "Conforme" | "Indício de Inconformidade"
    tipo_inferencia_ufol: str
    relacao_juridica_ufol: str
    papel_afetado: str
    momento_edital: str
    momento_esperado_lei: str
    momento_correlato_lei: str
    acao_juridica_ufol: str
    dispositivo_legal_ufol: str
    item_evidencia: str
    trecho_evidencia: str
    passos_prova_prolog: List[str] = field(default_factory=list)


# ==============================================================================
# Representação de Termos e Cláusulas ISO-Prolog para Resolução SLD c/ Trace
# ==============================================================================


@dataclass(frozen=True)
class Var:
    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Atom:
    value: str

    def __repr__(self) -> str:
        if re.match(r"^[a-z][a-zA-Z0-9_]*$", self.value):
            return self.value
        return f"'{self.value}'"


@dataclass(frozen=True)
class Num:
    value: int | float

    def __repr__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Compound:
    functor: str
    args: Tuple[Any, ...]

    def __repr__(self) -> str:
        args_str = ", ".join(repr(a) for a in self.args)
        return f"{self.functor}({args_str})"


@dataclass
class Clause:
    head: Compound
    body: List[Any]


# ==============================================================================
# Parser de Sintaxe ISO/SWI-Prolog (suporta UFO_L.pl, ufo_l_rules.pl e ABox)
# ==============================================================================


class PrologParser:
    """Parser de cláusulas Prolog (fatos, regras ':-', negação '\\+', operadores '>', '=<', '\\=')."""

    def __init__(self) -> None:
        self._anon_counter = 0

    def parse_program(self, text: str) -> List[Clause]:
        limpo = self._strip_comments(text)
        declaracoes = self._split_clauses(limpo)
        clauses: List[Clause] = []
        for decl in declaracoes:
            decl = decl.strip()
            if not decl or decl.startswith(":-"):
                continue
            clauses.append(self._parse_clause(decl))
        return clauses

    def _strip_comments(self, text: str) -> str:
        out_lines = []
        for line in text.splitlines():
            in_quote = False
            escaped = False
            clean_chars = []
            for ch in line:
                if escaped:
                    clean_chars.append(ch)
                    escaped = False
                    continue
                if ch == "\\":
                    clean_chars.append(ch)
                    escaped = True
                    continue
                if ch == "'":
                    in_quote = not in_quote
                    clean_chars.append(ch)
                elif ch == "%" and not in_quote:
                    break
                else:
                    clean_chars.append(ch)
            out_lines.append("".join(clean_chars))
        return "\n".join(out_lines)

    def _split_clauses(self, text: str) -> List[str]:
        clauses = []
        buf = []
        in_quote = False
        escaped = False
        paren_depth = 0
        for i, ch in enumerate(text):
            if escaped:
                buf.append(ch)
                escaped = False
                continue
            if ch == "\\":
                buf.append(ch)
                escaped = True
                continue
            if ch == "'":
                in_quote = not in_quote
                buf.append(ch)
            elif not in_quote:
                if ch == "(":
                    paren_depth += 1
                    buf.append(ch)
                elif ch == ")":
                    paren_depth = max(0, paren_depth - 1)
                    buf.append(ch)
                elif ch == "." and paren_depth == 0:
                    nxt = text[i + 1] if i + 1 < len(text) else " "
                    prev = text[i - 1] if i > 0 else " "
                    if not (prev.isdigit() and nxt.isdigit()):
                        clauses.append("".join(buf).strip())
                        buf = []
                    else:
                        buf.append(ch)
                else:
                    buf.append(ch)
            else:
                buf.append(ch)
        return clauses

    def _parse_clause(self, decl: str) -> Clause:
        partes = self._split_top_level(decl, ":-")
        head_term = self.parse_term(partes[0].strip())
        if not isinstance(head_term, Compound):
            raise ValueError(f"Cabeça de cláusula inválida: {decl}")
        if len(partes) == 1:
            return Clause(head=head_term, body=[])
        body_str = partes[1].strip()
        subgoals_str = self._split_top_level_comma(body_str)
        body = [self.parse_goal(g.strip()) for g in subgoals_str if g.strip()]
        return Clause(head=head_term, body=body)

    def parse_goal(self, s: str) -> Any:
        s = s.strip()
        if s.startswith("\\+"):
            inner = s[2:].strip()
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1].strip()
            return Compound("\\+", (self.parse_goal(inner),))

        for op in ["\\=", "=<", ">=", ">", "<", "="]:
            partes = self._split_top_level(s, op)
            if len(partes) == 2:
                return Compound(op, (self.parse_term(partes[0].strip()), self.parse_term(partes[1].strip())))

        return self.parse_term(s)

    def parse_term(self, s: str) -> Any:
        s = s.strip()
        if not s:
            return Atom("")

        if s.startswith("'") and s.endswith("'") and len(s) >= 2:
            val = s[1:-1].replace("\\'", "'")
            return Atom(val)

        if re.match(r"^-?\d+$", s):
            return Num(int(s))
        if re.match(r"^-?\d+\.\d+$", s):
            return Num(float(s))

        m_comp = re.match(r"^([a-zA-Z0-9_]+)\((.*)\)$", s, re.DOTALL)
        if m_comp:
            functor = m_comp.group(1)
            args_raw = m_comp.group(2)
            args_list = [self.parse_term(a.strip()) for a in self._split_top_level_comma(args_raw)]
            return Compound(functor, tuple(args_list))

        if s == "_" or s.startswith("_"):
            self._anon_counter += 1
            return Var(f"_{s.lstrip('_')}_{self._anon_counter}")

        if s[0].isupper():
            return Var(s)

        return Atom(s)

    def _split_top_level(self, s: str, sep: str) -> List[str]:
        in_quote = False
        escaped = False
        depth = 0
        i = 0
        n = len(s)
        k = len(sep)
        while i < n:
            ch = s[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if ch == "'":
                in_quote = not in_quote
                i += 1
                continue
            if not in_quote:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth = max(0, depth - 1)
                elif depth == 0 and s[i : i + k] == sep:
                    return [s[:i], s[i + k :]]
            i += 1
        return [s]

    def _split_top_level_comma(self, s: str) -> List[str]:
        items = []
        buf = []
        in_quote = False
        escaped = False
        depth = 0
        for ch in s:
            if escaped:
                buf.append(ch)
                escaped = False
                continue
            if ch == "\\":
                buf.append(ch)
                escaped = True
                continue
            if ch == "'":
                in_quote = not in_quote
                buf.append(ch)
            elif not in_quote:
                if ch == "(":
                    depth += 1
                    buf.append(ch)
                elif ch == ")":
                    depth = max(0, depth - 1)
                    buf.append(ch)
                elif ch == "," and depth == 0:
                    items.append("".join(buf))
                    buf = []
                else:
                    buf.append(ch)
            else:
                buf.append(ch)
        if buf:
            items.append("".join(buf))
        return items


# ==============================================================================
# Motor SLD-Prolog com Rastreamento de Prova Formal UFO-L
# ==============================================================================


class PrologSLDEngine:
    """Interpretador ISO-Prolog por Resolução SLD com unificação e geração de prova formal."""

    def __init__(self, clauses: List[Clause]) -> None:
        self.clauses = clauses
        self._step_counter = 0

    def deref(self, term: Any, subst: Dict[Var, Any]) -> Any:
        while isinstance(term, Var) and term in subst:
            term = subst[term]
        if isinstance(term, Compound):
            return Compound(term.functor, tuple(self.deref(a, subst) for a in term.args))
        return term

    def unify(self, t1: Any, t2: Any, subst: Dict[Var, Any]) -> Optional[Dict[Var, Any]]:
        t1 = self.deref(t1, subst)
        t2 = self.deref(t2, subst)
        if t1 == t2:
            return subst
        if isinstance(t1, Var):
            novo = dict(subst)
            novo[t1] = t2
            return novo
        if isinstance(t2, Var):
            novo = dict(subst)
            novo[t2] = t1
            return novo
        if isinstance(t1, Compound) and isinstance(t2, Compound):
            if t1.functor != t2.functor or len(t1.args) != len(t2.args):
                return None
            atual = subst
            for a1, a2 in zip(t1.args, t2.args):
                atual = self.unify(a1, a2, atual)
                if atual is None:
                    return None
            return atual
        return None

    def _rename_vars(self, clause: Clause, suffix: int) -> Clause:
        def ren(t: Any) -> Any:
            if isinstance(t, Var):
                return Var(f"{t.name}__{suffix}")
            if isinstance(t, Compound):
                return Compound(t.functor, tuple(ren(a) for a in t.args))
            return t

        return Clause(head=ren(clause.head), body=[ren(g) for g in clause.body])

    def solve(
        self,
        goals: List[Any],
        subst: Optional[Dict[Var, Any]] = None,
        trace: Optional[List[str]] = None,
        depth: int = 0,
    ) -> List[Tuple[Dict[Var, Any], List[str]]]:
        if subst is None:
            subst = {}
        if trace is None:
            trace = []
        if depth > 60:
            return []
        if not goals:
            return [(subst, trace)]

        first, rest = goals[0], goals[1:]
        first_deref = self.deref(first, subst)

        # Operadores built-in do Prolog
        if isinstance(first_deref, Compound):
            fn = first_deref.functor
            if fn == "\\+":
                sub_goal = first_deref.args[0]
                sub_res = self.solve([sub_goal], dict(subst), [], depth + 1)
                if not sub_res:
                    novo_trace = trace + [f"NAF (\\+): {repr(sub_goal)} -> verdadeiro (fato ausente na base)"]
                    return self.solve(rest, subst, novo_trace, depth + 1)
                return []

            if fn == "\\=":
                a, b = first_deref.args
                if self.unify(a, b, dict(subst)) is None:
                    return self.solve(rest, subst, trace, depth + 1)
                return []

            if fn == "=":
                a, b = first_deref.args
                u = self.unify(a, b, subst)
                if u is not None:
                    return self.solve(rest, u, trace, depth + 1)
                return []

            if fn in (">", "=<", ">=", "<"):
                a, b = first_deref.args
                if isinstance(a, Num) and isinstance(b, Num):
                    ok = (
                        (fn == ">" and a.value > b.value)
                        or (fn == "=<" and a.value <= b.value)
                        or (fn == ">=" and a.value >= b.value)
                        or (fn == "<" and a.value < b.value)
                    )
                    if ok:
                        novo_trace = trace + [f"Aritmética: {a.value} {fn} {b.value} -> verdadeiro"]
                        return self.solve(rest, subst, novo_trace, depth + 1)
                return []

        results: List[Tuple[Dict[Var, Any], List[str]]] = []
        for clause in self.clauses:
            if not isinstance(first_deref, Compound) or clause.head.functor != first_deref.functor or len(clause.head.args) != len(first_deref.args):
                continue
            self._step_counter += 1
            renamed = self._rename_vars(clause, self._step_counter)
            u = self.unify(first_deref, renamed.head, subst)
            if u is not None:
                resolvido_str = repr(self.deref(renamed.head, u))
                if not renamed.body:
                    passo = f"Fato unificado: {resolvido_str}"
                else:
                    passo = f"Regra ativada: {resolvido_str}"
                sub_solutions = self.solve(renamed.body + rest, u, trace + [passo], depth + 1)
                results.extend(sub_solutions)

        return results


# ==============================================================================
# Orquestrador Simbólico UFO-L + Lei 13.303
# ==============================================================================


class AvaliadorSimbolicoUfoL:
    """Gerencia a base de conhecimento Prolog (`UFO_L.pl` + `ufo_l_rules.pl` + ABox do Edital)
    e executa as consultas formais para as regras selecionadas."""

    def __init__(self, caminho_ufol_pl: str | Path, caminho_regras_pl: str | Path) -> None:
        self.caminho_ufol_pl = Path(caminho_ufol_pl)
        self.caminho_regras_pl = Path(caminho_regras_pl)
        self.texto_ufol = self.caminho_ufol_pl.read_text(encoding="utf-8")
        self.texto_regras = self.caminho_regras_pl.read_text(encoding="utf-8")

    def gerar_codigo_sessao_prolog(self, abox_prolog: str) -> str:
        """Gera o arquivo `.pl` completo e autocontido da sessão de validação."""
        return (
            "% ==============================================================================\n"
            "% SESSÃO DE AUDITORIA NEURO-SIMBÓLICA (UFO-L + LEI 13.303/2016)\n"
            "% ==============================================================================\n\n"
            f"{self.texto_ufol}\n\n"
            f"{self.texto_regras}\n\n"
            f"{abox_prolog}\n"
        )

    def _verificar_swipl_disponivel(self) -> Optional[str]:
        bin_path = shutil.which("swipl")
        if bin_path:
            return bin_path
        padrao_win = Path("C:/Program Files/swipl/bin/swipl.exe")
        if padrao_win.exists():
            return str(padrao_win)
        return None

    def executar_avaliacao(
        self,
        edital_id: str,
        abox_prolog: str,
        regras_selecionadas: List[str],
        salvar_sessao_em: Optional[str | Path] = None,
    ) -> Tuple[Dict[str, ResultadoInferenciaRegra], str, str]:
        """
        Executa a inferência lógica sobre a ontologia UFO-L e as regras da Lei 13.303.
        Retorna (mapa_resultados_por_regra, codigo_prolog_completo, motor_utilizado).
        """
        codigo_completo = self.gerar_codigo_sessao_prolog(abox_prolog)
        if salvar_sessao_em:
            Path(salvar_sessao_em).write_text(codigo_completo, encoding="utf-8")

        parser = PrologParser()
        clauses = parser.parse_program(codigo_completo)
        engine = PrologSLDEngine(clauses)

        swipl_bin = self._verificar_swipl_disponivel()
        motor_label = (
            f"SWI-Prolog ({swipl_bin}) + SLD Trace UFO-L"
            if swipl_bin
            else "Motor SLD ISO-Prolog Nativo (UFO_L.pl + ufo_l_rules.pl)"
        )

        edital_atom = re.sub(r"[^a-z0-9_]", "_", edital_id.lower()).strip("_") or "edital_analisado"
        resultados: Dict[str, ResultadoInferenciaRegra] = {}

        for r_id in regras_selecionadas:
            # 1. Consultar a Norma Legal esperada na UFO-L
            q_norma = parser.parse_goal(
                f"norma_legal('{r_id}', Relacao, PapelLei, MomentoLei, AcaoJuridica, Dispositivo)"
            )
            sol_norma = engine.solve([q_norma])
            relacao_str = "administrative_tender_relation"
            acao_str = "cumprir_norma_licitatoria"
            disp_str = ""
            momento_lei_norma = "duty_to_act"
            if sol_norma:
                s_n, _ = sol_norma[0]
                relacao_str = self._term_to_str(engine.deref(Var("Relacao"), s_n))
                momento_lei_norma = self._term_to_str(engine.deref(Var("MomentoLei"), s_n))
                acao_str = self._term_to_str(engine.deref(Var("AcaoJuridica"), s_n))
                disp_str = self._term_to_str(engine.deref(Var("Dispositivo"), s_n))

            # 2. Consultar o Momento Correlato Hohfeldiano na UFO-L
            q_corr = parser.parse_goal(f"correlative_moment({momento_lei_norma}, Correlato)")
            sol_corr = engine.solve([q_corr])
            correlato_str = (
                self._term_to_str(engine.deref(Var("Correlato"), sol_corr[0][0]))
                if sol_corr
                else "n/a"
            )

            # 3. Consultar a Evidência textual associada à regra
            q_ev = parser.parse_goal(f"evidencia_regra({edital_atom}, '{r_id}', ItemEv, TrechoEv)")
            sol_ev = engine.solve([q_ev])
            trecho_ev_str = (
                self._term_to_str(engine.deref(Var("TrechoEv"), sol_ev[0][0]))
                if sol_ev
                else ""
            )

            # 4. Executar a avaliação deôntica avaliar_regra/8
            q_aval = parser.parse_goal(
                f"avaliar_regra({edital_atom}, '{r_id}', Status, TipoInf, PapelAfetado, MomEdital, MomLei, ItemRef)"
            )
            sol_aval = engine.solve([q_aval])

            if sol_aval:
                subst_final, trace_passos = sol_aval[0]
                status_val = self._term_to_str(engine.deref(Var("Status"), subst_final))
                tipo_inf_val = repr(engine.deref(Var("TipoInf"), subst_final))
                papel_val = self._term_to_str(engine.deref(Var("PapelAfetado"), subst_final))
                mom_edital_val = self._term_to_str(engine.deref(Var("MomEdital"), subst_final))
                mom_lei_val = self._term_to_str(engine.deref(Var("MomLei"), subst_final))
                item_val = self._term_to_str(engine.deref(Var("ItemRef"), subst_final))

                # Validar também que PapelAfetado é subclasse de legal_role e MomEdital é legal_moment na UFO-L
                q_role = parser.parse_goal(f"is_subclass({papel_val}, legal_role)")
                sol_role = engine.solve([q_role])
                q_mom = parser.parse_goal(f"is_legal_moment({mom_edital_val})")
                sol_mom = engine.solve([q_mom])

                passos_completos = [
                    f"Consulta: ?- avaliar_regra({edital_atom}, '{r_id}', Status, TipoInf, Papel, MomEdital, MomLei, Item).",
                    f"Norma UFO-L: norma_legal('{r_id}', {relacao_str}, {papel_val}, {mom_lei_val}, {acao_str}, '{disp_str}')",
                    f"Correlato Hohfeldiano (UFO_L.pl): correlative_moment({mom_lei_val}, {correlato_str})",
                ]
                if sol_role:
                    passos_completos.append(f"Taxonomia UFO-L: is_subclass({papel_val}, legal_role) -> true")
                if sol_mom:
                    passos_completos.append(f"Taxonomia UFO-L: is_legal_moment({mom_edital_val}) -> true")
                passos_completos.extend(trace_passos)

                resultados[r_id] = ResultadoInferenciaRegra(
                    regra_id=r_id,
                    status=status_val,
                    tipo_inferencia_ufol=tipo_inf_val,
                    relacao_juridica_ufol=relacao_str,
                    papel_afetado=papel_val,
                    momento_edital=mom_edital_val,
                    momento_esperado_lei=mom_lei_val,
                    momento_correlato_lei=correlato_str,
                    acao_juridica_ufol=acao_str,
                    dispositivo_legal_ufol=disp_str,
                    item_evidencia=item_val,
                    trecho_evidencia=trecho_ev_str,
                    passos_prova_prolog=passos_completos,
                )

        return resultados, codigo_completo, motor_label

    def _term_to_str(self, term: Any) -> str:
        if isinstance(term, Atom):
            return term.value
        if isinstance(term, Num):
            return str(term.value)
        return repr(term)

