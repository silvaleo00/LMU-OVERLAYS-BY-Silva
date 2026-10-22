"""App Qt: uma janela transparente por overlay + painel de controlo + ícone na bandeja."""

from __future__ import annotations

import gc
import logging
import math
import os
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QFontDatabase, QFontMetricsF, QIcon, QImage,
                           QLinearGradient, QPainter, QPen, QPixmap, QPolygonF, QStaticText, QTextOption)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QMenu, QPushButton, QSlider, QSystemTrayIcon, QVBoxLayout, QWidget)

from . import config as C
from . import sims
from . import skins
from . import theme
from .canvas import rgba
from .i18n import LANGS, set_language, tr
from .model import session_group
from .overlays import ALL
from .paths import resource
from .trackers import Trackers

MIN_HZ = 8          # o regulador pode descer até aqui; o mesmo limite em todo o lado (evita o vaivém 10 -> 8)

log = logging.getLogger("lmuov")

_WEIGHTS = {300: QFont.Weight.Light, 400: QFont.Weight.Normal, 500: QFont.Weight.Medium,
            600: QFont.Weight.DemiBold, 700: QFont.Weight.Bold, 800: QFont.Weight.ExtraBold}
_ALIGN = {"l": Qt.AlignmentFlag.AlignLeft, "c": Qt.AlignmentFlag.AlignHCenter, "r": Qt.AlignmentFlag.AlignRight}


# Relógio de alta resolução. time.monotonic() no Windows (Python < 3.13) só anda de 15.6 em 15.6 ms,
# o que a 60 fps faz os overlays saltarem frames de forma irregular.
clock = time.perf_counter

# caches de objetos Qt (criar QColor/QPen a cada primitiva custa mais do que desenhá-la)
_COLORS: dict = {}
_PENS: dict = {}
_BRUSHES: dict = {}


def _qc(c) -> QColor:
    try:
        q = _COLORS.get(c)
    except TypeError:                      # cor em lista (vinda do config.json)
        return QColor(*rgba(c))
    if q is None:
        if len(_COLORS) > 4096:
            _COLORS.clear()
        q = _COLORS[c] = QColor(*rgba(c))
    return q


def _solid_brush(c) -> QBrush:
    c = tuple(c)
    b = _BRUSHES.get(c)
    if b is None:
        if len(_BRUSHES) > 4096:
            _BRUSHES.clear()
        b = _BRUSHES[c] = QBrush(_qc(c))
    return b


def _plain_pen(c, w) -> QPen:
    key = (tuple(c), w)
    pen = _PENS.get(key)
    if pen is None:
        if len(_PENS) > 4096:
            _PENS.clear()
        pen = _PENS[key] = QPen(_qc(c), w)
    return pen


def _enable_tnum(f: QFont) -> None:
    """Algarismos de largura fixa (Qt 6.7+); em versões antigas ignora-se."""
    for make in (lambda: QFont.Tag("tnum"), lambda: QFont.Tag.fromString("tnum")):
        try:
            tag = make()
            if tag is not None:
                f.setFeature(tag, 1)
                return
        except Exception:
            continue


ITALIC = 0.2   # inclinação do texto em itálico (x por unidade de y)


