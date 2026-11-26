"""Módulos das abas da interface minimalista M3."""

from src.ui.tabs.benchmark import render_tab_benchmark
from src.ui.tabs.comparativo import render_tab_comparativo
from src.ui.tabs.diagnostico import render_tab_diagnostico
from src.ui.tabs.edital import render_tab_edital
from src.ui.tabs.prova_prolog import render_tab_prova_prolog
from src.ui.tabs.whatif import render_tab_whatif

__all__ = [
    "render_tab_diagnostico",
    "render_tab_prova_prolog",
    "render_tab_comparativo",
    "render_tab_benchmark",
    "render_tab_whatif",
    "render_tab_edital",
]
