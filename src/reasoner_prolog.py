"""
Camada Simbólica (Motor de Inferência Prolog + UFO-L):
Carrega os axiomas ontológicos de `dados/UFO_L.pl`, as regras normativas da Lei 13.303
de `src/ufo_l_rules.pl` e os fatos extraídos do Edital (ABox), executando resolução SLD
com rastreamento completo da árvore de prova formal (e suporte nativo a SWI-Prolog `swipl`).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
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
    validacao_cruzada_ok: bool = True


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
            if in_quote and ch == "\\":
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
            if in_quote and ch == "\\":
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
            if in_quote and ch == "\\":
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
        self._swipl_version_cache: Dict[str, str] = {}

    def gerar_codigo_sessao_prolog(self, abox_prolog: str) -> str:
        """Gera o arquivo `.pl` completo e autocontido da sessão de validação."""
        return (
            ":- encoding(utf8).\n"
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
        for cand in (
            Path("C:/Program Files/swipl/bin/swipl.exe"),
            Path("C:/Program Files (x86)/swipl/bin/swipl.exe"),
        ):
            if cand.exists():
                return str(cand)
        return None

    def _obter_versao_swipl(self, swipl_bin: str) -> str:
        if swipl_bin in self._swipl_version_cache:
            return self._swipl_version_cache[swipl_bin]
        versao = ""
        try:
            proc = subprocess.run(
                [swipl_bin, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            m = re.search(r"version\s+([0-9]+\.[0-9]+\.[0-9]+)", proc.stdout or proc.stderr, re.IGNORECASE)
            if m:
                versao = m.group(1)
        except Exception:
            versao = ""
        self._swipl_version_cache[swipl_bin] = versao
        return versao

    def _executar_via_swipl(
        self,
        swipl_bin: str,
        caminho_pl: Path,
        edital_atom: str,
        regras_selecionadas: List[str],
    ) -> Dict[str, dict]:
        """Executa de fato o binário oficial do SWI-Prolog (`swipl`) via subprocesso."""
        regras_pl = "[" + ",".join(f"'{r}'" for r in regras_selecionadas) + "]"
        goal = (
            "set_stream(current_output, encoding(utf8)), "
            f"Regras = {regras_pl}, "
            "forall(member(R, Regras), ("
            "(once(norma_legal(R, Rel, _PapelLei, MomLeiN, Acao, Disp)) -> true ; "
            "(Rel=administrative_tender_relation, MomLeiN=duty_to_act, Acao=cumprir_norma_licitatoria, Disp='')), "
            "(once(correlative_moment(MomLeiN, Corr)) -> true ; Corr='n/a'), "
            f"(once(evidencia_regra({edital_atom}, R, _ItemEv, TrechoEv)) -> true ; TrechoEv=''), "
            f"(once(avaliar_regra({edital_atom}, R, Status, TipoInf, Papel, MomEd, MomLei, _FirstItem)) -> ("
            f"findall(It, avaliar_regra({edital_atom}, R, Status, _, _, _, _, It), RawItens), "
            "list_to_set(RawItens, UniqItens), "
            "atomic_list_concat(UniqItens, ' | ', ItemRef), "
            "(once(is_subclass(Papel, legal_role)) -> RoleOk='true' ; RoleOk='false'), "
            "(once(is_legal_moment(MomEd)) -> MomOk='true' ; MomOk='false'), "
            "format('<<<ROW>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<SEP>>>~w<<<END>>>~n', "
            "[R, Status, TipoInf, Rel, Papel, MomEd, MomLei, Corr, Acao, Disp, ItemRef, TrechoEv, RoleOk, MomOk])"
            ") ; true)"
            "))"
        )
        proc = subprocess.run(
            [swipl_bin, "-q", "-s", str(caminho_pl), "-g", goal, "-t", "halt"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=True,
        )
        if proc.stderr and "error:" in proc.stderr.lower():
            raise RuntimeError(f"Erro SWI-Prolog: {proc.stderr.strip()}")

        saida_swipl: Dict[str, dict] = {}
        for m in re.finditer(r"<<<ROW>>>(.*?)<<<END>>>", proc.stdout, re.DOTALL):
            partes = m.group(1).split("<<<SEP>>>")
            if len(partes) != 14:
                continue
            (
                r_id,
                status,
                tipo_inf,
                rel,
                papel,
                mom_ed,
                mom_lei,
                corr,
                acao,
                disp,
                item_ref,
                trecho_ev,
                role_ok,
                mom_ok,
            ) = partes
            saida_swipl[r_id] = {
                "status": status,
                "tipo_inferencia_ufol": tipo_inf,
                "relacao_juridica_ufol": rel,
                "papel_afetado": papel,
                "momento_edital": mom_ed,
                "momento_esperado_lei": mom_lei,
                "momento_correlato_lei": corr,
                "acao_juridica_ufol": acao,
                "dispositivo_legal_ufol": disp,
                "item_evidencia": item_ref,
                "trecho_evidencia": trecho_ev,
                "role_ok": role_ok == "true",
                "mom_ok": mom_ok == "true",
            }
        return saida_swipl

    def executar_avaliacao(
        self,
        edital_id: str,
        abox_prolog: str,
        regras_selecionadas: List[str],
        salvar_sessao_em: Optional[str | Path] = None,
    ) -> Tuple[Dict[str, ResultadoInferenciaRegra], str, str]:
        """
        Executa a inferência lógica sobre a ontologia UFO-L e as regras da Lei 13.303.
        Quando o executável oficial do SWI-Prolog (`swipl`) está disponível, delega a ele
        a derivação formal dos vereditos via `subprocess`, usando o `PrologSLDEngine` para
        reconstruir a trilha passo a passo de unificações (e como fallback se `swipl` não existir).
        """
        codigo_completo = self.gerar_codigo_sessao_prolog(abox_prolog)
        edital_atom = re.sub(r"[^a-z0-9_]", "_", edital_id.lower()).strip("_") or "edital_analisado"

        temp_file_path: Optional[Path] = None
        if salvar_sessao_em:
            caminho_exec_pl = Path(salvar_sessao_em)
            caminho_exec_pl.write_text(codigo_completo, encoding="utf-8")
        else:
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".pl",
                encoding="utf-8",
                delete=False,
            )
            tmp.write(codigo_completo)
            tmp.close()
            temp_file_path = Path(tmp.name)
            caminho_exec_pl = temp_file_path

        swipl_bin = self._verificar_swipl_disponivel()
        swipl_resultados: Dict[str, dict] = {}
        motor_label = "Motor SLD ISO-Prolog Nativo em Python (Fallback — swipl não instalado)"

        try:
            if swipl_bin:
                swipl_resultados = self._executar_via_swipl(
                    swipl_bin=swipl_bin,
                    caminho_pl=caminho_exec_pl,
                    edital_atom=edital_atom,
                    regras_selecionadas=regras_selecionadas,
                )
                versao_swipl = self._obter_versao_swipl(swipl_bin)
                ver_txt = f" {versao_swipl}" if versao_swipl else ""
                motor_label = f"SWI-Prolog{ver_txt} (Execução Real via swipl) + SLD Trace UFO-L"
        finally:
            if temp_file_path is not None and temp_file_path.exists():
                temp_file_path.unlink(missing_ok=True)

        parser = PrologParser()
        clauses = parser.parse_program(codigo_completo)
        engine = PrologSLDEngine(clauses)

        resultados: Dict[str, ResultadoInferenciaRegra] = {}

        for r_id in regras_selecionadas:
            # Gera o rastro SLD unificado de avaliar_regra/8 (que agora percorre
            # norma_legal/6, posicao_edital/6 com NAF \+, is_subclass/2, is_legal_moment/1 e conflito_hohfeldiano/3)
            q_aval = parser.parse_goal(
                f"avaliar_regra({edital_atom}, '{r_id}', Status, TipoInf, PapelAfetado, MomEdital, MomLei, ItemRef)"
            )
            sol_aval = engine.solve([q_aval])
            trace_passos = sol_aval[0][1] if sol_aval else []

            if r_id in swipl_resultados:
                sw = swipl_resultados[r_id]
                passos_completos = [
                    f"[SWI-Prolog Oficial] Veredito provado via subprocesso `{Path(swipl_bin).name}`.",
                ]
                validacao_cruzada_ok = False
                if sol_aval:
                    s0 = sol_aval[0][0]
                    py_vals = (
                        self._term_to_str(engine.deref(Var("Status"), s0)),
                        self._term_to_str(engine.deref(Var("PapelAfetado"), s0)),
                        self._term_to_str(engine.deref(Var("MomEdital"), s0)),
                        self._term_to_str(engine.deref(Var("MomLei"), s0)),
                    )
                    sw_vals = (
                        sw["status"],
                        sw["papel_afetado"],
                        sw["momento_edital"],
                        sw["momento_esperado_lei"],
                    )
                    if py_vals == sw_vals:
                        validacao_cruzada_ok = True
                        passos_completos.extend([
                            (
                                f"[Validação Cruzada OK] SWI-Prolog == PrologSLDEngine "
                                f"(Status={sw['status']}, Papel={sw['papel_afetado']}, "
                                f"MomEdital={sw['momento_edital']}, MomLei={sw['momento_esperado_lei']})."
                            ),
                            f"Consulta Unificada: ?- avaliar_regra({edital_atom}, '{r_id}', Status, TipoInf, Papel, MomEdital, MomLei, Item).",
                            "Árvore SLD Unificada (UFO-L + Lei 13.303):",
                        ])
                        passos_completos.extend(trace_passos)
                        if len(sol_aval) > 1:
                            itens_extras = []
                            for s_sub, _ in sol_aval:
                                it_s = self._term_to_str(engine.deref(Var("ItemRef"), s_sub))
                                if it_s not in itens_extras:
                                    itens_extras.append(it_s)
                            passos_completos.append(f"Ocorrências agregadas (findall): {len(itens_extras)} -> {' | '.join(itens_extras)}")
                    else:
                        passos_completos.append(
                            f"[Validação Cruzada DIVERGENTE] SWI-Prolog={sw_vals} vs. PrologSLDEngine={py_vals}."
                        )
                else:
                    passos_completos.append(
                        "[Validação Cruzada DIVERGENTE] PrologSLDEngine não derivou solução para a consulta unificada."
                    )

                resultados[r_id] = ResultadoInferenciaRegra(
                    regra_id=r_id,
                    status=sw["status"],
                    tipo_inferencia_ufol=sw["tipo_inferencia_ufol"],
                    relacao_juridica_ufol=sw["relacao_juridica_ufol"],
                    papel_afetado=sw["papel_afetado"],
                    momento_edital=sw["momento_edital"],
                    momento_esperado_lei=sw["momento_esperado_lei"],
                    momento_correlato_lei=sw["momento_correlato_lei"],
                    acao_juridica_ufol=sw["acao_juridica_ufol"],
                    dispositivo_legal_ufol=sw["dispositivo_legal_ufol"],
                    item_evidencia=sw["item_evidencia"],
                    trecho_evidencia=sw["trecho_evidencia"],
                    passos_prova_prolog=passos_completos,
                    validacao_cruzada_ok=validacao_cruzada_ok,
                )
                continue

            # Fallback caso `swipl` não esteja instalado no ambiente
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

            q_corr = parser.parse_goal(f"correlative_moment({momento_lei_norma}, Correlato)")
            sol_corr = engine.solve([q_corr])
            correlato_str = (
                self._term_to_str(engine.deref(Var("Correlato"), sol_corr[0][0]))
                if sol_corr
                else "n/a"
            )

            q_ev = parser.parse_goal(f"evidencia_regra({edital_atom}, '{r_id}', ItemEv, TrechoEv)")
            sol_ev = engine.solve([q_ev])
            trecho_ev_str = (
                self._term_to_str(engine.deref(Var("TrechoEv"), sol_ev[0][0]))
                if sol_ev
                else ""
            )

            if sol_aval:
                subst_final, trace_passos = sol_aval[0]
                status_val = self._term_to_str(engine.deref(Var("Status"), subst_final))
                tipo_inf_val = repr(engine.deref(Var("TipoInf"), subst_final))
                papel_val = self._term_to_str(engine.deref(Var("PapelAfetado"), subst_final))
                mom_edital_val = self._term_to_str(engine.deref(Var("MomEdital"), subst_final))
                mom_lei_val = self._term_to_str(engine.deref(Var("MomLei"), subst_final))
                itens_unicos = []
                for s_sub, _ in sol_aval:
                    it_s = self._term_to_str(engine.deref(Var("ItemRef"), s_sub))
                    if it_s not in itens_unicos:
                        itens_unicos.append(it_s)
                item_val = " | ".join(itens_unicos)

                passos_completos = [
                    f"Consulta Unificada: ?- avaliar_regra({edital_atom}, '{r_id}', Status, TipoInf, Papel, MomEdital, MomLei, Item).",
                    f"Árvore SLD Unificada (UFO-L + Lei 13.303):",
                ]
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