class QtCanvas:
    """Implementação da interface Canvas com QPainter."""

    _fonts: dict = {}
    families: list[str] = ["Segoe UI"]

    def __init__(self, painter: QPainter, k: float = 1.0) -> None:
        self.p = painter
        self.k = k                      # escala da janela (o layout do texto em cache depende dela)

    @classmethod
    def font(cls, size: float, weight: int, spacing: float = 0.0):
        key = (int(round(size)), weight, round(spacing, 2))
        hit = cls._fonts.get(key)
        if hit is None:
            f = QFont()
            f.setFamilies(cls.families)
            f.setPixelSize(max(1, key[0]))
            f.setWeight(_WEIGHTS[min(_WEIGHTS, key=lambda k: abs(k - weight))])
            f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            if spacing:
                f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
            _enable_tnum(f)
            hit = (f, QFontMetricsF(f))
            cls._fonts[key] = hit
        return hit

    def _brush(self, x, y, w, h, fill, fill2, horizontal):
        if fill is None:
            return Qt.BrushStyle.NoBrush
        if fill2 is None:
            return _solid_brush(fill)
        g = QLinearGradient(QPointF(x, y), QPointF(x + w, y) if horizontal else QPointF(x, y + h))
        g.setColorAt(0.0, _qc(fill))
        g.setColorAt(1.0, _qc(fill2))
        return QBrush(g)

    def rect(self, x, y, w, h, fill=None, radius=0, stroke=None, stroke_w=1.0, fill2=None, horizontal=False):
        if w <= 0 or h <= 0:
            return
        r = QRectF(x, y, w, h)
        if stroke:
            self.p.setPen(_plain_pen(stroke, stroke_w))
            r = r.adjusted(stroke_w / 2, stroke_w / 2, -stroke_w / 2, -stroke_w / 2)
        else:
            self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(self._brush(x, y, w, h, fill, fill2, horizontal))
        rad = min(radius, r.width() / 2, r.height() / 2)
        if rad > 0:
            self.p.drawRoundedRect(r, rad, rad)
        else:
            self.p.drawRect(r)

    def _pen(self, color, width):
        key = (tuple(color), width, "round")
        pen = _PENS.get(key)
        if pen is None:
            pen = QPen(_qc(color), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            _PENS[key] = pen
        return pen

    def line(self, x1, y1, x2, y2, color, width=1.0):
        self.p.setPen(self._pen(color, width))
        self.p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def polyline(self, pts, color, width=1.0, closed=False):
        if len(pts) < 2:
            return
        self.p.setPen(self._pen(color, width))
        poly = QPolygonF([QPointF(px, py) for px, py in pts])
        if closed:
            self.p.setBrush(Qt.BrushStyle.NoBrush)
            self.p.drawPolygon(poly)
        else:
            self.p.drawPolyline(poly)

    def polygon(self, pts, fill=None, stroke=None, stroke_w=1.0):
        self.p.setPen(_plain_pen(stroke, stroke_w) if stroke else Qt.PenStyle.NoPen)
        self.p.setBrush(_solid_brush(fill) if fill else Qt.BrushStyle.NoBrush)
        self.p.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))

    def ellipse(self, cx, cy, rx, ry, fill=None, stroke=None, stroke_w=1.0):
        self.p.setPen(_plain_pen(stroke, stroke_w) if stroke else Qt.PenStyle.NoPen)
        self.p.setBrush(_solid_brush(fill) if fill else Qt.BrushStyle.NoBrush)
        self.p.drawEllipse(QPointF(cx, cy), rx, ry)

    def mark_static(self) -> None:
        """Só tem efeito no Recorder (camada de fundo em cache)."""

    _pixmaps: dict = {}

    def image(self, path, cx, cy, size, angle=0.0, box=None):
        bw, bh = box if box else (size, size)              # box: cabe num retângulo (ex.: logótipos)
        key = (path, int(round(bw * self.k)), int(round(bh * self.k)))
        pm = QtCanvas._pixmaps.get(key)
        if pm is None:
            src = QPixmap(path)
            if src.isNull():
                return
            # o dobro da resolução: fica nítido ao rodar
            pm = src.scaled(max(1, key[1] * 2), max(1, key[2] * 2), Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
            if len(QtCanvas._pixmaps) > 96:
                QtCanvas._pixmaps.clear()
            QtCanvas._pixmaps[key] = pm
        p = self.p
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.translate(cx, cy)
        p.rotate(angle)
        w, h = pm.width() / 2, pm.height() / 2           # pixmap com o dobro: desenha a metade do tamanho
        p.drawPixmap(QRectF(-w / 2 / self.k, -h / 2 / self.k, w / self.k, h / self.k), pm, QRectF(pm.rect()))
        p.restore()

    # texto: QStaticText guarda o layout das letras (desenhar o mesmo texto outra vez é quase grátis)
    _static: dict = {}
    _widths: dict = {}
    fast_text = True

    @classmethod
    def _advance(cls, s, fkey, fm):
        key = (s, fkey)
        wd = cls._widths.get(key)
        if wd is None:
            if len(cls._widths) > 8000:
                cls._widths.clear()
            wd = cls._widths[key] = fm.horizontalAdvance(s)
        return wd

    def measure(self, s, size, weight=400, spacing=0.0):
        f, fm = self.font(size, weight, spacing)
        return self._advance(s, (int(round(size)), weight, round(spacing, 2)), fm)

    def text(self, x, y, w, h, s, size, color, align="l", weight=400, spacing=0.0, italic=False):
        if not s:
            return
        f, fm = self.font(size, weight, spacing)
        fkey = (int(round(size)), weight, round(spacing, 2))
        tw = self._advance(s, fkey, fm)
        if tw > w:
            s = fm.elidedText(s, Qt.TextElideMode.ElideRight, w)
            tw = self._advance(s, fkey, fm)
        p = self.p
        p.setFont(f)
        if italic:                       # inclinação à volta do centro vertical da caixa
            cy = y + h / 2
            p.save()
            p.translate(0, cy)
            p.shear(-ITALIC, 0)
            p.translate(0, -cy)
        shadow = theme.SKIN.get("text_shadow")
        try:
            if QtCanvas.fast_text:
                key = (s, fkey, self.k, italic)
                hit = QtCanvas._static.get(key)
                if hit is None:
                    if len(QtCanvas._static) > 6000:
                        QtCanvas._static.clear()
                    st = QStaticText(s)
                    st.setTextFormat(Qt.TextFormat.PlainText)
                    st.setPerformanceHint(QStaticText.PerformanceHint.AggressiveCaching)
                    hit = QtCanvas._static[key] = st
                st = hit
                x0 = x if align == "l" else (x + (w - tw) / 2 if align == "c" else x + w - tw)
                y0 = y + (h - fm.height()) / 2
                if shadow:
                    p.setPen(QColor(0, 0, 0, int(rgba(color)[3] * 0.85)))
                    p.drawStaticText(QPointF(x0 + 1.2, y0 + 1.2), st)
                p.setPen(_qc(color))
                p.drawStaticText(QPointF(x0, y0), st)
            else:
                self._text_slow(x, y, w, h, s, color, align, shadow)
        except Exception:                 # se o QStaticText falhar nesta máquina, volta ao método normal
            QtCanvas.fast_text = False
            log.warning("texto rápido desligado:\n%s", traceback.format_exc())
            self._text_slow(x, y, w, h, s, color, align, shadow)
        if italic:
            p.restore()

    def _text_slow(self, x, y, w, h, s, color, align, shadow):
        opt = QTextOption(_ALIGN[align] | Qt.AlignmentFlag.AlignVCenter)
        opt.setWrapMode(QTextOption.WrapMode.NoWrap)
        if shadow:
            self.p.setPen(QColor(0, 0, 0, int(rgba(color)[3] * 0.85)))
            self.p.drawText(QRectF(x + 1.2, y + 1.2, w, h), s, opt)
        self.p.setPen(_qc(color))
        self.p.drawText(QRectF(x, y, w, h), s, opt)


def load_fonts() -> list[str]:
    """Regista a fonte embutida (Barlow Semi Condensed) e devolve os nomes das famílias."""
    fams: list[str] = []
    folder = resource("assets/fonts")
    if folder.exists():
        for ttf in sorted(folder.glob("*.ttf")):
            fid = QFontDatabase.addApplicationFont(str(ttf))
            if fid >= 0:
                for fam in QFontDatabase.applicationFontFamilies(fid):
                    if fam not in fams:
                        fams.append(fam)
    return fams


# --------------------------------------------------------------------------- #
_QP_CACHE: dict = {}


class Recorder:
    """Canvas que só regista as operações de desenho.

    Cada overlay "desenha" primeiro para aqui; a janela só é redesenhada (Qt) se a lista
    de operações mudou desde a última vez. As coordenadas são arredondadas a meio pixel,
    para que mudanças invisíveis (uma barra que cresce 0.01 px) não obriguem a redesenhar.
    """

    __slots__ = ("ops", "mark")

    def __init__(self) -> None:
        self.ops: list = []
        self.mark = 0                      # ops[:mark] = fundo que não muda (vai para uma imagem em cache)

    def mark_static(self) -> None:
        self.mark = len(self.ops)

    Q = 1.0          # arredondamento: 1 px (modos leves) ou 0.5 px (Suave)

    @staticmethod
    def _q(a):
        q = Recorder.Q
        return tuple(round(v / q) * q if type(v) is float else v for v in a)

    @staticmethod
    def _qp(pts):
        if type(pts) is tuple:            # geometria fixa (ex.: traçado do mapa): arredonda uma vez só
            hit = _QP_CACHE.get(id(pts))
            if hit is not None and hit[0] is pts:
                return hit[1]
            q = [(round(x * 2) / 2, round(y * 2) / 2) for x, y in pts]
            if len(_QP_CACHE) > 64:
                _QP_CACHE.clear()
            _QP_CACHE[id(pts)] = (pts, q)
            return q
        return [(round(x * 2) / 2, round(y * 2) / 2) for x, y in pts]

    def rect(self, *a, **k):
        self.ops.append(("rect", self._q(a), k))

    def line(self, *a, **k):
        self.ops.append(("line", self._q(a), k))

    def polyline(self, pts, *a, **k):
        self.ops.append(("polyline", (self._qp(pts),) + a, k))

    def polygon(self, pts, *a, **k):
        self.ops.append(("polygon", (self._qp(pts),) + a, k))

    def ellipse(self, *a, **k):
        self.ops.append(("ellipse", self._q(a), k))

    def text(self, *a, **k):
        self.ops.append(("text", self._q(a), k))

    def image(self, *a, **k):
        self.ops.append(("image", self._q(a), k))

    @staticmethod
    def measure(s, size, weight=400, spacing=0.0):
        fm = QtCanvas.font(size, weight, spacing)[1]
        return QtCanvas._advance(s, (int(round(size)), weight, round(spacing, 2)), fm)


FADE_S = 0.22   # duração do fade in/out


class OverlayWindow(QWidget):
    def __init__(self, app: "OverlayApp", overlay) -> None:
        super().__init__(None)
        self.app = app
        self.ov = overlay
        self.ocfg = app.cfg["overlays"][overlay.key]
        self._ops: list = []
        self._mark = 0               # ops[:_mark] = fundo estático (desenhado uma vez para uma imagem)
        self._bg = None
        self._bg_key = None
        self._bg_ops = None
        self._wh = (0, 0)
        self._scale_used = 0.0
        self._small_since = None
        self._drag = None
        self._forced = True
        self.every = 1               # redesenha 1 em cada `every` frames
        self.phase = 0               # desfasamento, para os overlays lentos não calharem todos no mesmo frame
        self.paint_s = 0.0           # tempo gasto a pintar (medidor de carga)
        self._errors = 0
        self._alpha = 0.0          # fade atual 0..1
        self._applied = -1.0       # opacidade aplicada à janela
        self.vis_at = 0.0          # próxima reavaliação da regra de visibilidade
        self.vis_ok = True
        self.paints = 0            # nº de redesenhos (para o medidor de carga)
        self.setWindowTitle(f"LMU · {overlay.key}")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._pad = 0
        self.set_locked(True)
        self._place()

    def pad(self) -> float:
        """Margem à volta do conteúdo para o brilho néon (unidades base)."""
        return float(theme.NEON_PAD) if theme.NEON else 0.0

    def _padpx(self) -> int:
        return round(self.pad() * self.scale())

    def _place(self) -> None:
        """A posição guardada é a do conteúdo; a janela começa uma margem antes."""
        p = self._padpx()
        self.move(int(self.ocfg["x"]) - p, int(self.ocfg["y"]) - p)

    def set_locked(self, locked: bool) -> None:
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
                 | Qt.WindowType.NoDropShadowWindowHint)
        if locked:
            flags |= Qt.WindowType.WindowTransparentForInput   # cliques passam para o jogo
        visible = self.isVisible()
        self.setWindowFlags(flags)
        self.setCursor(Qt.CursorShape.ArrowCursor if locked else Qt.CursorShape.SizeAllCursor)
        if visible:
            self.show()
            self._applied = -1.0

    def scale(self) -> float:
        return max(0.4, min(3.0, float(self.ocfg.get("scale", 1.0))))

    def force(self) -> None:
        """Obriga a recalcular e redesenhar no próximo frame."""
        self._forced = True
        self._ops = None
        self._bg_ops = None

    def due(self, frame: int) -> bool:
        return self._forced or (frame + self.phase) % self.every == 0

    def feed(self, snap, ctx, frame: int) -> None:
        if not self.due(frame):
            return
        self._forced = False
        w, h = self.ov.size(snap, ctx)
        rec = Recorder()
        try:
            self.ov.draw(rec, snap, ctx, w, h)
        except Exception:
            self._errors += 1
            if self._errors <= 3:
                log.error("erro a desenhar %s:\n%s", self.ov.key, traceback.format_exc())
            rec.mark = 0
            rec.ops = [("rect", (0, 0, w, h, (60, 10, 10, 220)), {}),
                       ("text", (0, 0, w, h, f"{self.ov.title}: error", 12, theme.TEXT, "c"), {})]
        s = self.scale()
        pad = self.pad()
        need = (max(1, round((w + 2 * pad) * s)), max(1, round((h + 2 * pad) * s)))
        # Mudar o tamanho de uma janela transparente pode piscar; enquanto está à vista a janela só
        # cresce (o resto fica transparente) e encolhe quando volta a esconder-se.
        same = pad == self._pad and s == self._scale_used
        if same and self.isVisible() and not self.app.edit_mode:
            wh = (max(need[0], self._wh[0]), max(need[1], self._wh[1]))
            if wh != need:                       # ficou mais pequeno: encolhe se assim ficar 10 s
                t = clock()
                if self._small_since is None:
                    self._small_since = t
                elif t - self._small_since > 10.0:
                    wh, self._small_since = need, None
            else:
                self._small_since = None
        else:
            wh = need
        if wh != self._wh or not same:
            self._wh, self._pad, self._scale_used = wh, pad, s
            self.setFixedSize(*wh)
            self._place()
            self._ops = None
            self._bg_ops = None
        if rec.ops != self._ops:
            self._ops = rec.ops
            self._mark = rec.mark
            self._size_base = (w, h)
            self.update()

    def step_fade(self, target: bool, dt: float) -> None:
        if target:
            if not self.isVisible():
                self._alpha = 0.0
                self._applied = -1.0
                self.setWindowOpacity(0.0)
                self.show()
            self._alpha = min(1.0, self._alpha + dt / FADE_S)
        else:
            if not self.isVisible():
                return
            self._alpha = max(0.0, self._alpha - dt / FADE_S)
            if self._alpha <= 0.0:
                self.hide()
                return
        op = max(0.0, min(1.0, self.app.opacity * self._alpha))
        if abs(op - self._applied) > 0.004:
            self.setWindowOpacity(op)
            self._applied = op

    def _setup(self, p: QPainter, s: float) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.scale(s, s)
        p.translate(self._pad, self._pad)

    def _background(self, ops: list, s: float, dpr: float) -> QImage:
        """Fundo estático (caixa, néon, cabeçalho) desenhado uma vez para uma imagem e reaproveitado."""
        key = (self._wh, s, self._pad, dpr)
        if self._bg is not None and key == self._bg_key and ops == self._bg_ops:
            return self._bg
        img = QImage(max(1, round(self._wh[0] * dpr)), max(1, round(self._wh[1] * dpr)),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        try:
            self._setup(p, s)
            c = QtCanvas(p, s)
            for name, a, k in ops:
                getattr(c, name)(*a, **k)
        finally:
            p.end()
        self._bg, self._bg_key, self._bg_ops = img, key, ops
        return img

    def paintEvent(self, _event) -> None:
        t0 = clock()
        p = QPainter(self)
        try:
            s = self.scale()
            ops = self._ops or ()
            start, m = 0, self._mark
            if m >= 4 and not self.app.edit_mode:
                try:
                    p.drawImage(QPointF(0, 0), self._background(ops[:m], s, self.devicePixelRatioF()))
                    start = m
                except Exception:
                    log.warning("cache do fundo falhou (%s):\n%s", self.ov.key, traceback.format_exc())
                    self._mark = start = 0
            self._setup(p, s)
            c = QtCanvas(p, s)
            for name, a, k in (ops[start:] if start else ops):
                getattr(c, name)(*a, **k)
            self.paints += 1
            if self.app.edit_mode:
                w, h = getattr(self, "_size_base", (self.width() / s - 2 * self._pad, self.height() / s - 2 * self._pad))
                pen = QPen(QColor(255, 196, 0, 230), 1.5 / s, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(1, 1, w - 2, h - 2))
                label = f"{self.ov.title}  ·  {int(round(s * 100))}%"
                lw = c.measure(label, 11, 700) + 12
                c.rect(6, h - 22, lw, 18, (255, 196, 0, 235))
                c.text(12, h - 22, lw, 18, label, 11, (14, 16, 20, 255), "l", 700)
        finally:
            p.end()
            self.paint_s += clock() - t0

    # ---- arrastar / escalar (só com overlays desbloqueados) ------------- #
    def mousePressEvent(self, e) -> None:
        if self.app.edit_mode and e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e) -> None:
        if self._drag is not None:
            self._drag = None
            self.ocfg["x"], self.ocfg["y"] = self.x() + self._padpx(), self.y() + self._padpx()
            self.app.save_soon()

    def wheelEvent(self, e) -> None:
        if not self.app.edit_mode:
            return
        step = 0.05 if e.angleDelta().y() > 0 else -0.05
        self.ocfg["scale"] = round(max(0.4, min(3.0, self.scale() + step)), 2)
        self.force()
        self.app.save_soon()


