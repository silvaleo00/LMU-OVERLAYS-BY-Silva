"""Simuladores suportados. Para acrescentar um: escreve uma fonte que devolva Snapshots
(ver source_lmu.py / source_iracing.py) e regista-a aqui."""

from __future__ import annotations

SIMS = {
    "lmu": "Le Mans Ultimate",
    "iracing": "iRacing",
}
DEFAULT = "lmu"


def names() -> dict[str, str]:
    return dict(SIMS)


def make_source(sim: str, demo: bool = False):
    """Fonte de dados para o simulador escolhido (ou a simulação, no modo demo)."""
    if demo:
        from .source_demo import DemoSource
        return DemoSource()
    if sim == "iracing":
        from .source_iracing import IRacingSource
        return IRacingSource()
    from .source_lmu import LMUSource
    return LMUSource()
