"""Componentes reutilizáveis no padrão minimalista Material Design 3 (M3)."""

from __future__ import annotations

import html
import re
from typing import Iterable, List, Tuple

import pandas as pd
import streamlit as st


_EMOJIS_UI = (
    "🚨", "✅", "⚖️", "⚖", "🔴", "🟢", "📋", "🧠", "📊", "🧪", "📄",
    "🔍", "📌", "🏛️", "🏛", "📖", "⬇️", "⬇", "🔄", "💡", "🌲", "▶️", "▶",
    "➕", "📤", "⚙️", "⚙", "❌", "📝", "📑", "1️⃣", "2️⃣", "3️⃣", "4️⃣",
    "➡️", "➡", "\ufe0f",
)
_PADRAO_EMOJI = re.compile("|".join(re.escape(e) for e in _EMOJIS_UI))

_TONES_VALIDOS = {"neutral", "primary", "success", "warning", "error", "divergence"}


def limpar_emojis_ui(texto: str) -> str:
    """Remove emojis decorativos apenas na camada de exibição, preservando os dados."""
    if not texto:
        return ""
    limpo = _PADRAO_EMOJI.sub("", str(texto))
    limpo = re.sub(r"\s{2,}", " ", limpo)
    return limpo.strip()


def _normalizar_tone(tone: str) -> str:
    return tone if tone in _TONES_VALIDOS else "neutral"


def render_status_badge_html(label: str, tone: str = "neutral") -> str:
    """Retorna HTML seguro de um chip/pill tonal M3."""
    t = _normalizar_tone(tone)
    classe = "md-chip" if t == "neutral" else f"md-chip md-chip-{t}"
    return f'<span class="{classe}">{html.escape(label)}</span>'


def render_top_bar(
    titulo: str,
    subtitulo: str,
    chips: Iterable[Tuple[str, str]],
) -> None:
    """Renderiza o cabeçalho superior minimalista com chips de contexto."""
    chips_html = "".join(render_status_badge_html(lbl, tone) for lbl, tone in chips)
    html_str = (
        f'<div class="md-topbar">'
        f'<h1 class="md-topbar-title">{html.escape(titulo)}</h1>'
        f'<p class="md-topbar-subtitle">{html.escape(subtitulo)}</p>'
        f'<div class="md-chip-row">{chips_html}</div>'
        f"</div>"
    )
    st.markdown(html_str, unsafe_allow_html=True)


def render_kpi_strip(cards: List[dict]) -> None:
    """Renderiza faixa responsiva de KPI cards no estilo Outlined Card M3."""
    blocos = []
    for c in cards:
        label = html.escape(str(c.get("label", "")))
        value = html.escape(str(c.get("value", "")))
        detail = html.escape(str(c.get("detail", "")))
        tone = _normalizar_tone(str(c.get("tone", "neutral")))
        card_cls = "" if tone == "neutral" else f" card-{tone}"
        tone_cls = "" if tone == "neutral" else f" tone-{tone}"
        dot_html = f'<span class="md-dot dot-{tone}"></span>' if tone != "neutral" else ""
        blocos.append(
            f'<div class="md-kpi-card{card_cls}">'
            f'<div class="md-kpi-label">{dot_html}{label}</div>'
            f'<div class="md-kpi-value{tone_cls}">{value}</div>'
            f'<div class="md-kpi-detail">{detail}</div>'
            f"</div>"
        )
    st.markdown(f'<div class="md-kpi-grid">{"".join(blocos)}</div>', unsafe_allow_html=True)


def render_section_header(
    titulo: str,
    subtitulo: str | None = None,
    overline: str | None = None,
) -> None:
    """Renderiza cabeçalho de seção com hierarquia tipográfica M3."""
    overline_html = (
        f'<div class="md-overline" style="margin-top:0;">{html.escape(overline)}</div>'
        if overline
        else ""
    )
    sub_html = (
        f'<p class="md-section-subtitle">{html.escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    html_str = (
        f'<div class="md-section-header">'
        f"{overline_html}"
        f'<h2 class="md-section-title">{html.escape(titulo)}</h2>'
        f"{sub_html}"
        f"</div>"
    )
    st.markdown(html_str, unsafe_allow_html=True)