# --------------------------------------------------------------------------- #
def _tray_icon() -> QIcon:
    ico = resource("assets/icon.ico")
    if ico.exists():
        icon = QIcon(str(ico))
        if not icon.isNull():
            return icon
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(230, 57, 70))
    p.drawRoundedRect(QRectF(4, 4, 56, 56), 12, 12)
    p.setBrush(QColor(255, 255, 255))
    for i, hgt in enumerate((18, 30, 42)):
        p.drawRoundedRect(QRectF(14 + i * 13, 50 - hgt, 9, hgt), 3, 3)
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------- #
_VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12}


def parse_hotkey(text: str) -> list[int]:
    """'ctrl+shift+o' -> lista de códigos de tecla do Windows."""
    out = []
    for part in (text or "").lower().replace(" ", "").split("+"):
        if not part:
            continue
        if part in _VK:
            out.append(_VK[part])
        elif len(part) == 1 and part.isalnum():
            out.append(ord(part.upper()))
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            out.append(0x70 + int(part[1:]) - 1)
        elif part in ("home", "end", "insert", "delete", "pageup", "pagedown", "space", "tab"):
            out.append({"home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E,
                        "pageup": 0x21, "pagedown": 0x22, "space": 0x20, "tab": 0x09}[part])
    return out


class Hotkeys:
    """Atalhos globais (funcionam com o jogo em primeiro plano), lidos por polling."""

    def __init__(self, mapping: dict[str, str], actions: dict) -> None:
        self.keys = {name: parse_hotkey(mapping.get(name, "")) for name in actions}
        self.actions = actions
        self.down = {name: False for name in actions}
        self._get = None
        if sys.platform == "win32":
            try:
                import ctypes
                self._get = ctypes.windll.user32.GetAsyncKeyState
            except Exception:
                self._get = None

    def poll(self) -> None:
        if self._get is None:
            return
        for name, vks in self.keys.items():
            if not vks:
                continue
            pressed = all(self._get(vk) & 0x8000 for vk in vks)
            if pressed and not self.down[name]:
                self.actions[name]()
            self.down[name] = pressed


