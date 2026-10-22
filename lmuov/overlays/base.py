"""Base dos overlays (independente da biblioteca gráfica)."""

from __future__ import annotations

from .. import theme as T
from ..canvas import Canvas
from ..i18n import tr
from ..model import Snapshot
from ..trackers import Context


class Overlay:
    key = ""
    defaults: dict = {}
    default_pos = (100, 100)
    default_enabled = True
    # sessões onde aparece por defeito (practice / qualy / race)
    default_sessions = ("practice", "qualy", "race")
    # True = só aparece quando tem algo a mostrar (bandeiras, boxes, radar)
    contextual = False
    # True = tem modo "auto" (aparece/encolhe sozinho conforme o que está a acontecer)
    smart_capable = False
    default_mode = "always"

    def __init__(self, cfg: dict | None = None) -> None:
        self.cfg = {**self.defaults, **(cfg or {})}

    def mode(self) -> str:
        return self.cfg.get("mode", self.default_mode) if self.smart_capable else "always"

    def auto_visible(self, snap: Snapshot, ctx: Context) -> bool:
        """Regra do modo automático. Por defeito, sempre visível."""
        return True

    def has_content(self, snap: Snapshot, ctx: Context) -> bool:
        """Overlays contextuais: há alguma coisa para mostrar agora?"""
        return True

    def visible(self, snap: Snapshot | None, ctx: Context) -> bool:
        """Decide se a janela deve estar visível agora (modo auto, espreitar, edição)."""
        if ctx.edit_mode:
            return True
        try:
            if self.contextual:
                return snap is not None and bool(self.has_content(snap, ctx))
            if snap is None or ctx.peek or self.mode() != "auto":
                return True
            return bool(self.auto_visible(snap, ctx))
        except Exception:
            return True

    @property
    def title(self) -> str:
        return tr(f"ov.{self.key}")

    def size(self, snap: Snapshot | None, ctx: Context) -> tuple[int, int]:
        raise NotImplementedError

    def draw(self, c: Canvas, snap: Snapshot | None, ctx: Context, w: int, h: int) -> None:
        if snap is None:
            self.draw_empty(c, w, h)
            return
        self.render(c, snap, ctx, w, h)

    def render(self, c: Canvas, snap: Snapshot, ctx: Context, w: int, h: int) -> None:
        raise NotImplementedError

    def draw_empty(self, c: Canvas, w: int, h: int) -> None:
        y = T.panel(c, w, h, self.title)
        c.text(0, y, w, h - y, tr("no_data"), 13, T.FAINT, "c", 500)
