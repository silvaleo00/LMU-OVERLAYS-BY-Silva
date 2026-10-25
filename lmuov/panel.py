"""Painel de controlo: janela com menu lateral (Início, Overlays, Aspeto, Comandos, Controlos, Sistema).

Pensado para quem abre a app pela primeira vez: no Início está o essencial (simulador, estado,
mover/mostrar/esconder), os overlays vêm agrupados por tema com uma frase a explicar cada um, e o
volante do Input Graphics escolhe-se com imagens (ou com uma foto tua).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSlider,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from . import config as C
from . import sims, skins, theme
from .i18n import LANGS, tr

CATEGORIES = (
    ("cat.race", ("tower", "relative", "battle", "standings", "track_map", "lap_counter", "team_radio")),
    ("cat.car", ("delta", "fuel", "advanced", "inputs", "tyres", "damage", "engine_temps")),
    ("cat.alerts", ("flags", "digital_flag", "blind_spot", "pitbox", "track_limits")),
    ("cat.weather", ("weather", "wind")),
)
PAGES = ("home", "overlays", "layouts", "look", "inputs", "controls", "system")
ICONS = {"home": "🏁", "overlays": "🧩", "layouts": "📐", "look": "🎨", "inputs": "🎮", "controls": "⌨", "system": "⚙"}

QSS = """
QWidget { background: #15171c; color: #e8ebf1; font-size: 13px; }
QListWidget#nav { background: #0f1115; border: none; padding: 8px 6px; font-size: 14px; }
QListWidget#nav::item { padding: 10px 12px; border-radius: 8px; margin: 2px 0; }
QListWidget#nav::item:selected { background: #2b6cff; color: white; }
QListWidget#nav::item:hover:!selected { background: #1d2028; }
QLabel#h1 { font-size: 20px; font-weight: 700; }
QLabel#h2 { font-size: 12px; font-weight: 700; color: #8a93a6; letter-spacing: 1px; margin-top: 10px; }
QLabel#dim { color: #8a93a6; }
QLabel#status { font-size: 14px; font-weight: 600; }
QFrame#card { background: #1d2028; border: 1px solid #262a34; border-radius: 10px; }
QFrame#card:hover { border-color: #33394a; }
QPushButton { background: #262a34; border: 1px solid #323745; border-radius: 8px; padding: 7px 12px; }
QPushButton:hover { background: #2e3340; }
QPushButton:checked { background: #2b6cff; border-color: #2b6cff; color: white; }
QPushButton#big { padding: 14px; font-size: 14px; font-weight: 600; text-align: left; }
QPushButton#primary { background: #2b6cff; border-color: #2b6cff; color: white; font-weight: 700; }
QPushButton#sess { padding: 4px 0; min-width: 30px; max-width: 30px; font-weight: 700; }
QToolButton { background: #1d2028; border: 1px solid #262a34; border-radius: 10px; padding: 6px; }
QToolButton:checked { border: 2px solid #2b6cff; background: #1c2a4a; }
QComboBox { background: #262a34; border: 1px solid #323745; border-radius: 6px; padding: 5px 8px; }
QComboBox QAbstractItemView { background: #1d2028; selection-background-color: #2b6cff; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; background: #3a3f4d; }
QCheckBox::indicator:checked { background: #2bd67b; }
QScrollArea { border: none; }
QSlider::groove:horizontal { height: 6px; background: #323745; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; margin: -6px 0; border-radius: 8px; background: #2b6cff; }
"""


def esc(s: str) -> str:
    """Os botões/caixas do Qt usam '&' para atalhos: '&&' mostra o '&' a sério."""
    return s.replace("&", "&&")


def card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 12)
    return f, lay


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def page(title: str, sub: str = "", badge: str = "") -> tuple[QWidget, QVBoxLayout]:
    """Página com título e conteúdo que faz scroll."""
    outer = QWidget()
    ol = QVBoxLayout(outer)
    ol.setContentsMargins(0, 0, 0, 0)
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    inner = QWidget()
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(22, 18, 22, 18)
    lay.setSpacing(10)
    if badge:                                   # título + etiqueta no canto direito
        top = QHBoxLayout()
        top.addWidget(label(title, "h1"))
        top.addStretch(1)
        b = QLabel(badge)
        b.setStyleSheet("background: #3a2a05; color: #ffb400; border: 1px solid #ffb400; border-radius: 6px;"
                        " padding: 3px 9px; font-size: 11px; font-weight: 700;")
        b.setToolTip("These overlays are still in development: things may change or break. "
                     "Send suggestions or bugs to silva.leo on Discord.")
        top.addWidget(b)
        lay.addLayout(top)
    else:
        lay.addWidget(label(title, "h1"))
    if sub:
        lay.addWidget(label(sub, "dim", wrap=True))
    sc.setWidget(inner)
    ol.addWidget(sc)
    return outer, lay


def pixmap(w: int, h: int, draw, scale: float = 1.0) -> QPixmap:
    """Desenha com o mesmo canvas dos overlays para uma imagem (pré-visualizações no painel)."""
    from .qt_app import QtCanvas
    pm = QPixmap(max(1, int(w * scale)), max(1, int(h * scale)))
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.scale(scale, scale)
        draw(QtCanvas(p, scale))
    finally:
        p.end()
    return pm


class ControlPanel(QWidget):
    def __init__(self, app) -> None:
        super().__init__(None)
        self.app = app
        self.replacing = False
        self.setWindowTitle("LMU Overlays (Beta)")
        self.setWindowIcon(app.icon)
        self.resize(860, 660)
        self.setMinimumSize(720, 520)
        self.setStyleSheet(QSS)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(200)
        self.stack = QStackedWidget()
        root.addWidget(self.nav)
        root.addWidget(self.stack, 1)
        self.bind_labels: dict[str, QLabel] = {}
        self._wheel_btns: dict[str, QToolButton] = {}

        builders = {"home": self._home, "overlays": self._overlays, "layouts": self._layouts, "look": self._look,
                    "inputs": self._inputs,
                    "controls": self._controls, "system": self._system}
        for key in PAGES:
            item = QListWidgetItem(f"{ICONS[key]}   {tr(f'nav.{key}')}")
            item.setSizeHint(QSize(180, 40))
            self.nav.addItem(item)
            self.stack.addWidget(builders[key]())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.refresh_buttons()
        self.refresh()

    def go(self, key: str) -> None:
        self.nav.setCurrentRow(PAGES.index(key))

    # ------------------------------------------------------------------ #
    def _home(self) -> QWidget:
        app, g = self.app, self.app.cfg["global"]
        w, lay = page(tr("nav.home"), tr("home.sub"), badge="BETA · in development")
        c, cl = card()
        top = QHBoxLayout()
        self.dot = QLabel("●")
        top.addWidget(self.dot)
        self.status = label("…", "status", wrap=True)
        top.addWidget(self.status, 1)
        cl.addLayout(top)
        self.load = label("", "dim")
        cl.addWidget(self.load)
        lay.addWidget(c)

        lay.addWidget(label(tr("ui.sim").upper(), "h2"))
        row = QHBoxLayout()
        self.sim_group = QButtonGroup(self)
        for key, name in sims.names().items():
            b = QPushButton(name)
            b.setCheckable(True)
            b.setChecked(g.get("sim", sims.DEFAULT) == key)
            b.setMinimumHeight(44)
            b.clicked.connect(lambda _c=False, k=key: app.set_global("sim", k))
            self.sim_group.addButton(b)
            row.addWidget(b)
        lay.addLayout(row)
        self.sim_hint = label("", "dim", wrap=True)
        lay.addWidget(self.sim_hint)

        lay.addWidget(label(tr("home.actions").upper(), "h2"))
        grid = QGridLayout()
        self.lock_btn = QPushButton()
        self.lock_btn.setObjectName("big")
        self.lock_btn.clicked.connect(app.toggle_edit)
        peek = QPushButton("👁   " + tr("act.peek"))
        peek.setObjectName("big")
        peek.clicked.connect(app.peek)
        self.hide_btn = QPushButton()
        self.hide_btn.setObjectName("big")
        self.hide_btn.clicked.connect(app.toggle_hidden)
        self.demo_btn = QPushButton("🎮   " + tr("ui.demo"))
        self.demo_btn.setObjectName("big")
        self.demo_btn.setCheckable(True)
        self.demo_btn.setChecked(app.demo)
        self.demo_btn.toggled.connect(app.set_demo)
        for i, b in enumerate((self.lock_btn, peek, self.hide_btn, self.demo_btn)):
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        lay.addWidget(label(tr("ui.hint"), "dim", wrap=True))

        lay.addWidget(label(tr("home.update").upper(), "h2"))
        c, cl = card()
        row = QHBoxLayout()
        self.ver_label = label("", "", wrap=True)
        row.addWidget(self.ver_label, 1)
        self.update_btn = QPushButton()
        self.update_btn.setObjectName("primary")
        self.update_btn.clicked.connect(app.update_clicked)
        row.addWidget(self.update_btn)
        cl.addLayout(row)
        lay.addWidget(c)
        lay.addStretch(1)
        sign = label("Made by Silva  ·  silva.leo on Discord for suggestions or fixes", "dim")
        sign.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sign.setStyleSheet("color: #6f778a; font-size: 12px; padding-top: 8px;")
        sign.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(sign)
        return w

    def _overlays(self) -> QWidget:
        app = self.app
        w, lay = page(tr("nav.overlays"), tr("ov.sub"))
        legend = label(tr("ov.legend"), "dim", wrap=True)
        lay.addWidget(legend)
        by_key = {win.ov.key: win for win in app.windows}
        for cat, keys in CATEGORIES:
            wins = [by_key[k] for k in keys if k in by_key]
            if not wins:
                continue
            lay.addWidget(label(tr(cat).upper(), "h2"))
            for win in wins:
                lay.addWidget(self._overlay_row(win))
        lay.addStretch(1)
        return w

    def _overlay_row(self, win) -> QFrame:
        app = self.app
        f, fl = card()
        row = QHBoxLayout()
        row.setSpacing(10)
        on = QCheckBox()
        on.setChecked(bool(win.ocfg["enabled"]))
        on.toggled.connect(lambda v, w=win: app.set_enabled(w, v))
        row.addWidget(on)
        txt = QVBoxLayout()
        txt.setSpacing(1)
        name = QLabel(win.ov.title)
        name.setStyleSheet("font-weight: 700; font-size: 14px; background: transparent;")
        txt.addWidget(name)
        d = label(tr(f"desc.{win.ov.key}"), "dim", wrap=True)
        d.setStyleSheet("background: transparent;")
        txt.addWidget(d)
        row.addLayout(txt, 1)
        for sess, key in (("practice", "ui.p"), ("qualy", "ui.q"), ("race", "ui.r")):
            b = QPushButton(tr(key))
            b.setObjectName("sess")
            b.setCheckable(True)
            b.setChecked(sess in win.ocfg.get("sessions", []))
            b.setToolTip(tr(f"sess.{sess}"))
            b.toggled.connect(lambda v, w=win, s=sess: app.set_session(w, s, v))
            row.addWidget(b)
        if win.ov.smart_capable:
            mode = QComboBox()
            mode.addItem(tr("ui.mode_auto"), "auto")
            mode.addItem(tr("ui.mode_always"), "always")
            mode.setCurrentIndex(0 if win.ov.mode() == "auto" else 1)
            mode.setToolTip(tr("ui.mode_tip"))
            mode.setFixedWidth(104)
            mode.currentIndexChanged.connect(lambda _i, w=win, m=mode: app.set_mode(w, m.currentData()))
            row.addWidget(mode)
            design = {"damage": ("design", "blueprint", ("blueprint", "engineer", "exploded", "corners", "heatmap", "mini"),
                                 "dmgd", "ui.dmg_design"),
                      "delta": ("style", "bar", ("bar", "full"), "deltad", "ui.delta_style"),
                      "tyres": ("temp_source", "inner", ("inner", "surface", "carcass"), "tsrc", "ui.tyre_src")}.get(win.ov.key)
            if design:                                  # escolher o design (dano) ou o estilo (delta)
                opt, dflt, values, pre, tip = design
                des = QComboBox()
                for d in values:
                    des.addItem(tr(f"{pre}.{d}"), d)
                des.setCurrentIndex(max(0, des.findData(win.ocfg.get(opt, dflt))))
                des.setToolTip(tr(tip))
                des.setFixedWidth(150)
                des.currentIndexChanged.connect(lambda _i, c=des, k=win.ov.key, o=opt: app.set_overlay_opt(k, o, c.currentData()))
                row.addWidget(des)
        if win.ov.key in ("relative", "standings"):    # colunas e estilo
            b = QPushButton("⚙  " + tr("cols.btn"))
            b.setFixedWidth(104)
            b.clicked.connect(lambda _c=False, w=win: self._columns_dialog(w))
            row.addWidget(b)
        elif win.ov.key == "inputs":
            b = QPushButton("⚙  " + tr("ov.options"))
            b.setFixedWidth(104)
            b.clicked.connect(lambda: self.go("inputs"))
            row.addWidget(b)
        elif not win.ov.smart_capable:
            sp = QLabel("")
            sp.setFixedWidth(104)
            row.addWidget(sp)
        fl.addLayout(row)
        return f

    def _columns_dialog(self, win) -> None:
        """Escolher o estilo e as colunas do Relative / Standings."""
        from .overlays import compact as K
        app, key = self.app, win.ov.key
        allowed, default = ((K.RELATIVE_COLS, K.REL_DEFAULT) if key == "relative"
                            else (K.STANDINGS_COLS, K.STD_DEFAULT))
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{win.ov.title} · {tr('cols.btn')}")
        dlg.setStyleSheet(QSS)
        v = QVBoxLayout(dlg)
        v.addWidget(label(tr("cols.style").upper(), "h2"))
        style = QComboBox()
        style.addItem(tr("cols.compact"), "compact")
        style.addItem(tr("cols.tv"), "tv")
        style.setCurrentIndex(max(0, style.findData(win.ocfg.get("style", "compact"))))
        style.currentIndexChanged.connect(lambda _i: app.set_overlay_opt(key, "style", style.currentData()))
        v.addWidget(style)
        v.addWidget(label(tr("cols.title").upper(), "h2"))
        v.addWidget(label(tr("cols.sub"), "dim", wrap=True))
        cur = list(win.ocfg.get("columns") or default)
        grid = QGridLayout()
        boxes = {}

        def changed(_v=False):
            cols = [k for k in K.ORDER if k in boxes and boxes[k].isChecked()]
            app.set_overlay_opt(key, "columns", cols)
        for i, k in enumerate(allowed):
            cb = QCheckBox("  " + tr(f"cols.{k}"))
            cb.setChecked(k in cur or k == "name")
            cb.setEnabled(k != "name")
            cb.toggled.connect(changed)
            boxes[k] = cb
            grid.addWidget(cb, i // 2, i % 2)
        v.addLayout(grid)
        ok = QPushButton(tr("cols.done"))
        ok.setObjectName("primary")
        ok.clicked.connect(dlg.accept)
        v.addWidget(ok)
        dlg.exec()

    def _layouts(self) -> QWidget:
        """Guardar e carregar posições: ex. um layout para o LMU e outro para o iRacing."""
        app = self.app
        w, lay = page(tr("nav.layouts"), tr("lay.sub"))
        row = QHBoxLayout()
        self.lay_name = QLineEdit()
        self.lay_name.setPlaceholderText(tr("lay.name_ph"))
        self.lay_name.setStyleSheet("background: #262a34; border: 1px solid #323745; border-radius: 6px; padding: 7px;")
        row.addWidget(self.lay_name, 1)
        save = QPushButton("💾   " + tr("lay.save"))
        save.setObjectName("primary")
        save.clicked.connect(self._save_layout)
        row.addWidget(save)
        lay.addLayout(row)
        self.lay_msg = label("", "dim")
        lay.addWidget(self.lay_msg)
        lay.addWidget(label(tr("lay.saved").upper(), "h2"))
        self.lay_list = QVBoxLayout()
        lay.addLayout(self.lay_list)
        lay.addWidget(label(tr("lay.auto_title").upper(), "h2"))
        self.lay_auto = QGridLayout()
        lay.addLayout(self.lay_auto)
        lay.addWidget(label(tr("lay.hint"), "dim", wrap=True))
        lay.addStretch(1)
        self._fill_layouts()
        return w

    def _fill_layouts(self) -> None:
        app = self.app
        for box in (self.lay_list, self.lay_auto):
            while box.count():
                it = box.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
        names = list(app.layouts())
        current = app.cfg["global"].get("layout")
        if not names:
            self.lay_list.addWidget(label(tr("lay.empty"), "dim", wrap=True))
        for name in names:
            f, fl = card()
            row = QHBoxLayout()
            info = app.layouts()[name]
            txt = QLabel(("✔  " if name == current else "") + name)
            txt.setStyleSheet("font-weight: 700; background: transparent;")
            row.addWidget(txt, 1)
            when = label(str(info.get("saved", "")), "dim")
            when.setStyleSheet("background: transparent;")
            row.addWidget(when)
            b = QPushButton(tr("lay.apply"))
            b.clicked.connect(lambda _c=False, n=name: self._apply_layout(n))
            row.addWidget(b)
            b = QPushButton(tr("lay.update"))
            b.setToolTip(tr("lay.update_tip"))
            b.clicked.connect(lambda _c=False, n=name: (app.save_layout(n), self._fill_layouts(),
                                                        self.lay_msg.setText(tr("lay.done_save", n=n))))
            row.addWidget(b)
            b = QPushButton("🗑")
            b.setFixedWidth(40)
            b.setToolTip(tr("lay.delete"))
            b.clicked.connect(lambda _c=False, n=name: (app.delete_layout(n), self._fill_layouts()))
            row.addWidget(b)
            fl.addLayout(row)
            self.lay_list.addWidget(f)
        auto = app.cfg["global"].get("layout_by_sim") or {}
        for i, (sim, sname) in enumerate(sims.names().items()):
            self.lay_auto.addWidget(QLabel(sname), i, 0)
            cb = QComboBox()
            cb.addItem(tr("lay.none"), "")
            for name in names:
                cb.addItem(name, name)
            cb.setCurrentIndex(max(0, cb.findData(auto.get(sim, ""))))
            cb.currentIndexChanged.connect(lambda _i, s=sim, c=cb: app.set_sim_layout(s, c.currentData() or None))
            self.lay_auto.addWidget(cb, i, 1)
        self.lay_auto.setColumnStretch(1, 1)

    def _save_layout(self) -> None:
        name = self.app.save_layout(self.lay_name.text())
        self.lay_name.clear()
        self.lay_msg.setText(tr("lay.done_save", n=name))
        self._fill_layouts()

    def _apply_layout(self, name: str) -> None:
        if self.app.load_layout(name):
            self.lay_msg.setText(tr("lay.done_load", n=name))
        self._fill_layouts()

    def _look(self) -> QWidget:
        app, g = self.app, self.app.cfg["global"]
        w, lay = page(tr("nav.look"), tr("look.sub"))
        grid = QGridLayout()
        grid.addWidget(QLabel(tr("ui.skin")), 0, 0)
        self.skin = QComboBox()
        for key, name in skins.names().items():
            self.skin.addItem(name, key)
        self.skin.setCurrentIndex(max(0, self.skin.findData(g.get("skin", "wec25"))))
        self.skin.currentIndexChanged.connect(lambda _i: (app.set_global("skin", self.skin.currentData()),
                                                          self._update_preview()))
        grid.addWidget(self.skin, 0, 1)
        grid.addWidget(QLabel(tr("ui.accent")), 1, 0)
        self.accent = QComboBox()
        self.accent.addItem(tr("ui.mode_auto"), "auto")
        for name in theme.ACCENTS:
            self.accent.addItem(name, name)
        self.accent.setCurrentIndex(max(0, self.accent.findData(g.get("accent", "auto"))))
        self.accent.currentIndexChanged.connect(lambda _i: (app.set_global("accent", self.accent.currentData()),
                                                            self._update_preview()))
        grid.addWidget(self.accent, 1, 1)
        grid.addWidget(QLabel(tr("ui.opacity")), 2, 0)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(30, 100)
        self.opacity.setValue(int(app.opacity * 100))
        self.opacity.valueChanged.connect(app.set_opacity)
        grid.addWidget(self.opacity, 2, 1)
        self.neon_cb = QCheckBox("  " + tr("ui.neon"))
        self.neon_cb.setChecked(bool(g.get("neon", True)))
        self.neon_cb.toggled.connect(lambda on: (app.set_global("neon", on), self._update_preview()))
        grid.addWidget(self.neon_cb, 3, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        lay.addWidget(label(tr("look.preview").upper(), "h2"))
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.preview.setStyleSheet("background: #3c4a5c; border-radius: 10px; padding: 10px;")
        lay.addWidget(self.preview)

        lay.addWidget(label(tr("look.region").upper(), "h2"))
        grid = QGridLayout()
        grid.addWidget(QLabel(tr("ui.language")), 0, 0)
        self.lang = QComboBox()
        for code, name in LANGS.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(g.get("language", "en"))))
        self.lang.currentIndexChanged.connect(lambda _i: app.set_language(self.lang.currentData()))
        grid.addWidget(self.lang, 0, 1)
        grid.addWidget(QLabel(tr("ui.speed_unit")), 1, 0)
        self.speed = QComboBox()
        for lab, val in (("km/h", "kmh"), ("mph", "mph")):
            self.speed.addItem(lab, val)
        self.speed.setCurrentIndex(max(0, self.speed.findData(g.get("speed_unit", "kmh"))))
        self.speed.currentIndexChanged.connect(lambda _i: app.set_global("speed_unit", self.speed.currentData()))
        grid.addWidget(self.speed, 1, 1)
        grid.addWidget(QLabel(tr("ui.pressure_unit")), 2, 0)
        self.press = QComboBox()
        for val in ("kPa", "psi", "bar"):
            self.press.addItem(val, val)
        self.press.setCurrentIndex(max(0, self.press.findData(g.get("pressure_unit", "kPa"))))
        self.press.currentIndexChanged.connect(lambda _i: app.set_global("pressure_unit", self.press.currentData()))
        grid.addWidget(self.press, 2, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        # logótipos das marcas: um botão por marca; carregar = escolher o PNG
        lay.addWidget(label(tr("logo.title").upper(), "h2"))
        lay.addWidget(label(tr("logo.sub"), "dim", wrap=True))
        from . import tv
        self.logo_grid = QGridLayout()
        self.logo_grid.setSpacing(6)
        self._logo_btns = {}
        codes = list(dict.fromkeys(cd for _k, cd in tv.BRANDS))
        for i, code in enumerate(codes):
            b = QToolButton()
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(54, 24))
            b.setFixedSize(84, 58)
            b.clicked.connect(lambda _c=False, cd=code: self._pick_logo(cd))
            self._logo_btns[code] = b
            self.logo_grid.addWidget(b, i // 6, i % 6)
        lay.addLayout(self.logo_grid)
        rm = QPushButton(tr("logo.clear"))
        rm.clicked.connect(self._clear_logos)
        lay.addWidget(rm)
        self._refresh_logos()
        lay.addStretch(1)
        self._update_preview()
        return w

    def _refresh_logos(self) -> None:
        from . import tv
        tv.reload_logos()
        for code, b in self._logo_btns.items():
            path = tv.logo_path(code)
            b.setText(code)
            if path:
                b.setIcon(QIcon(QPixmap(path).scaled(54, 24, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)))
            else:
                bg, ink = tv.BRAND_COLORS.get(code, tv.DEFAULT_BRAND)
                b.setIcon(QIcon(pixmap(54, 24, lambda c, bg=bg, ink=ink, cd=code: (
                    c.rect(4, 3, 46, 18, bg, radius=3), c.text(4, 3, 46, 18, cd, 11, ink, "c", 800)))))
            b.setToolTip(tr("logo.tip", c=code))

    def _logo_changed(self) -> None:
        from .qt_app import QtCanvas
        QtCanvas._pixmaps.clear()
        self._refresh_logos()
        for win in self.app.windows:
            win.force()
        self.app.repaint_all()

    def _pick_logo(self, code: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("logo.tip", c=code), "", "PNG (*.png)")
        if not path:
            return
        from .paths import app_dir
        dest_dir = app_dir() / "data" / "logos"
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(path, dest_dir / f"{code}.png")
        except OSError:
            return
        self._logo_changed()

    def _clear_logos(self) -> None:
        from .paths import app_dir
        d = app_dir() / "data" / "logos"
        if d.is_dir():
            for f in d.glob("*.png"):
                try:
                    f.unlink()
                except OSError:
                    pass
        self._logo_changed()

    def _update_preview(self) -> None:
        """Mostra como fica o estilo escolhido (Relativo + Delta com dados simulados)."""
        try:
            from .overlays import BY_KEY
            from .source_demo import DemoSource
            from .trackers import Trackers
            demo = DemoSource()
            trk = Trackers(None)
            snap = demo.snapshot()
            ctx = trk.update(snap, now=demo.t)
            ctx.peek_until = ctx.now + 5
            pad = theme.NEON_PAD
            parts = [BY_KEY["delta"](), BY_KEY["relative"]()]
            sizes = [o.size(snap, ctx) for o in parts]
            W = max(s[0] for s in sizes) + 2 * pad
            H = sum(s[1] + 2 * pad for s in sizes)

            def draw(c):
                y = 0.0
                for o, (ow, oh) in zip(parts, sizes):
                    c.p.save()
                    c.p.translate(pad, y + pad)
                    o.draw(c, snap, ctx, ow, oh)
                    c.p.restore()
                    y += oh + 2 * pad
            self.preview.setPixmap(pixmap(W, H, draw, 0.8))
        except Exception:
            self.preview.setText("—")

    def _inputs(self) -> QWidget:
        app = self.app
        o = app.cfg["overlays"]["inputs"]
        w, lay = page(tr("nav.inputs"), tr("inp.sub"))
        lay.addWidget(label(tr("inp.modules").upper(), "h2"))
        grid = QGridLayout()
        opts = (("show_gear", "inp.gear"), ("show_wheel", "inp.wheel"), ("show_trace", "inp.trace"),
                ("show_pedals", "inp.pedals"), ("show_clutch", "inp.clutch"), ("show_steering_trace", "inp.steer"),
                ("show_aids", "inp.aids"))
        for i, (k, lab) in enumerate(opts):
            cb = QCheckBox("  " + tr(lab))
            cb.setChecked(bool(o.get(k, True)))
            cb.toggled.connect(lambda v, kk=k: app.set_overlay_opt("inputs", kk, v))
            grid.addWidget(cb, i // 2, i % 2)
        lay.addLayout(grid)

        lay.addWidget(label(tr("inp.wheel_type").upper(), "h2"))
        from .wheels import STYLES, draw_wheel
        import math
        grid = QGridLayout()
        grid.setSpacing(8)
        self.wheel_group = QButtonGroup(self)
        self.wheel_group.setExclusive(True)
        for i, st in enumerate(STYLES):
            b = QToolButton()
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setText(f"{i + 1} · {tr(f'wheel.{st}')}")
            b.setIconSize(QSize(64, 64))
            b.setFixedSize(116, 100)
            img = None
            if st == "custom":
                from .overlays.inputs import wheel_image
                img = wheel_image(o.get("wheel_image", ""))
            b.setIcon(QIcon(pixmap(72, 72, lambda c, s=st, im=img: draw_wheel(
                c, 36, 36, 30, math.radians(-12), s, image=im, gear="4", speed="172", rpm=0.8), 1.0)))
            b.setChecked(o.get("wheel", "simple") == st)
            b.clicked.connect(lambda _c=False, s=st: self._pick_wheel(s))
            self.wheel_group.addButton(b)
            self._wheel_btns[st] = b
            grid.addWidget(b, i // 5, i % 5)
        lay.addLayout(grid)
        row = QHBoxLayout()
        up = QPushButton("📷   " + tr("inp.upload"))
        up.clicked.connect(self._upload_wheel)
        row.addWidget(up)
        self.wheel_file = label(o.get("wheel_image", "") or "", "dim")
        row.addWidget(self.wheel_file, 1)
        lay.addLayout(row)
        lay.addWidget(label(tr("inp.upload_hint"), "dim", wrap=True))
        lay.addStretch(1)
        return w

    def _pick_wheel(self, style: str) -> None:
        self.app.set_overlay_opt("inputs", "wheel", style)
        if style == "custom" and not self.app.cfg["overlays"]["inputs"].get("wheel_image"):
            self._upload_wheel()

    def _upload_wheel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("inp.upload"), "", "PNG (*.png);;Imagens (*.png *.jpg *.jpeg)")
        if not path:
            return
        from .paths import app_dir
        dest_dir = app_dir() / "data" / "wheels"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / Path(path).name
        try:
            if Path(path).resolve() != dest.resolve():
                shutil.copyfile(path, dest)
        except OSError:
            return
        self.app.set_overlay_opt("inputs", "wheel_image", dest.name)
        self.app.set_overlay_opt("inputs", "wheel", "custom")
        self.wheel_file.setText(dest.name)
        b = self._wheel_btns.get("custom")
        if b is not None:
            b.setChecked(True)
            b.setIcon(QIcon(QPixmap(str(dest)).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation)))

    def _controls(self) -> QWidget:
        app, g = self.app, self.app.cfg["global"]
        w, lay = page(tr("nav.controls"), tr("ctl.sub"))
        hk = {**C.GLOBAL_DEFAULTS["hotkeys"], **(g.get("hotkeys") or {})}
        for action in ("peek", "tower_field", "toggle_all", "toggle_edit", "show_panel"):
            c, cl = card()
            row = QHBoxLayout()
            txt = QVBoxLayout()
            nm = QLabel(tr(f"act.{action}"))
            nm.setStyleSheet("font-weight: 700; background: transparent;")
            txt.addWidget(nm)
            kb = label("⌨  " + hk.get(action, "").upper(), "dim")
            kb.setStyleSheet("background: transparent;")
            txt.addWidget(kb)
            row.addLayout(txt, 1)
            if action != "show_panel":
                lab = QLabel()
                lab.setStyleSheet("background: transparent;")
                self.bind_labels[action] = lab
                row.addWidget(lab)
                b1 = QPushButton("🎮  " + tr("ui.assign"))
                b1.clicked.connect(lambda _c=False, a=action: app.learn_button(a))
                row.addWidget(b1)
                b2 = QPushButton("✕")
                b2.setFixedWidth(34)
                b2.setToolTip(tr("ui.clear"))
                b2.clicked.connect(lambda _c=False, a=action: app.clear_button(a))
                row.addWidget(b2)
            cl.addLayout(row)
            lay.addWidget(c)
        lay.addWidget(label(tr("ctl.hint"), "dim", wrap=True))
        lay.addStretch(1)
        return w

    def _system(self) -> QWidget:
        app, g = self.app, self.app.cfg["global"]
        w, lay = page(tr("nav.system"), "")
        lay.addWidget(label(tr("perf.title").upper(), "h2"))
        lay.addWidget(label(tr("perf.sub"), "dim", wrap=True))
        self.perf_group = QButtonGroup(self)
        cur = g.get("perf", "balanced")
        for key in ("light", "balanced", "smooth"):
            b = QPushButton(f"{tr(f'perf.{key}')}   ·   {C.PERF_MODES[key]} fps\n{tr(f'perf.{key}_d')}")
            b.setObjectName("big")
            b.setCheckable(True)
            b.setChecked(cur == key)
            b.clicked.connect(lambda _c=False, k=key: app.set_global("perf", k))
            self.perf_group.addButton(b)
            lay.addWidget(b)
        self.hide_cb = QCheckBox("  " + tr("ui.hide"))
        self.hide_cb.setChecked(bool(g["hide_when_not_driving"]))
        self.hide_cb.toggled.connect(lambda on: app.set_global("hide_when_not_driving", on))
        lay.addWidget(self.hide_cb)
        self.garage_cb = QCheckBox("  " + tr("ui.garage"))
        self.garage_cb.setChecked(bool(g.get("show_in_garage", True)))
        self.garage_cb.toggled.connect(lambda on: app.set_global("show_in_garage", on))
        lay.addWidget(self.garage_cb)
        reset = QPushButton(tr("ui.reset"))
        reset.clicked.connect(app.reset_positions)
        lay.addWidget(reset)
        diag = QPushButton("🩺   " + tr("ui.diag"))
        diag.clicked.connect(app.write_diagnostics)
        lay.addWidget(diag)
        lay.addWidget(label(tr("ui.diag_hint"), "dim", wrap=True))
        quit_btn = QPushButton("⏻   " + tr("ui.quit"))
        quit_btn.clicked.connect(app.quit)
        lay.addWidget(quit_btn)
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        app = self.app
        self.lock_btn.setText(("🔒   " + tr("ui.lock")) if app.edit_mode else ("✋   " + tr("ui.unlock")))
        self.hide_btn.setText(("👀   " + tr("home.show")) if app.hidden else ("🙈   " + tr("home.hide")))
        key = getattr(app.source, "status", ("waiting", ""))[0]
        ok = key in ("connected", "ir_connected", "demo") or app.demo
        if key in ("ir_not_driving", "connected_waiting"):
            ok = None
        col = "#2bd67b" if ok else ("#4aa3ff" if ok is None else "#ffb400")
        self.dot.setStyleSheet(f"color: {col}; font-size: 18px;")
        self.status.setText(app.status_text())
        self.load.setText(tr("ui.load", ms=f"{app.load_ms:.1f}", p=f"{app.load_paints:.0f}", f=f"{app.load_fps:.0f}"))
        sim = app.cfg["global"].get("sim", sims.DEFAULT)
        self.sim_hint.setText(tr(f"sim.hint_{sim}"))
        for b in self.sim_group.buttons():
            b.setChecked(b.text() == sims.names().get(sim))
        self.refresh_update()

    def refresh_update(self) -> None:
        from .version import VERSION
        u = self.app.updater
        st = u.state
        info = tr("ui.version", v=VERSION)
        btn, enabled = "", True
        if st == "off":
            info += " · " + tr("ui.update_off")
        elif st in ("idle", "latest", "error"):
            btn = tr("ui.update_check")
            if st == "latest":
                info += " · " + tr("ui.update_latest")
            elif st == "error":
                info += " · " + tr("ui.update_error", x=u.error)
        elif st == "checking":
            btn, enabled = tr("ui.update_checking"), False
        elif st == "available":
            btn = tr("ui.update_btn", v=u.release["version"])
            info += " · " + tr("ui.update_new", v=u.release["version"])
        elif st == "downloading":
            btn, enabled = tr("ui.update_downloading", p=f"{u.progress * 100:.0f}"), False
        elif st == "ready":
            btn, enabled = tr("ui.update_restart"), False
        self.ver_label.setText(info)
        self.ver_label.setToolTip(u.error if st == "error" else (u.release or {}).get("notes", ""))
        self.update_btn.setVisible(bool(btn))
        self.update_btn.setText(btn)
        self.update_btn.setEnabled(enabled)

    def refresh_buttons(self) -> None:
        learning = self.app.buttons.learning[0] if self.app.buttons.learning else None
        for action, lab in self.bind_labels.items():
            bind = self.app.cfg["global"].get("buttons", {}).get(action)
            if action == learning:
                lab.setText(tr("ui.press"))
                lab.setStyleSheet("color: #ffb400; font-weight: 700; background: transparent;")
            else:
                lab.setText(tr("ui.joy", j=bind[0] + 1, b=bind[1] + 1) if bind else "—")
                lab.setStyleSheet("background: transparent;")

    def closeEvent(self, e) -> None:
        if not self.replacing:
            self.app.quit()
        e.accept()