class Joystick:
    """Botões do volante / button box via winmm (os primeiros 32 botões de cada dispositivo)."""

    def __init__(self) -> None:
        self.fn = None
        self.info = None
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            class JOYINFOEX(ctypes.Structure):
                _fields_ = [(n, wintypes.DWORD) for n in (
                    "dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos",
                    "dwButtons", "dwButtonNumber", "dwPOV", "dwReserved1", "dwReserved2")]

            fn = ctypes.WinDLL("winmm").joyGetPosEx
            fn.argtypes = [ctypes.c_uint, ctypes.POINTER(JOYINFOEX)]
            fn.restype = ctypes.c_uint
            info = JOYINFOEX()
            info.dwSize = ctypes.sizeof(JOYINFOEX)
            info.dwFlags = 0x80 | 0x100          # JOY_RETURNBUTTONS | JOY_RETURNRAWDATA
            self.fn, self.info, self._byref = fn, info, ctypes.byref
        except Exception:
            self.fn = None

    def buttons(self, jid: int) -> int | None:
        """Máscara de botões premidos do dispositivo `jid` (None se não existe)."""
        if self.fn is None:
            return None
        try:
            if self.fn(jid, self._byref(self.info)) == 0:
                return int(self.info.dwButtons)
        except Exception:
            pass
        return None


