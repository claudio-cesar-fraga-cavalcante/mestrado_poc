"""Tokens e estilos globais Material Design 3 (M3) para o Streamlit."""

from __future__ import annotations

import textwrap

import streamlit as st


def aplicar_tema_material_m3() -> None:
    """Injeta tokens de cor, tipografia, superfícies e componentes inspirados no Material Design 3."""
    css_bruto = textwrap.dedent(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --md-primary: #1D4ED8;
            --md-primary-container: #EDF2FE;
            --md-on-primary-container: #172E7A;
            --md-surface: #F8F9FA;
            --md-surface-card: #FFFFFF;
            --md-surface-subtle: #F1F3F6;
            --md-on-surface: #1C1B1F;
            --md-on-surface-variant: #5F6368;
            --md-outline: #E2E5EC;
            --md-outline-strong: #CBD2E0;
            --md-radius-md: 12px;
            --md-radius-sm: 8px;
            --md-radius-pill: 999px;
            --md-error: #C62828;
            --md-error-stripe: #DC2626;
            --md-error-bg: #FEF2F2;
            --md-error-border: #FECACA;
            --md-divergence: #6D28D9;
            --md-divergence-stripe: #7C3AED;
            --md-divergence-bg: #F5F3FF;
            --md-divergence-border: #DDD6FE;
            --md-success: #15803D;
            --md-success-stripe: #16A34A;
            --md-success-bg: #F0FDF4;
            --md-success-border: #BBF7D0;
            --md-warning: #B45309;
            --md-warning-stripe: #D97706;
            --md-warning-bg: #FFFBEB;
            --md-warning-border: #FDE68A;
            --md-elevation-1: 0 1px 2px rgba(28, 27, 31, 0.04), 0 1px 3px rgba(28, 27, 31, 0.03);
            --md-elevation-2: 0 2px 6px rgba(28, 27, 31, 0.06), 0 1px 2px rgba(28, 27, 31, 0.04);
        }

        html, body, [class*="css"], .stApp {
            font-family: 'Inter', 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: var(--md-on-surface);
        }

        code, pre, kbd, samp, .stCode, .stCode pre {
            font-family: 'JetBrains Mono', 'Roboto Mono', monospace !important;
        }

        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 3rem !important;
            max-width: 1320px !important;
        }

        /* Sidebar / Navigation Drawer */
        section[data-testid="stSidebar"] {
            border-right: 1px solid var(--md-outline);
            background-color: var(--md-surface-card);
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
        }

        .md-overline {
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--md-on-surface-variant);
            font-weight: 600;
            margin: 0.9rem 0 0.4rem 0;
        }

        /* Material Primary Tabs */
        div[data-baseweb="tab-list"] {
            gap: 4px !important;
            flex-wrap: wrap !important;
            border-bottom: 1px solid var(--md-outline) !important;
            padding-bottom: 0 !important;
            margin-bottom: 1.25rem !important;
        }

        button[data-baseweb="tab"] {
            font-size: 0.9rem !important;
            font-weight: 500 !important;
            color: var(--md-on-surface-variant) !important;
            padding: 0.65rem 1rem !important;
            border-radius: 8px 8px 0 0 !important;
            background: transparent !important;
            transition: background-color 140ms ease, color 140ms ease;
        }

        button[data-baseweb="tab"]:hover {
            background-color: var(--md-surface-subtle) !important;
            color: var(--md-on-surface) !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            font-weight: 600 !important;
            color: var(--md-primary) !important;
        }

        /* Expanders (M3 Outlined Cards) */
        div[data-testid="stExpander"] {
            background-color: var(--md-surface-card);
            border: 1px solid var(--md-outline) !important;
            border-radius: var(--md-radius-md) !important;
            box-shadow: var(--md-elevation-1);
            overflow: hidden;
            transition: box-shadow 160ms ease, border-color 160ms ease;
        }

        div[data-testid="stExpander"]:hover {
            border-color: var(--md-outline-strong) !important;
            box-shadow: var(--md-elevation-2);
        }

        div[data-testid="stExpander"] details summary {
            padding: 0.75rem 1rem !important;
            font-weight: 500 !important;
            color: var(--md-on-surface) !important;
        }

        /* Containers com borda */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--md-surface-card);
            border: 1px solid var(--md-outline) !important;
            border-radius: var(--md-radius-md) !important;
            box-shadow: var(--md-elevation-1);
        }

        /* Botões M3 */
        .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
            border-radius: var(--md-radius-sm) !important;
            font-weight: 500 !important;
            transition: box-shadow 140ms ease, background-color 140ms ease;
        }

        .stButton > button[kind="secondary"],
        .stDownloadButton > button {
            background-color: var(--md-surface-card) !important;
            border: 1px solid var(--md-outline-strong) !important;
            color: var(--md-on-surface) !important;
        }

        .stButton > button[kind="secondary"]:hover,
        .stDownloadButton > button:hover {
            background-color: var(--md-surface-subtle) !important;
            border-color: var(--md-primary) !important;
            color: var(--md-primary) !important;
        }

        /* Top App Bar */
        .md-topbar {
            background-color: var(--md-surface-card);
            border: 1px solid var(--md-outline);
            border-top: 3px solid var(--md-primary);
            border-radius: var(--md-radius-md);
            padding: 1.25rem 1.5rem;
            margin-bottom: 1rem;
            box-shadow: var(--md-elevation-1);
        }

        .md-topbar-title {
            font-size: 1.45rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            color: var(--md-on-surface);
            margin: 0;
            line-height: 1.25;
        }

        .md-topbar-subtitle {
            font-size: 0.88rem;
            color: var(--md-on-surface-variant);
            margin: 0.35rem 0 0.85rem 0;
            line-height: 1.45;
        }

        .md-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            align-items: center;
        }

        .md-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.22rem 0.65rem;
            border-radius: var(--md-radius-pill);
            font-size: 0.76rem;
            font-weight: 500;
            line-height: 1.4;
            border: 1px solid var(--md-outline);
            background-color: var(--md-surface-subtle);
            color: var(--md-on-surface-variant);
        }

        .md-chip-primary {
            background-color: var(--md-primary-container);
            border-color: #CBD9FB;
            color: var(--md-on-primary-container);
        }

        .md-chip-success {
            background-color: var(--md-success-bg);
            border-color: var(--md-success-border);
            color: var(--md-success);
        }

        .md-chip-warning {
            background-color: var(--md-warning-bg);
            border-color: var(--md-warning-border);
            color: var(--md-warning);
        }

        .md-chip-error {
            background-color: var(--md-error-bg);
            border-color: var(--md-error-border);
            color: var(--md-error);
        }

        .md-chip-divergence {
            background-color: var(--md-divergence-bg);
            border-color: var(--md-divergence-border);
            color: var(--md-divergence);
        }

        /* KPI Grid */
        .md-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.25rem;
        }

        @media (max-width: 960px) {
            .md-kpi-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 560px) {
            .md-kpi-grid {
                grid-template-columns: 1fr;
            }
        }

        .md-kpi-card {
            background-color: var(--md-surface-card);
            border: 1px solid var(--md-outline);
            border-radius: var(--md-radius-md);
            padding: 0.95rem 1.1rem;
            box-shadow: var(--md-elevation-1);
        }

        .md-kpi-card.card-primary {
            border-top: 3px solid var(--md-primary);
            background-color: #FAFBFD;
        }

        .md-kpi-card.card-error {
            border-top: 3px solid var(--md-error-stripe);
            background-color: #FFFBFB;
        }

        .md-kpi-card.card-divergence {
            border-top: 3px solid var(--md-divergence-stripe);
            background-color: #FAF8FF;
        }

        .md-kpi-card.card-warning {
            border-top: 3px solid var(--md-warning-stripe);
            background-color: #FFFDF5;
        }

        .md-kpi-card.card-success {
            border-top: 3px solid var(--md-success-stripe);
            background-color: #F7FEF9;
        }

        .md-kpi-label {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--md-on-surface-variant);
            margin-bottom: 0.3rem;
        }

        .md-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            flex-shrink: 0;
        }

        .dot-primary { background-color: var(--md-primary); }
        .dot-error { background-color: var(--md-error-stripe); }
        .dot-divergence { background-color: var(--md-divergence-stripe); }
        .dot-warning { background-color: var(--md-warning-stripe); }
        .dot-success { background-color: var(--md-success-stripe); }

        .md-kpi-value {
            font-size: 1.6rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            color: var(--md-on-surface);
            line-height: 1.2;
        }

        .md-kpi-value.tone-primary { color: var(--md-primary); }
        .md-kpi-value.tone-error { color: var(--md-error); }
        .md-kpi-value.tone-divergence { color: var(--md-divergence); }
        .md-kpi-value.tone-success { color: var(--md-success); }
        .md-kpi-value.tone-warning { color: var(--md-warning); }

        .md-kpi-detail {
            font-size: 0.78rem;
            color: var(--md-on-surface-variant);
            margin-top: 0.3rem;
            line-height: 1.35;
        }

        /* Section Header */
        .md-section-header {
            margin: 0.25rem 0 0.85rem 0;
        }

        .stMarkdown h2.md-section-title,
        .md-section-title {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            color: var(--md-on-surface) !important;
            padding: 0 !important;
            margin: 0 !important;
            line-height: 1.3 !important;
        }

        .md-section-subtitle {
            font-size: 0.85rem;
            color: var(--md-on-surface-variant);
            margin: 0.25rem 0 0 0;
            line-height: 1.45;
        }

        /* Accent Banner (3px left border on clean surface) */
        .md-accent-bar {
            border-left: 3px solid var(--md-outline-strong);
            background-color: var(--md-surface-subtle);
            border-radius: 0 var(--md-radius-sm) var(--md-radius-sm) 0;
            padding: 0.55rem 0.85rem;
            margin-bottom: 0.75rem;
            font-size: 0.84rem;
            font-weight: 600;
            color: var(--md-on-surface);
        }

        .md-accent-bar.tone-error {
            border-left-color: var(--md-error);
            background-color: var(--md-error-bg);
            color: var(--md-error);
        }

        .md-accent-bar.tone-success {
            border-left-color: var(--md-success);
            background-color: var(--md-success-bg);
            color: var(--md-success);
        }

        .md-accent-bar.tone-warning {
            border-left-color: var(--md-warning);
            background-color: var(--md-warning-bg);
            color: var(--md-warning);
        }

        .md-accent-bar.tone-primary {
            border-left-color: var(--md-primary);
            background-color: var(--md-primary-container);
            color: var(--md-on-primary-container);
        }

        .md-accent-bar.tone-divergence {
            border-left-color: var(--md-divergence-stripe);
            background-color: var(--md-divergence-bg);
            color: var(--md-divergence);
        }

        /* Divergence Spotlight */
        .md-spotlight {
            background-color: var(--md-divergence-bg);
            border: 1px solid var(--md-divergence-border);
            border-left: 4px solid var(--md-divergence-stripe);
            border-radius: var(--md-radius-sm);
            padding: 0.7rem 0.95rem;
            margin-bottom: 0.85rem;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
        }

        .md-spotlight-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--md-divergence);
        }

        .md-spotlight-pair {
            display: inline-flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.45rem;
            font-size: 0.78rem;
            color: var(--md-on-surface-variant);
            font-weight: 500;
        }

        .md-spotlight-arrow {
            color: var(--md-divergence);
            font-weight: 700;
        }

        /* Key-Value Metadata List */
        .md-kv-table {
            width: 100%;
            border-top: 1px solid var(--md-outline);
            margin-top: 0.5rem;
            margin-bottom: 0.65rem;
        }

        .md-kv-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 0.75rem;
            padding: 0.42rem 0;
            border-bottom: 1px solid var(--md-outline);
            font-size: 0.82rem;
        }

        .md-kv-key {
            color: var(--md-on-surface-variant);
            font-weight: 500;
            flex-shrink: 0;
        }

        .md-kv-val {
            color: var(--md-on-surface);
            text-align: right;
            word-break: break-word;
        }

        .md-kv-val code {
            background-color: var(--md-surface-subtle);
            padding: 0.1rem 0.38rem;
            border-radius: 4px;
            font-size: 0.78rem;
            color: var(--md-on-surface);
        }

        /* Scrollable box for dense artifacts */
        .md-scroll-box {
            max-height: 460px;
            overflow-y: auto;
        }
        </style>
        """
    ).strip()
    css_limpo = "\n".join(linha.strip() for linha in css_bruto.splitlines() if linha.strip())
    st.markdown(css_limpo, unsafe_allow_html=True)