def render_accent_banner(titulo: str, tone: str = "neutral") -> None:
    """Renderiza faixa discreta com borda lateral semântica de 3px."""
    t = _normalizar_tone(tone)
    st.markdown(
        f'<div class="md-accent-bar tone-{t}">{html.escape(titulo)}</div>',
        unsafe_allow_html=True,
    )


def render_kv_list(itens: List[Tuple[str, str, bool]]) -> None:
    """Renderiza lista chave-valor limpa `(rotulo, valor, is_code)`."""
    linhas = []
    for rotulo, valor, is_code in itens:
        val_esc = html.escape(str(valor))
        val_html = f"<code>{val_esc}</code>" if is_code else val_esc
        linhas.append(
            f'<div class="md-kv-row">'
            f'<span class="md-kv-key">{html.escape(str(rotulo))}</span>'
            f'<span class="md-kv-val">{val_html}</span>'
            f"</div>"
        )
    st.markdown(f'<div class="md-kv-table">{"".join(linhas)}</div>', unsafe_allow_html=True)


def render_sidebar_overline(texto: str) -> None:
    """Renderiza rótulo de agrupamento overline na barra lateral."""
    st.markdown(f'<div class="md-overline">{html.escape(texto)}</div>', unsafe_allow_html=True)


def render_nota_discreta(texto: str, tone: str = "neutral") -> None:
    """Renderiza nota inline discreta no padrão M3 (sem alertas pesados)."""
    render_accent_banner(texto, tone=tone)


def render_divergence_spotlight(
    titulo: str,
    status_neural: str,
    status_nesy: str,
) -> None:
    """Renderiza faixa violeta M3 destacando divergência entre Somente Neural e Neuro-Simbólico."""
    tone_n = "error" if "Inconform" in status_neural else "success"
    tone_s = "error" if "Inconform" in status_nesy else "success"
    badge_n = render_status_badge_html(status_neural, tone_n)
    badge_s = render_status_badge_html(status_nesy, tone_s)
    html_str = (
        f'<div class="md-spotlight">'
        f'<span class="md-spotlight-title">{html.escape(titulo)}</span>'
        f'<span class="md-spotlight-pair">'
        f"Somente Neural: {badge_n}"
        f'<span class="md-spotlight-arrow">&rarr;</span>'
        f"Neuro-Simbólico: {badge_s}"
        f"</span>"
        f"</div>"
    )
    st.markdown(html_str, unsafe_allow_html=True)


def estilizar_coluna_status(val: object) -> str:
    """Aplica destaque tonal M3 para células de status de conformidade."""
    s = str(val).strip()
    if s in {"Indício de Inconformidade", "Inconforme"}:
        return "background-color: #FEF2F2; color: #C62828; font-weight: 600;"
    if s == "Conforme":
        return "background-color: #F0FDF4; color: #15803D; font-weight: 600;"
    return ""


def _estilo_celula_divergencia(val: object) -> str:
    s = str(val).strip()
    if s and s.lower() not in {"nenhuma", "-", "none"}:
        return "background-color: #F5F3FF; color: #6D28D9; font-weight: 600;"
    return ""


def estilizar_matriz_benchmark(df: pd.DataFrame):
    """Limpa emojis das colunas da matriz do benchmark e aplica tons pastel M3."""
    df_limpo = df.copy()
    colunas_regras = [c for c in df_limpo.columns if re.match(r"^R\d+$", str(c))]
    for col in df_limpo.columns:
        if df_limpo[col].dtype == object:
            df_limpo[col] = df_limpo[col].map(
                lambda v: limpar_emojis_ui(v) if isinstance(v, str) else v
            )

    styler = df_limpo.style
    if colunas_regras:
        styler = styler.map(estilizar_coluna_status, subset=colunas_regras)
    if "Divergências (LLM vs NeSy)" in df_limpo.columns:
        styler = styler.map(_estilo_celula_divergencia, subset=["Divergências (LLM vs NeSy)"])
    return df_limpo, styler