class ButtonBindings:
    """Liga botões do volante a ações (só reage ao premir, não enquanto está premido)."""

    def __init__(self, joy: Joystick, bindings: dict, actions: dict) -> None:
        self.joy = joy
        self.bindings = bindings          # ação -> [joy_id, botão] ou None (fica no config.json)
        self.actions = actions
        self.down: dict[str, bool] = {}
        self.learning: tuple[str, float, dict] | None = None

    def poll(self, now: float) -> str | None:
        """Devolve o nome da ação acabada de atribuir (modo aprender), se houver."""
        if self.joy.fn is None:
            return None
        if self.learning:
            action, until, base = self.learning
            if now > until:
                self.learning = None
                return ""
            for jid in range(16):
                b = self.joy.buttons(jid)
                if b is None:
                    continue
                new = b & ~base.get(jid, 0)
                if new:
                    btn = (new & -new).bit_length() - 1
                    self.bindings[action] = [jid, btn]
                    self.down[action] = True
                    self.learning = None
                    return action
                base[jid] = b
            return None
        cache: dict[int, int | None] = {}
        for action, bind in self.bindings.items():
            if not bind or action not in self.actions:
                continue
            jid, btn = int(bind[0]), int(bind[1])
            if jid not in cache:
                cache[jid] = self.joy.buttons(jid)
            mask = cache[jid]
            pressed = bool(mask is not None and mask >> btn & 1)
            if pressed and not self.down.get(action):
                self.actions[action]()
            self.down[action] = pressed
        return None

    def learn(self, action: str, now: float, seconds: float = 6.0) -> None:
        base = {}
        for jid in range(16):
            b = self.joy.buttons(jid)
            if b is not None:
                base[jid] = b
        self.learning = (action, now + seconds, base)


class OverlayApp:
    def __init__(self, root: Path, demo: bool) -> None:
        self.qapp = QApplication.instance() or QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)
        self.root = root
        self.cfg_path = root / "config.json"
        geo = self.qapp.primaryScreen().geometry()
        self.cfg = C.load(self.cfg_path, geo.width(), geo.height())
        g = self.cfg["global"]
        set_language(g.get("language", "en"))
        bundled = load_fonts()
        QtCanvas.families = bundled + [f for f in (g.get("font_families") or []) if f not in bundled]
        QtCanvas.fast_text = bool(g.get("fast_text", True))
        theme.set_class_rules(g.get("class_rules", theme.DEFAULT_CLASSES))
        theme.set_neon(g.get("neon", True))
        skins.apply(g.get("skin", "wec"), g.get("accent", "auto"))
        self.opacity = max(0.3, min(1.0, float(g.get("opacity", 1.0))))
        self.edit_mode = False
        self.hidden = False
        self.demo = demo
        self.source = self._make_source(demo)
        fo = self.cfg["overlays"]["fuel"]
        self.trackers = Trackers(root / "data", int(fo.get("avg_laps", 5)), float(fo.get("margin_laps", 0.5)))
        self._sync_ctx_cfg()
        self.actions = {"peek": self.peek, "toggle_all": self.toggle_hidden, "toggle_edit": self.toggle_edit,
                        "show_panel": self.show_panel, "tower_field": self.tower_field}
        hk = {**C.GLOBAL_DEFAULTS["hotkeys"], **(g.get("hotkeys") or {})}
        self.hotkeys = Hotkeys(hk, self.actions)
        g.setdefault("buttons", {})
        self.buttons = ButtonBindings(Joystick(), g["buttons"], self.actions)
        self._last_tick = clock()
        self._perf = [0.0, 0, 0]        # tempo acumulado, nº de frames, redesenhos
        self._perf_at = clock()
        self.load_ms = 0.0
        self.load_paints = 0.0
        self.load_fps = 0.0
        self.frame = 0
        self.hz = self.user_hz = 30
        self.period = 1 / 30
        self._input_every = 1
        if g.get("low_priority", True):
            self._lower_priority()
        self.icon = _tray_icon()
        from .updater import Updater
        from .version import UPDATE_REPO
        self.updater = Updater(g.get("update_repo") or UPDATE_REPO,
                               None if getattr(sys, "frozen", False) else self.root)
        Updater.cleanup_old()
        self.windows = [OverlayWindow(self, cls(self.cfg["overlays"][cls.key])) for cls in ALL]
        self.win_by_key = {w.ov.key: w for w in self.windows}
        self._clamp_on_screen()
        self.panel = self._make_panel()
        self._save_at = 0.0
        self._next_status = 0.0
        self._next_topmost = 0.0

        self.tray = QSystemTrayIcon(self.icon)
        self._build_tray_menu()
        self.tray.activated.connect(lambda reason: self.show_panel()
                                    if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

        self._set_hz(g.get("hz", 20))
        self._apply_perf()
        # Frames a ritmo certo: temporizador preciso, de uma só vez, apontado ao próximo prazo
        # (um temporizador normal no Windows atrasa até 15 ms e os overlays parecem "engasgar").
        self.timer = QTimer()
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timer)
        self._deadline = clock()
        self.timer.start(0)
        # menos pausas do recolhedor de lixo do Python a meio de um frame
        gc.collect()
        if hasattr(gc, "freeze"):
            gc.freeze()
        gc.set_threshold(5000, 25, 25)

    def _set_hz(self, hz, user: bool = True) -> None:
        try:
            hz = int(hz)
        except (TypeError, ValueError):
            hz = 30
        self.hz = max(MIN_HZ, min(240, hz))
        if user:
            self.user_hz = self.hz
        self.period = 1.0 / self.hz
        self._input_every = max(1, round(self.hz / 30))     # volante/teclado: ~30x por segundo chega
        for win in self.windows:
            fps = max(1.0, float(win.ocfg.get("fps", 10) or 10))
            # 60 ou mais = acompanha o FPS escolhido (a 120/144 fps os overlays com movimento também)
            win.every = 1 if fps >= 60 else max(1, round(self.hz / min(fps, float(self.hz))))
            win.phase = 0
            if user:                  # mudança feita pelo utilizador: redesenha já; pelo regulador não
                win.force()
        # Desfasa os overlays lentos para não calharem no mesmo frame: cada um fica com o
        # desfasamento que deixa o frame mais carregado o menos carregado possível.
        span = 1
        for e in {w.every for w in self.windows}:
            span = span * e // math.gcd(span, e)
        span = min(span, 240)
        occ = [0] * span
        for win in sorted((w for w in self.windows if w.every > 1), key=lambda w: w.every):
            best = min(range(win.every), key=lambda p: (max(occ[f] for f in range(span) if (f + p) % win.every == 0), p))
            win.phase = best
            for f in range(span):
                if (f + best) % win.every == 0:
                    occ[f] += 1

    def _on_timer(self) -> None:
        try:
            self.tick()
        finally:
            now = clock()
            # sem jogo ou sem nada à vista: 5 leituras por segundo chegam (quase zero CPU)
            self._deadline += 0.2 if getattr(self, "_idle", False) else self.period
            if now - self._deadline > self.period:      # muito atrasado (PC ocupado): recomeça daqui
                self._deadline = now
            self.timer.start(max(0, int((self._deadline - now) * 1000)))

    def _build_tray_menu(self) -> None:
        menu = QMenu()
        for text, fn in ((tr("ui.overlays"), self.show_panel), (tr("ui.unlock") + " / " + tr("ui.lock"), self.toggle_edit),
                         (tr("ui.quit"), self.quit)):
            act = QAction(text, menu)
            act.triggered.connect(fn)
            menu.addAction(act)
        self._menu = menu
        self.tray.setContextMenu(menu)

    def _sync_ctx_cfg(self) -> None:
        g = self.cfg["global"]
        self.trackers.ctx.cfg = {
            "green_flag_seconds": 5, "speed_unit": g.get("speed_unit", "kmh"),
            "pressure_unit": g.get("pressure_unit", "kPa"),
        }

    # ------------------------------------------------------------------ #
    def _make_source(self, demo: bool):
        return sims.make_source(self.cfg["global"].get("sim", sims.DEFAULT), demo)

    def status_text(self) -> str:
        if self.hidden:
            return tr("st.hidden", k=self.cfg["global"].get("hotkeys", {}).get("toggle_all", "").upper())
        key, extra = getattr(self.source, "status", ("waiting", ""))
        return tr(f"st.{key}", x=extra)

    def tick(self) -> None:
        now = clock()
        t_start = now
        dt = max(0.0, min(0.1, now - self._last_tick))
        self._last_tick = now
        self.frame += 1
        frame = self.frame
        if frame % self._input_every == 0:
            self.hotkeys.poll()
            learned = self.buttons.poll(now)
            if learned is not None:
                self.save_soon()
                self.panel.refresh_buttons()
        try:
            snap = self.source.read()
        except Exception:
            log.error("erro a ler dados:\n%s", traceback.format_exc())
            snap = None
        ctx = self.trackers.update(snap, now)
        ctx.edit_mode = self.edit_mode
        driving = snap is not None and snap.session.in_realtime
        show_all = not self.hidden and (self.edit_mode or driving or not self.cfg["global"]["hide_when_not_driving"])
        group = session_group(snap.session.kind) if snap is not None else None
        targets = {}
        for win in self.windows:
            want = bool(win.ocfg["enabled"]) and show_all
            if want and not self.edit_mode and group is not None:
                want = group in win.ocfg.get("sessions", ["practice", "qualy", "race"])
            if want and now >= win.vis_at:              # regra auto: reavaliada 5x por segundo
                win.vis_at = now + 0.2
                win.vis_ok = win.ov.visible(snap, ctx)
            target = want and win.vis_ok
            targets[win.ov.key] = target
            if target:
                win.feed(snap, ctx, frame)
            win.step_fade(target, dt)
        self._idle = (snap is None or not any(targets.values())) and not any(w.isVisible() for w in self.windows)
        # só se calcula o que está à vista
        self.trackers.track_inputs = targets.get("inputs", False)
        if hasattr(self.source, "need_positions"):
            self.source.need_positions = targets.get("blind_spot", True) or targets.get("track_map", True)
        if hasattr(self.source, "need_tyres"):
            self.source.need_tyres = any(
                targets.get(k, False) and "tyre" in (self.cfg["overlays"].get(k, {}).get("columns") or [])
                and self.cfg["overlays"].get(k, {}).get("style", "compact") == "compact" for k in ("relative", "standings"))

        st = getattr(self.source, "status", None)
        if st != getattr(self, "_last_status", None):        # regista mudanças de estado (ajuda no suporte)
            self._last_status = st
            log.info("estado da leitura: %s", st)
        if now >= self._next_status:
            self._next_status = now + 1.0
            self.updater.poll(time.time())
            if self.updater.state == "ready":                 # descarregado: troca e volta a abrir
                if self.updater.apply():
                    self.quit()
                    return
            self.panel.refresh()
            self.tray.setToolTip(f"LMU Overlays · {self.status_text()}")
        if now >= self._next_topmost and sys.platform == "win32":
            self._next_topmost = now + 3.0
            self._reassert_topmost()
        if self._save_at and now >= self._save_at:
            self._save_at = 0.0
            C.save(self.cfg_path, self.cfg)
        # medidor de carga (média de 2 s): cálculo + pintura, por frame
        self._perf[0] += clock() - t_start
        self._perf[1] += 1
        if now - self._perf_at >= 2.0:
            paints = sum(w.paints for w in self.windows)
            paint_s = sum(w.paint_s for w in self.windows)
            for w in self.windows:
                w.paint_s = 0.0
            span = now - self._perf_at
            self.load_ms = 1000 * (self._perf[0] + paint_s) / max(1, self._perf[1])
            self.load_paints = (paints - self._perf[2]) / span
            self.load_fps = self._perf[1] / span
            self._perf = [0.0, 0, paints]
            self._perf_at = now
            self._govern()

    def _apply_perf(self) -> None:
        smooth = self.cfg["global"].get("perf", "balanced") == "smooth"
        theme.LITE = not smooth
        Recorder.Q = 0.5 if smooth else 1.0

    def _govern(self) -> None:
        """Se a app estiver a gastar demasiado do tempo de cada frame, baixa os fps sozinha (e volta
        a subir quando há folga). Protege o jogo em PCs mais fracos."""
        share = self.load_ms / (1000.0 / self.hz)
        now = clock()
        if now - getattr(self, "_gov_at", -1e9) < 6.0:     # dá tempo à mudança anterior antes de medir de novo
            return
        target = self.hz
        if share > 0.12 and self.hz > MIN_HZ:
            target = max(MIN_HZ, int(self.hz * 0.75))
        elif share < 0.04 and self.hz < self.user_hz:
            target = min(self.user_hz, int(self.hz * 1.25) + 1)
        if target != self.hz:
            log.info("fps dos overlays: %s -> %s (carga %.0f%% do frame)", self.hz, target, share * 100)
            self._gov_at = now
            self._set_hz(target, user=False)

    def _lower_priority(self) -> None:
        """Prioridade 'abaixo do normal': o jogo tem sempre preferência no CPU."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL_PRIORITY_CLASS
        except Exception:
            pass
        if self.cfg["global"].get("perf", "balanced") == "smooth":
            return
        try:
            # "EcoQoS": o Windows corre a app nos núcleos de eficiência / a menor frequência, longe do jogo
            import ctypes

            class PPTS(ctypes.Structure):
                _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong), ("StateMask", ctypes.c_ulong)]
            st = PPTS(1, 0x1, 0x1)                                  # PROCESS_POWER_THROTTLING_EXECUTION_SPEED
            k32 = ctypes.windll.kernel32
            k32.SetProcessInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
            k32.SetProcessInformation(k32.GetCurrentProcess(), 4, ctypes.byref(st), ctypes.sizeof(st))
        except Exception:
            pass

    def peek(self) -> None:
        """Mostra tudo (completo) durante alguns segundos."""
        self.trackers.ctx.peek_until = clock() + float(self.cfg["global"].get("peek_s", 8.0))
        self.hidden = False
        for win in self.windows:
            win.vis_at = 0.0
            win.force()

    def tower_field(self) -> None:
        """Muda o campo da Torre (intervalo → gap → última → melhor → paragens → automático)."""
        from .overlays.tower import FIELDS
        ctx = self.trackers.ctx
        ctx.focus_field = (ctx.focus_field + 1) % (len(FIELDS) + 1)
        ctx.events["tower_req"] = clock()
        tw = self.win_by_key.get("tower")
        if tw:
            tw.force()

    def learn_button(self, action: str) -> None:
        self.buttons.learn(action, clock())
        self.panel.refresh_buttons()

    def clear_button(self, action: str) -> None:
        self.cfg["global"]["buttons"][action] = None
        self.save_soon()
        self.panel.refresh_buttons()

    def _reassert_topmost(self) -> None:
        """Alguns jogos em borderless tapam janelas 'topmost'; volta a pô-las por cima sem roubar o foco."""
        try:
            import ctypes
            from ctypes import wintypes
            u32 = ctypes.windll.user32
            u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            for win in self.windows:
                if win.isVisible():
                    u32.SetWindowPos(int(win.winId()), ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        except Exception:
            pass

    # ---- ações do painel ------------------------------------------------ #
    def save_soon(self) -> None:
        self._save_at = clock() + 1.0

    def repaint_all(self) -> None:
        for win in self.windows:
            win.force()
            win._applied = -1.0
            win.vis_at = 0.0

    def toggle_edit(self) -> None:
        self.edit_mode = not self.edit_mode
        if self.edit_mode:
            self.hidden = False
        for win in self.windows:
            win.set_locked(not self.edit_mode)
        if not self.edit_mode:                 # ao bloquear, as posições ficam logo guardadas
            C.save(self.cfg_path, self.cfg)
        self.repaint_all()
        self.panel.refresh()

    # ---- layouts guardados (posições, tamanhos e overlays ligados) ------ #
    LAYOUT_KEYS = ("x", "y", "scale", "enabled", "mode", "sessions")

    def _screen(self) -> tuple[int, int]:
        try:
            geo = self.qapp.primaryScreen().geometry()
            return max(1, int(geo.width())), max(1, int(geo.height()))
        except Exception:
            return 1920, 1080

    def layouts(self) -> dict:
        return self.cfg.setdefault("layouts", {})

    def save_layout(self, name: str) -> str:
        name = (name or "").strip()[:40] or tr("lay.default_name", n=len(self.layouts()) + 1)
        sw, sh = self._screen()
        self.layouts()[name] = {
            "screen": [sw, sh], "saved": time.strftime("%Y-%m-%d %H:%M"),
            "overlays": {w.ov.key: {k: w.ocfg[k] for k in self.LAYOUT_KEYS if k in w.ocfg} for w in self.windows},
        }
        C.save(self.cfg_path, self.cfg)
        return name

    def load_layout(self, name: str) -> bool:
        lay = self.layouts().get(name)
        if not isinstance(lay, dict):
            return False
        sw, sh = self._screen()
        ow, oh = (lay.get("screen") or [sw, sh])[:2]
        fx, fy = sw / max(1, ow), sh / max(1, oh)        # outro ecrã/resolução: ajusta as posições
        for w in self.windows:
            o = (lay.get("overlays") or {}).get(w.ov.key)
            if not isinstance(o, dict):
                continue
            for k in self.LAYOUT_KEYS:
                if k in o:
                    w.ocfg[k] = o[k]
            w.ocfg["x"], w.ocfg["y"] = int(w.ocfg.get("x", 0) * fx), int(w.ocfg.get("y", 0) * fy)
            if "mode" in o:
                w.ov.cfg["mode"] = o["mode"]
            w._place()
        self.cfg["global"]["layout"] = name
        self._clamp_on_screen()
        self.repaint_all()
        C.save(self.cfg_path, self.cfg)
        return True

    def delete_layout(self, name: str) -> None:
        self.layouts().pop(name, None)
        auto = self.cfg["global"].setdefault("layout_by_sim", {})
        for sim in [s for s, n in auto.items() if n == name]:
            auto.pop(sim, None)
        C.save(self.cfg_path, self.cfg)

    def set_sim_layout(self, sim: str, name: str | None) -> None:
        auto = self.cfg["global"].setdefault("layout_by_sim", {})
        if name:
            auto[sim] = name
        else:
            auto.pop(sim, None)
        self.save_soon()

    def _clamp_on_screen(self) -> None:
        """Nenhum overlay fica fora do ecrã (ex.: depois de mudar de resolução ou de monitor)."""
        try:                                   # todos os monitores juntos (overlays no 2.º ecrã ficam)
            g = self.qapp.primaryScreen().virtualGeometry()
            x0, y0 = int(g.x()), int(g.y())
            x1, y1 = x0 + int(g.width()), y0 + int(g.height())
        except Exception:
            return
        for w in self.windows:
            x, y = int(w.ocfg.get("x", 0)), int(w.ocfg.get("y", 0))
            nx, ny = max(x0, min(x1 - 60, x)), max(y0, min(y1 - 40, y))
            if (nx, ny) != (x, y):
                w.ocfg["x"], w.ocfg["y"] = nx, ny
                w._place()

    def toggle_hidden(self) -> None:
        self.hidden = not self.hidden
        self.panel.refresh()

    def set_enabled(self, win: OverlayWindow, on: bool) -> None:
        win.ocfg["enabled"] = on
        self.save_soon()

    def set_mode(self, win: OverlayWindow, mode: str) -> None:
        win.ocfg["mode"] = mode
        win.ov.cfg["mode"] = mode
        win.vis_at = 0.0
        win.force()
        self.save_soon()

    def write_diagnostics(self) -> Path:
        """Relatório para quem dá suporte: versão, simulador, estado da leitura e o fim do log."""
        import json as _json
        import platform
        from .version import VERSION
        src = self.source
        lines = [f"LMU Overlays {VERSION}", f"Python {sys.version.split()[0]} · {platform.platform()}",
                 f"simulador: {self.cfg['global'].get('sim')} · demo: {self.demo} · fonte: {type(src).__name__}",
                 f"estado: {getattr(src, 'status', None)} -> {self.status_text()}",
                 f"fps {self.load_fps:.0f} · {self.load_ms:.1f} ms/frame", "",
                 "diagnóstico da leitura:",
                 _json.dumps(getattr(src, "diag", {}), ensure_ascii=False, indent=2, default=str), "",
                 "overlays visíveis: " + ", ".join(w.ov.key for w in self.windows if w.isVisible()),
                 "erros a desenhar: " + ", ".join(f"{w.ov.key}={w._errors}" for w in self.windows if w._errors), ""]
        log_path = self.root / "lmu_overlays.log"
        try:
            lines += ["--- fim do log ---"] + log_path.read_text("utf-8", errors="replace").splitlines()[-120:]
        except OSError:
            lines.append("(sem log)")
        desk = Path.home() / "Desktop"
        out = (desk if desk.is_dir() else self.root) / "LMU Overlays - diagnostico.txt"
        out.write_text("\n".join(lines), "utf-8")
        try:
            if sys.platform == "win32":
                os.startfile(str(out))  # type: ignore[attr-defined]
        except Exception:
            pass
        return out

    def update_clicked(self) -> None:
        u = self.updater
        if u.state == "available":
            if u.frozen:
                u.download()
            else:                                          # a correr com Python: abre a página da versão
                import webbrowser
                webbrowser.open(u.release.get("page") or f"https://github.com/{u.repo}/releases")
        elif u.state in ("idle", "latest", "error"):
            u.check()
        self.panel.refresh_update()

    def set_overlay_opt(self, key: str, name: str, value) -> None:
        """Muda uma opção de um overlay (ex.: o tipo de volante do Input Graphics)."""
        win = self.win_by_key.get(key)
        if win is None:
            return
        win.ocfg[name] = value
        win.ov.cfg[name] = value
        win.force()
        self.save_soon()

    def set_session(self, win: OverlayWindow, sess: str, on: bool) -> None:
        cur = [s for s in win.ocfg.get("sessions", []) if s != sess]
        if on:
            cur.append(sess)
        win.ocfg["sessions"] = [s for s in ("practice", "qualy", "race") if s in cur]
        self.save_soon()

    def set_opacity(self, v: int) -> None:
        self.opacity = v / 100
        self.cfg["global"]["opacity"] = self.opacity
        self.repaint_all()
        self.save_soon()

    def set_global(self, key: str, value) -> None:
        self.cfg["global"][key] = value
        if key in ("accent", "skin"):
            skins.apply(self.cfg["global"].get("skin", "wec"), self.cfg["global"].get("accent", "auto"))
        if key == "neon":
            theme.set_neon(value)
        if key == "hz":
            self._set_hz(value)
        if key == "perf":
            self.cfg["global"]["hz"] = C.PERF_MODES.get(value, 20)
            self._set_hz(self.cfg["global"]["hz"])
            self._apply_perf()
        if key == "sim":
            auto = (self.cfg["global"].get("layout_by_sim") or {}).get(value)
            if auto:
                self.load_layout(auto)
            self.source = self._make_source(self.demo)
            self.trackers = Trackers(self.root / "data", int(self.cfg["overlays"]["fuel"].get("avg_laps", 5)),
                                     float(self.cfg["overlays"]["fuel"].get("margin_laps", 0.5)))
            self._sync_ctx_cfg()
            self.panel.refresh()
        self._sync_ctx_cfg()
        self.repaint_all()
        self.save_soon()

    def set_language(self, code: str) -> None:
        self.cfg["global"]["language"] = code
        set_language(code)
        self._build_tray_menu()
        old = self.panel
        self.panel = self._make_panel()
        self.panel.setGeometry(old.geometry())
        old.replacing = True
        old.hide()
        old.deleteLater()
        self.panel.show()
        self.repaint_all()
        self.save_soon()

    def _make_panel(self):
        """Painel com menu lateral (Início, Overlays, Layouts, Aspeto, Input Graphics, Controlos, Sistema)."""
        self.cfg["global"].pop("panel", None)          # opção antiga (painel de uma coluna): já não existe
        from .panel import ControlPanel
        return ControlPanel(self)

    def set_demo(self, on: bool) -> None:
        self.demo = on
        self.source = self._make_source(on)
        self.panel.refresh()

    def reset_positions(self) -> None:
        geo = self.qapp.primaryScreen().geometry()
        fresh = C.defaults(geo.width(), geo.height())["overlays"]
        for win in self.windows:
            for k in ("x", "y", "scale"):
                win.ocfg[k] = fresh[win.ov.key][k]
            win._place()
        self.repaint_all()
        self.save_soon()

    def show_panel(self) -> None:
        self.panel.showNormal()
        self.panel.raise_()
        self.panel.activateWindow()

    def quit(self) -> None:
        C.save(self.cfg_path, self.cfg)
        self.tray.hide()
        self.qapp.quit()

    def run(self) -> int:
        C.save(self.cfg_path, self.cfg)   # cria o config.json na primeira vez
        self.panel.show()
        return self.qapp.exec()


def main(root: Path, demo: bool = False) -> int:
    winmm = None
    if sys.platform == "win32":
        try:  # ícone próprio na barra de tarefas em vez do do Python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lmu.overlays")
        except Exception:
            pass
    try:
        return OverlayApp(root, demo).run()
    finally:
        if winmm is not None:
            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass
