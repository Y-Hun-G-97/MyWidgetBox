# -*- coding: utf-8 -*-
import sys
import os
import math
import time

import ctypes
from ctypes import wintypes
import win32api
import win32gui
import win32con
try:
    import win32ui
except Exception:
    win32ui = None
try:
    import win32com.client
except Exception:
    win32com = None
else:
    win32com = win32com.client
try:
    import win32pdh
except Exception:
    win32pdh = None
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtMultimedia import *
try:
    from PyQt6.QtMultimediaWidgets import QVideoWidget, QGraphicsVideoItem
except Exception:
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    QGraphicsVideoItem = None

def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "on"):
            return True
        if v in ("0", "false", "no", "off"):
            return False
    return default


class GpuUsageSampler:
    """Windows GPU utilization sampler via PDH counters."""

    def __init__(self):
        self._query = None
        self._counters = []
        self._last_refresh = 0.0
        self._enabled = win32pdh is not None
        if self._enabled:
            self._rebuild_query()

    def close(self):
        if self._query is not None and win32pdh is not None:
            try:
                win32pdh.CloseQuery(self._query)
            except Exception:
                pass
        self._query = None
        self._counters = []

    def _rebuild_query(self):
        self.close()
        if not self._enabled or win32pdh is None:
            return
        try:
            query = win32pdh.OpenQuery()
            _, instances = win32pdh.EnumObjectItems(
                None, None, "GPU Engine", win32pdh.PERF_DETAIL_WIZARD
            )
            counters = []
            for inst in instances:
                if not inst or inst == "_Total":
                    continue
                try:
                    path = win32pdh.MakeCounterPath(
                        (None, "GPU Engine", inst, None, 0, "Utilization Percentage")
                    )
                    counters.append(win32pdh.AddCounter(query, path))
                except Exception:
                    continue
            self._query = query
            self._counters = counters
            self._last_refresh = time.monotonic()
            if self._query is not None:
                try:
                    win32pdh.CollectQueryData(self._query)
                except Exception:
                    pass
        except Exception:
            self.close()

    def sample_pct(self):
        if not self._enabled or win32pdh is None:
            return None
        if self._query is None or not self._counters:
            self._rebuild_query()
            if self._query is None or not self._counters:
                return None
        now = time.monotonic()
        if now - self._last_refresh > 10.0:
            self._rebuild_query()
            if self._query is None or not self._counters:
                return None

        try:
            win32pdh.CollectQueryData(self._query)
        except Exception:
            self._rebuild_query()
            return None

        total = 0.0
        valid_count = 0
        for counter in self._counters:
            try:
                v = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)[1]
                if v > 0.0:
                    total += float(v)
                valid_count += 1
            except Exception:
                continue
        if valid_count == 0:
            return None
        # Normalize to a familiar 0..100 scale.
        return max(0.0, min(100.0, total))

# Overlay widget for selection highlight
class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)


    def paintEvent(self, event):
        painter = QPainter(self)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))


class ResizeHandleOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Big corner triangles; offset outward so rounded window mask clips the 90deg tip.
        self.handle_size = 36
        self.handle_margin = -12

    def _handle_rects(self):
        s = self.handle_size
        m = self.handle_margin
        w = max(0, self.width() - s - m)
        h = max(0, self.height() - s - m)
        return {
            "tl": QRect(m, m, s, s),
            "tr": QRect(w, m, s, s),
            "bl": QRect(m, h, s, s),
            "br": QRect(w, h, s, s),
        }

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 110))

        s = int(self.handle_size)
        o = max(0, -int(self.handle_margin))
        w = max(0, self.width())
        h = max(0, self.height())

        # Top-left
        painter.drawPolygon(
            QPolygon([
                QPoint(-o, -o),
                QPoint(s, -o),
                QPoint(-o, s),
            ])
        )
        # Top-right
        painter.drawPolygon(
            QPolygon([
                QPoint(w + o, -o),
                QPoint(w - s, -o),
                QPoint(w + o, s),
            ])
        )
        # Bottom-left
        painter.drawPolygon(
            QPolygon([
                QPoint(-o, h + o),
                QPoint(-o, h - s),
                QPoint(s, h + o),
            ])
        )
        # Bottom-right
        painter.drawPolygon(
            QPolygon([
                QPoint(w + o, h + o),
                QPoint(w - s, h + o),
                QPoint(w + o, h - s),
            ])
        )


class DesktopIconCloneOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._items = []
        self._font = self._resolve_icon_title_font()
        self._flags = int(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
            | Qt.TextFlag.TextWrapAnywhere
            | Qt.TextFlag.TextDontClip
        )

    @staticmethod
    def _resolve_icon_title_font():
        try:
            class LOGFONTW(ctypes.Structure):
                _fields_ = [
                    ("lfHeight", ctypes.c_long),
                    ("lfWidth", ctypes.c_long),
                    ("lfEscapement", ctypes.c_long),
                    ("lfOrientation", ctypes.c_long),
                    ("lfWeight", ctypes.c_long),
                    ("lfItalic", ctypes.c_ubyte),
                    ("lfUnderline", ctypes.c_ubyte),
                    ("lfStrikeOut", ctypes.c_ubyte),
                    ("lfCharSet", ctypes.c_ubyte),
                    ("lfOutPrecision", ctypes.c_ubyte),
                    ("lfClipPrecision", ctypes.c_ubyte),
                    ("lfQuality", ctypes.c_ubyte),
                    ("lfPitchAndFamily", ctypes.c_ubyte),
                    ("lfFaceName", ctypes.c_wchar * 32),
                ]

            spi_geticontitlelogfont = 0x001F
            lf = LOGFONTW()
            ok = ctypes.windll.user32.SystemParametersInfoW(
                int(spi_geticontitlelogfont),
                int(ctypes.sizeof(LOGFONTW)),
                ctypes.byref(lf),
                0,
            )
            if ok:
                face = str(lf.lfFaceName or "").strip() or "Segoe UI"
                font = QFont(face)
                h = int(abs(int(lf.lfHeight or 0)))
                if h > 0:
                    font.setPixelSize(h)
                weight = int(lf.lfWeight or 400)
                if weight >= 600:
                    font.setBold(True)
                font.setItalic(bool(lf.lfItalic))
                return font
        except Exception:
            pass
        return QFont("Segoe UI", 9)

    def set_items(self, items):
        self._items = list(items or [])
        self.update()

    def _elided_icon_label_text(self, text, label_rect, selected=False, focused=False):
        raw = str(text or "")
        if not raw:
            return ""
        # Explorer-like behavior: idle desktop labels are visually constrained and elided.
        if bool(selected) or bool(focused):
            return raw
        if not isinstance(label_rect, QRect):
            return raw
        max_width = max(10, int(label_rect.width()))
        max_height = max(10, int(label_rect.height()))
        fm = QFontMetrics(self._font)
        line_h = max(1, int(fm.lineSpacing()))
        max_lines = max(1, min(2, int(max_height // line_h)))
        src = raw.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        if max_lines <= 1:
            return str(fm.elidedText(src, Qt.TextElideMode.ElideRight, int(max_width)))
        if fm.horizontalAdvance(src) <= int(max_width):
            return src

        lines = []
        remaining = str(src)
        for i in range(int(max_lines)):
            if not remaining:
                break
            is_last = (i == int(max_lines - 1))
            if is_last:
                lines.append(str(fm.elidedText(remaining, Qt.TextElideMode.ElideRight, int(max_width))))
                remaining = ""
                break
            if fm.horizontalAdvance(remaining) <= int(max_width):
                lines.append(str(remaining))
                remaining = ""
                break
            lo = 1
            hi = len(remaining)
            best = 1
            while lo <= hi:
                mid = (lo + hi) // 2
                chunk = remaining[:mid]
                if fm.horizontalAdvance(chunk) <= int(max_width):
                    best = int(mid)
                    lo = int(mid + 1)
                else:
                    hi = int(mid - 1)
            part = str(remaining[:max(1, int(best))]).rstrip()
            lines.append(part if part else remaining[:1])
            remaining = str(remaining[max(1, int(best)):]).lstrip()

        if not lines:
            return str(fm.elidedText(src, Qt.TextElideMode.ElideRight, int(max_width)))
        return "\n".join([ln for ln in lines if ln])

    def paintEvent(self, event):
        if not self._items:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._font)
        for item in self._items:
            if not isinstance(item, dict):
                continue
            edit_rect = item.get("edit_rect")
            if isinstance(edit_rect, QRect):
                if int(edit_rect.width()) > 0 and int(edit_rect.height()) > 0:
                    painter.setPen(QPen(QColor(74, 130, 218, 230), 1))
                    painter.setBrush(QColor(255, 255, 255, 230))
                    painter.drawRoundedRect(QRectF(edit_rect), 2.0, 2.0)
                    txt = str(item.get("edit_text", "") or "")
                    if txt:
                        painter.setPen(QColor(18, 18, 18, 255))
                        painter.drawText(
                            QRect(
                                int(edit_rect.x()) + 4,
                                int(edit_rect.y()) + 1,
                                max(0, int(edit_rect.width()) - 6),
                                max(0, int(edit_rect.height()) - 2),
                            ),
                            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                            txt,
                        )
                continue

            selected = bool(item.get("selected", False))
            focused = bool(item.get("focused", False))
            select_rect = item.get("select_rect")
            if isinstance(select_rect, QRect) and int(select_rect.width()) > 0 and int(select_rect.height()) > 0:
                if selected:
                    painter.setPen(QPen(QColor(112, 170, 255, 230), 1))
                    painter.setBrush(QColor(64, 136, 255, 96))
                    painter.drawRoundedRect(QRectF(select_rect), 4.0, 4.0)
                elif focused:
                    painter.setPen(QPen(QColor(150, 192, 255, 170), 1, Qt.PenStyle.DotLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(QRectF(select_rect), 4.0, 4.0)

            icon_rect = item.get("icon_rect")
            icon_pm = item.get("icon_pixmap")
            if (
                isinstance(icon_rect, QRect)
                and isinstance(icon_pm, QPixmap)
                and not icon_pm.isNull()
                and int(icon_rect.width()) > 0
                and int(icon_rect.height()) > 0
            ):
                target = QRect(icon_rect)
                if int(target.width()) != int(icon_pm.width()) or int(target.height()) != int(icon_pm.height()):
                    target = QRect(
                        int(icon_rect.x() + ((int(icon_rect.width()) - int(icon_pm.width())) // 2)),
                        int(icon_rect.y() + ((int(icon_rect.height()) - int(icon_pm.height())) // 2)),
                        int(icon_pm.width()),
                        int(icon_pm.height()),
                    )
                painter.drawPixmap(target, icon_pm)

            label_rect = item.get("label_rect")
            text = str(item.get("text", "") or "")
            if isinstance(label_rect, QRect) and int(label_rect.width()) > 0 and int(label_rect.height()) > 0 and text:
                # Explorer label bounds are tight; expand slightly to avoid glyph clipping.
                draw_rect = QRect(label_rect).adjusted(-4, 0, 4, 2)
                display_text = self._elided_icon_label_text(
                    text,
                    draw_rect,
                    selected=bool(selected),
                    focused=bool(focused),
                )
                if not display_text:
                    continue
                shadow_rect = QRect(draw_rect).translated(1, 1)
                painter.setPen(QColor(0, 0, 0, 190))
                painter.drawText(shadow_rect, self._flags, display_text)
                painter.setPen(QColor(255, 255, 255, 255))
                painter.drawText(draw_rect, self._flags, display_text)


class DownwardComboBox(QComboBox):
    def showPopup(self):
        super().showPopup()
        popup = self.view().window() if self.view() else None
        if popup is None:
            return
        popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        popup.setStyleSheet("QFrame { background-color: #23344d; border: 1px solid #5977a4; }")
        popup.setContentsMargins(0, 0, 0, 0)
        popup.setMinimumWidth(max(self.width(), popup.width()))
        popup.move(self.mapToGlobal(QPoint(0, self.height() + 3)))


class ProfileRowWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self._selected = False
        self._action_buttons = []
        self.setMouseTracking(True)

    def set_action_buttons(self, buttons):
        self._action_buttons = list(buttons)
        self._apply_action_visibility()

    def set_hovered(self, hovered):
        self._hovered = bool(hovered)
        self.setProperty("hovered", "true" if self._hovered else "false")
        self._apply_action_visibility()
        self._refresh_style()

    def set_selected(self, selected):
        self._selected = bool(selected)
        self.setProperty("selected", "true" if self._selected else "false")
        self._apply_action_visibility()
        self._refresh_style()

    def enterEvent(self, event):
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_hovered(False)
        super().leaveEvent(event)

    def _apply_action_visibility(self):
        visible = self._hovered or self._selected
        for btn in self._action_buttons:
            btn.setVisible(visible)

    def _refresh_style(self):
        style = self.style()
        if style:
            style.unpolish(self)
            style.polish(self)
        self.update()


class ProfileListWidget(QListWidget):
    orderChanged = pyqtSignal(list)

    def dropEvent(self, event):
        super().dropEvent(event)
        ordered_ids = []
        for idx in range(self.count()):
            item = self.item(idx)
            if item is None:
                continue
            raw_pid = item.data(Qt.ItemDataRole.UserRole)
            if raw_pid in (None, ""):
                continue
            ordered_ids.append(str(raw_pid))
        self.orderChanged.emit(ordered_ids)


class SetNameLabel(QLabel):
    renameRequested = pyqtSignal(str)

    def __init__(self, set_id, text="", parent=None):
        super().__init__(text, parent)
        self._set_id = str(set_id)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.renameRequested.emit(self._set_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class SetManagerDialog(QDialog):
    def __init__(self, master, parent=None):
        super().__init__(parent if parent is not None else master)
        self.master = master
        self._title_bar_themed = False
        self.setObjectName("setManagerDialog")
        self.setWindowTitle("세트 관리")
        self.setWindowIcon(QIcon())
        self.setFixedSize(360, 198)
        self.setStyleSheet("""
            QDialog#setManagerDialog { background-color: #1f2f46; }
            QFrame#setCard {
                background-color: #23344d;
                border: 1px solid #3f567a;
                border-radius: 12px;
            }
            QLabel#setTitle {
                color: #eef3ff;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel {
                color: #d7e4fb;
                font-size: 12px;
            }
            QPushButton {
                min-height: 30px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 10px;
                color: #e6efff;
                background-color: #2a3f60;
                border: 1px solid #4a6591;
            }
            QPushButton:hover { background-color: #35527d; }
            QPushButton#copyBtn {
                background-color: #2b5664;
                border: 1px solid #41798b;
            }
            QPushButton#copyBtn:hover { background-color: #346676; }
            QPushButton#deleteBtn {
                background-color: #6e4048;
                border: 1px solid #955761;
                color: #ffe4e9;
            }
            QPushButton#deleteBtn:hover { background-color: #7b4a54; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        card = QFrame()
        card.setObjectName("setCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(8)

        title = QLabel("세트 관리")
        title.setObjectName("setTitle")
        card_layout.addWidget(title)

        self.info_label = QLabel("")
        card_layout.addWidget(self.info_label)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.copy_btn = QPushButton("다른 세트 복사")
        self.copy_btn.setObjectName("copyBtn")
        self.delete_btn = QPushButton("현재 세트 삭제")
        self.delete_btn.setObjectName("deleteBtn")
        row1.addWidget(self.copy_btn)
        row1.addWidget(self.delete_btn)
        card_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        close_btn = QPushButton("닫기")
        row2.addStretch()
        row2.addWidget(close_btn)
        card_layout.addLayout(row2)

        root.addWidget(card)

        self.copy_btn.clicked.connect(self._copy_set)
        self.delete_btn.clicked.connect(self._delete_set)
        close_btn.clicked.connect(self.accept)

        self._refresh_info()

    def showEvent(self, event):
        if not self._title_bar_themed:
            self._title_bar_themed = True
            try:
                self.master._apply_window_title_bar_theme(self)
            except Exception:
                pass
        super().showEvent(event)

    def _refresh_info(self):
        sid = self.master.selected_set_id()
        data = self.master._set_defs.get(sid, {})
        name = str(data.get("name", f"세트{sid}" if sid else "세트"))
        count = len(data.get("profiles", []))
        self.info_label.setText(f"현재 세트: {name}  |  위젯 {count}개")
        self.delete_btn.setEnabled(len(self.master._set_order) > 1)

    def _copy_set(self):
        items = self.master.get_set_items()
        if not items:
            return
        target_sid = self.master.selected_set_id()
        choices = [(str(sid), str(name)) for sid, name, _ in items if str(sid) != str(target_sid)]
        labels = [f"{name} ({sid})" for sid, name in choices]
        if not labels:
            QMessageBox.information(self, "세트 복사", "복사할 다른 세트가 없습니다.")
            return
        sid_by_label = {labels[i]: choices[i][0] for i in range(len(choices))}
        source_label, ok = self.master._prompt_choice_dialog(
            "세트 복사", "현재 세트로 가져올 원본 세트:", labels
        )
        if not ok or not source_label:
            return
        source_sid = sid_by_label.get(source_label, "")
        if self.master.copy_profiles_from_set(source_sid, target_sid):
            self.master.load_profiles()
            self._refresh_info()
            self.accept()

    def _delete_set(self):
        sid = self.master.selected_set_id()
        if not sid:
            return
        if self.master.delete_set(sid):
            self._refresh_info()
            self.accept()


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_data=None):
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("위젯 상세 설정")
        self.setWindowIcon(QIcon())
        self._title_bar_themed = False
        self.resize(760, 680)
        self.setFixedWidth(760)
        self.setStyleSheet("""
            QDialog#settingsDialog {
                background-color: #1d2a3d;
            }
            QFrame#settingsHeader {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QLabel#settingsTitle {
                color: #eef3ff;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#settingsSubtitle {
                color: #c2d1ea;
                font-size: 12px;
            }
            QFrame#settingsCard {
                background-color: #23344d;
                border: 1px solid #3f567a;
                border-radius: 12px;
            }
            QFrame#settingsRightPanel {
                background-color: transparent;
                border: none;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLabel#pathLabel {
                color: #d0dcf1;
                padding: 2px 0 6px 0;
            }
            QSpinBox, QComboBox {
                min-height: 34px;
                color: #edf3ff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                border-radius: 9px;
                padding: 2px 10px;
            }
            QSpinBox:focus, QComboBox:focus {
                border: 1px solid #77a3f2;
            }
            QComboBox {
                padding-right: 18px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #23344d;
                color: #eef4ff;
                border: none;
                selection-background-color: #3f5e8e;
                selection-color: #ffffff;
                outline: 0;
                font-size: 13px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 5px 8px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #435a7d;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: #8eb8ff;
            }
            QPushButton {
                min-height: 34px;
                border-radius: 9px;
                font-size: 12px;
                font-weight: 600;
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #3f5e8e;
            }
            QPushButton:pressed {
                background-color: #324f79;
            }
            QPushButton#primaryBtn {
                background-color: #4f79de;
                border: 1px solid #7e9eeb;
            }
            QPushButton#primaryBtn:hover {
                background-color: #5d86e6;
            }
            QPushButton#masterBtn {
                background-color: #35507a;
                border: 1px solid #5977a4;
                min-height: 30px;
            }
            QPushButton#masterBtn:hover {
                background-color: #3f5e8e;
            }
            QCheckBox {
                color: #e6eefc;
                spacing: 7px;
                min-height: 28px;
            }
            QToolButton#shortcutToggle {
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                border-radius: 9px;
                padding: 6px 12px;
                text-align: left;
                font-weight: 600;
            }
            QToolButton#shortcutToggle:hover {
                background-color: #3f5e8e;
            }
            QFrame#shortcutPanel {
                background-color: #233854;
                border: 1px solid #5879a9;
                border-radius: 10px;
            }
            QLabel#shortcutText {
                color: #c6d6f3;
                font-size: 13px;
                line-height: 1.4;
            }
        """)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("settingsHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(3)
        title_label = QLabel("위젯 상세 설정")
        title_label.setObjectName("settingsTitle")
        subtitle_label = QLabel("현재 위젯의 재생/표시/상호작용 설정을 변경합니다")
        subtitle_label.setObjectName("settingsSubtitle")
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        root.addWidget(header)

        card = QFrame()
        card.setObjectName("settingsCard")
        root.addWidget(card, 1)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(24)
        card_layout.addLayout(content_row, 1)

        left_panel = QWidget(card)
        left_form = QFormLayout(left_panel)
        left_form.setContentsMargins(0, 0, 0, 0)
        left_form.setHorizontalSpacing(12)
        left_form.setVerticalSpacing(8)
        left_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        right_panel = QFrame(card)
        right_panel.setObjectName("settingsRightPanel")
        right_form = QFormLayout(right_panel)
        right_form.setContentsMargins(0, 0, 0, 0)
        right_form.setHorizontalSpacing(12)
        right_form.setVerticalSpacing(8)
        right_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        content_row.addWidget(left_panel, 5)
        content_row.addWidget(right_panel, 5)

        s = settings_data if settings_data else {}
        
        self.folder_path = s.get('folder_path', "")
        self.exec_path = s.get('exec_path', "")
        
        self.folder_label = QLabel(self.folder_path if self.folder_path else "미지정")
        self.folder_label.setObjectName("pathLabel")
        self.folder_label.setWordWrap(True)
        self.folder_btn = QPushButton("폴더 선택")
        self.exec_label = QLabel(os.path.basename(self.exec_path) if self.exec_path else "미지정")
        self.exec_label.setObjectName("pathLabel")
        self.exec_label.setWordWrap(True)
        self.exec_btn = QPushButton("실행파일 선택")
        
        self.width_input = QSpinBox(); self.width_input.setRange(50, 5000)
        self.width_input.setValue(s.get('w', 200))
        self.height_input = QSpinBox(); self.height_input.setRange(50, 5000)
        self.height_input.setValue(s.get('h', 200))
        self.sec_input = QSpinBox(); self.sec_input.setRange(1, 3600)
        self.sec_input.setValue(s.get('interval', 5))


        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        curr_op = s.get('opacity_pct', 100)
        self.opacity_slider.setValue(curr_op)
        self.opacity_slider.setFixedHeight(26)
    
        self.opacity_spinbox = QSpinBox()
        self.opacity_spinbox.setRange(10, 100)
        self.opacity_spinbox.setValue(curr_op)
        self.opacity_spinbox.setSuffix("%")
        self.opacity_slider.setToolTip("100% = 완전 표시, 10% = 거의 투명")
        self.opacity_spinbox.setToolTip("100% = 완전 표시, 10% = 거의 투명")
        for _sb in (self.width_input, self.height_input, self.sec_input, self.opacity_spinbox):
            _sb.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            _sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.opacity_slider.valueChanged.connect(self.opacity_spinbox.setValue)
        self.opacity_spinbox.valueChanged.connect(self.opacity_slider.setValue)
        
        if parent and hasattr(parent, 'preview_opacity'):
            self.opacity_slider.valueChanged.connect(parent.preview_opacity)


        self.bg_combo = DownwardComboBox(); self.bg_combo.addItems(["투명", "검정", "흰색"])
        self.bg_combo.setCurrentIndex(s.get('bg_color_mode', 1))
        self.bg_combo.setView(QListView())
        self.bg_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.bg_combo.setStyle(QStyleFactory.create("Fusion"))
        self.bg_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.bg_combo.setMinimumHeight(36)

        self.corner_combo = DownwardComboBox()
        self.corner_combo.addItems(["곡선", "직각"])
        self.corner_combo.setCurrentIndex(max(0, min(int(s.get('corner_mode', 0)), 1)))
        self.corner_combo.setView(QListView())
        self.corner_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.corner_combo.setStyle(QStyleFactory.create("Fusion"))
        self.corner_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.corner_combo.setMinimumHeight(36)

        self.media_mode_combo = DownwardComboBox()
        self.media_mode_combo.addItems(["원본 유지 (전체 보기)", "위젯 채우기 (중앙 크롭)"])
        self.media_mode_combo.setCurrentIndex(max(0, min(int(s.get('media_fit_mode', 0)), 1)))
        self.media_mode_combo.setView(QListView())
        self.media_mode_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.media_mode_combo.setStyle(QStyleFactory.create("Fusion"))
        self.media_mode_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.media_mode_combo.setMinimumHeight(36)

        self.layer_combo = DownwardComboBox()
        self.layer_combo.addItems([
            "0: 화면 뒤 (아이콘 위)",
            "1: 일반",
            "2: 화면 앞 (최상단)"
        ])
        layer_idx = DesktopWidget.coerce_layer_mode(
            s.get('layer_mode', DesktopWidget.LAYER_NORMAL),
            s.get('layer_schema_version', DesktopWidget.LAYER_SCHEMA_VERSION),
        )
        self.layer_combo.setCurrentIndex(layer_idx)
        self.layer_combo.setView(QListView())
        self.layer_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.layer_combo.setStyle(QStyleFactory.create("Fusion"))
        self.layer_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.layer_combo.setMinimumHeight(36)

        self.lock_cb = QCheckBox("클릭 잠금 (마우스 통과)")
        self.lock_cb.setChecked(_as_bool(s.get('is_locked', False), False))
        
        self.mute_checkbox = QCheckBox("음소거")
        self.mute_checkbox.setChecked(_as_bool(s.get('is_muted', True), True))
        self.gpu_guard_checkbox = QCheckBox("GPU 고부하 시 영상/GIF 자동 일시정지")
        self.gpu_guard_checkbox.setChecked(_as_bool(s.get('gpu_guard_enabled', False), False))
        self.mute_hint_label = QLabel(
            "위젯 위 단축키:\n"
            "- 스크롤: 파일 변경\n"
            "- Ctrl+스크롤: 불투명도 조절\n"
            "- Shift+코너 드래그: 크기 조절\n"
            "- Alt+클릭: 마우스 잠금 토글\n"
            "- G: 임시 그룹 토글\n"
            "- Ctrl+G: 임시 그룹 전체 해제\n"
            "- H: 성능 보호 토글\n"
            "- R: 모서리 모드 전환\n"
            "- M: 음소거 토글\n"
            "- O: 설정 상세\n"
            "- P: 위젯 종료\n"
            "- C: 위젯 컨트롤러"
        )
        self.mute_hint_label.setObjectName("shortcutText")
        self.mute_hint_label.setWordWrap(True)
        self.shortcut_panel = QFrame(self)
        self.shortcut_panel.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        )
        self.shortcut_panel.setObjectName("shortcutPanel")
        self.shortcut_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.shortcut_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.shortcut_panel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        shortcut_layout = QVBoxLayout(self.shortcut_panel)
        shortcut_layout.setContentsMargins(10, 8, 10, 8)
        shortcut_layout.setSpacing(0)
        shortcut_layout.addWidget(self.mute_hint_label)

        self.shortcut_toggle = QToolButton()
        self.shortcut_toggle.setObjectName("shortcutToggle")
        self.shortcut_toggle.setCheckable(True)
        self.shortcut_toggle.setChecked(False)
        self.shortcut_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.shortcut_toggle.toggled.connect(self._set_shortcut_panel_visible)
        self._set_shortcut_panel_visible(False)

        self.master_btn = QPushButton("위젯 컨트롤러 열기")
        self.master_btn.setObjectName("masterBtn")


        left_form.addRow("미디어 폴더:", self.folder_btn)
        left_form.addRow("", self.folder_label)
        left_form.addRow("실행 파일:", self.exec_btn)
        left_form.addRow("", self.exec_label)
        left_form.addRow("너비:", self.width_input)
        left_form.addRow("높이:", self.height_input)
        left_form.addRow("재생 간격(초):", self.sec_input)
        left_form.addRow("불투명도(%):", self.opacity_spinbox)
        left_form.addRow("", self.opacity_slider)

        right_form.addRow("배경색:", self.bg_combo)
        right_form.addRow("모서리:", self.corner_combo)
        right_form.addRow("미디어 맞춤:", self.media_mode_combo)
        right_form.addRow("레이어:", self.layer_combo)
        right_form.addRow("클릭 잠금:", self.lock_cb)
        right_form.addRow("음소거:", self.mute_checkbox)
        right_form.addRow("성능 보호:", self.gpu_guard_checkbox)
        
        btns = QHBoxLayout(); apply = QPushButton("저장"); cancel = QPushButton("취소")
        btns.setSpacing(12)
        btns.setContentsMargins(0, 0, 0, 0)
        apply.setObjectName("primaryBtn")
        apply.setFixedSize(86, 30)
        cancel.setFixedSize(86, 30)
        self.master_btn.setFixedSize(146, 30)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)
        action_row.addWidget(self.shortcut_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        action_row.addWidget(self.master_btn, 0, Qt.AlignmentFlag.AlignLeft)
        action_row.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(apply)
        action_row.addLayout(btns)
        card_layout.addLayout(action_row)
        
        self.folder_btn.clicked.connect(self.select_folder)
        self.exec_btn.clicked.connect(self.select_exec)
        self.master_btn.clicked.connect(self.open_master)
        apply.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        QTimer.singleShot(0, self._apply_title_bar_theme)
        QTimer.singleShot(0, self._sync_dialog_height)

    def _set_shortcut_panel_visible(self, expanded):
        expanded = bool(expanded)
        self.shortcut_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.shortcut_toggle.setText("단축키 안내")
        if expanded:
            self._place_shortcut_panel()
            self.shortcut_panel.show()
            self.shortcut_panel.raise_()
            self.shortcut_panel.activateWindow()
        else:
            self.shortcut_panel.hide()
        self.shortcut_panel.update()

    def _sync_dialog_height(self):
        # Release any previous fixed-height lock so collapse/expand can recalculate.
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        if self.layout():
            self.layout().invalidate()
            self.layout().activate()
        target_height = max(420, self.minimumSizeHint().height())
        if self.height() != target_height:
            self.resize(self.width(), target_height)

    def _place_shortcut_panel(self):
        self.shortcut_panel.adjustSize()
        hint = self.shortcut_panel.sizeHint()
        popup_w = max(300, max(300, hint.width()))
        popup_h = hint.height()

        anchor_global = self.shortcut_toggle.mapToGlobal(QPoint(0, self.shortcut_toggle.height() + 6))
        x = anchor_global.x()
        y = anchor_global.y()

        screen = QGuiApplication.screenAt(anchor_global) or self.screen() or QGuiApplication.primaryScreen()
        if screen:
            ag = screen.availableGeometry()
            max_x = ag.right() - popup_w - 8
            min_x = ag.left() + 8
            x = max(min_x, min(x, max_x))

            # Keep panel below the button; if space is tight, shrink height instead of moving above.
            available_below = max(120, ag.bottom() - y - 8)
            popup_h = min(popup_h, available_below)

        self.shortcut_panel.setGeometry(x, y, popup_w, popup_h)

    def _apply_title_bar_theme(self):
        if self._title_bar_themed:
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(20),
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
            self._title_bar_themed = True
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_title_bar_theme()
        self._sync_dialog_height()
        if self.shortcut_toggle.isChecked():
            self._place_shortcut_panel()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.shortcut_toggle.isChecked() and self.shortcut_panel.isVisible():
            self._place_shortcut_panel()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.shortcut_toggle.isChecked() and self.shortcut_panel.isVisible():
            self._place_shortcut_panel()

    def closeEvent(self, event):
        if hasattr(self, "shortcut_panel") and self.shortcut_panel.isVisible():
            self.shortcut_panel.hide()
        super().closeEvent(event)

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if path: self.folder_path = path; self.folder_label.setText(path)

    def select_exec(self):
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "실행 파일 (*.exe *.lnk);;모든 파일 (*)")
        if path: self.exec_path = path; self.exec_label.setText(os.path.basename(path))

    def open_master(self):

        master = self.parent().manager if hasattr(self.parent(), 'manager') else None
        
        if master:
            anchor_rect = self.frameGeometry()
            QTimer.singleShot(
                0,
                lambda m=master, a=QRect(anchor_rect): m.show_master_window(anchor_rect=a, restart=True),
            )
            self.reject()



class DesktopWidget(QMainWindow):
    _desktop_icon_listview_hwnd = 0
    _desktop_icon_cache_hwnd = 0
    _desktop_icon_cache_ts = 0.0
    _desktop_icon_cache_rects = []
    _desktop_icon_cache_max_age = 0.16
    _desktop_caption_path_cache_ts = 0.0
    _desktop_caption_path_cache = {}
    _desktop_icon_alpha_cache = {}
    _desktop_icon_pixmap_cache = {}
    _desktop_icon_image_cache = {}
    _desktop_text_alpha_cache = {}
    _desktop_icon_title_font_cache = None
    _desktop_icon_title_font_cache_ts = 0.0
    _desktop_sys_himl_large = 0
    _desktop_shell_items_cache_ts = 0.0
    _desktop_shell_items_cache = {}
    _desktop_shell_items_cache_list = []
    _desktop_icon_edit_info = {}
    LAYER_BACK = 0
    LAYER_NORMAL = 1
    LAYER_TOPMOST = 2
    LAYER_SCHEMA_VERSION = 4

    @classmethod
    def coerce_layer_mode(cls, raw_layer, schema_version=None):
        try:
            val = int(raw_layer)
        except Exception:
            return int(cls.LAYER_NORMAL)
        try:
            schema = int(schema_version) if schema_version is not None else int(cls.LAYER_SCHEMA_VERSION)
        except Exception:
            schema = 0
        if schema >= int(cls.LAYER_SCHEMA_VERSION):
            return max(int(cls.LAYER_BACK), min(int(cls.LAYER_TOPMOST), int(val)))
        # v3 layout: 0(retired), 1(back/icon-above), 2(normal), 3(top)
        if schema == 3:
            v3_map = {
                0: int(cls.LAYER_BACK),
                1: int(cls.LAYER_BACK),
                2: int(cls.LAYER_NORMAL),
                3: int(cls.LAYER_TOPMOST),
            }
            return int(v3_map.get(int(val), int(cls.LAYER_NORMAL)))
        # v2 layout: 0(bottom), 1(icon-above), 2(normal), 3(top)
        if schema == 2:
            v2_map = {
                0: int(cls.LAYER_BACK),
                1: int(cls.LAYER_BACK),
                2: int(cls.LAYER_NORMAL),
                3: int(cls.LAYER_TOPMOST),
            }
            return int(v2_map.get(int(val), int(cls.LAYER_NORMAL)))
        # Legacy v1 migration: 0(back), 1(normal), 2(top)
        legacy_map = {
            0: int(cls.LAYER_BACK),
            1: int(cls.LAYER_NORMAL),
            2: int(cls.LAYER_TOPMOST),
            3: int(cls.LAYER_TOPMOST),
        }
        return int(legacy_map.get(int(val), int(cls.LAYER_NORMAL)))

    def __init__(self, profile_id, name, manager):
        super().__init__()
        self.profile_id = profile_id
        self.manager = manager
        self.settings = QSettings("MyHomeApp", f"Profile_{profile_id}")
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow) 

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(50, 50)
        self.setAcceptDrops(True)
        
        self.container = QWidget(); self.container.setObjectName("mainContainer")
        self.container.setMinimumSize(0, 0)
        self.container.setAcceptDrops(True)
        self.setCentralWidget(self.container)
        self.main_layout = QVBoxLayout(self.container); self.main_layout.setContentsMargins(0,0,0,0)
        
        self.stack = QStackedWidget()
        self.stack.setMinimumSize(0, 0)
        self.stack.setAcceptDrops(True)
        self.main_layout.addWidget(self.stack)

        self.selection_overlay = OverlayWidget(self)
        self.selection_overlay.hide()
        self.resize_overlay = ResizeHandleOverlay(self)
        self.resize_overlay.hide()
        self.desktop_icon_clone_overlay = DesktopIconCloneOverlay(self)
        self.desktop_icon_clone_overlay.hide()
        self.size_hud = QLabel(self)
        self.size_hud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.size_hud.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_hud.setStyleSheet(
            "QLabel { color: white; background-color: rgba(0, 0, 0, 150); "
            "border: 1px solid rgba(255, 255, 255, 80); border-radius: 8px; padding: 4px 10px; }"
        )
        self.size_hud.hide()
        self.action_hud = QLabel(self)
        self.action_hud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.action_hud.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.action_hud.setStyleSheet(
            "QLabel { color: white; background-color: rgba(0, 0, 0, 150); "
            "border: 1px solid rgba(255, 255, 255, 80); border-radius: 8px; padding: 3px 10px; }"
        )
        self.action_hud.hide()
        self.action_hud_timer = QTimer(self)
        self.action_hud_timer.setSingleShot(True)
        self.action_hud_timer.timeout.connect(self.action_hud.hide)
        self.group_badge = QLabel("G", self)
        self.group_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.group_badge.setStyleSheet(
            "QLabel { color: #eff7ff; background-color: rgba(40, 86, 146, 180); "
            "border: 1px solid rgba(145, 192, 255, 170); border-radius: 9px; padding: 1px 6px; "
            "font-size: 10pt; font-weight: 700; }"
        )
        self.group_badge.hide()
        self._size_hud_top_padding = 10
        self.resize_corner = None
        self.is_resizing = False
        self.resize_start_pos = None
        self.resize_start_geo = QRect()
        self.is_moving = False
        self._drag_topmost_active = False
        self._drag_restore_layer = None
        self._drag_restore_lock = None
        self._cursor_inside = False
        self._drag_threshold = 5
        self._axis_snap_threshold = 4
        self._axis_snap_release = 8
        self._snap_lock_x = None
        self._snap_lock_y = None
        self._snap_origin_pointer_x = None
        self._snap_origin_pointer_y = None
        self._shortcut_last_ms = {}


        self.placeholder = QWidget()
        self.placeholder.setMinimumSize(0, 0)
        self.placeholder.setAcceptDrops(True)
        self.placeholder.setStyleSheet("background: #222; border-radius: 20px;")
        p_layout = QVBoxLayout(self.placeholder); p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_label = QLabel("NEW"); new_label.setStyleSheet("font-size: 40px; font-weight: bold; color: rgba(255,255,255,0.4); background: transparent;")
        hint_label = QLabel("우클릭으로 설정"); hint_label.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.3); background: transparent;")
        p_layout.addWidget(new_label); p_layout.addWidget(hint_label)
        self.stack.addWidget(self.placeholder)


        self.img_label = QLabel(); self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setMinimumSize(0, 0)
        self.img_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.img_label.setAcceptDrops(True)
        self.stack.addWidget(self.img_label)
        
        self.video_scene = None
        self.video_item = None
        self._video_graphics_mode = bool(QGraphicsVideoItem is not None)
        if self._video_graphics_mode:
            self.video_widget = QGraphicsView()
            self.video_widget.setFrameShape(QFrame.Shape.NoFrame)
            self.video_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.video_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.video_widget.setInteractive(False)
            self.video_widget.setStyleSheet("QGraphicsView { background: transparent; border: none; }")
            self.video_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.video_widget.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
            self.video_scene = QGraphicsScene(self.video_widget)
            self.video_scene.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
            self.video_widget.setScene(self.video_scene)
            self.video_item = QGraphicsVideoItem()
            self.video_scene.addItem(self.video_item)
            try:
                vp = self.video_widget.viewport()
                if isinstance(vp, QWidget):
                    vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    vp.setAutoFillBackground(False)
            except Exception:
                pass
        else:
            self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(0, 0)
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_widget.setAcceptDrops(True)
        self.stack.addWidget(self.video_widget)

        self.setMouseTracking(True)
        self.container.setMouseTracking(True)
        self.stack.setMouseTracking(True)
        self.placeholder.setMouseTracking(True)
        self.img_label.setMouseTracking(True)
        self.video_widget.setMouseTracking(True)

        self.placeholder.installEventFilter(self)
        self.img_label.installEventFilter(self)
        self.video_widget.installEventFilter(self)
        self.container.installEventFilter(self)
        self.stack.installEventFilter(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput(); self.media_player.setAudioOutput(self.audio_output)
        if self._video_graphics_mode and self.video_item is not None:
            self.media_player.setVideoOutput(self.video_item)
        else:
            self.media_player.setVideoOutput(self.video_widget)
        self._last_unmuted_volume = 1.0
        self._audio_output_attached = True
        self.media_player.mediaStatusChanged.connect(self.check_video_status)
        self.media_player.errorOccurred.connect(self._on_video_error)

        self.timer = QTimer(self); self.timer.timeout.connect(self.next_media)
        self.movie = None; self.playlist = []; self.current_idx = -1; self.start_pos = None
        self.current_static_pixmap = None
        self.current_media_path = None
        self.media_fail_counts = {}
        self.quarantined_media = set()
        self.max_media_failures = 1
        self._failure_scheduled = False
        self._media_resetting = False
        self.gpu_guard_enabled = False
        self.media_fit_mode = 0  # 0: 원본 유지(전체 표시), 1: 위젯 채우기(중앙 크롭)
        self._performance_paused = False
        self._perf_paused_video = False
        self._perf_paused_gif = False
        self._perf_gif_timer_was_active = False
        self._gif_loop_watch_active = False
        self._gif_loop_last_frame = -1
        self._gif_loop_min_deadline = 0.0
        self._gif_loop_fallback_timer = QTimer(self)
        self._gif_loop_fallback_timer.setSingleShot(True)
        self._gif_loop_fallback_timer.timeout.connect(self._on_gif_loop_fallback_timeout)
        self._gif_swap_pending_movie = None
        self._gif_swap_pending_path = ""
        self._gif_swap_pending_duration_ms = 0
        self._gif_swap_timeout = QTimer(self)
        self._gif_swap_timeout.setSingleShot(True)
        self._gif_swap_timeout.setInterval(3200)
        self._gif_swap_timeout.timeout.connect(self._on_gif_swap_timeout)
        self._desktop_icon_clone_enabled = True
        self._desktop_icon_mask_timer = QTimer(self)
        self._desktop_icon_mask_timer.setInterval(420)
        self._desktop_icon_mask_timer.timeout.connect(self._refresh_desktop_icon_mask)
        self._desktop_icon_bootstrap_timer = QTimer(self)
        self._desktop_icon_bootstrap_timer.setSingleShot(True)
        self._desktop_icon_bootstrap_timer.setInterval(120)
        self._desktop_icon_bootstrap_timer.timeout.connect(self._run_desktop_icon_overlay_bootstrap)
        self._desktop_icon_bootstrap_retries = 0
        self.folder_watcher = QFileSystemWatcher(self)
        self.folder_watcher.directoryChanged.connect(self._on_folder_changed_signal)
        self.folder_refresh_timer = QTimer(self)
        self.folder_refresh_timer.setSingleShot(True)
        self.folder_refresh_timer.setInterval(250)
        self.folder_refresh_timer.timeout.connect(self._refresh_playlist_from_folder_change)

        self._initial_media_pending = False
        self._initial_media_prepared = False
        self.load_settings()
        if self.folder_path:
            self.update_playlist()
            self._initial_media_pending = True

    def setWindowOpacity(self, level):
        try:
            value = float(level)
        except Exception:
            value = 1.0
        value = max(0.0, min(1.0, value))
        super().setWindowOpacity(value)

    def _desktop_icon_overlay_base_condition(self):
        if int(getattr(self, "layer_mode", self.LAYER_NORMAL)) != int(self.LAYER_BACK):
            return False
        if not bool(getattr(self, "is_locked", False)):
            return False
        return True

    @staticmethod
    def _is_video_path(path):
        p = str(path or "").lower()
        return p.endswith((".mp4", ".avi", ".mov"))

    def _is_current_media_video(self):
        return self._is_video_path(getattr(self, "current_media_path", ""))

    def _refresh_icon_overlay_for_current_media(self):
        # Media-type switch (video <-> image/gif) can change icon-overlay strategy.
        # Apply immediately to avoid one-frame artifacts/flicker.
        try:
            self.apply_mask_and_style()
        except Exception:
            self._sync_desktop_icon_mask_timer()

    def _should_clone_desktop_icons(self):
        if not (bool(getattr(self, "_desktop_icon_clone_enabled", True)) and self._desktop_icon_overlay_base_condition()):
            return False
        # Fallback for environments where graphics-video path is unavailable.
        if self._is_current_media_video() and not bool(getattr(self, "_video_graphics_mode", False)):
            return False
        return True

    def _should_punch_desktop_icons(self):
        if self._should_clone_desktop_icons():
            return False
        return self._desktop_icon_overlay_base_condition()

    def _sync_desktop_icon_mask_timer(self):
        if not hasattr(self, "_desktop_icon_mask_timer"):
            return
        enabled = (self._should_clone_desktop_icons() or self._should_punch_desktop_icons()) and self.isVisible()
        if enabled:
            target_interval = 420
            if self._should_clone_desktop_icons():
                target_interval = 120
            elif self._should_punch_desktop_icons():
                target_interval = 320
            try:
                if int(self._desktop_icon_mask_timer.interval()) != int(target_interval):
                    self._desktop_icon_mask_timer.setInterval(int(target_interval))
            except Exception:
                pass
            if not self._desktop_icon_mask_timer.isActive():
                self._desktop_icon_mask_timer.start()
            return
        if self._desktop_icon_mask_timer.isActive():
            self._desktop_icon_mask_timer.stop()

    def _schedule_desktop_icon_overlay_bootstrap(self, retries=3, delay_ms=120):
        if not hasattr(self, "_desktop_icon_bootstrap_timer"):
            return
        if not (self._should_clone_desktop_icons() or self._should_punch_desktop_icons()):
            self._desktop_icon_bootstrap_retries = 0
            if self._desktop_icon_bootstrap_timer.isActive():
                self._desktop_icon_bootstrap_timer.stop()
            return
        try:
            retry_count = max(0, min(8, int(retries)))
        except Exception:
            retry_count = 3
        self._desktop_icon_bootstrap_retries = max(int(self._desktop_icon_bootstrap_retries), int(retry_count))
        try:
            wait_ms = max(20, int(delay_ms))
        except Exception:
            wait_ms = 120
        self._desktop_icon_bootstrap_timer.start(int(wait_ms))

    def _run_desktop_icon_overlay_bootstrap(self):
        if not self.isVisible():
            return
        if self._should_clone_desktop_icons():
            self._refresh_desktop_icon_clone_overlay(force=True)
        elif self._should_punch_desktop_icons():
            self.apply_mask_and_style()
        self._sync_desktop_icon_mask_timer()
        if int(getattr(self, "_desktop_icon_bootstrap_retries", 0)) > 0:
            self._desktop_icon_bootstrap_retries = int(self._desktop_icon_bootstrap_retries) - 1
            if hasattr(self, "_desktop_icon_bootstrap_timer"):
                self._desktop_icon_bootstrap_timer.start(140)

    def _set_clone_overlay_items(self, items):
        if not hasattr(self, "desktop_icon_clone_overlay"):
            return
        overlay = self.desktop_icon_clone_overlay
        if not isinstance(overlay, QWidget):
            return
        if not items:
            overlay.set_items([])
            overlay.hide()
            return
        overlay.setGeometry(self.rect())
        overlay.set_items(items)
        overlay.show()
        overlay.raise_()

    def _refresh_desktop_icon_clone_overlay(self, force=False):
        if not self._should_clone_desktop_icons() or not self.isVisible():
            self._set_clone_overlay_items([])
            return
        items = self._desktop_icon_clone_items_local(force=bool(force))
        if not items and not force:
            items = self._desktop_icon_clone_items_local(force=True)
        self._set_clone_overlay_items(items)

    def _refresh_desktop_icon_mask(self):
        clone_mode = self._should_clone_desktop_icons()
        punch_mode = self._should_punch_desktop_icons()
        if (not clone_mode and not punch_mode) or not self.isVisible():
            self._set_clone_overlay_items([])
            self._sync_desktop_icon_mask_timer()
            return
        if clone_mode:
            self._refresh_desktop_icon_clone_overlay(force=False)
            return
        self.apply_mask_and_style()

    @classmethod
    def _resolve_desktop_listview_hwnd(cls, refresh=False):
        cached = int(getattr(cls, "_desktop_icon_listview_hwnd", 0) or 0)
        if not refresh and cached:
            try:
                if win32gui.IsWindow(cached) and str(win32gui.GetClassName(cached)) == "SysListView32":
                    return int(cached)
            except Exception:
                pass
        hwnd = 0
        defview = 0
        try:
            prog = int(win32gui.FindWindow("Progman", None) or 0)
        except Exception:
            prog = 0
        if prog:
            try:
                defview = int(win32gui.FindWindowEx(int(prog), 0, "SHELLDLL_DefView", None) or 0)
            except Exception:
                defview = 0
        if not defview:
            found = {"defview": 0}

            def _enum_top(window_hwnd, lparam):
                try:
                    dv = int(win32gui.FindWindowEx(int(window_hwnd), 0, "SHELLDLL_DefView", None) or 0)
                except Exception:
                    dv = 0
                if dv:
                    lparam["defview"] = int(dv)
                    return False
                return True

            try:
                win32gui.EnumWindows(_enum_top, found)
            except Exception:
                pass
            defview = int(found.get("defview") or 0)
        if defview:
            try:
                hwnd = int(win32gui.FindWindowEx(int(defview), 0, "SysListView32", None) or 0)
            except Exception:
                hwnd = 0
        try:
            if hwnd and win32gui.IsWindow(hwnd) and str(win32gui.GetClassName(hwnd)) == "SysListView32":
                cls._desktop_icon_listview_hwnd = int(hwnd)
                return int(hwnd)
        except Exception:
            pass
        cls._desktop_icon_listview_hwnd = 0
        return 0

    @classmethod
    def _query_desktop_icon_rects_screen(cls, listview_hwnd):
        if not listview_hwnd:
            return []
        lvm_first = 0x1000
        lvm_getitemcount = lvm_first + 4
        lvm_getitemrect = lvm_first + 14
        lvm_getitemtextw = lvm_first + 115
        lvm_getitemw = lvm_first + 75
        lvm_getitemstate = lvm_first + 44
        lvm_geteditcontrol = lvm_first + 24
        lvif_image = 0x00000002
        lvif_text = 0x00000001
        lvir_icon = 1
        lvir_label = 2
        lvir_selectbounds = 3
        lvis_selected = 0x0002
        lvis_focused = 0x0001
        try:
            count = int(win32gui.SendMessage(int(listview_hwnd), int(lvm_getitemcount), 0, 0) or 0)
        except Exception:
            count = 0
        if count <= 0:
            cls._desktop_icon_edit_info = {}
            return []

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class LVITEMW(ctypes.Structure):
            _fields_ = [
                ("mask", wintypes.UINT),
                ("iItem", ctypes.c_int),
                ("iSubItem", ctypes.c_int),
                ("state", wintypes.UINT),
                ("stateMask", wintypes.UINT),
                ("pszText", wintypes.LPWSTR),
                ("cchTextMax", ctypes.c_int),
                ("iImage", ctypes.c_int),
                ("lParam", wintypes.LPARAM),
                ("iIndent", ctypes.c_int),
                ("iGroupId", ctypes.c_int),
                ("cColumns", wintypes.UINT),
                ("puColumns", ctypes.POINTER(wintypes.UINT)),
                ("piColFmt", ctypes.POINTER(ctypes.c_int)),
                ("iGroup", ctypes.c_int),
            ]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.VirtualAllocEx.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                ctypes.c_size_t,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            kernel32.VirtualAllocEx.restype = wintypes.LPVOID
            kernel32.ReadProcessMemory.argtypes = [
                wintypes.HANDLE,
                wintypes.LPCVOID,
                wintypes.LPVOID,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            kernel32.ReadProcessMemory.restype = wintypes.BOOL
            kernel32.WriteProcessMemory.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.LPCVOID,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            kernel32.WriteProcessMemory.restype = wintypes.BOOL
            kernel32.VirtualFreeEx.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                ctypes.c_size_t,
                wintypes.DWORD,
            ]
            kernel32.VirtualFreeEx.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
        except Exception:
            pass

        pid = wintypes.DWORD(0)
        try:
            user32.GetWindowThreadProcessId(int(listview_hwnd), ctypes.byref(pid))
        except Exception:
            return []
        if int(pid.value) <= 0:
            return []

        process_access = int(0x0400 | 0x0010 | 0x0020 | 0x0008)  # QUERY | VM_READ | VM_WRITE | VM_OPERATION
        mem_commit_reserve = int(0x1000 | 0x2000)
        mem_release = int(0x8000)
        page_readwrite = int(0x04)
        proc = None
        remote_ptr = None
        layouts = []
        rect_size = int(ctypes.sizeof(RECT))
        lvitem_size = int(ctypes.sizeof(LVITEMW))
        text_cch = 280
        text_buf_size = int(text_cch * ctypes.sizeof(ctypes.c_wchar))
        align = 16
        rect_off = 0
        lvitem_off = int(((rect_size + (align - 1)) // align) * align)
        text_off = int(((lvitem_off + lvitem_size + (align - 1)) // align) * align)
        alloc_size = max(rect_size, int(text_off + text_buf_size))
        shell_items = cls._desktop_shell_items_by_name(refresh=False)
        shell_items_order = cls._desktop_shell_items_in_order(refresh=False)
        shell_name_seen = {}

        def _normalize_item_name(value):
            s = str(value or "").strip().lower()
            if not s:
                return ""
            return " ".join(s.split())

        def _names_similar(a, b):
            na = _normalize_item_name(a)
            nb = _normalize_item_name(b)
            if not na or not nb:
                return False
            if na == nb:
                return True
            sa = os.path.splitext(na)[0]
            sb = os.path.splitext(nb)[0]
            return bool(sa and sb and (sa == sb or sa == nb or sb == na))

        def _read_item_rect(item_index, rect_code, remote_rect):
            probe = RECT()
            probe.left = int(rect_code)
            probe.top = 0
            probe.right = 0
            probe.bottom = 0
            try:
                written = ctypes.c_size_t(0)
                ok_write = bool(
                    kernel32.WriteProcessMemory(
                        proc,
                        ctypes.c_void_p(int(remote_rect)),
                        ctypes.byref(probe),
                        rect_size,
                        ctypes.byref(written),
                    )
                )
            except Exception:
                ok_write = False
            if not ok_write:
                return None
            try:
                ok = int(
                    win32gui.SendMessage(
                        int(listview_hwnd),
                        int(lvm_getitemrect),
                        int(item_index),
                        int(remote_rect),
                    )
                    or 0
                )
            except Exception:
                ok = 0
            if not ok:
                return None
            out = RECT()
            bytes_read = ctypes.c_size_t(0)
            try:
                copied = bool(
                    kernel32.ReadProcessMemory(
                        proc,
                        ctypes.c_void_p(int(remote_rect)),
                        ctypes.byref(out),
                        rect_size,
                        ctypes.byref(bytes_read),
                    )
                )
            except Exception:
                copied = False
            if not copied or int(bytes_read.value) < rect_size:
                return None
            return (int(out.left), int(out.top), int(out.right), int(out.bottom))

        def _read_item_image_index(item_index, remote_lvitem):
            item = LVITEMW()
            item.mask = int(lvif_image)
            item.iItem = int(item_index)
            item.iSubItem = 0
            item.iImage = -1
            try:
                written = ctypes.c_size_t(0)
                ok_write = bool(
                    kernel32.WriteProcessMemory(
                        proc,
                        ctypes.c_void_p(int(remote_lvitem)),
                        ctypes.byref(item),
                        lvitem_size,
                        ctypes.byref(written),
                    )
                )
            except Exception:
                ok_write = False
            if not ok_write:
                return -1
            try:
                ok = int(
                    win32gui.SendMessage(
                        int(listview_hwnd),
                        int(lvm_getitemw),
                        0,
                        int(remote_lvitem),
                    )
                    or 0
                )
            except Exception:
                ok = 0
            if not ok:
                return -1
            out = LVITEMW()
            bytes_read = ctypes.c_size_t(0)
            try:
                copied = bool(
                    kernel32.ReadProcessMemory(
                        proc,
                        ctypes.c_void_p(int(remote_lvitem)),
                        ctypes.byref(out),
                        lvitem_size,
                        ctypes.byref(bytes_read),
                    )
                )
            except Exception:
                copied = False
            if not copied or int(bytes_read.value) < lvitem_size:
                return -1
            try:
                return int(out.iImage)
            except Exception:
                return -1

        def _read_item_text(item_index, remote_lvitem, remote_text):
            item = LVITEMW()
            item.mask = int(lvif_text)
            item.iItem = int(item_index)
            item.iSubItem = 0
            item.cchTextMax = int(text_cch)
            item.pszText = ctypes.cast(ctypes.c_void_p(int(remote_text)), wintypes.LPWSTR)
            try:
                written = ctypes.c_size_t(0)
                ok_write = bool(
                    kernel32.WriteProcessMemory(
                        proc,
                        ctypes.c_void_p(int(remote_lvitem)),
                        ctypes.byref(item),
                        lvitem_size,
                        ctypes.byref(written),
                    )
                )
            except Exception:
                ok_write = False
            if not ok_write:
                return ""
            try:
                win32gui.SendMessage(
                    int(listview_hwnd),
                    int(lvm_getitemtextw),
                    int(item_index),
                    int(remote_lvitem),
                )
            except Exception:
                return ""
            raw = ctypes.create_string_buffer(text_buf_size)
            bytes_read = ctypes.c_size_t(0)
            try:
                copied = bool(
                    kernel32.ReadProcessMemory(
                        proc,
                        ctypes.c_void_p(int(remote_text)),
                        raw,
                        text_buf_size,
                        ctypes.byref(bytes_read),
                    )
                )
            except Exception:
                copied = False
            if not copied:
                return ""
            try:
                text = raw.raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
            except Exception:
                text = ""
            return str(text or "").strip()

        def _read_item_state(item_index, mask):
            try:
                st = int(
                    win32gui.SendMessage(
                        int(listview_hwnd),
                        int(lvm_getitemstate),
                        int(item_index),
                        int(mask),
                    )
                    or 0
                )
            except Exception:
                st = 0
            return int(st)

        def _client_rect_to_screen(rect_tuple):
            if not rect_tuple:
                return None
            left, top, right, bottom = rect_tuple
            try:
                sx1, sy1 = win32gui.ClientToScreen(int(listview_hwnd), (int(left), int(top)))
                sx2, sy2 = win32gui.ClientToScreen(int(listview_hwnd), (int(right), int(bottom)))
            except Exception:
                return None
            x1 = min(int(sx1), int(sx2))
            y1 = min(int(sy1), int(sy2))
            x2 = max(int(sx1), int(sx2))
            y2 = max(int(sy1), int(sy2))
            w = max(0, int(x2 - x1))
            h = max(0, int(y2 - y1))
            if w <= 0 or h <= 0:
                return None
            return QRect(int(x1), int(y1), int(w), int(h))

        try:
            proc = kernel32.OpenProcess(process_access, False, int(pid.value))
            if not proc:
                return []
            remote_ptr = kernel32.VirtualAllocEx(proc, None, alloc_size, mem_commit_reserve, page_readwrite)
            if not remote_ptr:
                return []
            remote_base = int(remote_ptr)
            remote_rect = int(remote_base + rect_off)
            remote_lvitem = int(remote_base + lvitem_off)
            remote_text = int(remote_base + text_off)
            for idx in range(int(count)):
                icon_rect = _client_rect_to_screen(_read_item_rect(int(idx), int(lvir_icon), int(remote_rect)))
                label_rect = _client_rect_to_screen(_read_item_rect(int(idx), int(lvir_label), int(remote_rect)))
                select_rect = _client_rect_to_screen(_read_item_rect(int(idx), int(lvir_selectbounds), int(remote_rect)))
                image_index = _read_item_image_index(int(idx), int(remote_lvitem))
                label_text = _read_item_text(int(idx), int(remote_lvitem), int(remote_text))
                state_bits = _read_item_state(int(idx), int(lvis_selected | lvis_focused))
                if icon_rect is None and label_rect is None:
                    continue
                key = str(label_text or "").strip().lower()
                shell_meta = {}
                seq_meta = {}
                if int(idx) < len(shell_items_order):
                    try:
                        seq_meta = dict(shell_items_order[int(idx)] or {})
                    except Exception:
                        seq_meta = {}
                if seq_meta:
                    seq_name = str(seq_meta.get("name", "") or "")
                    if _names_similar(label_text, seq_name):
                        shell_meta = dict(seq_meta)
                if key:
                    pos = int(shell_name_seen.get(key, 0) or 0)
                    shell_name_seen[key] = int(pos + 1)
                    candidates = list(shell_items.get(key, []) or [])
                    if not shell_meta and pos < len(candidates):
                        shell_meta = dict(candidates[pos] or {})
                    elif not shell_items:
                        shell_items = cls._desktop_shell_items_by_name(refresh=True)
                        shell_items_order = cls._desktop_shell_items_in_order(refresh=True)
                        candidates = list(shell_items.get(key, []) or [])
                        if not shell_meta and pos < len(candidates):
                            shell_meta = dict(candidates[pos] or {})
                if not shell_meta and seq_meta:
                    shell_meta = dict(seq_meta)
                shell_path = str(shell_meta.get("path", "") or "")
                shell_virtual = bool(shell_meta.get("is_virtual", False))
                shell_folder = bool(shell_meta.get("is_folder", False))
                display_text = str(shell_meta.get("name", "") or "").strip()
                if not display_text:
                    display_text = str(label_text or "").strip()
                if select_rect is None:
                    merged = None
                    if isinstance(icon_rect, QRect) and isinstance(label_rect, QRect):
                        merged = QRect(icon_rect).united(QRect(label_rect))
                    elif isinstance(icon_rect, QRect):
                        merged = QRect(icon_rect)
                    elif isinstance(label_rect, QRect):
                        merged = QRect(label_rect)
                    if isinstance(merged, QRect) and int(merged.width()) > 0 and int(merged.height()) > 0:
                        select_rect = merged.adjusted(-4, -2, 4, 2)
                if shell_path and not shell_virtual:
                    try:
                        shell_folder = bool(os.path.isdir(shell_path))
                    except Exception:
                        pass
                layouts.append(
                    {
                        "icon": icon_rect,
                        "label": label_rect,
                        "text": display_text,
                        "image_index": int(image_index),
                        "shell_path": shell_path,
                        "shell_is_folder": bool(shell_folder),
                        "shell_is_virtual": bool(shell_virtual),
                        "selected": bool(int(state_bits) & int(lvis_selected)),
                        "focused": bool(int(state_bits) & int(lvis_focused)),
                        "select": select_rect,
                    }
                )
            edit_info = {}
            try:
                edit_hwnd = int(
                    win32gui.SendMessage(
                        int(listview_hwnd),
                        int(lvm_geteditcontrol),
                        0,
                        0,
                    )
                    or 0
                )
            except Exception:
                edit_hwnd = 0
            if edit_hwnd:
                try:
                    if win32gui.IsWindow(edit_hwnd) and win32gui.IsWindowVisible(edit_hwnd):
                        left, top, right, bottom = win32gui.GetWindowRect(int(edit_hwnd))
                        txt = str(win32gui.GetWindowText(int(edit_hwnd)) or "")
                        edit_info = {
                            "rect": QRect(
                                int(left),
                                int(top),
                                max(0, int(right - left)),
                                max(0, int(bottom - top)),
                            ),
                            "text": txt,
                            "hwnd": int(edit_hwnd),
                        }
                except Exception:
                    edit_info = {}
            cls._desktop_icon_edit_info = dict(edit_info)
        finally:
            try:
                if proc and remote_ptr:
                    kernel32.VirtualFreeEx(proc, ctypes.c_void_p(int(remote_ptr)), 0, mem_release)
            except Exception:
                pass
            try:
                if proc:
                    kernel32.CloseHandle(proc)
            except Exception:
                pass
        return layouts

    @classmethod
    def _desktop_icon_rects_screen(cls, force=False):
        now = float(time.monotonic())
        cache_hwnd = int(getattr(cls, "_desktop_icon_cache_hwnd", 0) or 0)
        cache_ts = float(getattr(cls, "_desktop_icon_cache_ts", 0.0) or 0.0)
        cache_rects = list(getattr(cls, "_desktop_icon_cache_rects", []) or [])
        try:
            cache_max_age = max(0.05, float(getattr(cls, "_desktop_icon_cache_max_age", 0.16) or 0.16))
        except Exception:
            cache_max_age = 0.16
        if (
            not force
            and cache_hwnd
            and (now - cache_ts) <= cache_max_age
        ):
            try:
                if win32gui.IsWindow(int(cache_hwnd)):
                    return cache_rects
            except Exception:
                pass
        listview_hwnd = cls._resolve_desktop_listview_hwnd(refresh=bool(force))
        if not listview_hwnd:
            cls._desktop_icon_cache_hwnd = 0
            cls._desktop_icon_cache_ts = now
            cls._desktop_icon_cache_rects = []
            cls._desktop_icon_edit_info = {}
            return []
        rects = cls._query_desktop_icon_rects_screen(int(listview_hwnd))
        cls._desktop_icon_cache_hwnd = int(listview_hwnd)
        cls._desktop_icon_cache_ts = now
        cls._desktop_icon_cache_rects = list(rects)
        return list(rects)

    @classmethod
    def _desktop_icon_edit_info_screen(cls):
        info = dict(getattr(cls, "_desktop_icon_edit_info", {}) or {})
        rect = info.get("rect")
        if isinstance(rect, QRect) and int(rect.width()) > 0 and int(rect.height()) > 0:
            return info
        return {}

    @classmethod
    def _desktop_caption_path_map(cls, refresh=False):
        now = float(time.monotonic())
        cache_ts = float(getattr(cls, "_desktop_caption_path_cache_ts", 0.0) or 0.0)
        cached = dict(getattr(cls, "_desktop_caption_path_cache", {}) or {})
        if not refresh and cached and (now - cache_ts) <= 6.0:
            return cached

        mapping = {}
        dirs = []
        try:
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            def _guid(text):
                s = str(text or "").strip().strip("{}")
                parts = s.split("-")
                if len(parts) != 5:
                    return None
                d4_hex = parts[3] + parts[4]
                if len(d4_hex) != 16:
                    return None
                d4 = (ctypes.c_ubyte * 8)(*([int(d4_hex[i:i + 2], 16) for i in range(0, 16, 2)]))
                return GUID(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), d4)

            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32
            shell32.SHGetKnownFolderPath.argtypes = [
                ctypes.POINTER(GUID),
                wintypes.DWORD,
                wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_wchar_p),
            ]
            shell32.SHGetKnownFolderPath.restype = ctypes.c_long

            def _known_folder_path(guid_text):
                g = _guid(guid_text)
                if g is None:
                    return ""
                out_ptr = ctypes.c_wchar_p()
                hr = int(shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out_ptr)))
                if hr != 0:
                    return ""
                try:
                    return str(out_ptr.value or "")
                finally:
                    try:
                        ole32.CoTaskMemFree(out_ptr)
                    except Exception:
                        pass

            desktop_dir = _known_folder_path("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
            public_desktop_dir = _known_folder_path("C4AA340D-F20F-4863-AFEF-F87EF2E6BA25")
            if desktop_dir:
                dirs.append(desktop_dir)
            if public_desktop_dir:
                dirs.append(public_desktop_dir)
        except Exception:
            pass
        try:
            dirs.append(os.path.join(os.path.expanduser("~"), "Desktop"))
        except Exception:
            pass
        try:
            pub = str(os.environ.get("PUBLIC", "") or "").strip()
            if pub:
                dirs.append(os.path.join(pub, "Desktop"))
        except Exception:
            pass

        seen_dirs = set()
        for base in dirs:
            d = os.path.normpath(str(base or ""))
            if not d or d in seen_dirs:
                continue
            seen_dirs.add(d)
            if not os.path.isdir(d):
                continue
            try:
                for entry in os.scandir(d):
                    try:
                        name = str(entry.name or "")
                        path = str(entry.path or "")
                    except Exception:
                        continue
                    if not name or not path:
                        continue
                    low_full = name.lower()
                    stem = os.path.splitext(name)[0].lower()
                    if low_full and low_full not in mapping:
                        mapping[low_full] = path
                    if stem and stem not in mapping:
                        mapping[stem] = path
            except Exception:
                continue

        cls._desktop_caption_path_cache = dict(mapping)
        cls._desktop_caption_path_cache_ts = now
        return dict(mapping)

    @classmethod
    def _desktop_caption_to_path(cls, caption):
        key = str(caption or "").strip().lower()
        if not key:
            return ""
        table = cls._desktop_caption_path_map(refresh=False)
        path = str(table.get(key, "") or "")
        if path:
            return path
        # Handle trailing ellipsis fallback from narrow icon labels.
        key2 = key.rstrip(".").strip()
        if key2:
            path = str(table.get(key2, "") or "")
            if path:
                return path
        return ""

    @classmethod
    def _desktop_shell_items_by_name(cls, refresh=False):
        now = float(time.monotonic())
        cache_ts = float(getattr(cls, "_desktop_shell_items_cache_ts", 0.0) or 0.0)
        cached = dict(getattr(cls, "_desktop_shell_items_cache", {}) or {})
        cached_list = list(getattr(cls, "_desktop_shell_items_cache_list", []) or [])
        if not refresh and cached and cached_list and (now - cache_ts) <= 2.0:
            return cached
        out = {}
        ordered = []
        if win32com is None:
            cls._desktop_shell_items_cache = {}
            cls._desktop_shell_items_cache_list = []
            cls._desktop_shell_items_cache_ts = now
            return {}
        try:
            shell = win32com.Dispatch("Shell.Application")
            ns = shell.Namespace(0)
            if ns is not None:
                items = ns.Items()
                count = int(getattr(items, "Count", 0) or 0)
                for i in range(count):
                    try:
                        it = items.Item(i)
                    except Exception:
                        continue
                    try:
                        name = str(getattr(it, "Name", "") or "").strip()
                    except Exception:
                        name = ""
                    if not name:
                        continue
                    key = name.lower()
                    try:
                        path = str(getattr(it, "Path", "") or "").strip()
                    except Exception:
                        path = ""
                    try:
                        is_folder = bool(getattr(it, "IsFolder", False))
                    except Exception:
                        is_folder = False
                    is_virtual = bool(path.startswith("::")) if path else True
                    rec = {
                        "name": str(name),
                        "path": str(path),
                        "is_folder": bool(is_folder),
                        "is_virtual": bool(is_virtual),
                    }
                    ordered.append(rec)
                    out.setdefault(key, []).append(rec)
        except Exception:
            out = {}
            ordered = []
        cls._desktop_shell_items_cache = dict(out)
        cls._desktop_shell_items_cache_list = list(ordered)
        cls._desktop_shell_items_cache_ts = now
        return dict(out)

    @classmethod
    def _desktop_shell_items_in_order(cls, refresh=False):
        now = float(time.monotonic())
        cache_ts = float(getattr(cls, "_desktop_shell_items_cache_ts", 0.0) or 0.0)
        cached = list(getattr(cls, "_desktop_shell_items_cache_list", []) or [])
        if not refresh and cached and (now - cache_ts) <= 2.0:
            return cached
        cls._desktop_shell_items_by_name(refresh=bool(refresh))
        return list(getattr(cls, "_desktop_shell_items_cache_list", []) or [])

    @staticmethod
    def _is_recycle_caption(caption):
        key = str(caption or "").strip().lower()
        if not key:
            return False
        recycle_keys = {
            "recycle bin",
            "휴지통",
            "papelera de reciclaje",
            "corbeille",
            "cestino",
            "корзина",
            "kosz",
            "lixeira",
        }
        return bool(key in recycle_keys)

    @classmethod
    def _desktop_icon_identity(cls, caption):
        caption_key = str(caption or "").strip().lower()
        path = cls._desktop_caption_to_path(caption)
        stock_recycle = cls._is_recycle_caption(caption)
        if path and os.path.exists(path):
            icon_key = str(os.path.normcase(path))
            return icon_key, str(path), False
        if stock_recycle:
            return "stock::recycler", "", True
        return f"caption::{caption_key}", "", False

    @staticmethod
    def _as_win_handle(value):
        try:
            return int(ctypes.c_void_p(int(value)).value or 0)
        except Exception:
            return 0

    @classmethod
    def _resolve_desktop_sys_himl_large(cls):
        cached = cls._as_win_handle(getattr(cls, "_desktop_sys_himl_large", 0) or 0)
        if cached:
            return int(cached)
        try:
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_uint),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80),
                ]

            shfi = SHFILEINFOW()
            shgfi_sysiconindex = int(0x000004000)
            shgfi_large = int(0x000000000)
            shell32 = ctypes.windll.shell32
            shell32.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.POINTER(SHFILEINFOW),
                ctypes.c_uint,
                ctypes.c_uint,
            ]
            shell32.SHGetFileInfoW.restype = ctypes.c_void_p
            himl_raw = shell32.SHGetFileInfoW(
                    ctypes.c_wchar_p("C:\\"),
                    0,
                    ctypes.byref(shfi),
                    ctypes.sizeof(shfi),
                    int(shgfi_sysiconindex | shgfi_large),
                )
            himl = cls._as_win_handle(himl_raw)
            cls._desktop_sys_himl_large = int(himl)
            return int(himl)
        except Exception:
            cls._desktop_sys_himl_large = 0
            return 0

    @classmethod
    def _icon_image_for_sys_index(cls, image_index, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            idx = int(image_index)
        except Exception:
            idx = -1
        cache_key = ("sysidx", int(idx), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)
        if idx < 0:
            img = QImage()
            cls._desktop_icon_image_cache[cache_key] = QImage(img)
            return QImage(img)

        himl = cls._resolve_desktop_sys_himl_large()
        if not himl:
            img = QImage()
            cls._desktop_icon_image_cache[cache_key] = QImage(img)
            return QImage(img)

        image = QImage()
        hicon = 0
        hbm_color = 0
        hbm_mask = 0
        try:
            comctl32 = ctypes.windll.comctl32
            comctl32.ImageList_GetIcon.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint]
            comctl32.ImageList_GetIcon.restype = ctypes.c_void_p
            hicon = cls._as_win_handle(comctl32.ImageList_GetIcon(int(himl), int(idx), 0))
            if hicon:
                icon_info = win32gui.GetIconInfo(int(hicon))
                if isinstance(icon_info, tuple) and len(icon_info) >= 5:
                    hbm_mask = cls._as_win_handle(icon_info[3])
                    hbm_color = cls._as_win_handle(icon_info[4])

            if hbm_color and win32ui is not None:
                bmp = win32ui.CreateBitmapFromHandle(int(hbm_color))
                info = bmp.GetInfo()
                bits = bmp.GetBitmapBits(True)
                bw = int(info.get("bmWidth", 0))
                bh = int(info.get("bmHeight", 0))
                bpp = int(info.get("bmBitsPixel", 0))
                stride = int(max(0, bw * 4))
                if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                    qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                    qimg = qimg.scaled(
                        int(size),
                        int(size),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                    canvas.fill(0)
                    painter = QPainter(canvas)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    dx = int((int(size) - int(qimg.width())) // 2)
                    dy = int((int(size) - int(qimg.height())) // 2)
                    painter.drawImage(int(dx), int(dy), qimg)
                    painter.end()
                    image = canvas
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass
            try:
                if hbm_color:
                    win32gui.DeleteObject(int(hbm_color))
            except Exception:
                pass
            try:
                if hbm_mask:
                    win32gui.DeleteObject(int(hbm_mask))
            except Exception:
                pass

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        if len(cls._desktop_icon_image_cache) > 480:
            try:
                cls._desktop_icon_image_cache.pop(next(iter(cls._desktop_icon_image_cache)))
            except Exception:
                pass
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_sys_index(cls, image_index, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            idx = int(image_index)
        except Exception:
            idx = -1
        cache_key = ("sysidx", int(idx), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_sys_index(int(idx), int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        if len(cls._desktop_icon_pixmap_cache) > 480:
            try:
                cls._desktop_icon_pixmap_cache.pop(next(iter(cls._desktop_icon_pixmap_cache)))
            except Exception:
                pass
        return QPixmap(pix)

    @classmethod
    def _image_from_hicon(cls, hicon, icon_px):
        size = max(12, min(128, int(icon_px)))
        hicon = cls._as_win_handle(hicon)
        if not hicon:
            return QImage()
        hbm_color = 0
        hbm_mask = 0
        try:
            icon_info = win32gui.GetIconInfo(int(hicon))
            if isinstance(icon_info, tuple) and len(icon_info) >= 5:
                hbm_mask = cls._as_win_handle(icon_info[3])
                hbm_color = cls._as_win_handle(icon_info[4])
            if hbm_color and win32ui is not None:
                bmp = win32ui.CreateBitmapFromHandle(int(hbm_color))
                info = bmp.GetInfo()
                bits = bmp.GetBitmapBits(True)
                bw = int(info.get("bmWidth", 0))
                bh = int(info.get("bmHeight", 0))
                bpp = int(info.get("bmBitsPixel", 0))
                stride = int(max(0, bw * 4))
                if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                    qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                    qimg = qimg.scaled(
                        int(size),
                        int(size),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                    canvas.fill(0)
                    painter = QPainter(canvas)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    dx = int((int(size) - int(qimg.width())) // 2)
                    dy = int((int(size) - int(qimg.height())) // 2)
                    painter.drawImage(int(dx), int(dy), qimg)
                    painter.end()
                    return canvas
        except Exception:
            pass
        finally:
            try:
                if hbm_color:
                    win32gui.DeleteObject(int(hbm_color))
            except Exception:
                pass
            try:
                if hbm_mask:
                    win32gui.DeleteObject(int(hbm_mask))
            except Exception:
                pass
        return QImage()

    @staticmethod
    def _guid_from_text(text):
        s = str(text or "").strip().strip("{}")
        parts = s.split("-")
        if len(parts) != 5:
            return None

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        raw = parts[3] + parts[4]
        if len(raw) != 16:
            return None
        try:
            d4 = (ctypes.c_ubyte * 8)(*([int(raw[i:i + 2], 16) for i in range(0, 16, 2)]))
            return GUID(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), d4)
        except Exception:
            return None

    @classmethod
    def _shell_item_image_for_path(cls, path, icon_px, thumbnail_first=True):
        size = max(12, min(256, int(icon_px)))
        path = str(path or "").strip()
        if not path:
            return QImage()
        cache_key = ("shellitem", str(os.path.normcase(path)), int(size), int(bool(thumbnail_first)))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        image = QImage()
        hbitmap = 0
        item_ptr = ctypes.c_void_p()
        try:
            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32
            iid = cls._guid_from_text("{BCC18B79-BA16-442F-80C4-8A59C30C463B}")  # IShellItemImageFactory
            if iid is None:
                cls._desktop_icon_image_cache[cache_key] = QImage()
                return QImage()

            shell32.SHCreateItemFromParsingName.argtypes = [
                wintypes.LPCWSTR,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            shell32.SHCreateItemFromParsingName.restype = ctypes.c_long
            coinit = int(ole32.CoInitialize(None))
            try:
                hr = int(
                    shell32.SHCreateItemFromParsingName(
                        ctypes.c_wchar_p(path),
                        None,
                        ctypes.byref(iid),
                        ctypes.byref(item_ptr),
                    )
                )
                if hr != 0 or not item_ptr.value:
                    cls._desktop_icon_image_cache[cache_key] = QImage()
                    return QImage()

                class SIZE(ctypes.Structure):
                    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

                siigbf_resizetofit = 0x00
                siigbf_biggersizeok = 0x01
                siigbf_icononly = 0x04
                siigbf_thumbnailonly = 0x08
                # COM vtable: IUnknown(3) + GetImage(1)
                vtbl = ctypes.cast(item_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                fn_type = ctypes.WINFUNCTYPE(
                    ctypes.c_long,
                    ctypes.c_void_p,
                    SIZE,
                    ctypes.c_uint,
                    ctypes.POINTER(ctypes.c_void_p),
                )
                get_image = fn_type(vtbl[3])

                flags = int(siigbf_resizetofit | siigbf_biggersizeok)
                if thumbnail_first:
                    flags |= int(siigbf_thumbnailonly)
                else:
                    flags |= int(siigbf_icononly)

                hbmp = ctypes.c_void_p()
                hr_img = int(get_image(item_ptr, SIZE(int(size), int(size)), int(flags), ctypes.byref(hbmp)))
                if hr_img != 0 or not hbmp.value:
                    hbmp = ctypes.c_void_p()
                    flags_fallback = int(siigbf_resizetofit | siigbf_biggersizeok | siigbf_icononly)
                    hr_img = int(get_image(item_ptr, SIZE(int(size), int(size)), int(flags_fallback), ctypes.byref(hbmp)))
                if hr_img == 0 and hbmp.value:
                    hbitmap = cls._as_win_handle(hbmp.value)
                    if hbitmap and win32ui is not None:
                        bmp = win32ui.CreateBitmapFromHandle(int(hbitmap))
                        info = bmp.GetInfo()
                        bits = bmp.GetBitmapBits(True)
                        bw = int(info.get("bmWidth", 0))
                        bh = int(info.get("bmHeight", 0))
                        bpp = int(info.get("bmBitsPixel", 0))
                        stride = int(max(0, bw * 4))
                        if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                            qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                            image = qimg.scaled(
                                int(size),
                                int(size),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
            finally:
                if coinit in (0, 1):  # S_OK or S_FALSE
                    try:
                        ole32.CoUninitialize()
                    except Exception:
                        pass
        except Exception:
            image = QImage()
        finally:
            try:
                if hbitmap:
                    win32gui.DeleteObject(int(hbitmap))
            except Exception:
                pass
            try:
                if item_ptr and item_ptr.value:
                    vtbl = ctypes.cast(item_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    rel_t = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
                    release = rel_t(vtbl[2])
                    release(item_ptr)
            except Exception:
                pass

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        return QImage(image)

    @classmethod
    def _icon_image_for_path(cls, path, icon_px):
        size = max(12, min(128, int(icon_px)))
        path = str(path or "").strip()
        if not path:
            return QImage()
        cache_key = ("path", str(os.path.normcase(path)), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        image = cls._shell_item_image_for_path(path, int(size), thumbnail_first=True)
        if not image.isNull():
            cls._desktop_icon_image_cache[cache_key] = QImage(image)
            return QImage(image)

        image = QImage()
        hicon = 0
        try:
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_uint),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80),
                ]

            shell32 = ctypes.windll.shell32
            shell32.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.POINTER(SHFILEINFOW),
                ctypes.c_uint,
                ctypes.c_uint,
            ]
            shell32.SHGetFileInfoW.restype = ctypes.c_void_p
            shfi = SHFILEINFOW()
            shgfi_icon = int(0x000000100)
            shgfi_large = int(0x000000000)
            ok_raw = shell32.SHGetFileInfoW(
                ctypes.c_wchar_p(path),
                0,
                ctypes.byref(shfi),
                ctypes.sizeof(shfi),
                int(shgfi_icon | shgfi_large),
            )
            ok = cls._as_win_handle(ok_raw)
            if ok and shfi.hIcon:
                hicon = cls._as_win_handle(shfi.hIcon)
                image = cls._image_from_hicon(int(hicon), int(size))
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass

        if image.isNull():
            try:
                provider = QFileIconProvider()
                icon = provider.icon(QFileInfo(path))
                if not icon.isNull():
                    pm = icon.pixmap(int(size), int(size))
                    if not pm.isNull():
                        image = pm.toImage().scaled(
                            int(size),
                            int(size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
            except Exception:
                image = QImage()

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_path(cls, path, icon_px):
        size = max(12, min(128, int(icon_px)))
        path = str(path or "").strip()
        if not path:
            return QPixmap()
        cache_key = ("path", str(os.path.normcase(path)), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_path(path, int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        return QPixmap(pix)

    @classmethod
    def _icon_image_for_stock_id(cls, stock_id, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            sid = int(stock_id)
        except Exception:
            sid = 0
        cache_key = ("stock", int(sid), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        image = QImage()
        hicon = 0
        try:
            class SHSTOCKICONINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hIcon", ctypes.c_void_p),
                    ("iSysImageIndex", ctypes.c_int),
                    ("iIcon", ctypes.c_int),
                    ("szPath", ctypes.c_wchar * 260),
                ]

            shell32 = ctypes.windll.shell32
            sii = SHSTOCKICONINFO()
            sii.cbSize = int(ctypes.sizeof(SHSTOCKICONINFO))
            shgsi_icon = int(0x000000100)
            shgsi_large = int(0x000000000)
            hr = int(
                shell32.SHGetStockIconInfo(
                    int(sid),
                    int(shgsi_icon | shgsi_large),
                    ctypes.byref(sii),
                )
            )
            if hr == 0 and sii.hIcon:
                hicon = cls._as_win_handle(sii.hIcon)
                image = cls._image_from_hicon(int(hicon), int(size))
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass

        if image.isNull():
            try:
                std = QStyle.StandardPixmap.SP_FileIcon
                if sid in (3, 4):
                    std = QStyle.StandardPixmap.SP_DirIcon
                elif sid in (31, 32):
                    std = QStyle.StandardPixmap.SP_TrashIcon
                icon = QApplication.style().standardIcon(std)
                if not icon.isNull():
                    pm = icon.pixmap(int(size), int(size))
                    if not pm.isNull():
                        image = pm.toImage().scaled(
                            int(size),
                            int(size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
            except Exception:
                image = QImage()

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_stock_id(cls, stock_id, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            sid = int(stock_id)
        except Exception:
            sid = 0
        cache_key = ("stock", int(sid), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_stock_id(int(sid), int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        return QPixmap(pix)

    @classmethod
    def _icon_image_for_item(cls, caption, icon_px):
        size = max(12, min(128, int(icon_px)))
        icon_key, path, stock_recycle = cls._desktop_icon_identity(caption)
        cache_key = (str(icon_key), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        if not path and not stock_recycle:
            img = QImage()
            cls._desktop_icon_image_cache[cache_key] = QImage(img)
            return QImage(img)

        image = QImage()
        hicon = 0
        hbm_color = 0
        hbm_mask = 0
        try:
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_uint),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80),
                ]

            class SHSTOCKICONINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hIcon", ctypes.c_void_p),
                    ("iSysImageIndex", ctypes.c_int),
                    ("iIcon", ctypes.c_int),
                    ("szPath", ctypes.c_wchar * 260),
                ]

            def _as_handle(v):
                try:
                    return int(ctypes.c_void_p(int(v)).value or 0)
                except Exception:
                    return 0

            shell32 = ctypes.windll.shell32
            shell32.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.POINTER(SHFILEINFOW),
                ctypes.c_uint,
                ctypes.c_uint,
            ]
            shell32.SHGetFileInfoW.restype = ctypes.c_void_p
            if path and os.path.exists(path):
                shfi = SHFILEINFOW()
                shgfi_icon = int(0x000000100)
                shgfi_large = int(0x000000000)
                ok_raw = shell32.SHGetFileInfoW(
                    ctypes.c_wchar_p(path),
                    0,
                    ctypes.byref(shfi),
                    ctypes.sizeof(shfi),
                    shgfi_icon | shgfi_large,
                )
                ok = cls._as_win_handle(ok_raw)
                if ok and shfi.hIcon:
                    hicon = _as_handle(shfi.hIcon)
            elif stock_recycle:
                sii = SHSTOCKICONINFO()
                sii.cbSize = int(ctypes.sizeof(SHSTOCKICONINFO))
                siid_recycler = 31
                shgsi_icon = int(0x000000100)
                shgsi_large = int(0x000000000)
                hr = int(
                    shell32.SHGetStockIconInfo(
                        int(siid_recycler),
                        int(shgsi_icon | shgsi_large),
                        ctypes.byref(sii),
                    )
                )
                if hr == 0 and sii.hIcon:
                    hicon = _as_handle(sii.hIcon)

            if hicon:
                icon_info = win32gui.GetIconInfo(int(hicon))
                if isinstance(icon_info, tuple) and len(icon_info) >= 5:
                    hbm_mask = _as_handle(icon_info[3])
                    hbm_color = _as_handle(icon_info[4])

            if hbm_color and win32ui is not None:
                bmp = win32ui.CreateBitmapFromHandle(int(hbm_color))
                info = bmp.GetInfo()
                bits = bmp.GetBitmapBits(True)
                bw = int(info.get("bmWidth", 0))
                bh = int(info.get("bmHeight", 0))
                bpp = int(info.get("bmBitsPixel", 0))
                stride = int(max(0, bw * 4))
                if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                    qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                    qimg = qimg.scaled(
                        int(size),
                        int(size),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                    canvas.fill(0)
                    painter = QPainter(canvas)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    dx = int((int(size) - int(qimg.width())) // 2)
                    dy = int((int(size) - int(qimg.height())) // 2)
                    painter.drawImage(int(dx), int(dy), qimg)
                    painter.end()
                    image = canvas
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass
            try:
                if hbm_color:
                    win32gui.DeleteObject(int(hbm_color))
            except Exception:
                pass
            try:
                if hbm_mask:
                    win32gui.DeleteObject(int(hbm_mask))
            except Exception:
                pass

        if image.isNull():
            try:
                provider = QFileIconProvider()
                icon = QIcon()
                if path and os.path.exists(path):
                    icon = provider.icon(QFileInfo(path))
                elif stock_recycle:
                    icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
                else:
                    icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
                if not icon.isNull():
                    pm = icon.pixmap(int(size), int(size))
                    if not pm.isNull():
                        img = pm.toImage().scaled(
                            int(size),
                            int(size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                        canvas.fill(0)
                        painter = QPainter(canvas)
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                        dx = int((int(size) - int(img.width())) // 2)
                        dy = int((int(size) - int(img.height())) // 2)
                        painter.drawImage(int(dx), int(dy), img)
                        painter.end()
                        image = canvas
            except Exception:
                image = QImage()

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        if len(cls._desktop_icon_image_cache) > 320:
            try:
                cls._desktop_icon_image_cache.pop(next(iter(cls._desktop_icon_image_cache)))
            except Exception:
                pass
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_item(cls, caption, icon_px):
        size = max(12, min(128, int(icon_px)))
        icon_key, _path, _stock_recycle = cls._desktop_icon_identity(caption)
        cache_key = (str(icon_key), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_item(caption, int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        if len(cls._desktop_icon_pixmap_cache) > 320:
            try:
                cls._desktop_icon_pixmap_cache.pop(next(iter(cls._desktop_icon_pixmap_cache)))
            except Exception:
                pass
        return QPixmap(pix)

    @staticmethod
    def _alpha_region_from_image(image, alpha_threshold=22):
        if image is None or image.isNull():
            return QRegion()
        img = image.convertToFormat(QImage.Format.Format_ARGB32)
        w = int(img.width())
        h = int(img.height())
        if w <= 0 or h <= 0:
            return QRegion()
        try:
            stride = int(img.bytesPerLine())
            total = int(img.sizeInBytes())
            ptr = img.bits()
            ptr.setsize(total)
            raw = ptr.asstring(total)
        except Exception:
            return QRegion()

        region = QRegion()
        threshold = int(max(0, min(255, int(alpha_threshold))))
        for y in range(h):
            row = int(y * stride)
            x = 0
            while x < w:
                while x < w and raw[row + (x * 4) + 3] <= threshold:
                    x += 1
                if x >= w:
                    break
                start = x
                x += 1
                while x < w and raw[row + (x * 4) + 3] > threshold:
                    x += 1
                length = int(x - start)
                if length > 0:
                    region = region.united(QRegion(QRect(int(start), int(y), int(length), 1)))
        return region

    @classmethod
    def _icon_alpha_region_for_item(cls, caption, icon_px):
        size = max(12, min(128, int(icon_px)))
        icon_key, _path, _stock_recycle = cls._desktop_icon_identity(caption)
        cache_key = (icon_key, int(size))
        cached = cls._desktop_icon_alpha_cache.get(cache_key)
        if isinstance(cached, QRegion):
            return QRegion(cached)

        image = cls._icon_image_for_item(caption, int(size))
        if image.isNull():
            region = QRegion()
        else:
            region = cls._alpha_region_from_image(image, alpha_threshold=20)

        cls._desktop_icon_alpha_cache[cache_key] = QRegion(region)
        if len(cls._desktop_icon_alpha_cache) > 320:
            try:
                cls._desktop_icon_alpha_cache.pop(next(iter(cls._desktop_icon_alpha_cache)))
            except Exception:
                pass
        return QRegion(region)

    @classmethod
    def _desktop_icon_title_font(cls):
        now = float(time.monotonic())
        cached = getattr(cls, "_desktop_icon_title_font_cache", None)
        cache_ts = float(getattr(cls, "_desktop_icon_title_font_cache_ts", 0.0) or 0.0)
        if isinstance(cached, QFont) and (now - cache_ts) <= 8.0:
            return QFont(cached)
        font = DesktopIconCloneOverlay._resolve_icon_title_font()
        if not isinstance(font, QFont):
            font = QFont("Segoe UI", 9)
        cls._desktop_icon_title_font_cache = QFont(font)
        cls._desktop_icon_title_font_cache_ts = now
        return QFont(font)

    @classmethod
    def _label_alpha_region(cls, text, size):
        if not isinstance(size, QSize):
            return QRegion()
        w = max(0, int(size.width()))
        h = max(0, int(size.height()))
        label = str(text or "").strip()
        if not label or w <= 0 or h <= 0:
            return QRegion()
        font = cls._desktop_icon_title_font()
        font_key = (
            str(font.family() or ""),
            int(font.pixelSize()),
            float(font.pointSizeF()),
            int(font.weight()),
            bool(font.italic()),
        )
        cache_key = (label, int(w), int(h), font_key)
        cached = cls._desktop_text_alpha_cache.get(cache_key)
        if isinstance(cached, QRegion):
            return QRegion(cached)

        pad_x = 6
        pad_y = 2
        cw = int(max(1, w + (pad_x * 2)))
        ch = int(max(1, h + (pad_y * 2)))
        img = QImage(cw, ch, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)
        flags = int(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
            | Qt.TextFlag.TextWrapAnywhere
            | Qt.TextFlag.TextDontClip
        )
        draw_rect = QRect(int(pad_x - 4), int(pad_y), int(w + 8), int(h + 2))
        shadow_rect = QRect(draw_rect).translated(1, 1)
        # Include icon-label shadow pixels so only visibly rendered text gets punched.
        painter.setPen(QColor(0, 0, 0, 190))
        painter.drawText(shadow_rect, flags, label)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(draw_rect, flags, label)
        painter.end()

        region = cls._alpha_region_from_image(img, alpha_threshold=20)
        if not region.isEmpty():
            clip_rect = QRect(int(pad_x), int(pad_y), int(w), int(h))
            region = region.intersected(QRegion(clip_rect)).translated(-int(pad_x), -int(pad_y))
        cls._desktop_text_alpha_cache[cache_key] = QRegion(region)
        if len(cls._desktop_text_alpha_cache) > 1024:
            try:
                cls._desktop_text_alpha_cache.pop(next(iter(cls._desktop_text_alpha_cache)))
            except Exception:
                pass
        return QRegion(region)

    def _desktop_icon_clone_items_local(self, force=False):
        if not self._should_clone_desktop_icons():
            return []
        top_left = self._global_top_left()
        wx = int(top_left.x())
        wy = int(top_left.y())
        ww = int(self.width())
        wh = int(self.height())
        if ww <= 0 or wh <= 0:
            return []
        widget_screen_rect = QRect(wx, wy, ww, wh)
        rects_screen = self.__class__._desktop_icon_rects_screen(force=bool(force))
        edit_info_screen = self.__class__._desktop_icon_edit_info_screen()
        local_items = []
        for entry in rects_screen:
            if not isinstance(entry, dict):
                continue
            icon_rect = entry.get("icon")
            label_rect = entry.get("label")
            select_rect = entry.get("select")
            caption = str(entry.get("text", "") or "")
            shell_path = str(entry.get("shell_path", "") or "")
            shell_is_folder = bool(entry.get("shell_is_folder", False))
            shell_is_virtual = bool(entry.get("shell_is_virtual", False))
            selected = bool(entry.get("selected", False))
            focused = bool(entry.get("focused", False))
            try:
                image_index = int(entry.get("image_index", -1))
            except Exception:
                image_index = -1
            local_icon = QRect()
            local_label = QRect()
            local_select = QRect()
            local_icon_visible = QRect()
            local_label_visible = QRect()
            if isinstance(icon_rect, QRect):
                icon_hit = icon_rect.intersected(widget_screen_rect)
                if int(icon_hit.width()) > 0 and int(icon_hit.height()) > 0:
                    local_icon_visible = icon_hit.translated(-wx, -wy)
                    local_icon = QRect(icon_rect).translated(-wx, -wy)
            if isinstance(label_rect, QRect):
                label_hit = label_rect.intersected(widget_screen_rect)
                if int(label_hit.width()) > 0 and int(label_hit.height()) > 0:
                    local_label_visible = label_hit.translated(-wx, -wy)
                    local_label = QRect(label_rect).translated(-wx, -wy)
            if isinstance(select_rect, QRect):
                select_hit = select_rect.intersected(widget_screen_rect)
                if int(select_hit.width()) > 0 and int(select_hit.height()) > 0:
                    local_select = select_hit.translated(-wx, -wy)
            if int(local_select.width()) <= 0 or int(local_select.height()) <= 0:
                if bool(selected) or bool(focused):
                    merged = QRect()
                    if int(local_icon_visible.width()) > 0 and int(local_icon_visible.height()) > 0:
                        merged = QRect(local_icon_visible)
                    if int(local_label_visible.width()) > 0 and int(local_label_visible.height()) > 0:
                        merged = QRect(local_label_visible) if merged.isNull() else merged.united(QRect(local_label_visible))
                    if not merged.isNull() and int(merged.width()) > 0 and int(merged.height()) > 0:
                        local_select = merged.adjusted(-4, -2, 4, 2)
            if (
                (int(local_icon_visible.width()) <= 0 or int(local_icon_visible.height()) <= 0)
                and (int(local_label_visible.width()) <= 0 or int(local_label_visible.height()) <= 0)
            ):
                continue
            icon_side = 0
            if int(local_icon.width()) > 0 and int(local_icon.height()) > 0:
                icon_side = max(12, min(int(local_icon.width()), int(local_icon.height())))
            icon_pixmap = QPixmap()
            if shell_path and os.path.exists(shell_path):
                if shell_is_folder:
                    icon_pixmap = self.__class__._icon_pixmap_for_stock_id(3, int(icon_side or 48))
                else:
                    icon_pixmap = self.__class__._icon_pixmap_for_path(shell_path, int(icon_side or 48))
            elif shell_is_virtual and self.__class__._is_recycle_caption(caption):
                icon_pixmap = self.__class__._icon_pixmap_for_stock_id(31, int(icon_side or 48))
            elif image_index >= 0:
                icon_pixmap = self.__class__._icon_pixmap_for_sys_index(int(image_index), int(icon_side or 48))
            if icon_pixmap.isNull():
                icon_pixmap = self.__class__._icon_pixmap_for_item(caption, int(icon_side or 48))
            if int(local_icon.width()) > 0 and int(local_icon.height()) > 0 and not icon_pixmap.isNull():
                if int(icon_pixmap.width()) != int(icon_side) or int(icon_pixmap.height()) != int(icon_side):
                    icon_pixmap = icon_pixmap.scaled(
                        int(icon_side),
                        int(icon_side),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
            local_items.append(
                {
                    "icon_rect": local_icon,
                    "icon_pixmap": icon_pixmap,
                    "label_rect": local_label,
                    "text": caption,
                    "select_rect": local_select,
                    "selected": bool(selected),
                    "focused": bool(focused),
                }
            )
        if isinstance(edit_info_screen, dict):
            edit_rect = edit_info_screen.get("rect")
            if isinstance(edit_rect, QRect):
                edit_hit = edit_rect.intersected(widget_screen_rect)
                if int(edit_hit.width()) > 0 and int(edit_hit.height()) > 0:
                    local_items.append(
                        {
                            "edit_rect": edit_hit.translated(-wx, -wy),
                            "edit_text": str(edit_info_screen.get("text", "") or ""),
                        }
                    )
        return local_items

    def _desktop_icon_hole_rects_local(self, force=False):
        if not self._should_punch_desktop_icons():
            return []
        top_left = self._global_top_left()
        wx = int(top_left.x())
        wy = int(top_left.y())
        ww = int(self.width())
        wh = int(self.height())
        if ww <= 0 or wh <= 0:
            return []
        widget_screen_rect = QRect(wx, wy, ww, wh)
        widget_local_region = QRegion(QRect(0, 0, int(ww), int(wh)))
        rects_screen = self.__class__._desktop_icon_rects_screen(force=bool(force))
        local_items = []
        for entry in rects_screen:
            if not isinstance(entry, dict):
                continue
            icon_rect = entry.get("icon")
            label_rect = entry.get("label")
            caption = str(entry.get("text", "") or "").strip()
            shell_path = str(entry.get("shell_path", "") or "")
            shell_is_folder = bool(entry.get("shell_is_folder", False))
            shell_is_virtual = bool(entry.get("shell_is_virtual", False))
            try:
                image_index = int(entry.get("image_index", -1))
            except Exception:
                image_index = -1
            icon_region = QRegion()
            text_region = QRegion()

            if isinstance(icon_rect, QRect):
                icon_hit = icon_rect.intersected(widget_screen_rect)
                if int(icon_hit.width()) > 0 and int(icon_hit.height()) > 0:
                    icon_local_full = QRect(icon_rect).translated(-wx, -wy)
                    side = max(12, min(int(icon_local_full.width()), int(icon_local_full.height())))
                    alpha_region = QRegion()
                    if shell_path and os.path.exists(shell_path):
                        if shell_is_folder:
                            image = self.__class__._icon_image_for_stock_id(3, int(side))
                        else:
                            image = self.__class__._icon_image_for_path(shell_path, int(side))
                        if not image.isNull():
                            alpha_region = self.__class__._alpha_region_from_image(image, alpha_threshold=20)
                    elif shell_is_virtual and self.__class__._is_recycle_caption(caption):
                        image = self.__class__._icon_image_for_stock_id(31, int(side))
                        if not image.isNull():
                            alpha_region = self.__class__._alpha_region_from_image(image, alpha_threshold=20)
                    elif image_index >= 0:
                        image = self.__class__._icon_image_for_sys_index(int(image_index), int(side))
                        if not image.isNull():
                            alpha_region = self.__class__._alpha_region_from_image(image, alpha_threshold=20)
                    if alpha_region.isEmpty():
                        alpha_region = self.__class__._icon_alpha_region_for_item(caption, int(side))
                    if not alpha_region.isEmpty():
                        px = int(icon_local_full.x() + ((int(icon_local_full.width()) - int(side)) // 2))
                        py = int(icon_local_full.y() + ((int(icon_local_full.height()) - int(side)) // 2))
                        icon_region = alpha_region.translated(int(px), int(py)).intersected(widget_local_region)
                    if icon_region.isEmpty():
                        fallback_box = QRect(icon_rect).translated(-wx, -wy)
                        fb_side = max(10, min(int(fallback_box.width()), int(fallback_box.height())) - 16)
                        fx = int(fallback_box.x() + ((int(fallback_box.width()) - int(fb_side)) // 2))
                        fy = int(fallback_box.y() + ((int(fallback_box.height()) - int(fb_side)) // 2))
                        fallback = QRect(int(fx), int(fy), int(fb_side), int(fb_side))
                        if int(fallback.width()) > 0 and int(fallback.height()) > 0:
                            path = QPainterPath()
                            rr = max(3.0, min(float(fallback.width()), float(fallback.height())) * 0.16)
                            path.addRoundedRect(QRectF(fallback), rr, rr)
                            icon_region = QRegion(path.toFillPolygon().toPolygon()).intersected(widget_local_region)

            if isinstance(label_rect, QRect):
                label_hit = label_rect.intersected(widget_screen_rect)
                if int(label_hit.width()) > 0 and int(label_hit.height()) > 0:
                    label_local = QRect(label_rect).translated(-wx, -wy)
                    glyph_region = self.__class__._label_alpha_region(caption, label_local.size())
                    if not glyph_region.isEmpty():
                        text_region = glyph_region.translated(
                            int(label_local.x()),
                            int(label_local.y()),
                        ).intersected(widget_local_region)

            if not icon_region.isEmpty() or not text_region.isEmpty():
                local_items.append({"icon_region": icon_region, "label_region": text_region})
        return local_items

    def eventFilter(self, watched, event):
        # App-level key handling for widget-local shortcuts.
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            key = event.key() if hasattr(event, "key") else None
            if key == Qt.Key.Key_Shift and (self._is_cursor_over_widget() or self.is_resizing):
                self._refresh_resize_ui()
            elif (
                event.type() == QEvent.Type.KeyPress
                and key in (
                    Qt.Key.Key_M, Qt.Key.Key_O, Qt.Key.Key_P, Qt.Key.Key_C, Qt.Key.Key_G,
                    Qt.Key.Key_H, Qt.Key.Key_R
                )
                and self._is_topmost_widget_under_cursor()
            ):
                modifiers = event.modifiers() if hasattr(event, "modifiers") else Qt.KeyboardModifier.NoModifier
                ctrl_mod = Qt.KeyboardModifier.ControlModifier
                blocked_mods = ctrl_mod | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier
                is_auto_repeat = event.isAutoRepeat() if hasattr(event, "isAutoRepeat") else False
                if key == Qt.Key.Key_G:
                    only_ctrl = (
                        bool(modifiers & ctrl_mod)
                        and not bool(modifiers & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier))
                    )
                    no_mod = modifiers == Qt.KeyboardModifier.NoModifier
                    if is_auto_repeat:
                        return True
                    if only_ctrl and self._consume_shortcut_once(key, 1):
                        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "clear_temp_group"):
                            self.manager.clear_temp_group()
                        return True
                    if no_mod and self._consume_shortcut_once(key, 0):
                        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "toggle_temp_group_member"):
                            self.manager.toggle_temp_group_member(self.profile_id)
                        return True
                    return False
                if (modifiers & blocked_mods) == Qt.KeyboardModifier.NoModifier and not is_auto_repeat:
                    if self._consume_shortcut_once(key, 0):
                        if key == Qt.Key.Key_M:
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "set_temp_group_mute"):
                                self.manager.set_temp_group_mute(self.profile_id, not bool(self.is_muted))
                            else:
                                self.toggle_mute_shortcut()
                        elif key == Qt.Key.Key_O:
                            self.open_settings()
                        elif key == Qt.Key.Key_C:
                            self.open_master_controller()
                        elif key == Qt.Key.Key_P:
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "stop_widget"):
                                QTimer.singleShot(0, lambda pid=self.profile_id: self.manager.stop_widget(pid))
                        elif key == Qt.Key.Key_H:
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "set_temp_group_gpu_guard"):
                                self.manager.set_temp_group_gpu_guard(self.profile_id, not bool(self.gpu_guard_enabled))
                            else:
                                self.toggle_gpu_guard_shortcut()
                        elif key == Qt.Key.Key_R:
                            next_corner = 0 if int(getattr(self, "corner_mode", 0)) == 1 else 1
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "set_temp_group_corner_mode"):
                                self.manager.set_temp_group_corner_mode(self.profile_id, next_corner)
                            else:
                                self.toggle_corner_mode_shortcut()
                        return True
            return False

        if not self._is_event_for_this_widget(watched):
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            self.mousePressEvent(event)
            return True
        elif event.type() == QEvent.Type.MouseMove:
            self.mouseMoveEvent(event)
            return True
        elif event.type() == QEvent.Type.MouseButtonRelease:
            self.mouseReleaseEvent(event)
            return True
        elif event.type() == QEvent.Type.Wheel:
            self.wheelEvent(event)
            return True
        elif event.type() == QEvent.Type.ContextMenu:
            self.contextMenuEvent(event)
            return True
        elif event.type() == QEvent.Type.DragEnter:
            self.dragEnterEvent(event)
            return True
        elif event.type() == QEvent.Type.DragMove:
            self.dragMoveEvent(event)
            return True
        elif event.type() == QEvent.Type.Drop:
            self.dropEvent(event)
            return True
        elif event.type() == QEvent.Type.DragLeave:
            self.dragLeaveEvent(event)
            return True
        elif event.type() in (
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.HoverEnter,
            QEvent.Type.HoverLeave,
            QEvent.Type.HoverMove,
        ):
            QTimer.singleShot(0, self._refresh_resize_ui)
            return False
        return super().eventFilter(watched, event)

    def _is_event_for_this_widget(self, watched):
        if watched is self:
            return True
        if isinstance(watched, QWidget):
            return self.isAncestorOf(watched)
        return False

    @staticmethod
    def _extract_first_local_drop_path(event):
        mime = event.mimeData() if event else None
        if not mime or not mime.hasUrls():
            return ""
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if path:
                return os.path.normpath(path)
        return ""

    def _apply_drop_target(self, path):
        if not path:
            return False
        if os.path.isdir(path):
            self.folder_path = path
            self._set_watched_folder(path)
            self.update_playlist()
            self.current_idx = -1
            self.next_media()
            self.save_all_settings()
            print(f"[drop-folder] profile={self.profile_id} folder={path}")
            return True
        if os.path.isfile(path):
            self.exec_path = path
            self.save_all_settings()
            print(f"[drop-exec] profile={self.profile_id} exec={path}")
            return True
        return False

    def _is_shift_down(self):
        return bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)

    def _consume_shortcut_once(self, key, modifier_bucket=0):
        now_ms = QDateTime.currentMSecsSinceEpoch()
        token = f"{int(key)}:{int(modifier_bucket)}"
        last_ms = int(self._shortcut_last_ms.get(token, 0))
        if (now_ms - last_ms) <= 120:
            return False
        self._shortcut_last_ms[token] = now_ms
        return True

    def _is_topmost_widget_under_cursor(self):
        pos = QCursor.pos()
        top_widget = QApplication.widgetAt(pos)
        while top_widget is not None:
            if top_widget is self:
                return True
            if isinstance(top_widget, DesktopWidget):
                return top_widget is self
            top_widget = top_widget.parentWidget()

        # Fallback for native/transparent edge cases.
        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "_widget_under_global_pos"):
            return self.manager._widget_under_global_pos(pos) is self
        return self.geometry().contains(pos)

    def _place_group_badge(self):
        if not hasattr(self, "group_badge"):
            return
        self.group_badge.adjustSize()
        margin = 10
        x = margin
        y = margin
        self.group_badge.move(x, y)

    def _refresh_group_badge(self):
        is_grouped = False
        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "is_temp_group_member"):
            is_grouped = bool(self.manager.is_temp_group_member(self.profile_id))
        if is_grouped:
            self._place_group_badge()
            self.group_badge.show()
            self.group_badge.raise_()
        else:
            self.group_badge.hide()

    def _set_audio_output_attached(self, attach):
        if attach:
            self.media_player.setAudioOutput(self.audio_output)
            self._audio_output_attached = True
        else:
            self.media_player.setAudioOutput(None)
            self._audio_output_attached = False

    def _apply_mute_state(self, force_refresh=False):
        if self.is_muted:
            current_volume = float(self.audio_output.volume())
            if current_volume > 0.001:
                self._last_unmuted_volume = current_volume
            if not self._audio_output_attached:
                self._set_audio_output_attached(True)
            self.audio_output.setMuted(True)
            self.audio_output.setVolume(0.0)
            return

        if force_refresh:
            self._set_audio_output_attached(True)
        elif not self._audio_output_attached:
            self._set_audio_output_attached(True)
        restore_volume = float(getattr(self, "_last_unmuted_volume", 1.0))
        if restore_volume <= 0.001:
            restore_volume = 1.0
        restore_volume = max(0.0, min(1.0, restore_volume))
        self.audio_output.setVolume(restore_volume)
        self.audio_output.setMuted(False)
        if force_refresh and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            pos = self.media_player.position()
            self.media_player.play()
            if pos >= 0:
                self.media_player.setPosition(pos)

    def set_mute_shortcut_state(self, muted, log=False):
        self.is_muted = bool(muted)
        self._apply_mute_state(force_refresh=True)
        self.save_all_settings()
        if not log:
            return
        playback_state = self.media_player.playbackState().name if self.media_player else "n/a"
        media_path = self.current_media_path if self.current_media_path else "none"
        print(
            f"[mute-toggle] profile={self.profile_id} muted={self.is_muted} "
            f"output_muted={self.audio_output.isMuted()} volume={self.audio_output.volume():.2f} "
            f"output_attached={self._audio_output_attached} state={playback_state} media={media_path}"
        )

    def toggle_mute_shortcut(self):
        self.set_mute_shortcut_state(not bool(self.is_muted), log=True)

    def set_gpu_guard_shortcut_state(self, enabled, log=False, show_hud=False):
        self.gpu_guard_enabled = bool(enabled)
        if not self.gpu_guard_enabled:
            self.set_performance_paused(False, reason="guard_toggle_off")
        elif hasattr(self, "manager") and self.manager and bool(getattr(self.manager, "_gpu_guard_paused", False)):
            usage = float(getattr(self.manager, "_gpu_last_usage", 0.0))
            self.set_performance_paused(True, reason=f"gpu {usage:.1f}%", force=True)
        self.save_all_settings()
        if show_hud:
            self.show_gpu_guard_hud(self.gpu_guard_enabled)
        if log:
            print(f"[gpu-guard-toggle] profile={self.profile_id} enabled={self.gpu_guard_enabled}")

    def toggle_gpu_guard_shortcut(self):
        self.set_gpu_guard_shortcut_state(not bool(self.gpu_guard_enabled), log=True, show_hud=True)

    def set_corner_mode_shortcut_state(self, mode, log=False):
        mode_int = int(mode)
        if mode_int not in (0, 1):
            mode_int = 0
        self.corner_mode = mode_int
        self.apply_mask_and_style()
        self.save_all_settings()
        if log:
            mode_text = "곡선" if self.corner_mode == 0 else "직각"
            print(f"[corner-toggle] profile={self.profile_id} corner_mode={mode_text}")

    def toggle_corner_mode_shortcut(self):
        curr = int(getattr(self, "corner_mode", 0))
        self.set_corner_mode_shortcut_state(0 if curr == 1 else 1, log=True)

    def set_performance_paused(self, paused, reason="", force=False):
        paused = bool(paused)
        if paused == self._performance_paused and not force:
            return

        self._performance_paused = paused
        if paused:
            self._perf_paused_video = False
            self._perf_paused_gif = False
            self._perf_gif_timer_was_active = False

            if self.stack.currentIndex() == 2:
                if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self.media_player.pause()
                    self._perf_paused_video = True
            elif self.stack.currentIndex() == 1 and self.movie is not None:
                if self.movie.state() == QMovie.MovieState.Running:
                    self.movie.setPaused(True)
                    self._perf_paused_gif = True
                if self.timer.isActive():
                    self.timer.stop()
                    self._perf_gif_timer_was_active = True

            if reason:
                print(f"[gpu-guard-pause] profile={self.profile_id} reason={reason}")
            return

        if self._perf_paused_video and self.stack.currentIndex() == 2:
            self.media_player.play()
        if self._perf_paused_gif and self.movie is not None:
            self.movie.setPaused(False)
        if self._perf_gif_timer_was_active and self.stack.currentIndex() == 1 and self.movie is not None:
            if not self.timer.isActive():
                self.timer.start(self.interval_ms)

        self._perf_paused_video = False
        self._perf_paused_gif = False
        self._perf_gif_timer_was_active = False
        if reason:
            print(f"[gpu-guard-resume] profile={self.profile_id} reason={reason}")

    def _is_cursor_over_widget(self):
        if not self.isVisible():
            return False
        local = self.mapFromGlobal(QCursor.pos())
        return self.rect().contains(local)

    def _corner_rects(self):
        s = self.resize_overlay.handle_size
        m = self.resize_overlay.handle_margin
        w = max(0, self.width() - s - m)
        h = max(0, self.height() - s - m)
        return {
            "tl": QRect(m, m, s, s),
            "tr": QRect(w, m, s, s),
            "bl": QRect(m, h, s, s),
            "br": QRect(w, h, s, s),
        }

    def _corner_hit_test(self, local_pos):
        if local_pos is None:
            return None
        if not self.rect().contains(local_pos):
            return None

        for corner, rect in self._corner_rects().items():
            hit_box = rect.adjusted(-4, -4, 4, 4)
            if hit_box.contains(local_pos):
                return corner
        return None

    def _set_resize_cursor(self, corner):
        if corner in ("tl", "br"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif corner in ("tr", "bl"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def _refresh_resize_ui(self):
        self._cursor_inside = self._is_cursor_over_widget()
        show_handles = (
            (self._cursor_inside and self._is_shift_down() and not getattr(self, "is_locked", False))
            or self.is_resizing
        )

        if show_handles:
            self.resize_overlay.setGeometry(self.rect())
            self.resize_overlay.show()
            self.resize_overlay.raise_()
            if not self.is_resizing:
                local = self.mapFromGlobal(QCursor.pos())
                corner = self._corner_hit_test(local)
                self._set_resize_cursor(corner)
        else:
            self.resize_overlay.hide()
            if not self.is_resizing:
                self.unsetCursor()

    def _refresh_size_hud(self):
        text = f"{self.width()} x {self.height()}"
        self.size_hud.setText(text)
        fm = QFontMetrics(self.size_hud.font())
        hud_w = max(80, fm.horizontalAdvance(text) + 26)
        hud_h = max(24, fm.height() + 12)
        self.size_hud.resize(hud_w, hud_h)
        hud_x = max(0, (self.width() - hud_w) // 2)
        self.size_hud.move(hud_x, self._size_hud_top_padding)
        self.size_hud.raise_()

    def _show_size_hud(self):
        self._refresh_size_hud()
        self.size_hud.show()

    def _hide_size_hud(self):
        self.size_hud.hide()

    def _refresh_action_hud(self):
        if not hasattr(self, "action_hud"):
            return
        text = self.action_hud.text()
        if not text:
            return
        fm = QFontMetrics(self.action_hud.font())
        hud_w = max(92, fm.horizontalAdvance(text) + 24)
        hud_h = max(22, fm.height() + 10)
        self.action_hud.resize(hud_w, hud_h)
        hud_x = max(0, (self.width() - hud_w) // 2)
        self.action_hud.move(hud_x, self._size_hud_top_padding)
        self.action_hud.raise_()

    def _show_action_hud(self, text, timeout_ms=1200):
        if not hasattr(self, "action_hud"):
            return
        self.action_hud.setText(str(text))
        self._refresh_action_hud()
        self.action_hud.show()
        self.action_hud.raise_()
        if hasattr(self, "action_hud_timer"):
            self.action_hud_timer.start(max(400, int(timeout_ms)))

    def show_lock_hud(self, lock_enabled):
        self._show_action_hud(f"마우스 잠금 {'ON' if lock_enabled else 'OFF'}", timeout_ms=1300)

    def show_gpu_guard_hud(self, guard_enabled):
        self._show_action_hud(f"성능 보호 {'ON' if guard_enabled else 'OFF'}", timeout_ms=1300)

    def _set_drag_topmost(self, enabled):
        enabled = bool(enabled)
        active = bool(getattr(self, "_drag_topmost_active", False))
        if enabled == active:
            return

        self._drag_topmost_active = enabled
        if enabled:
            restore_layer = int(getattr(self, "layer_mode", self.LAYER_NORMAL))
            restore_lock = bool(getattr(self, "is_locked", False))
            self._drag_restore_layer = int(restore_layer)
            self._drag_restore_lock = bool(restore_lock)
            self.apply_window_settings(
                int(self.LAYER_TOPMOST),
                bool(restore_lock),
                cancel_interaction=False,
            )
            # Keep configured state logical value unchanged while dragging.
            self.layer_mode = int(restore_layer)
            self.is_locked = bool(restore_lock)
            return

        if not self.isVisible():
            self._drag_restore_layer = None
            self._drag_restore_lock = None
            return
        restore_layer = int(getattr(self, "_drag_restore_layer", getattr(self, "layer_mode", self.LAYER_NORMAL)))
        restore_lock = bool(getattr(self, "_drag_restore_lock", getattr(self, "is_locked", False)))
        self._drag_restore_layer = None
        self._drag_restore_lock = None
        self.apply_window_settings(
            int(restore_layer),
            bool(restore_lock),
            cancel_interaction=False,
        )

    def cancel_active_interaction(self):
        """Force-clear dragging/resizing transient states (used by lock toggle)."""
        self.start_pos = None
        self.is_moving = False
        self.is_resizing = False
        self.resize_corner = None
        self.resize_start_pos = None
        self._set_drag_topmost(False)
        self._reset_axis_snap()
        self._hide_size_hud()
        self.unsetCursor()
        self._refresh_resize_ui()

    def _apply_corner_resize(self, global_pos):
        if not self.is_resizing or not self.resize_corner:
            return

        prev_geo = QRect(self.geometry())
        delta = global_pos - self.resize_start_pos
        start = QRect(self.resize_start_geo)
        x = start.x()
        y = start.y()
        w = start.width()
        h = start.height()
        min_w = max(50, self.minimumWidth())
        min_h = max(50, self.minimumHeight())

        if self.resize_corner == "tl":
            x = start.x() + delta.x()
            y = start.y() + delta.y()
            w = start.width() - delta.x()
            h = start.height() - delta.y()
        elif self.resize_corner == "tr":
            y = start.y() + delta.y()
            w = start.width() + delta.x()
            h = start.height() - delta.y()
        elif self.resize_corner == "bl":
            x = start.x() + delta.x()
            w = start.width() - delta.x()
            h = start.height() + delta.y()
        elif self.resize_corner == "br":
            w = start.width() + delta.x()
            h = start.height() + delta.y()

        if w < min_w:
            if self.resize_corner in ("tl", "bl"):
                x = start.x() + (start.width() - min_w)
            w = min_w
        if h < min_h:
            if self.resize_corner in ("tl", "tr"):
                y = start.y() + (start.height() - min_h)
            h = min_h

        self.setGeometry(QRect(int(x), int(y), int(w), int(h)))
        new_geo = QRect(self.geometry())
        left_step = int(new_geo.x() - prev_geo.x())
        top_step = int(new_geo.y() - prev_geo.y())
        right_step = int((new_geo.x() + new_geo.width()) - (prev_geo.x() + prev_geo.width()))
        bottom_step = int((new_geo.y() + new_geo.height()) - (prev_geo.y() + prev_geo.height()))
        if left_step or top_step or right_step or bottom_step:
            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "resize_temp_group_by_edges"):
                self.manager.resize_temp_group_by_edges(
                    self.profile_id,
                    left_step,
                    top_step,
                    right_step,
                    bottom_step,
                )

    def _reset_axis_snap(self):
        self._snap_lock_x = None
        self._snap_lock_y = None
        self._snap_origin_pointer_x = None
        self._snap_origin_pointer_y = None

    def _other_widgets(self):
        if not hasattr(self, "manager") or not self.manager:
            return []
        widgets = getattr(self.manager, "widgets", {})
        if not isinstance(widgets, dict):
            return []
        return [w for w in widgets.values() if w is not self and isinstance(w, QWidget) and w.isVisible()]

    def _find_axis_snap_target(self, axis, raw_value):
        best_target = None
        best_dist = self._axis_snap_threshold + 1
        own_span = self.width() if axis == "x" else self.height()
        for w in self._other_widgets():
            other_lead = w.x() if axis == "x" else w.y()
            other_trail = (w.x() + w.width()) if axis == "x" else (w.y() + w.height())

            # Snap candidates for this widget's top-left coordinate:
            # - own lead to other lead/trail
            # - own trail to other lead/trail
            candidates = (
                other_lead,                    # left-left / top-top
                other_trail,                   # left-right / top-bottom
                other_lead - own_span,         # right-left / bottom-top
                other_trail - own_span,        # right-right / bottom-bottom
            )
            for target in candidates:
                dist = abs(raw_value - target)
                if dist <= self._axis_snap_threshold and dist < best_dist:
                    best_target = target
                    best_dist = dist
        return best_target

    def _apply_axis_snap(self, axis, raw_value, pointer_value):
        if axis == "x":
            lock = self._snap_lock_x
            origin = self._snap_origin_pointer_x
        else:
            lock = self._snap_lock_y
            origin = self._snap_origin_pointer_y

        if lock is not None and origin is not None:
            if abs(pointer_value - origin) > self._axis_snap_release:
                if axis == "x":
                    self._snap_lock_x = None
                    self._snap_origin_pointer_x = None
                else:
                    self._snap_lock_y = None
                    self._snap_origin_pointer_y = None
            else:
                return lock

        target = self._find_axis_snap_target(axis, raw_value)
        if target is not None:
            if axis == "x":
                self._snap_lock_x = target
                self._snap_origin_pointer_x = pointer_value
            else:
                self._snap_lock_y = target
                self._snap_origin_pointer_y = pointer_value
            return target

        return raw_value

    def _as_path_set(self, value):
        if isinstance(value, list):
            return {str(v) for v in value if str(v)}
        if value in (None, ""):
            return set()
        return {str(value)}

    def _save_quarantined_media(self):
        self.settings.setValue("quarantined_media", sorted(self.quarantined_media))

    def _current_screen(self):
        screen = self.screen()
        if not screen:
            screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        return screen

    def _find_screen_by_name(self, name):
        if not name:
            return None
        for screen in QGuiApplication.screens():
            if screen.name() == name:
                return screen
        return None

    def _save_position_metadata(self):
        screen = self._current_screen()
        if not screen:
            return

        ag = screen.availableGeometry()
        max_x = max(1, ag.width() - self.width())
        max_y = max(1, ag.height() - self.height())
        gpos = self._global_top_left()
        rel_x = (gpos.x() - ag.x()) / max_x
        rel_y = (gpos.y() - ag.y()) / max_y
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))

        self.settings.setValue("screen_name", screen.name())
        self.settings.setValue("screen_rel_x", rel_x)
        self.settings.setValue("screen_rel_y", rel_y)
        self.settings.setValue("screen_dpr", float(screen.devicePixelRatio()))
        self.settings.setValue("screen_dpi", float(screen.logicalDotsPerInch()))

    def _restore_position_with_screen_fallback(self, saved_pos):
        if saved_pos:
            self._move_exact(saved_pos)
            if self.is_visible_on_any_screen():
                return

        saved_screen_name = self.settings.value("screen_name", "")
        rel_x = float(self.settings.value("screen_rel_x", 0.0))
        rel_y = float(self.settings.value("screen_rel_y", 0.0))
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))

        target_screen = self._find_screen_by_name(saved_screen_name) or QGuiApplication.primaryScreen()
        if not target_screen:
            return

        ag = target_screen.availableGeometry()
        max_x = max(0, ag.width() - self.width())
        max_y = max(0, ag.height() - self.height())
        x = ag.x() + int(round(max_x * rel_x))
        y = ag.y() + int(round(max_y * rel_y))
        self._move_exact((x, y))

    def _record_media_failure(self, path, reason):
        if not path:
            return

        count = self.media_fail_counts.get(path, 0) + 1
        self.media_fail_counts[path] = count
        print(f"[media-skip] {os.path.basename(path)} ({reason}) count={count}")

        if count >= self.max_media_failures:
            self.quarantined_media.add(path)
            self._save_quarantined_media()
            print(f"[media-quarantine] {os.path.basename(path)}")

    def _schedule_next_media(self):
        if self._failure_scheduled:
            return
        self._failure_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_next_media)

    def _run_scheduled_next_media(self):
        self._failure_scheduled = False
        self.next_media()

    def _skip_current_media(self, reason):
        path = self.current_media_path
        if path:
            self._record_media_failure(path, reason)

        if path in self.playlist and path in self.quarantined_media:
            idx = self.playlist.index(path)
            self.playlist.pop(idx)
            if idx <= self.current_idx:
                self.current_idx -= 1

        if not self.playlist:
            self.current_media_path = None
            self.stack.setCurrentIndex(0)
            return

        self._schedule_next_media()

    def load_settings(self):
        self.folder_path = self.settings.value("folder_path", "")
        self.exec_path = self.settings.value("exec_path", "")
        self.interval_ms = int(self.settings.value("interval", 5)) * 1000
        self.is_muted = _as_bool(self.settings.value("is_muted", True), True)
        self.current_opacity_pct = int(self.settings.value("opacity_pct", 100))
        self.setWindowOpacity(self.current_opacity_pct / 100.0)
        self.bg_color_mode = int(self.settings.value("bg_color_mode", 1))
        self.corner_mode = int(self.settings.value("corner_mode", 0))
        self.media_fit_mode = max(0, min(int(self.settings.value("media_fit_mode", 0)), 1))
        if self.settings.contains("layer_mode"):
            layer_schema_ver = int(self.settings.value("layer_schema_version", 0))
            raw_layer_mode = int(self.settings.value("layer_mode", self.LAYER_NORMAL))
            self.layer_mode = self.coerce_layer_mode(raw_layer_mode, layer_schema_ver)
            if layer_schema_ver < int(self.LAYER_SCHEMA_VERSION):
                self.settings.setValue("layer_mode", int(self.layer_mode))
                self.settings.setValue("layer_schema_version", int(self.LAYER_SCHEMA_VERSION))
                self.settings.sync()
        else:
            self.layer_mode = int(self.LAYER_NORMAL)
            self.settings.setValue("layer_mode", int(self.layer_mode))
            self.settings.setValue("layer_schema_version", int(self.LAYER_SCHEMA_VERSION))
            self.settings.sync()
        self.is_locked = _as_bool(self.settings.value("is_locked", False), False)
        self.gpu_guard_enabled = _as_bool(self.settings.value("gpu_guard_enabled", False), False)
        self.quarantined_media = self._as_path_set(self.settings.value("quarantined_media", []))
        w = int(self.settings.value("w", 200))
        h = int(self.settings.value("h", 200))
        self.resize(w, h)
        saved_pos = self.settings.value("pos")
        saved_size = self.settings.value("size")
        if saved_size:
            self.resize(saved_size)
        self._restore_position_with_screen_fallback(saved_pos)
        if not self.is_visible_on_any_screen():
            geo = self.settings.value("geometry")
            if geo:
                self.restoreGeometry(geo)
        if not self.is_visible_on_any_screen():
            self._move_exact((100, 100))
        self._set_watched_folder(self.folder_path)
        self._apply_mute_state()
        self._update_video_aspect_mode()
        self.apply_window_settings(self.layer_mode, self.is_locked)
        if saved_size:
            self.resize(saved_size)
        self._restore_position_with_screen_fallback(saved_pos)

    def _is_media_fill_mode(self):
        return int(getattr(self, "media_fit_mode", 0)) == 1

    @staticmethod
    def _safe_target_size(widget, fallback_size):
        fw = 0
        fh = 0
        if isinstance(fallback_size, QSize):
            fw = max(0, int(fallback_size.width()))
            fh = max(0, int(fallback_size.height()))

        if isinstance(widget, QWidget):
            s = widget.size()
            sw = int(s.width()) if isinstance(s, QSize) else 0
            sh = int(s.height()) if isinstance(s, QSize) else 0
            if sw > 0 and sh > 0:
                if widget.isVisible():
                    return QSize(int(sw), int(sh))
                # Hidden startup state: prefer fallback if widget child is still pre-layout small.
                if fw <= 0 or fh <= 0:
                    return QSize(int(sw), int(sh))
                min_w = max(24, int(fw * 0.90))
                min_h = max(24, int(fh * 0.90))
                if sw >= min_w and sh >= min_h:
                    return QSize(int(sw), int(sh))
        if fw > 0 and fh > 0:
            return QSize(int(fw), int(fh))
        return QSize(1, 1)

    @staticmethod
    def _scaled_size_for_source(source_size, target_size, fill):
        if not isinstance(source_size, QSize) or not isinstance(target_size, QSize):
            return QSize(1, 1)
        sw = max(1, int(source_size.width()))
        sh = max(1, int(source_size.height()))
        tw = max(1, int(target_size.width()))
        th = max(1, int(target_size.height()))
        if bool(fill):
            scale = max(float(tw) / float(sw), float(th) / float(sh))
        else:
            scale = min(float(tw) / float(sw), float(th) / float(sh))
        nw = max(1, int(round(float(sw) * float(scale))))
        nh = max(1, int(round(float(sh) * float(scale))))
        return QSize(int(nw), int(nh))

    def _resize_video_surface(self):
        if not bool(getattr(self, "_video_graphics_mode", False)):
            return
        if not isinstance(getattr(self, "video_widget", None), QGraphicsView):
            return
        if getattr(self, "video_scene", None) is None or getattr(self, "video_item", None) is None:
            return
        try:
            target = self._safe_target_size(getattr(self, "video_widget", None), self.size())
            w = max(1, int(target.width()))
            h = max(1, int(target.height()))
            self.video_scene.setSceneRect(QRectF(0.0, 0.0, float(w), float(h)))
            self.video_item.setPos(QPointF(0.0, 0.0))
            self.video_item.setSize(QSizeF(float(w), float(h)))
        except Exception:
            pass

    def _update_video_aspect_mode(self):
        if not hasattr(self, "video_widget"):
            return
        mode = Qt.AspectRatioMode.KeepAspectRatio
        if self._is_media_fill_mode():
            mode = getattr(
                Qt.AspectRatioMode,
                "KeepAspectRatioByExpanding",
                Qt.AspectRatioMode.KeepAspectRatio,
            )
        if bool(getattr(self, "_video_graphics_mode", False)) and getattr(self, "video_item", None) is not None:
            try:
                self.video_item.setAspectRatioMode(mode)
            except Exception:
                pass
            self._resize_video_surface()
            return
        try:
            self.video_widget.setAspectRatioMode(mode)
        except Exception:
            pass

    def _update_movie_scaled_size(self):
        if not self.movie:
            return
        self._update_movie_scaled_size_for(self.movie)

    def _update_movie_scaled_size_for(self, movie_obj):
        if movie_obj is None:
            return
        target = self._safe_target_size(getattr(self, "img_label", None), self.size())
        src = QSize()
        try:
            fr = movie_obj.frameRect()
            if isinstance(fr, QRect):
                src = fr.size()
        except Exception:
            src = QSize()
        if int(src.width()) <= 0 or int(src.height()) <= 0:
            try:
                pm = movie_obj.currentPixmap()
                if isinstance(pm, QPixmap) and not pm.isNull():
                    src = pm.size()
            except Exception:
                src = QSize()
        if int(src.width()) <= 0 or int(src.height()) <= 0:
            src = QSize(int(target.width()), int(target.height()))
        scaled = self._scaled_size_for_source(src, target, fill=self._is_media_fill_mode())
        try:
            movie_obj.setScaledSize(scaled)
        except Exception:
            pass

    def _estimate_gif_duration_ms(self, movie_obj):
        if movie_obj is None:
            return 0
        try:
            frame_count = int(movie_obj.frameCount())
        except Exception:
            frame_count = 0
        if frame_count <= 0:
            return 0
        try:
            frame_delay = int(movie_obj.nextFrameDelay())
        except Exception:
            frame_delay = 0
        if frame_delay <= 0:
            return 0
        # Cheap estimate only: avoid frame-by-frame seeking that can stall startup.
        return int(max(0, min(600000, int(frame_count) * int(frame_delay))))

    def _clear_active_gif_loop_watch(self):
        if hasattr(self, "_gif_loop_fallback_timer") and self._gif_loop_fallback_timer.isActive():
            self._gif_loop_fallback_timer.stop()
        self._gif_loop_watch_active = False
        self._gif_loop_last_frame = -1
        self._gif_loop_min_deadline = 0.0
        self._gif_wait_for_finished_only = False
        if self.movie is None:
            return
        try:
            self.movie.frameChanged.disconnect(self._on_active_gif_frame_changed)
        except Exception:
            pass
        try:
            self.movie.finished.disconnect(self._on_active_gif_finished)
        except Exception:
            pass

    def _start_active_gif_loop_watch(self):
        if self.movie is None:
            self._clear_active_gif_loop_watch()
            return
        self._clear_active_gif_loop_watch()
        self._gif_loop_watch_active = True
        try:
            loop_count = int(self.movie.loopCount())
        except Exception:
            loop_count = -1
        # Finite-loop GIFs should advance only when playback actually finishes.
        self._gif_wait_for_finished_only = (loop_count != -1)
        try:
            self._gif_loop_last_frame = int(self.movie.currentFrameNumber())
        except Exception:
            self._gif_loop_last_frame = -1
        self._gif_loop_min_deadline = float(time.monotonic()) + (max(1, int(self.interval_ms)) / 1000.0)
        try:
            if not self._gif_wait_for_finished_only:
                self.movie.frameChanged.connect(self._on_active_gif_frame_changed)
        except Exception:
            pass
        try:
            self.movie.finished.connect(self._on_active_gif_finished)
        except Exception:
            pass
        # Safety fallback: prevent getting stuck forever if frame signals stop unexpectedly.
        try:
            # Use a generous watchdog so long GIFs are not cut early.
            fallback_ms = max(300000, int(self.interval_ms) * 12)
        except Exception:
            fallback_ms = 300000
        if hasattr(self, "_gif_loop_fallback_timer"):
            self._gif_loop_fallback_timer.start(int(fallback_ms))

    def _on_active_gif_frame_changed(self, frame_number):
        if not bool(getattr(self, "_gif_loop_watch_active", False)):
            return
        if bool(getattr(self, "_gif_wait_for_finished_only", False)):
            return
        if self.movie is None or self.stack.currentIndex() != 1:
            self._clear_active_gif_loop_watch()
            return
        sender_obj = self.sender()
        if sender_obj is not self.movie:
            return
        try:
            frame_idx = int(frame_number)
        except Exception:
            frame_idx = -1
        last = int(getattr(self, "_gif_loop_last_frame", -1))
        if last > 0 and frame_idx == 0:
            now = float(time.monotonic())
            if now >= float(getattr(self, "_gif_loop_min_deadline", 0.0)):
                self._clear_active_gif_loop_watch()
                self._schedule_next_media()
                return
        self._gif_loop_last_frame = int(frame_idx)

    def _on_active_gif_finished(self):
        if self.movie is None or self.stack.currentIndex() != 1:
            return
        sender_obj = self.sender()
        if sender_obj is not self.movie:
            return
        if self.timer.isActive():
            self.timer.stop()
        now = float(time.monotonic())
        deadline = float(getattr(self, "_gif_loop_min_deadline", 0.0))
        self._clear_active_gif_loop_watch()
        if now >= deadline:
            self._schedule_next_media()
            return
        remain_ms = max(1, int(round((deadline - now) * 1000.0)))
        active_movie = self.movie
        QTimer.singleShot(
            int(remain_ms),
            lambda m=active_movie: (
                self._schedule_next_media()
                if (self.movie is m and self.stack.currentIndex() == 1)
                else None
            ),
        )

    def _on_gif_loop_fallback_timeout(self):
        if not bool(getattr(self, "_gif_loop_watch_active", False)):
            return
        if bool(getattr(self, "_performance_paused", False)):
            if hasattr(self, "_gif_loop_fallback_timer"):
                self._gif_loop_fallback_timer.start(max(5000, int(self.interval_ms)))
            return
        self._clear_active_gif_loop_watch()
        self._schedule_next_media()

    def _apply_media_scale_mode(self):
        self._update_video_aspect_mode()
        if self.movie:
            try:
                # Keep GIF behavior aligned with legacy logic to avoid resize-time artifacts.
                self.movie.setScaledSize(self.size())
            except Exception:
                pass
            return
        if self.current_static_pixmap and not self.current_static_pixmap.isNull():
            self._update_static_pixmap_size()

    def _cancel_pending_gif_swap(self):
        if hasattr(self, "_gif_swap_timeout") and self._gif_swap_timeout.isActive():
            self._gif_swap_timeout.stop()
        pending = getattr(self, "_gif_swap_pending_movie", None)
        self._gif_swap_pending_movie = None
        self._gif_swap_pending_path = ""
        self._gif_swap_pending_duration_ms = 0
        if pending is None:
            return
        try:
            pending.frameChanged.disconnect(self._on_gif_swap_frame_changed)
        except Exception:
            pass
        try:
            pending.stop()
        except Exception:
            pass
        try:
            pending.deleteLater()
        except Exception:
            pass

    def _schedule_gif_swap(self, path):
        self._cancel_pending_gif_swap()
        movie = QMovie(path)
        if not movie.isValid():
            try:
                movie.deleteLater()
            except Exception:
                pass
            return False
        self._gif_swap_pending_movie = movie
        self._gif_swap_pending_path = str(path)
        self._gif_swap_pending_duration_ms = 0
        movie.frameChanged.connect(self._on_gif_swap_frame_changed)
        movie.start()
        try:
            first_ready = bool(movie.jumpToFrame(0))
        except Exception:
            first_ready = False
        if first_ready:
            try:
                movie.setPaused(True)
            except Exception:
                pass
            self._update_movie_scaled_size_for(movie)
            self._gif_swap_pending_duration_ms = int(self._estimate_gif_duration_ms(movie))
            QTimer.singleShot(0, self._complete_gif_swap)
            return True
        if hasattr(self, "_gif_swap_timeout"):
            self._gif_swap_timeout.start()
        return True

    def _start_gif_direct(self, path):
        movie = QMovie(path)
        if not movie.isValid():
            try:
                movie.deleteLater()
            except Exception:
                pass
            return False
        self.movie = movie
        self.stack.setCurrentIndex(1)
        self.img_label.setUpdatesEnabled(False)
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setMovie(self.movie)
        try:
            self.movie.jumpToFrame(0)
        except Exception:
            pass
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setUpdatesEnabled(True)
        self.movie.start()
        if self.movie.state() != QMovie.MovieState.Running:
            self.movie.start()
        gif_total_duration = int(self._estimate_gif_duration_ms(self.movie))
        try:
            loop_count = int(self.movie.loopCount())
        except Exception:
            loop_count = -1
        if loop_count == 1:
            wait_time = max(self.interval_ms, gif_total_duration) if gif_total_duration > 0 else self.interval_ms
            self.timer.start(wait_time)
            self._clear_active_gif_loop_watch()
        else:
            self._start_active_gif_loop_watch()
        if self._performance_paused:
            self.set_performance_paused(True, reason="guard_active", force=True)
        return True

    def _complete_gif_swap(self):
        pending = getattr(self, "_gif_swap_pending_movie", None)
        if pending is None:
            return False
        if hasattr(self, "_gif_swap_timeout") and self._gif_swap_timeout.isActive():
            self._gif_swap_timeout.stop()
        try:
            pending.frameChanged.disconnect(self._on_gif_swap_frame_changed)
        except Exception:
            pass
        self._gif_swap_pending_movie = None
        self._gif_swap_pending_path = ""
        pending_duration = int(getattr(self, "_gif_swap_pending_duration_ms", 0) or 0)
        self._gif_swap_pending_duration_ms = 0
        self.movie = pending
        self.stack.setCurrentIndex(1)
        self.img_label.setUpdatesEnabled(False)
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setMovie(self.movie)
        try:
            self.movie.jumpToFrame(0)
        except Exception:
            pass
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setUpdatesEnabled(True)
        try:
            self.movie.setPaused(False)
        except Exception:
            pass
        if self.movie.state() != QMovie.MovieState.Running:
            self.movie.start()
        gif_total_duration = int(pending_duration)
        if gif_total_duration <= 0:
            gif_total_duration = int(self._estimate_gif_duration_ms(self.movie))
        try:
            loop_count = int(self.movie.loopCount())
        except Exception:
            loop_count = -1
        if loop_count == 1:
            wait_time = max(self.interval_ms, gif_total_duration) if gif_total_duration > 0 else self.interval_ms
            self.timer.start(wait_time)
            self._clear_active_gif_loop_watch()
        else:
            self._start_active_gif_loop_watch()
        self._refresh_icon_overlay_for_current_media()
        if self._performance_paused:
            self.set_performance_paused(True, reason="guard_active", force=True)
        return True

    def _on_gif_swap_frame_changed(self, frame_number):
        if int(frame_number) < 0:
            return
        pending = getattr(self, "_gif_swap_pending_movie", None)
        if pending is None:
            return
        sender_obj = self.sender()
        if sender_obj is not pending:
            return
        try:
            pending.setPaused(True)
        except Exception:
            pass
        self._update_movie_scaled_size_for(pending)
        self._gif_swap_pending_duration_ms = int(self._estimate_gif_duration_ms(pending))
        self._complete_gif_swap()

    def _on_gif_swap_timeout(self):
        pending = getattr(self, "_gif_swap_pending_movie", None)
        if pending is None:
            return
        fallback_path = str(getattr(self, "_gif_swap_pending_path", "") or "")
        if int(pending.currentFrameNumber()) >= 0:
            self._complete_gif_swap()
            return
        self._cancel_pending_gif_swap()
        if fallback_path and str(getattr(self, "current_media_path", "")) == fallback_path:
            if self._start_gif_direct(fallback_path):
                self._refresh_icon_overlay_for_current_media()
                return
        self._skip_current_media("gif_preload_timeout")

    def prepare_media_before_show(self):
        """Prime first media frame while hidden so opening doesn't pop from small->large."""
        if bool(getattr(self, "_initial_media_prepared", False)):
            self._apply_media_scale_mode()
            return
        pending = bool(getattr(self, "_initial_media_pending", False))
        if not pending:
            self._apply_media_scale_mode()
            self._initial_media_prepared = True
            return

        self._initial_media_pending = False
        if not self.folder_path:
            self._initial_media_prepared = True
            return
        if not self.playlist:
            self.update_playlist()
        if not self.playlist:
            self._initial_media_prepared = True
            return
        if not self.current_media_path:
            self.current_idx = -1
            self.next_media()
        else:
            self._apply_media_scale_mode()
        self._initial_media_prepared = True

    def is_visible_on_any_screen(self):
        for screen in QGuiApplication.screens():
            if screen.geometry().intersects(self.geometry()):
                return True
        return False

    def _move_exact(self, target):
        if isinstance(target, QPoint):
            x, y = target.x(), target.y()
        else:
            x, y = target

        try:
            hwnd = int(self.winId())
            win32gui.SetWindowPos(
                hwnd,
                0,
                int(x),
                int(y),
                0,
                0,
                win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            )
            # Keep Qt geometry in sync with native move result.
            self.move(int(x), int(y))
        except Exception:
            self.move(int(x), int(y))

    def _global_top_left(self):
        try:
            gp = self.mapToGlobal(QPoint(0, 0))
            if isinstance(gp, QPoint):
                return QPoint(int(gp.x()), int(gp.y()))
        except Exception:
            pass
        try:
            hwnd = int(self.winId())
            left, top, _right, _bottom = win32gui.GetWindowRect(hwnd)
            return QPoint(int(left), int(top))
        except Exception:
            return QPoint(int(self.x()), int(self.y()))

    def apply_mask_and_style(self):
        radius = 0 if int(getattr(self, "corner_mode", 0)) == 1 else 20

        bg_options = ["transparent", "black", "white"]
        bg_idx = max(0, min(int(self.bg_color_mode), len(bg_options) - 1))
        bg = bg_options[bg_idx]
        

        self.container.setStyleSheet(f"QWidget#mainContainer {{ background-color: {bg}; border-radius: {radius}px; }}")
        if hasattr(self, "placeholder"):
            self.placeholder.setStyleSheet(f"background: #222; border-radius: {radius}px;")
     

        self._sync_desktop_icon_mask_timer()
        clone_icons = self._should_clone_desktop_icons()
        if clone_icons:
            self._refresh_desktop_icon_clone_overlay(force=False)
        else:
            self._set_clone_overlay_items([])

        if hasattr(self, "desktop_icon_clone_overlay") and self.desktop_icon_clone_overlay.isVisible():
            self.desktop_icon_clone_overlay.raise_()
        if hasattr(self, 'selection_overlay'):
            self.selection_overlay.raise_()
        if hasattr(self, 'resize_overlay'):
            self.resize_overlay.raise_()
        if hasattr(self, 'size_hud') and self.size_hud.isVisible():
            self.size_hud.raise_()
        if hasattr(self, 'action_hud') and self.action_hud.isVisible():
            self.action_hud.raise_()
        if hasattr(self, "group_badge") and self.group_badge.isVisible():
            self.group_badge.raise_()

        punch_icons = self._should_punch_desktop_icons()
        mask_region = None
        if radius > 0:
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), radius, radius)
            mask_region = QRegion(path.toFillPolygon().toPolygon())
        elif punch_icons:
            mask_region = QRegion(self.rect())

        if punch_icons and mask_region is not None:
            local_holes = self._desktop_icon_hole_rects_local(force=False)
            if not local_holes:
                local_holes = self._desktop_icon_hole_rects_local(force=True)
            for hole in local_holes:
                if not isinstance(hole, dict):
                    continue
                label_region = hole.get("label_region")
                if isinstance(label_region, QRegion) and not label_region.isEmpty():
                    mask_region = mask_region.subtracted(label_region)
                icon_region = hole.get("icon_region")
                if isinstance(icon_region, QRegion) and not icon_region.isEmpty():
                    mask_region = mask_region.subtracted(icon_region)

        if mask_region is not None:
            self.setMask(mask_region)
        else:
            self.clearMask()

    def update_playlist(self):
        if not os.path.exists(self.folder_path):
            # Prevent stale media list when folder path is invalid/missing.
            self.playlist = []
            return
        ext = ('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.avi', '.mov', '.ico', '.jfif', '.webp')
        try:
            files = os.listdir(self.folder_path)
        except OSError:
            self.playlist = []
            return
        candidates = sorted([os.path.join(self.folder_path, f) for f in files if f.lower().endswith(ext)])
        if not candidates:
            self.playlist = []
            return

        filtered = [p for p in candidates if p not in self.quarantined_media]
        if filtered:
            self.playlist = filtered
            return

        # If everything got quarantined, recover gracefully instead of showing an empty widget forever.
        self.quarantined_media.clear()
        self._save_quarantined_media()
        self.playlist = candidates

    def _set_watched_folder(self, folder_path):
        old_dirs = self.folder_watcher.directories()
        if old_dirs:
            self.folder_watcher.removePaths(old_dirs)
        if folder_path and os.path.isdir(folder_path):
            self.folder_watcher.addPath(folder_path)

    def _on_folder_changed_signal(self, _path):
        self.folder_refresh_timer.start()

    def _refresh_playlist_from_folder_change(self):
        if not self.folder_path:
            return

        prev_playlist = list(self.playlist)
        current_path = None
        if 0 <= self.current_idx < len(self.playlist):
            current_path = self.playlist[self.current_idx]

        self.update_playlist()
        self._set_watched_folder(self.folder_path)

        if not self.playlist:
            if self.stack.currentIndex() != 0:
                self.current_idx = -1
                self.next_media()
            return

        if current_path and current_path in self.playlist:
            self.current_idx = self.playlist.index(current_path)
            return

        if prev_playlist != self.playlist:
            next_hint = 0
            if current_path and current_path in prev_playlist:
                removed_index = prev_playlist.index(current_path)
                next_hint = min(removed_index, len(self.playlist) - 1)
            elif self.current_idx >= 0:
                next_hint = min(self.current_idx, len(self.playlist) - 1)

            self.current_idx = next_hint - 1
            self.next_media()

    def open_settings(self):
        old_folder = self.folder_path
        

        current_data = {
            'w': self.width(), 'h': self.height(),
            'is_muted': self.is_muted,
            'gpu_guard_enabled': self.gpu_guard_enabled,
            'folder_path': self.folder_path,
            'exec_path': self.exec_path,
            'interval': self.interval_ms // 1000,
            'bg_color_mode': self.bg_color_mode,
            'corner_mode': getattr(self, 'corner_mode', 0),
            'media_fit_mode': int(getattr(self, "media_fit_mode", 0)),
            'opacity_pct': self.current_opacity_pct,
            'layer_mode': getattr(self, 'layer_mode', self.LAYER_NORMAL),
            'layer_schema_version': int(self.LAYER_SCHEMA_VERSION),
            'is_locked': getattr(self, 'is_locked', False)
        }
        

        dialog = SettingsDialog(self, current_data)
        
        if dialog.exec():
            self.resize(dialog.width_input.value(), dialog.height_input.value())
            self.is_muted = dialog.mute_checkbox.isChecked()
            self._apply_mute_state()
            self.gpu_guard_enabled = dialog.gpu_guard_checkbox.isChecked()
            self.exec_path = dialog.exec_path
            self.folder_path = dialog.folder_path
            self._set_watched_folder(self.folder_path)
            self.interval_ms = dialog.sec_input.value() * 1000
            self.bg_color_mode = dialog.bg_combo.currentIndex()
            self.corner_mode = dialog.corner_combo.currentIndex()
            self.media_fit_mode = int(dialog.media_mode_combo.currentIndex())
            

            self.apply_window_settings(dialog.layer_combo.currentIndex(), dialog.lock_cb.isChecked())
            self.apply_mask_and_style()
            
            if old_folder != self.folder_path:
                self.update_playlist(); self.current_idx = -1; self.next_media()
            else:
                self._apply_media_scale_mode()

            self.current_opacity_pct = dialog.opacity_slider.value()
            self.setWindowOpacity(self.current_opacity_pct / 100.0)
            if not self.gpu_guard_enabled:
                self.set_performance_paused(False, reason="guard_disabled")
            self.save_all_settings()
        else:
             self.setWindowOpacity(self.current_opacity_pct / 100.0)

    def apply_window_settings(self, layer, lock, cancel_interaction=True):
        # Prevent stale drag/resize state from leaking across lock toggles.
        if bool(cancel_interaction) and hasattr(self, "cancel_active_interaction"):
            self.cancel_active_interaction()
        layer = self.coerce_layer_mode(layer, self.LAYER_SCHEMA_VERSION)
        self.layer_mode = layer
        self.is_locked = lock
        was_visible = self.isVisible()
        current_pos = self._global_top_left()
        current_size = self.size()

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if int(layer) == int(self.LAYER_BACK):
            flags |= Qt.WindowType.WindowStaysOnBottomHint
        elif int(layer) == int(self.LAYER_TOPMOST):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if lock:
            flags |= Qt.WindowType.WindowTransparentForInput

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if was_visible:
            self.show()
        self.resize(current_size)
        self._move_exact(current_pos)
        self.setWindowOpacity(float(self.current_opacity_pct) / 100.0)
        self.apply_mask_and_style()
        self._schedule_desktop_icon_overlay_bootstrap(retries=3, delay_ms=60)
        self._refresh_resize_ui()
        self._refresh_group_badge()

    def show_selection(self, state):
            if state:
                self.selection_overlay.setGeometry(self.rect())
                self.selection_overlay.show()
                self.selection_overlay.raise_()
                if hasattr(self, "resize_overlay") and self.resize_overlay.isVisible():
                    self.resize_overlay.raise_()
            else:
                self.selection_overlay.hide()

    def save_all_settings(self):
        self.settings.setValue("folder_path", self.folder_path)
        self.settings.setValue("exec_path", self.exec_path)
        self.settings.setValue("interval", self.interval_ms // 1000)
        self.settings.setValue("bg_color_mode", self.bg_color_mode)
        self.settings.setValue("corner_mode", int(getattr(self, "corner_mode", 0)))
        self.settings.setValue("media_fit_mode", int(getattr(self, "media_fit_mode", 0)))
        self.settings.setValue("is_muted", bool(self.is_muted))
        self.settings.setValue("gpu_guard_enabled", bool(self.gpu_guard_enabled))
        self.settings.setValue("layer_mode", int(getattr(self, "layer_mode", self.LAYER_NORMAL)))
        self.settings.setValue("layer_schema_version", int(self.LAYER_SCHEMA_VERSION))
        self.settings.setValue("is_locked", bool(getattr(self, "is_locked", False)))
        self.settings.setValue("opacity_pct", self.current_opacity_pct)
        self.settings.setValue("w", self.width())
        self.settings.setValue("h", self.height())
        
        self.settings.setValue("pos", self._global_top_left())
        self.settings.setValue("size", self.size())
        self._save_position_metadata()
        self._save_quarantined_media()
        
        self.settings.sync()

    def preview_opacity(self, val_pct):
        self.setWindowOpacity(val_pct / 100.0)

    def next_media(self):
        # 1. existing timer/playback stop to avoid overlap
        self._media_resetting = True
        self.timer.stop()
        self._clear_active_gif_loop_watch()
        self._cancel_pending_gif_swap()
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        self.media_player.setSource(QUrl())  # release previous media source

        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        self.current_static_pixmap = None
        self.current_media_path = None
        self._media_resetting = False

        if not self.playlist:
            self.stack.setCurrentIndex(0)
            self._refresh_icon_overlay_for_current_media()
            return

        attempts = len(self.playlist)
        while attempts > 0 and self.playlist:
            # 2. advance index
            self.current_idx = (self.current_idx + 1) % len(self.playlist)
            path = self.playlist[self.current_idx]
            self.current_media_path = path

            # 3. branch by extension
            if self._is_video_path(path):
                self.stack.setCurrentIndex(2)
                self._update_video_aspect_mode()
                self.media_player.setSource(QUrl.fromLocalFile(path))
                self._apply_mute_state()
                self.media_player.play()
                self._refresh_icon_overlay_for_current_media()
                if self._performance_paused:
                    self.set_performance_paused(True, reason="guard_active", force=True)
                return

            if path.lower().endswith('.gif'):
                self.stack.setCurrentIndex(1)
                self.movie = QMovie(path)
                if not self.movie.isValid():
                    self.movie.deleteLater()
                    self.movie = None
                    self._record_media_failure(path, "invalid_gif")
                    if path in self.quarantined_media:
                        self.playlist.pop(self.current_idx)
                        self.current_idx -= 1
                    attempts -= 1
                    continue

                try:
                    self.movie.setScaledSize(self.size())
                except Exception:
                    pass
                self.img_label.setMovie(self.movie)
                self.movie.start()
                try:
                    self.movie.jumpToFrame(0)
                except Exception:
                    pass
                self._start_active_gif_loop_watch()
                self._refresh_icon_overlay_for_current_media()
                if self._performance_paused:
                    self.set_performance_paused(True, reason="guard_active", force=True)
                return

            self.stack.setCurrentIndex(1)
            pix = QPixmap(path)
            if pix.isNull():
                self._record_media_failure(path, "invalid_image")
                if path in self.quarantined_media:
                    self.playlist.pop(self.current_idx)
                    self.current_idx -= 1
                attempts -= 1
                continue

            self.current_static_pixmap = pix
            self._update_static_pixmap_size()
            self.timer.start(self.interval_ms)
            self._refresh_icon_overlay_for_current_media()
            return

        self.current_media_path = None
        self.stack.setCurrentIndex(0)
        self._refresh_icon_overlay_for_current_media()

    def _update_static_pixmap_size(self):
        if self.current_static_pixmap and not self.current_static_pixmap.isNull():
            target = self._safe_target_size(getattr(self, "img_label", None), self.size())
            fill_mode = self._is_media_fill_mode()
            expand_mode = getattr(
                Qt.AspectRatioMode,
                "KeepAspectRatioByExpanding",
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            if fill_mode:
                scaled = self.current_static_pixmap.scaled(
                    target,
                    expand_mode,
                    Qt.TransformationMode.SmoothTransformation
                )
                if int(scaled.width()) > int(target.width()) or int(scaled.height()) > int(target.height()):
                    cut_w = min(int(target.width()), int(scaled.width()))
                    cut_h = min(int(target.height()), int(scaled.height()))
                    cut_x = max(0, (int(scaled.width()) - int(cut_w)) // 2)
                    cut_y = max(0, (int(scaled.height()) - int(cut_h)) // 2)
                    scaled = scaled.copy(int(cut_x), int(cut_y), int(cut_w), int(cut_h))
            else:
                scaled = self.current_static_pixmap.scaled(
                    target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            self.img_label.setPixmap(
                scaled
            )

    def check_video_status(self, s):
        if self._media_resetting:
            return
        if s in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            self._apply_mute_state()
            return
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_media()
            return
        if s == QMediaPlayer.MediaStatus.InvalidMedia:
            self._skip_current_media("invalid_video_status")

    def _on_video_error(self, error, error_string):
        if self._media_resetting:
            return
        if error == QMediaPlayer.Error.NoError:
            return
        reason = error_string if error_string else str(error)
        self._skip_current_media(f"video_error:{reason}")


    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if bool(getattr(self, "is_locked", False)):
                self.cancel_active_interaction()
                return
            self._reset_axis_snap()
            local_pos = e.position().toPoint() if hasattr(e, "position") else self.mapFromGlobal(e.globalPosition().toPoint())
            if self._is_shift_down() and not getattr(self, "is_locked", False):
                corner = self._corner_hit_test(local_pos)
                if corner:
                    self.is_resizing = True
                    self.resize_corner = corner
                    self.resize_start_pos = e.globalPosition().toPoint()
                    self.resize_start_geo = self.geometry()
                    self.start_pos = None
                    self.is_moving = False
                    self._set_resize_cursor(corner)
                    self._show_size_hud()
                    self._refresh_resize_ui()
                    return
            self.start_pos = e.globalPosition().toPoint()
            self.is_moving = False

    def mouseMoveEvent(self, e):
        if bool(getattr(self, "is_locked", False)):
            if self.start_pos or self.is_moving or self.is_resizing:
                self.cancel_active_interaction()
            else:
                self._refresh_resize_ui()
            return
        if self.is_resizing:
            self._apply_corner_resize(e.globalPosition().toPoint())
            self._show_size_hud()
            return

        self._refresh_resize_ui()
        if self.start_pos:
            current_global = e.globalPosition().toPoint()
            delta = current_global - self.start_pos
            if delta.manhattanLength() > self._drag_threshold:
                if not self.is_moving:
                    self._set_drag_topmost(True)
                self.is_moving = True
                prev_x = self.x()
                prev_y = self.y()
                raw_x = self.x() + delta.x()
                raw_y = self.y() + delta.y()
                snap_x = self._apply_axis_snap("x", raw_x, current_global.x())
                snap_y = self._apply_axis_snap("y", raw_y, current_global.y())
                self._move_exact((snap_x, snap_y))
                moved_dx = self.x() - prev_x
                moved_dy = self.y() - prev_y
                if moved_dx or moved_dy:
                    if hasattr(self, "manager") and self.manager and hasattr(self.manager, "move_temp_group_by_delta"):
                        self.manager.move_temp_group_by_delta(self.profile_id, moved_dx, moved_dy)
                self._show_size_hud()
                self.start_pos = current_global

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if bool(getattr(self, "is_locked", False)):
                self.cancel_active_interaction()
                return
            if self.is_resizing:
                self.is_resizing = False
                self.resize_corner = None
                self.resize_start_pos = None
                self._reset_axis_snap()
                self.save_all_settings()
                if hasattr(self, "manager") and self.manager and hasattr(self.manager, "save_temp_group_positions"):
                    self.manager.save_temp_group_positions(self.profile_id)
                self._hide_size_hud()
                self._refresh_resize_ui()
                return
            if getattr(self, 'is_moving', False):
                self.save_all_settings()
                if hasattr(self, "manager") and self.manager and hasattr(self.manager, "save_temp_group_positions"):
                    self.manager.save_temp_group_positions(self.profile_id)
                self._hide_size_hud()
            else:
                if not self.exec_path or not os.path.exists(self.exec_path):
                    print("Executable is not configured or missing.")
                    self.start_pos = None
                    self.is_moving = False
                    self._set_drag_topmost(False)
                    self._reset_axis_snap()
                    self._hide_size_hud()
                    self._refresh_resize_ui()
                    return
                os.startfile(self.exec_path)
        self._set_drag_topmost(False)
        self.start_pos = None
        self.is_moving = False
        self._reset_axis_snap()
        self._hide_size_hud()
        self._refresh_resize_ui()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            wheel_delta = e.angleDelta().y()
            steps = int(wheel_delta / 120) if wheel_delta else 0
            if steps == 0 and wheel_delta != 0:
                steps = 1 if wheel_delta > 0 else -1
            if steps != 0:
                if hasattr(self, "manager") and self.manager and hasattr(self.manager, "adjust_temp_group_opacity"):
                    self.manager.adjust_temp_group_opacity(self.profile_id, steps * 5)
                else:
                    new_opacity = max(10, min(100, self.current_opacity_pct + (steps * 5)))
                    if new_opacity != self.current_opacity_pct:
                        self.current_opacity_pct = new_opacity
                        self.setWindowOpacity(self.current_opacity_pct / 100.0)
                        self.save_all_settings()
            return

        if not self.playlist:
            return

        if e.angleDelta().y() > 0:
            self.current_idx = (self.current_idx - 2) % len(self.playlist)

        self.next_media()

    def dragEnterEvent(self, event):
        path = self._extract_first_local_drop_path(event)
        if path and (os.path.isdir(path) or os.path.isfile(path)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        path = self._extract_first_local_drop_path(event)
        if path and (os.path.isdir(path) or os.path.isfile(path)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        path = self._extract_first_local_drop_path(event)
        if self._apply_drop_target(path):
            event.acceptProposedAction()
        else:
            event.ignore()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #333; color: white; border: 1px solid #555; } QMenu::item:selected { background-color: #555; }")
        action_settings = menu.addAction("위젯 설정")
        action_settings.triggered.connect(self.open_settings)
        action_master = menu.addAction("위젯 컨트롤러")
        action_master.triggered.connect(self.open_master_controller)
        menu.exec(e.globalPos())

    def open_master_controller(self):
        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "show_master_window"):
            self.manager.show_master_window()

    def showEvent(self, e):
        if not bool(getattr(self, "_initial_media_prepared", False)):
            self.prepare_media_before_show()
        super().showEvent(e)
        if self._should_clone_desktop_icons() or self._should_punch_desktop_icons():
            self.apply_mask_and_style()
            self._schedule_desktop_icon_overlay_bootstrap(retries=4, delay_ms=60)

    def resizeEvent(self, e):
        if hasattr(self, "desktop_icon_clone_overlay"):
            self.desktop_icon_clone_overlay.setGeometry(self.rect())
            if self.desktop_icon_clone_overlay.isVisible():
                self.desktop_icon_clone_overlay.raise_()
        if hasattr(self, 'selection_overlay'):
            self.selection_overlay.setGeometry(self.rect())
            self.selection_overlay.raise_()
        if hasattr(self, 'resize_overlay'):
            self.resize_overlay.setGeometry(self.rect())
            if self.resize_overlay.isVisible():
                self.resize_overlay.raise_()
        if hasattr(self, "group_badge"):
            self._place_group_badge()
            if self.group_badge.isVisible():
                self.group_badge.raise_()
        if hasattr(self, 'size_hud') and self.size_hud.isVisible():
            self._refresh_size_hud()
        if hasattr(self, "action_hud") and self.action_hud.isVisible():
            self._refresh_action_hud()

        self._apply_media_scale_mode()

        self.apply_mask_and_style()
        self._refresh_resize_ui()
        self._refresh_group_badge()
        super().resizeEvent(e)

    def moveEvent(self, e):
        if self._should_clone_desktop_icons() or self._should_punch_desktop_icons():
            self.apply_mask_and_style()
        super().moveEvent(e)

    def closeEvent(self, event):
        self.timer.stop()
        self._clear_active_gif_loop_watch()
        self._cancel_pending_gif_swap()
        

        self.media_player.stop()
        self.media_player.setSource(QUrl())
        

        self.media_player.deleteLater()
        self.audio_output.deleteLater()
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()

        if hasattr(self, "folder_refresh_timer"):
            self.folder_refresh_timer.stop()
        if hasattr(self, "folder_watcher"):
            old_dirs = self.folder_watcher.directories()
            if old_dirs:
                self.folder_watcher.removePaths(old_dirs)
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        if hasattr(self, "_desktop_icon_mask_timer") and self._desktop_icon_mask_timer.isActive():
            self._desktop_icon_mask_timer.stop()
        if hasattr(self, "_desktop_icon_bootstrap_timer") and self._desktop_icon_bootstrap_timer.isActive():
            self._desktop_icon_bootstrap_timer.stop()
        self._set_clone_overlay_items([])
             
        self.save_all_settings()
        super().closeEvent(event)


class MasterController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("위젯 컨트롤러")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_candidates = [
            "icon.ico",
            "MyWidgetBox.ico",
            os.path.join(script_dir, "icon.ico"),
            os.path.join(script_dir, "MyWidgetBox.ico"),
        ]
        icon_path = next((p for p in icon_candidates if os.path.exists(p)), "")
        if icon_path:
            self.app_icon = QIcon(icon_path)
        else:
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.green)
            self.app_icon = QIcon(pixmap)

        self.setWindowIcon(QIcon())
        self.setFixedSize(476, 680)
        self.setObjectName("masterWindow")
        self.master_settings = QSettings("MyHomeApp", "MasterV3")
        self.widgets = {}
        self._temp_group_ids = set()
        self.profile_rows = {}
        self._startup_queue = []
        self._startup_queue_active = False
        self._startup_queue_timer = QTimer(self)
        self._startup_queue_timer.setSingleShot(True)
        self._startup_queue_timer.timeout.connect(self._run_next_startup_item)


        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        tray_menu = QMenu()
        tray_menu.addAction("관리자 열기", self.show_master_window); tray_menu.addSeparator(); tray_menu.addAction("전체 종료", self.quit_app)
        self.tray_icon.setContextMenu(tray_menu); self.tray_icon.show()

        self.setStyleSheet("""
            QMainWindow#masterWindow {
                background-color: #1b2a3f;
            }
            QWidget#masterRoot {
                background-color: #24354e;
            }
            QFrame#titleBar {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QLabel#titleLabel {
                color: #f5f7ff;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: #d0dcf2;
                font-size: 11px;
            }
            QLabel#groupHeaderLabel {
                color: #b8c8e6;
                font-size: 11px;
                font-weight: 700;
                padding: 8px 2px 4px 2px;
            }
            QLabel#gpuCfgLabel {
                color: #d6e2f7;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#gpuCfgValue {
                color: #edf3ff;
                font-size: 12px;
                font-weight: 700;
            }
            QToolButton#gpuCfgBtn {
                min-width: 50px;
                min-height: 26px;
                color: #eef3ff;
                background-color: #2f466d;
                border: 1px solid #5478ae;
                border-radius: 8px;
                padding: 0 10px;
            }
            QToolButton#gpuCfgBtn:hover {
                background-color: #3b5988;
            }
            QToolButton#gpuCfgBtn:checked {
                background-color: #476ca6;
            }
            QToolButton#setMgrBtn {
                min-width: 72px;
                min-height: 26px;
                color: #eef3ff;
                background-color: #2f466d;
                border: 1px solid #5478ae;
                border-radius: 8px;
                padding: 0 10px;
            }
            QToolButton#setMgrBtn:hover {
                background-color: #3b5988;
            }
            QFrame#gpuCfgPopup {
                background-color: #263b5a;
                border: 1px solid #4c6997;
                border-radius: 10px;
            }
            QFrame#setSidebar {
                background-color: rgba(23, 35, 54, 205);
                border: 1px solid #3f587e;
                border-radius: 12px;
            }
            QPushButton#addSetBtn,
            QPushButton#addWidgetBtn {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 15px;
                color: #eef3ff;
                background-color: #2f4569;
                border: 1px solid #5878a6;
                font-size: 14px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton#addSetBtn:hover,
            QPushButton#addWidgetBtn:hover {
                background-color: #3a5885;
            }
            QPushButton[kind="setIndexBtn"] {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                border-radius: 15px;
                color: #e5edff;
                background-color: #2f4569;
                border: 1px solid #5878a6;
                font-size: 12px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton[kind="setIndexBtn"][selected="true"] {
                background-color: #4a74e2;
                border: 1px solid #7fa0f0;
                color: #ffffff;
            }
            QPushButton[kind="setIndexBtn"]:hover {
                background-color: #3a5885;
            }
            QLabel#setNameTag {
                color: #e6efff;
                font-size: 12px;
                font-weight: 600;
                padding-left: 6px;
            }
            QLabel#setNewLabel {
                color: #d8e6ff;
                font-size: 12px;
                font-weight: 600;
                padding-left: 6px;
            }
            QLabel#addWidgetLabel {
                color: #d8e6ff;
                font-size: 12px;
                font-weight: 600;
                padding-left: 6px;
            }
            QSlider#gpuCfgSlider::groove:horizontal {
                height: 6px;
                border-radius: 3px;
                background: #4f6f9d;
            }
            QSlider#gpuCfgSlider::handle:horizontal {
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
                border: none;
                background: #82aff8;
            }
            QListWidget#profileList {
                background-color: rgba(24, 38, 60, 220);
                border: 1px solid #45618a;
                border-radius: 14px;
                padding: 6px 8px;
                outline: none;
            }
            QListWidget#profileList::item {
                border: none;
                padding: 0px;
            }
            QListWidget#profileList::item:selected {
                background-color: transparent;
            }
            QWidget#profileRow {
                background-color: transparent;
                border: none;
            }
            QWidget#addWidgetRow {
                background-color: transparent;
                border: none;
            }
            QWidget#profileRow[hovered="true"] {
                background-color: rgba(138, 173, 233, 40);
            }
            QWidget#profileRow[selected="true"] {
                background-color: rgba(150, 192, 255, 56);
            }
            QWidget#profileRow[running="true"][selected="true"] {
                background-color: rgba(119, 205, 178, 56);
            }
            QLabel#profileName {
                color: #edf2ff;
                font-size: 13px;
                font-weight: 600;
                padding: 0;
            }
            QLabel#statusDot {
                min-width: 10px;
                max-width: 10px;
                min-height: 10px;
                max-height: 10px;
                border-radius: 5px;
                background-color: #8d99ad;
            }
            QLabel#statusDot[running="true"] {
                background-color: #58c796;
            }
            QPushButton#primaryBtn,
            QPushButton#secondaryBtn,
            QPushButton#dangerBtn {
                min-height: 40px;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton#primaryBtn {
                color: #edf2ff;
                background-color: #406bdc;
                border: 1px solid #5f84e5;
            }
            QPushButton#primaryBtn:hover {
                background-color: #4a74e2;
            }
            QPushButton#primaryBtn:pressed {
                background-color: #365fc6;
            }
            QPushButton#secondaryBtn {
                color: #e5edf8;
                background-color: #283a54;
                border: 1px solid #3f5678;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #33486a;
            }
            QPushButton#secondaryBtn:pressed {
                background-color: #263a56;
            }
            QPushButton#secondaryBtn[pendingApply="true"] {
                color: #10251d;
                background-color: #58c796;
                border: 1px solid #7ad8af;
            }
            QPushButton#secondaryBtn[pendingApply="true"]:hover {
                background-color: #68d3a3;
            }
            QPushButton#secondaryBtn[pendingApply="true"]:pressed {
                background-color: #4cb487;
            }
            QPushButton#dangerBtn {
                color: #ffe8ec;
                background-color: #8f3741;
                border: 1px solid #b55460;
            }
            QPushButton#dangerBtn:hover {
                background-color: #a3434e;
            }
            QPushButton#dangerBtn:pressed {
                background-color: #7f2f39;
            }
            QPushButton[kind="rowAction"] {
                min-width: 28px;
                min-height: 28px;
                border-radius: 7px;
                font-size: 11px;
                font-weight: 600;
                color: #dbe4f6;
                background-color: transparent;
                border: none;
            }
            QPushButton[kind="rowAction"]:hover {
                background-color: #375074;
            }
            QPushButton[kind="rowAction"]:pressed {
                background-color: #21314b;
            }
            QPushButton#runBtn {
                border: none;
                color: #dbfff3;
            }
            QPushButton#runBtn:hover {
                background-color: #2b7d68;
            }
            QPushButton#stopBtn {
                border: none;
                color: #ffe9ef;
            }
            QPushButton#stopBtn:hover {
                background-color: #755b67;
            }
            QPushButton#deleteBtn {
                border: none;
                color: #ffe4e9;
            }
            QPushButton#deleteBtn:hover {
                background-color: #7b4a54;
            }
            QPushButton#setBtn {
                border: none;
                color: #e3edff;
            }
            QPushButton#setBtn:hover {
                background-color: #45638f;
            }
            QPushButton[kind="rowAction"]:disabled {
                background-color: #1b2639;
                border: none;
                color: #6f7f99;
            }
        """)

        central = QWidget()
        central.setObjectName("masterRoot")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_bar = QFrame()
        title_bar.setObjectName("titleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 6, 10, 6)
        title_bar_layout.setSpacing(8)
        title_left_layout = QVBoxLayout()
        title_left_layout.setContentsMargins(0, 0, 0, 0)
        title_left_layout.setSpacing(0)
        title_label = QLabel("위젯 컨트롤러")
        title_label.setObjectName("titleLabel")
        title_left_layout.addWidget(title_label)
        title_bar_layout.addLayout(title_left_layout, 1)

        self.gpu_cfg_toggle = QToolButton()
        self.gpu_cfg_toggle.setObjectName("gpuCfgBtn")
        self.gpu_cfg_toggle.setCheckable(True)
        self.gpu_cfg_toggle.setChecked(False)
        self.gpu_cfg_toggle.setText("GPU")
        self.gpu_cfg_toggle.toggled.connect(self._toggle_gpu_cfg_panel)
        self.set_mgr_btn = QToolButton()
        self.set_mgr_btn.setObjectName("setMgrBtn")
        self.set_mgr_btn.setText("세트 관리")
        self.set_mgr_btn.clicked.connect(self.open_set_manager)
        title_bar_layout.addWidget(self.set_mgr_btn, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        title_bar_layout.addWidget(self.gpu_cfg_toggle, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        layout.addWidget(title_bar)

        self.gpu_cfg_panel = QFrame(self)
        self.gpu_cfg_panel.setObjectName("gpuCfgPopup")
        self.gpu_cfg_panel.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.gpu_cfg_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        gpu_cfg_panel_layout = QVBoxLayout(self.gpu_cfg_panel)
        gpu_cfg_panel_layout.setContentsMargins(10, 8, 10, 10)
        gpu_cfg_panel_layout.setSpacing(6)

        gpu_pause_row = QHBoxLayout()
        gpu_pause_row.setContentsMargins(0, 0, 0, 0)
        gpu_pause_row.setSpacing(6)
        gpu_pause_lbl = QLabel("GPU 일시정지")
        gpu_pause_lbl.setObjectName("gpuCfgLabel")
        self.gpu_pause_value_lbl = QLabel("90%")
        self.gpu_pause_value_lbl.setObjectName("gpuCfgValue")
        gpu_pause_row.addWidget(gpu_pause_lbl)
        gpu_pause_row.addStretch()
        gpu_pause_row.addWidget(self.gpu_pause_value_lbl)
        gpu_cfg_panel_layout.addLayout(gpu_pause_row)

        self.gpu_pause_slider = QSlider(Qt.Orientation.Horizontal)
        self.gpu_pause_slider.setObjectName("gpuCfgSlider")
        self.gpu_pause_slider.setRange(1, 100)
        self.gpu_pause_slider.setSingleStep(1)
        gpu_cfg_panel_layout.addWidget(self.gpu_pause_slider)

        gpu_resume_row = QHBoxLayout()
        gpu_resume_row.setContentsMargins(0, 0, 0, 0)
        gpu_resume_row.setSpacing(6)
        gpu_resume_lbl = QLabel("GPU 재개")
        gpu_resume_lbl.setObjectName("gpuCfgLabel")
        self.gpu_resume_value_lbl = QLabel("70%")
        self.gpu_resume_value_lbl.setObjectName("gpuCfgValue")
        gpu_resume_row.addWidget(gpu_resume_lbl)
        gpu_resume_row.addStretch()
        gpu_resume_row.addWidget(self.gpu_resume_value_lbl)
        gpu_cfg_panel_layout.addLayout(gpu_resume_row)

        self.gpu_resume_slider = QSlider(Qt.Orientation.Horizontal)
        self.gpu_resume_slider.setObjectName("gpuCfgSlider")
        self.gpu_resume_slider.setRange(0, 99)
        self.gpu_resume_slider.setSingleStep(1)
        gpu_cfg_panel_layout.addWidget(self.gpu_resume_slider)
        self.gpu_cfg_panel.installEventFilter(self)

        content_row = QHBoxLayout()
        content_row.setSpacing(8)

        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.setSpacing(6)

        self.set_column_label = QLabel("위젯 세트")
        self.set_column_label.setObjectName("groupHeaderLabel")
        left_panel_layout.addWidget(self.set_column_label, 0)

        self.set_sidebar = QFrame()
        self.set_sidebar.setObjectName("setSidebar")
        self._set_sidebar_expanded_width = 182
        self._set_sidebar_collapsed_width = 56
        self._set_list_collapsed = _as_bool(self.master_settings.value("set_list_collapsed", False), False)
        self.set_sidebar.setFixedWidth(self._set_sidebar_collapsed_width if self._set_list_collapsed else self._set_sidebar_expanded_width)
        set_sidebar_layout = QVBoxLayout(self.set_sidebar)
        set_sidebar_layout.setContentsMargins(8, 8, 8, 8)
        set_sidebar_layout.setSpacing(6)

        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(6)

        self.add_set_btn = QPushButton("＋")
        self.add_set_btn.setObjectName("addSetBtn")
        self.add_set_btn.clicked.connect(self._on_add_set_clicked)
        self.add_set_label = QLabel("새로운 세트", top_row)
        self.add_set_label.setObjectName("setNewLabel")
        self.add_set_label.setVisible(not self._set_list_collapsed)

        top_row_layout.addWidget(self.add_set_btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top_row_layout.addWidget(self.add_set_label, 1, Qt.AlignmentFlag.AlignVCenter)
        set_sidebar_layout.addWidget(top_row, 0)

        self.set_list_container = QWidget()
        self.set_list_layout = QVBoxLayout(self.set_list_container)
        self.set_list_layout.setContentsMargins(0, 2, 0, 0)
        self.set_list_layout.setSpacing(4)
        set_sidebar_layout.addWidget(self.set_list_container, 1)
        left_panel_layout.addWidget(self.set_sidebar, 1)
        content_row.addWidget(left_panel, 0)

        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(6)

        self.profile_column_label = QLabel("위젯 리스트")
        self.profile_column_label.setObjectName("groupHeaderLabel")
        right_panel_layout.addWidget(self.profile_column_label, 0)

        self.list_widget = ProfileListWidget()
        self.list_widget.setObjectName("profileList")
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setSpacing(0)
        self.list_widget.setMouseTracking(True)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)
        right_panel_layout.addWidget(self.list_widget, 1)
        content_row.addWidget(right_panel, 1)
        layout.addLayout(content_row, 1)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        self.exit_btn = QPushButton("프로그램 종료 (Exit)")
        self.exit_btn.setObjectName("dangerBtn")
        self.exit_btn.clicked.connect(self.quit_app)
        self.run_all_btn = QPushButton("세트 적용")
        self.run_all_btn.setObjectName("secondaryBtn")
        btn_box.addWidget(self.exit_btn)
        btn_box.addWidget(self.run_all_btn)
        layout.addLayout(btn_box)

        self.run_all_btn.clicked.connect(self.run_all)
        self.list_widget.itemClicked.connect(self.highlight_widget)
        self.list_widget.itemDoubleClicked.connect(self.rename_profile)
        self.list_widget.itemEntered.connect(self._on_profile_item_entered)
        self.list_widget.orderChanged.connect(self._on_profile_order_changed)
        self.list_widget.viewport().installEventFilter(self)

        self._set_order = []
        self._set_defs = {}
        self._current_set_id = ""
        self._applied_set_id = ""
        self._load_set_state()
        self._migrate_profile_run_flags()
        self._refresh_set_ui()

        self.load_profiles()
        QTimer.singleShot(100, self.restore_last_session)
        app = QApplication.instance()
        if app:
            app.focusChanged.connect(self.handle_focus_change)
            app.installEventFilter(self)
        self._alt_click_pressed_prev = False
        self._alt_click_poll_timer = QTimer(self)
        self._alt_click_poll_timer.setInterval(25)
        self._alt_click_poll_timer.timeout.connect(self._poll_alt_click_toggle_lock)
        self._alt_click_poll_timer.start()
        self._gpu_sampler = GpuUsageSampler()
        self._gpu_guard_paused = False
        self._gpu_last_usage = 0.0
        self._gpu_high_streak = 0
        self._gpu_low_streak = 0
        self._gpu_below_high_streak = 0
        self._gpu_guard_high_pct = 90.0
        self._gpu_guard_low_pct = 70.0
        self._gpu_guard_high_hold = 2
        self._gpu_guard_low_hold = 3
        self._hovered_profile_pid = None
        self._apply_gpu_guard_thresholds(
            self.master_settings.value("gpu_guard_high_pct", 90),
            self.master_settings.value("gpu_guard_low_pct", 70),
            persist=False,
        )
        self._sync_gpu_threshold_inputs()
        self.gpu_pause_slider.valueChanged.connect(self._on_gpu_threshold_inputs_changed)
        self.gpu_resume_slider.valueChanged.connect(self._on_gpu_threshold_inputs_changed)
        self._gpu_guard_timer = QTimer(self)
        self._gpu_guard_timer.setInterval(1000)
        self._gpu_guard_timer.timeout.connect(self._poll_gpu_guard)
        self._gpu_guard_timer.start()
        QTimer.singleShot(0, self._apply_title_bar_theme)
        
    @staticmethod
    def _as_list(value):
        if isinstance(value, list):
            return [str(v) for v in value if str(v)]
        if value in (None, ""):
            return []
        return [str(value)]

    @staticmethod
    def _normalize_ids(values):
        out = []
        seen = set()
        for value in values:
            sid = str(value)
            if not sid or sid in seen:
                continue
            out.append(sid)
            seen.add(sid)
        return out

    def _set_key(self, set_id, field):
        return f"sets/{set_id}/{field}"

    def _all_profile_ids(self):
        return self._normalize_ids(self._as_list(self.master_settings.value("profile_ids", [])))

    def _next_profile_id(self, existing_ids=None):
        if existing_ids is None:
            existing_ids = self._all_profile_ids()
        max_id = 0
        for pid in existing_ids:
            try:
                max_id = max(max_id, int(str(pid)))
            except Exception:
                continue
        return str(max_id + 1)

    def _next_set_id(self):
        max_id = 0
        for sid in self._set_order:
            try:
                max_id = max(max_id, int(str(sid)))
            except Exception:
                continue
        return str(max_id + 1)

    def _default_set_name(self):
        used = {str(data.get("name", "")).strip() for data in self._set_defs.values()}
        idx = 1
        while True:
            candidate = f"세트{idx}"
            if candidate not in used:
                return candidate
            idx += 1

    def _profile_run_enabled(self, pid):
        spid = str(pid)
        raw = QSettings("MyHomeApp", f"Profile_{spid}").value("run_enabled", None)
        if raw is None:
            return True
        return _as_bool(raw, True)

    def _set_profile_run_enabled(self, pid, enabled):
        spid = str(pid)
        settings = QSettings("MyHomeApp", f"Profile_{spid}")
        settings.setValue("run_enabled", bool(enabled))
        settings.sync()

    def _clone_profile_settings(self, src_pid, dst_pid):
        src = QSettings("MyHomeApp", f"Profile_{src_pid}")
        dst = QSettings("MyHomeApp", f"Profile_{dst_pid}")
        dst.clear()
        for key in src.allKeys():
            dst.setValue(key, src.value(key))
        if dst.value("run_enabled", None) is None:
            dst.setValue("run_enabled", True)
        dst.sync()

    def _set_current_set_id(self, set_id, persist=True):
        sid = str(set_id)
        if sid not in self._set_defs:
            sid = self._set_order[0] if self._set_order else ""
        self._current_set_id = sid
        if persist and sid:
            self.master_settings.setValue("current_set_id", sid)
            self.master_settings.sync()
        self._refresh_set_ui()

    def selected_set_id(self):
        return str(self._current_set_id) if self._current_set_id else ""

    def get_set_items(self):
        items = []
        for sid in self._set_order:
            data = self._set_defs.get(str(sid), {})
            items.append((str(sid), str(data.get("name", f"세트{sid}")), len(data.get("profiles", []))))
        return items

    def _clear_set_list_sidebar(self):
        if not hasattr(self, "set_list_layout"):
            return
        while self.set_list_layout.count():
            item = self.set_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_name_width(self):
        base = self._set_sidebar_collapsed_width if self._set_list_collapsed else self._set_sidebar_expanded_width
        return max(40, int(base) - 46)

    def _elide_set_text(self, text):
        width = self._set_name_width()
        metrics = QFontMetrics(self.font())
        return metrics.elidedText(str(text), Qt.TextElideMode.ElideRight, width)

    def _set_sidebar_collapsed(self, collapsed, persist=True):
        collapsed = bool(collapsed)
        if self._set_list_collapsed == collapsed:
            if persist:
                self.master_settings.setValue("set_list_collapsed", bool(collapsed))
                self.master_settings.sync()
            return
        self._set_list_collapsed = collapsed
        if persist:
            self.master_settings.setValue("set_list_collapsed", bool(collapsed))
            self.master_settings.sync()
        self._refresh_set_ui()

    def _rebuild_set_sidebar(self):
        self._clear_set_list_sidebar()
        sid_selected = self.selected_set_id()
        for idx, sid in enumerate(self._set_order, start=1):
            data = self._set_defs.get(str(sid), {})
            name = str(data.get("name", f"세트{sid}"))
            selected = (str(sid) == str(sid_selected))

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            btn = QPushButton(str(idx), row)
            btn.setProperty("kind", "setIndexBtn")
            btn.setProperty("selected", "true" if selected else "false")
            btn.clicked.connect(lambda _, s=str(sid): self._on_set_selected(s))

            name_label = SetNameLabel(str(sid), self._elide_set_text(name), row)
            name_label.setObjectName("setNameTag")
            name_label.setVisible(not self._set_list_collapsed)
            name_label.setFixedWidth(self._set_name_width())
            name_label.renameRequested.connect(self._on_set_name_double_clicked)

            row_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)
            self.set_list_layout.addWidget(row)

        self.set_list_layout.addStretch(1)

    def _refresh_set_ui(self):
        if hasattr(self, "set_mgr_btn"):
            sid = self.selected_set_id()
            data = self._set_defs.get(sid, {})
            _ = str(data.get("name", "세트"))
            self.set_mgr_btn.setText("세트 관리")
        if hasattr(self, "set_sidebar"):
            self.set_sidebar.setFixedWidth(
                self._set_sidebar_collapsed_width if self._set_list_collapsed else self._set_sidebar_expanded_width
            )
        if hasattr(self, "add_set_label"):
            full_text = "새로운 세트"
            self.add_set_label.setVisible(not self._set_list_collapsed)
            self.add_set_label.setFixedWidth(self._set_name_width())
            self.add_set_label.setText(self._elide_set_text(full_text))
        self._rebuild_set_sidebar()
        self._refresh_apply_button_state()

    def _refresh_apply_button_state(self):
        if not hasattr(self, "run_all_btn"):
            return
        selected_sid = str(self.selected_set_id() or "")
        applied_sid = str(getattr(self, "_applied_set_id", "") or "")
        pending = bool(selected_sid and applied_sid and selected_sid != applied_sid)
        self.run_all_btn.setProperty("pendingApply", "true" if pending else "false")
        self.run_all_btn.setText("세트 적용 *" if pending else "세트 적용")
        style = self.run_all_btn.style()
        if style:
            style.unpolish(self.run_all_btn)
            style.polish(self.run_all_btn)
        self.run_all_btn.update()

    def _on_set_selected(self, sid):
        sid = str(sid)
        if sid not in self._set_defs:
            return
        current_sid = self.selected_set_id()
        if not self._set_list_collapsed and sid == current_sid:
            self._set_sidebar_collapsed(True, persist=True)
            return
        if self._set_list_collapsed:
            self._set_sidebar_collapsed(False, persist=True)
        self._set_current_set_id(sid, persist=True)
        self.clear_all_highlights()
        self.load_profiles()

    def _on_set_name_double_clicked(self, sid):
        sid = str(sid)
        if sid not in self._set_defs:
            return
        current_name = str(self._set_defs.get(sid, {}).get("name", f"세트{sid}"))
        new_name, ok = self._prompt_text_dialog("세트 이름 변경", "세트 이름:", current_name)
        if not ok or not new_name:
            return
        self.rename_set(sid, new_name)

    def _on_add_set_clicked(self):
        if self._set_list_collapsed:
            self._set_sidebar_collapsed(False, persist=True)
            return
        default_name = self._default_set_name()
        name, ok = self._prompt_text_dialog("새 세트", "새 세트 이름:", default_name)
        if not ok or not name:
            return
        sid = self.create_empty_set(name)
        if sid:
            self._set_current_set_id(sid, persist=True)
            self.clear_all_highlights()
            self.load_profiles()

    def _load_set_state(self):
        profile_ids = self._all_profile_ids()
        raw_set_ids = self._normalize_ids(self._as_list(self.master_settings.value("set_ids", [])))
        changed = False

        if not raw_set_ids:
            raw_set_ids = ["1"]
            self.master_settings.setValue("set_ids", raw_set_ids)
            self.master_settings.setValue(self._set_key("1", "name"), "세트1")
            self.master_settings.setValue(self._set_key("1", "profiles"), list(profile_ids))
            changed = True

        set_defs = {}
        assigned_profiles = set()
        for sid in raw_set_ids:
            name_raw = self.master_settings.value(self._set_key(sid, "name"), f"세트{sid}")
            name = str(name_raw).strip() or f"세트{sid}"
            raw_profiles = self._normalize_ids(
                self._as_list(self.master_settings.value(self._set_key(sid, "profiles"), []))
            )
            clean_profiles = []
            for pid in raw_profiles:
                if pid not in profile_ids:
                    changed = True
                    continue
                if pid in assigned_profiles:
                    changed = True
                    continue
                assigned_profiles.add(pid)
                clean_profiles.append(pid)
            if raw_profiles != clean_profiles:
                self.master_settings.setValue(self._set_key(sid, "profiles"), clean_profiles)
                changed = True
            if str(name_raw) != name:
                self.master_settings.setValue(self._set_key(sid, "name"), name)
                changed = True
            set_defs[sid] = {"name": name, "profiles": clean_profiles}

        if not set_defs:
            raw_set_ids = ["1"]
            set_defs = {"1": {"name": "세트1", "profiles": list(profile_ids)}}
            self.master_settings.setValue("set_ids", raw_set_ids)
            self.master_settings.setValue(self._set_key("1", "name"), "세트1")
            self.master_settings.setValue(self._set_key("1", "profiles"), list(profile_ids))
            changed = True

        current_sid = str(self.master_settings.value("current_set_id", raw_set_ids[0]))
        if current_sid not in set_defs:
            current_sid = raw_set_ids[0]
            self.master_settings.setValue("current_set_id", current_sid)
            changed = True

        # Backward-compat: if profile_ids contains entries that are not referenced by
        # any set, attach them to the currently selected set so they remain operable.
        unassigned_profiles = [pid for pid in profile_ids if pid not in assigned_profiles]
        if unassigned_profiles:
            attach_sid = current_sid if current_sid in set_defs else (raw_set_ids[0] if raw_set_ids else "")
            if attach_sid:
                existing_profiles = list(set_defs.get(attach_sid, {}).get("profiles", []))
                merged_profiles = existing_profiles + [pid for pid in unassigned_profiles if pid not in existing_profiles]
                if merged_profiles != existing_profiles:
                    set_defs.setdefault(attach_sid, {"name": f"세트{attach_sid}", "profiles": []})
                    set_defs[attach_sid]["profiles"] = merged_profiles
                    self.master_settings.setValue(self._set_key(attach_sid, "profiles"), merged_profiles)
                    changed = True

        self._set_order = list(raw_set_ids)
        self._set_defs = set_defs
        self._current_set_id = current_sid
        applied_sid = str(self.master_settings.value("applied_set_id", current_sid))
        if applied_sid not in set_defs:
            applied_sid = current_sid
            self.master_settings.setValue("applied_set_id", applied_sid)
            changed = True
        self._applied_set_id = applied_sid
        if changed:
            self.master_settings.sync()

    def _migrate_profile_run_flags(self):
        profile_ids = self._all_profile_ids()
        legacy_raw = self.master_settings.value("active_profiles", None)
        has_legacy = legacy_raw is not None
        legacy_active = set(self._as_list(legacy_raw)) if has_legacy else set()
        for pid in profile_ids:
            settings = QSettings("MyHomeApp", f"Profile_{pid}")
            if settings.value("run_enabled", None) is None:
                should_run = (pid in legacy_active) if has_legacy else True
                settings.setValue("run_enabled", bool(should_run))
                settings.sync()

    def _current_set_profiles(self):
        sid = self.selected_set_id()
        data = self._set_defs.get(sid, {})
        return list(data.get("profiles", []))

    def _set_current_profiles(self, profile_ids):
        sid = self.selected_set_id()
        if not sid or sid not in self._set_defs:
            return
        clean_profiles = self._normalize_ids(profile_ids)
        self._set_defs[sid]["profiles"] = clean_profiles
        self.master_settings.setValue(self._set_key(sid, "profiles"), clean_profiles)
        self.master_settings.sync()

    def _remove_profile_from_sets(self, profile_id):
        spid = str(profile_id)
        changed = False
        for sid in self._set_order:
            data = self._set_defs.get(sid, {})
            profiles = [pid for pid in data.get("profiles", []) if pid != spid]
            if profiles != data.get("profiles", []):
                data["profiles"] = profiles
                self._set_defs[sid] = data
                self.master_settings.setValue(self._set_key(sid, "profiles"), profiles)
                changed = True
        if changed:
            self.master_settings.sync()

    def _cleanup_orphan_profiles(self):
        referenced = set()
        for data in self._set_defs.values():
            for pid in data.get("profiles", []):
                referenced.add(str(pid))

        profile_ids = self._all_profile_ids()
        orphan_ids = [pid for pid in profile_ids if pid not in referenced]
        if not orphan_ids:
            return 0

        for pid in orphan_ids:
            profile_settings = QSettings("MyHomeApp", f"Profile_{pid}")
            profile_settings.clear()
            profile_settings.sync()

        kept_profile_ids = [pid for pid in profile_ids if pid in referenced]
        self.master_settings.setValue("profile_ids", kept_profile_ids)
        active_ids = self._as_list(self.master_settings.value("active_profiles", []))
        self.master_settings.setValue(
            "active_profiles",
            [pid for pid in active_ids if pid in referenced]
        )
        self.master_settings.sync()
        return len(orphan_ids)

    def _profile_startup_media_kind(self, pid):
        spid = str(pid)
        settings = QSettings("MyHomeApp", f"Profile_{spid}")
        folder_path = str(settings.value("folder_path", "") or "").strip()
        if not folder_path or not os.path.isdir(folder_path):
            return "other"
        ext = (".png", ".jpg", ".jpeg", ".gif", ".mp4", ".avi", ".mov", ".ico", ".jfif", ".webp")
        try:
            files = os.listdir(folder_path)
        except OSError:
            return "other"
        candidates = sorted([name for name in files if str(name).lower().endswith(ext)])
        if not candidates:
            return "other"
        first_name = str(candidates[0]).lower()
        if first_name.endswith((".mp4", ".avi", ".mov")):
            return "video"
        if first_name.endswith(".gif"):
            return "gif"
        return "other"

    @staticmethod
    def _startup_delay_for_kind(kind):
        key = str(kind or "").strip().lower()
        if key == "video":
            return 450
        if key == "gif":
            return 320
        return 80

    def _cancel_startup_queue(self):
        if hasattr(self, "_startup_queue_timer") and self._startup_queue_timer.isActive():
            self._startup_queue_timer.stop()
        self._startup_queue = []
        self._startup_queue_active = False

    def _build_set_startup_queue(self, set_id):
        sid = str(set_id)
        data = self._set_defs.get(sid, {})
        ordered = []
        for order_idx, pid in enumerate(data.get("profiles", [])):
            spid = str(pid)
            if not self._profile_run_enabled(spid):
                continue
            name = QSettings("MyHomeApp", f"Profile_{spid}").value("name", "New 세팅")
            kind = self._profile_startup_media_kind(spid)
            if kind == "video":
                priority = 1
            elif kind == "gif":
                priority = 2
            else:
                priority = 0
            ordered.append((int(priority), int(order_idx), spid, str(name), str(kind)))
        ordered.sort(key=lambda x: (x[0], x[1]))
        return [(pid, name, kind) for _prio, _idx, pid, name, kind in ordered]

    def _begin_startup_queue(self, entries):
        self._cancel_startup_queue()
        self._startup_queue = list(entries)
        self._startup_queue_active = bool(self._startup_queue)
        if not self._startup_queue_active:
            self.update_active_status()
            self.load_profiles()
            self._refresh_apply_button_state()
            return
        self._run_next_startup_item()

    def _run_next_startup_item(self):
        if not bool(getattr(self, "_startup_queue_active", False)):
            return
        if not self._startup_queue:
            self._startup_queue_active = False
            self.update_active_status()
            self.load_profiles()
            self._refresh_apply_button_state()
            return

        pid, name, kind = self._startup_queue.pop(0)
        self._start_widget_instance(pid, name)
        self.update_active_status()

        if not self._startup_queue:
            self._startup_queue_active = False
            self.load_profiles()
            self._refresh_apply_button_state()
            return
        self._startup_queue_timer.start(self._startup_delay_for_kind(kind))

    def _start_widget_instance(self, pid, name):
        spid = str(pid)
        if spid in self.widgets:
            return False
        widget = DesktopWidget(spid, name, self)
        try:
            widget.prepare_media_before_show()
        except Exception:
            pass
        self.widgets[spid] = widget
        widget.show()
        try:
            widget = self.widgets[spid]
            QTimer.singleShot(
                0,
                lambda w=widget: (
                    w._schedule_desktop_icon_overlay_bootstrap(retries=4, delay_ms=50)
                    if isinstance(w, DesktopWidget)
                    else None
                ),
            )
        except Exception:
            pass
        if spid in self._temp_group_ids:
            self.widgets[spid]._refresh_group_badge()
        if self._gpu_guard_paused and bool(getattr(self.widgets[spid], "gpu_guard_enabled", False)):
            self.widgets[spid].set_performance_paused(
                True, reason=f"gpu {self._gpu_last_usage:.1f}%", force=True
            )
        return True

    def _stop_all_widgets_bulk(self):
        self._cancel_startup_queue()
        self.clear_temp_group(silent=True)
        changed = False
        for pid in list(self.widgets.keys()):
            widget = self.widgets.get(pid)
            if widget is None:
                continue
            widget.close()
            widget.deleteLater()
            self.widgets.pop(pid, None)
            changed = True
        return changed

    def is_temp_group_member(self, pid):
        spid = str(pid)
        return spid in self._temp_group_ids

    def _sync_temp_group_badges(self):
        for widget in self.widgets.values():
            if isinstance(widget, DesktopWidget):
                widget._refresh_group_badge()

    def toggle_temp_group_member(self, pid):
        spid = str(pid)
        if not spid or spid not in self.widgets:
            return False
        if spid in self._temp_group_ids:
            self._temp_group_ids.remove(spid)
            grouped = False
        else:
            self._temp_group_ids.add(spid)
            grouped = True
        self._sync_temp_group_badges()
        print(f"[temp-group] profile={spid} grouped={grouped} members={sorted(self._temp_group_ids)}")
        return grouped

    def clear_temp_group(self, silent=False):
        if not self._temp_group_ids:
            return 0
        count = len(self._temp_group_ids)
        self._temp_group_ids.clear()
        self._sync_temp_group_badges()
        if not silent:
            print(f"[temp-group] cleared count={count}")
        return count

    def _temp_group_shortcut_targets(self, source_pid):
        spid = str(source_pid)
        source_widget = self.widgets.get(spid)
        if not isinstance(source_widget, DesktopWidget):
            return []
        if spid not in self._temp_group_ids:
            return [source_widget]

        targets = []
        for pid in self._temp_group_ids:
            widget = self.widgets.get(str(pid))
            if isinstance(widget, DesktopWidget):
                targets.append(widget)
        if not targets:
            return [source_widget]

        targets.sort(key=lambda w: (0 if str(w.profile_id) == spid else 1, str(w.profile_id)))
        return targets

    def _temp_group_move_targets(self, source_pid):
        spid = str(source_pid)
        if spid not in self._temp_group_ids:
            return []
        targets = []
        for pid in self._temp_group_ids:
            if pid == spid:
                continue
            widget = self.widgets.get(pid)
            if not isinstance(widget, DesktopWidget):
                continue
            if not widget.isVisible():
                continue
            if bool(getattr(widget, "is_locked", False)):
                continue
            targets.append(widget)
        return targets

    def move_temp_group_by_delta(self, source_pid, dx, dy):
        if not dx and not dy:
            return
        src = self.widgets.get(str(source_pid))
        if isinstance(src, DesktopWidget) and bool(getattr(src, "is_locked", False)):
            return
        for widget in self._temp_group_move_targets(source_pid):
            widget._move_exact((widget.x() + int(dx), widget.y() + int(dy)))

    def resize_temp_group_by_edges(self, source_pid, left_step, top_step, right_step, bottom_step):
        try:
            d_left = int(left_step)
            d_top = int(top_step)
            d_right = int(right_step)
            d_bottom = int(bottom_step)
        except Exception:
            return
        if not (d_left or d_top or d_right or d_bottom):
            return

        src = self.widgets.get(str(source_pid))
        if isinstance(src, DesktopWidget) and bool(getattr(src, "is_locked", False)):
            return

        for widget in self._temp_group_move_targets(source_pid):
            old_left = int(widget.x())
            old_top = int(widget.y())
            old_right = int(widget.x() + widget.width())
            old_bottom = int(widget.y() + widget.height())

            new_left = int(old_left + d_left)
            new_top = int(old_top + d_top)
            new_right = int(old_right + d_right)
            new_bottom = int(old_bottom + d_bottom)

            min_w = max(50, int(widget.minimumWidth()))
            min_h = max(50, int(widget.minimumHeight()))

            width = int(new_right - new_left)
            height = int(new_bottom - new_top)

            if width < int(min_w):
                if d_left != 0 and d_right == 0:
                    new_left = int(new_right - int(min_w))
                else:
                    new_right = int(new_left + int(min_w))
                width = int(min_w)
            if height < int(min_h):
                if d_top != 0 and d_bottom == 0:
                    new_top = int(new_bottom - int(min_h))
                else:
                    new_bottom = int(new_top + int(min_h))
                height = int(min_h)

            widget.setGeometry(QRect(int(new_left), int(new_top), int(width), int(height)))

    def save_temp_group_positions(self, source_pid):
        for widget in self._temp_group_move_targets(source_pid):
            widget.save_all_settings()

    def set_temp_group_mute(self, source_pid, muted):
        targets = self._temp_group_shortcut_targets(source_pid)
        if not targets:
            return
        for idx, widget in enumerate(targets):
            widget.set_mute_shortcut_state(bool(muted), log=(idx == 0))
        if len(targets) > 1:
            print(f"[temp-group-mute] source={source_pid} members={len(targets)} muted={bool(muted)}")

    def set_temp_group_gpu_guard(self, source_pid, enabled):
        targets = self._temp_group_shortcut_targets(source_pid)
        if not targets:
            return
        for idx, widget in enumerate(targets):
            widget.set_gpu_guard_shortcut_state(bool(enabled), log=(idx == 0), show_hud=True)
        if len(targets) > 1:
            print(f"[temp-group-gpu-guard] source={source_pid} members={len(targets)} enabled={bool(enabled)}")

    def set_temp_group_corner_mode(self, source_pid, mode):
        mode_int = 0 if int(mode) != 1 else 1
        targets = self._temp_group_shortcut_targets(source_pid)
        if not targets:
            return
        for idx, widget in enumerate(targets):
            widget.set_corner_mode_shortcut_state(mode_int, log=(idx == 0))
        if len(targets) > 1:
            mode_text = "곡선" if mode_int == 0 else "직각"
            print(f"[temp-group-corner] source={source_pid} members={len(targets)} mode={mode_text}")

    def adjust_temp_group_opacity(self, source_pid, delta_pct):
        try:
            delta = int(delta_pct)
        except Exception:
            delta = 0
        if delta == 0:
            return
        targets = self._temp_group_shortcut_targets(source_pid)
        if not targets:
            return
        changed = 0
        for widget in targets:
            old_val = int(getattr(widget, "current_opacity_pct", 100))
            new_val = max(10, min(100, old_val + delta))
            if new_val == old_val:
                continue
            widget.current_opacity_pct = new_val
            widget.setWindowOpacity(new_val / 100.0)
            widget.save_all_settings()
            changed += 1
        if len(targets) > 1 and changed > 0:
            print(f"[temp-group-opacity] source={source_pid} members={len(targets)} delta={delta}")

    def set_temp_group_lock(self, source_pid, lock):
        targets = self._temp_group_shortcut_targets(source_pid)
        if not targets:
            return 0
        lock_val = bool(lock)
        for widget in targets:
            if hasattr(widget, "cancel_active_interaction"):
                widget.cancel_active_interaction()
        for widget in targets:
            widget.apply_window_settings(int(getattr(widget, "layer_mode", DesktopWidget.LAYER_NORMAL)), lock_val)
            widget.save_all_settings()
            if hasattr(widget, "show_lock_hud"):
                widget.show_lock_hud(lock_val)
        self._sync_temp_group_badges()
        if len(targets) > 1:
            print(f"[temp-group-lock] source={source_pid} members={len(targets)} lock={lock_val}")
        return len(targets)

    def apply_set(self, set_id):
        sid = str(set_id)
        if sid not in self._set_defs:
            return

        self._cancel_startup_queue()
        self._set_current_set_id(sid, persist=True)
        self.clear_all_highlights()
        self.clear_temp_group(silent=True)
        self._stop_all_widgets_bulk()
        startup_entries = self._build_set_startup_queue(sid)

        self._applied_set_id = sid
        self.master_settings.setValue("applied_set_id", sid)
        self.master_settings.sync()
        self._begin_startup_queue(startup_entries)

    def create_empty_set(self, name):
        clean_name = str(name).strip()
        if not clean_name:
            return ""
        sid = self._next_set_id()
        self._set_order.append(sid)
        self._set_defs[sid] = {"name": clean_name, "profiles": []}
        self.master_settings.setValue("set_ids", list(self._set_order))
        self.master_settings.setValue(self._set_key(sid, "name"), clean_name)
        self.master_settings.setValue(self._set_key(sid, "profiles"), [])
        self.master_settings.sync()
        return sid

    def copy_set(self, source_set_id, new_name):
        source_sid = str(source_set_id)
        if source_sid not in self._set_defs:
            return ""
        clean_name = str(new_name).strip()
        if not clean_name:
            return ""

        profile_ids = self._all_profile_ids()
        profile_id_set = set(profile_ids)
        next_profile_num = 0
        for pid in profile_ids:
            try:
                next_profile_num = max(next_profile_num, int(pid))
            except Exception:
                continue

        copied_profiles = []
        for src_pid in self._set_defs[source_sid].get("profiles", []):
            next_profile_num += 1
            while str(next_profile_num) in profile_id_set:
                next_profile_num += 1
            new_pid = str(next_profile_num)
            self._clone_profile_settings(src_pid, new_pid)
            profile_ids.append(new_pid)
            profile_id_set.add(new_pid)
            copied_profiles.append(new_pid)

        sid = self._next_set_id()
        self._set_order.append(sid)
        self._set_defs[sid] = {"name": clean_name, "profiles": copied_profiles}
        self.master_settings.setValue("profile_ids", profile_ids)
        self.master_settings.setValue("set_ids", list(self._set_order))
        self.master_settings.setValue(self._set_key(sid, "name"), clean_name)
        self.master_settings.setValue(self._set_key(sid, "profiles"), copied_profiles)
        self.master_settings.sync()
        return sid

    def copy_profiles_from_set(self, source_set_id, target_set_id):
        source_sid = str(source_set_id)
        target_sid = str(target_set_id)
        if source_sid not in self._set_defs or target_sid not in self._set_defs:
            return False
        if source_sid == target_sid:
            return False

        profile_ids = self._all_profile_ids()
        profile_id_set = set(profile_ids)
        next_profile_num = 0
        for pid in profile_ids:
            try:
                next_profile_num = max(next_profile_num, int(pid))
            except Exception:
                continue

        copied_profiles = []
        for src_pid in self._set_defs[source_sid].get("profiles", []):
            next_profile_num += 1
            while str(next_profile_num) in profile_id_set:
                next_profile_num += 1
            new_pid = str(next_profile_num)
            self._clone_profile_settings(src_pid, new_pid)
            profile_ids.append(new_pid)
            profile_id_set.add(new_pid)
            copied_profiles.append(new_pid)

        if not copied_profiles:
            return False

        target_profiles = list(self._set_defs[target_sid].get("profiles", []))
        target_profiles = copied_profiles + target_profiles
        self._set_defs[target_sid]["profiles"] = target_profiles

        self.master_settings.setValue("profile_ids", profile_ids)
        self.master_settings.setValue(self._set_key(target_sid, "profiles"), target_profiles)
        self.master_settings.sync()
        self._refresh_set_ui()
        return True

    def rename_set(self, set_id, new_name):
        sid = str(set_id)
        if sid not in self._set_defs:
            return False
        clean_name = str(new_name).strip()
        if not clean_name:
            return False
        self._set_defs[sid]["name"] = clean_name
        self.master_settings.setValue(self._set_key(sid, "name"), clean_name)
        self.master_settings.sync()
        self._refresh_set_ui()
        return True

    def delete_set(self, set_id):
        sid = str(set_id)
        if sid not in self._set_defs:
            return False
        if len(self._set_order) <= 1:
            QMessageBox.information(self, "세트 삭제", "최소 1개의 세트는 유지되어야 합니다.")
            return False

        set_name = str(self._set_defs[sid].get("name", f"세트{sid}"))
        removed_profiles = [str(pid) for pid in self._set_defs[sid].get("profiles", [])]
        remaining_set_ids = [str(x) for x in self._set_order if str(x) != sid]
        if not remaining_set_ids:
            QMessageBox.information(self, "세트 삭제", "최소 1개의 세트는 유지되어야 합니다.")
            return False
        absorb_target_sid = str(remaining_set_ids[0])
        absorb_target_name = str(self._set_defs.get(absorb_target_sid, {}).get("name", f"세트{absorb_target_sid}"))

        delete_profiles = False
        if removed_profiles:
            choice_box = QMessageBox(self)
            choice_box.setWindowTitle("세트 삭제")
            choice_box.setIcon(QMessageBox.Icon.Warning)
            choice_box.setText(f"'{set_name}' 세트를 삭제합니다.")
            choice_box.setInformativeText(
                f"포함된 프로필 {len(removed_profiles)}개 처리 방식을 선택하세요.\n"
                f"- 흡수: '{absorb_target_name}'(첫번째 세트)로 이동\n"
                f"- 삭제: 프로필도 함께 완전 삭제"
            )
            absorb_btn = choice_box.addButton("첫번째 세트로 흡수", QMessageBox.ButtonRole.AcceptRole)
            purge_btn = choice_box.addButton("프로필도 함께 삭제", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = choice_box.addButton("취소", QMessageBox.ButtonRole.RejectRole)
            choice_box.setDefaultButton(absorb_btn)
            choice_box.exec()
            clicked = choice_box.clickedButton()
            if clicked is cancel_btn:
                return False
            delete_profiles = (clicked is purge_btn)
        else:
            confirm = QMessageBox.question(
                self,
                "세트 삭제",
                f"'{set_name}' 세트를 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return False

        if delete_profiles and removed_profiles:
            remove_ids = set([str(pid) for pid in removed_profiles])
            for pid in list(remove_ids):
                if pid in self._temp_group_ids:
                    self._temp_group_ids.remove(pid)
                if pid in self.widgets:
                    widget = self.widgets.get(pid)
                    if widget is not None:
                        widget.close()
                        widget.deleteLater()
                    self.widgets.pop(pid, None)
                profile_settings = QSettings("MyHomeApp", f"Profile_{pid}")
                profile_settings.clear()
                profile_settings.sync()

            profile_ids = [pid for pid in self._all_profile_ids() if str(pid) not in remove_ids]
            self.master_settings.setValue("profile_ids", profile_ids)
            active_ids = self._as_list(self.master_settings.value("active_profiles", []))
            self.master_settings.setValue(
                "active_profiles",
                [pid for pid in active_ids if str(pid) not in remove_ids],
            )
        elif removed_profiles:
            target_profiles = list(self._set_defs.get(absorb_target_sid, {}).get("profiles", []))
            merged_profiles = target_profiles + [pid for pid in removed_profiles if pid not in target_profiles]
            if absorb_target_sid in self._set_defs:
                self._set_defs[absorb_target_sid]["profiles"] = merged_profiles
            self.master_settings.setValue(self._set_key(absorb_target_sid, "profiles"), merged_profiles)

        self.master_settings.remove(f"sets/{sid}")
        self._set_defs.pop(sid, None)
        self._set_order = [x for x in self._set_order if str(x) != sid]
        self.master_settings.setValue("set_ids", list(self._set_order))
        self.master_settings.sync()

        selected_sid = self.selected_set_id()
        if selected_sid == sid:
            self.apply_set(absorb_target_sid)
        elif str(getattr(self, "_applied_set_id", "")) == sid:
            fallback_sid = selected_sid if selected_sid in self._set_defs else absorb_target_sid
            self.apply_set(fallback_sid)
        else:
            self._refresh_set_ui()
            self._sync_temp_group_badges()
            self.update_active_status()
            self.load_profiles()
        return True

    def _on_profile_order_changed(self, ordered_ids):
        sid = self.selected_set_id()
        if not sid or sid not in self._set_defs:
            return
        current = list(self._set_defs[sid].get("profiles", []))
        if not current:
            return
        current_set = set(current)
        ordered = [pid for pid in self._normalize_ids(ordered_ids) if pid in current_set]
        if len(ordered) != len(current):
            for pid in current:
                if pid not in ordered:
                    ordered.append(pid)
        if ordered == current:
            return
        self._set_defs[sid]["profiles"] = ordered
        self.master_settings.setValue(self._set_key(sid, "profiles"), ordered)
        self.master_settings.sync()
        self.load_profiles()

    def open_set_manager(self):
        self._load_set_state()
        dialog = SetManagerDialog(self, self)
        dialog.exec()
        self._refresh_set_ui()
        self.load_profiles()

    def _toggle_gpu_cfg_panel(self, expanded=None):
        if expanded is None:
            expanded = self.gpu_cfg_toggle.isChecked()
        expanded = bool(expanded)
        if expanded:
            self._place_gpu_cfg_panel()
            self.gpu_cfg_panel.show()
            self.gpu_cfg_panel.raise_()
            self.gpu_cfg_panel.activateWindow()
        else:
            self.gpu_cfg_panel.hide()

    def _place_gpu_cfg_panel(self):
        self.gpu_cfg_panel.adjustSize()
        hint = self.gpu_cfg_panel.sizeHint()
        popup_w = max(256, hint.width())
        popup_h = hint.height()

        anchor_global = self.gpu_cfg_toggle.mapToGlobal(QPoint(0, self.gpu_cfg_toggle.height() + 6))
        x = anchor_global.x() - (popup_w - self.gpu_cfg_toggle.width())
        y = anchor_global.y()

        screen = QGuiApplication.screenAt(anchor_global) or self.screen() or QGuiApplication.primaryScreen()
        if screen:
            ag = screen.availableGeometry()
            x = max(ag.left() + 8, min(x, ag.right() - popup_w - 8))
            y = max(ag.top() + 8, min(y, ag.bottom() - popup_h - 8))

        self.gpu_cfg_panel.setGeometry(x, y, popup_w, popup_h)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            if self._is_master_internal_object(obj):
                QTimer.singleShot(0, self._activate_from_internal_click)
        if obj is getattr(self, "gpu_cfg_panel", None):
            if event.type() == QEvent.Type.Hide and self.gpu_cfg_toggle.isChecked():
                prev = self.gpu_cfg_toggle.blockSignals(True)
                self.gpu_cfg_toggle.setChecked(False)
                self.gpu_cfg_toggle.blockSignals(prev)
        list_widget = getattr(self, "list_widget", None)
        viewport = list_widget.viewport() if list_widget is not None else None
        if obj is viewport:
            if event.type() == QEvent.Type.Leave:
                self._set_hovered_profile_row(None)
        return super().eventFilter(obj, event)

    def _is_master_internal_object(self, obj):
        if obj is self:
            return True
        if not isinstance(obj, QWidget):
            return False
        if obj is getattr(self, "gpu_cfg_panel", None):
            return True
        if self.isAncestorOf(obj):
            return True
        top = obj.window()
        return top is self or top is getattr(self, "gpu_cfg_panel", None)

    def _activate_from_internal_click(self):
        if not self.isVisible():
            return
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _apply_gpu_guard_thresholds(self, high_pct, low_pct, persist=True):
        try:
            high = float(high_pct)
        except Exception:
            high = 90.0
        try:
            low = float(low_pct)
        except Exception:
            low = 70.0

        high = max(1.0, min(100.0, high))
        low = max(0.0, min(99.0, low))
        if low >= high:
            low = max(0.0, high - 1.0)

        self._gpu_guard_high_pct = high
        self._gpu_guard_low_pct = low
        self._sync_gpu_threshold_inputs()

        if persist:
            self.master_settings.setValue("gpu_guard_high_pct", int(round(high)))
            self.master_settings.setValue("gpu_guard_low_pct", int(round(low)))
            self.master_settings.sync()

    def _sync_gpu_threshold_inputs(self):
        if not hasattr(self, "gpu_pause_slider") or not hasattr(self, "gpu_resume_slider"):
            return
        pause_val = int(round(self._gpu_guard_high_pct))
        resume_val = int(round(self._gpu_guard_low_pct))
        prev = self.gpu_pause_slider.blockSignals(True)
        self.gpu_pause_slider.setValue(pause_val)
        self.gpu_pause_slider.blockSignals(prev)
        prev = self.gpu_resume_slider.blockSignals(True)
        self.gpu_resume_slider.setValue(resume_val)
        self.gpu_resume_slider.blockSignals(prev)
        if hasattr(self, "gpu_pause_value_lbl"):
            self.gpu_pause_value_lbl.setText(f"{pause_val}%")
        if hasattr(self, "gpu_resume_value_lbl"):
            self.gpu_resume_value_lbl.setText(f"{resume_val}%")

    def _on_gpu_threshold_inputs_changed(self):
        self._apply_gpu_guard_thresholds(
            self.gpu_pause_slider.value(),
            self.gpu_resume_slider.value(),
            persist=True,
        )
        self._sync_gpu_threshold_inputs()

    @staticmethod
    def _action_icon_pixmap(kind, color_hex, size=16):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color_hex), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind == "run":
            painter.drawPolygon(
                QPolygonF([
                    QPointF(4.2, 3.2),
                    QPointF(12.0, 8.0),
                    QPointF(4.2, 12.8),
                ])
            )
        elif kind == "stop":
            painter.drawRect(QRectF(4.0, 4.0, 8.0, 8.0))
        elif kind == "settings":
            center = QPointF(8.0, 8.0)
            outer_r = 3.6
            inner_r = 1.9
            for i in range(8):
                angle = math.radians(i * 45.0)
                x1 = center.x() + math.cos(angle) * 5.0
                y1 = center.y() + math.sin(angle) * 5.0
                x2 = center.x() + math.cos(angle) * 6.7
                y2 = center.y() + math.sin(angle) * 6.7
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            painter.drawEllipse(center, outer_r, outer_r)
            painter.drawEllipse(center, inner_r, inner_r)
        elif kind == "delete":
            painter.drawLine(QPointF(4.2, 4.2), QPointF(11.8, 11.8))
            painter.drawLine(QPointF(11.8, 4.2), QPointF(4.2, 11.8))

        painter.end()
        return pixmap

    @classmethod
    def _build_action_icon(cls, kind, color_hex):
        icon = QIcon()
        icon.addPixmap(cls._action_icon_pixmap(kind, color_hex), QIcon.Mode.Normal)
        icon.addPixmap(cls._action_icon_pixmap(kind, color_hex), QIcon.Mode.Active)
        disabled_color = QColor(color_hex).darker(170).name()
        icon.addPixmap(cls._action_icon_pixmap(kind, disabled_color), QIcon.Mode.Disabled)
        return icon

    def _set_profile_row_selected(self, pid, selected):
        row = self.profile_rows.get(str(pid))
        if row is None:
            return
        if isinstance(row, ProfileRowWidget):
            row.set_selected(selected)
            return
        row.setProperty("selected", "true" if selected else "false")
        style = row.style()
        if style:
            style.unpolish(row)
            style.polish(row)
        row.update()

    def _apply_title_bar_theme(self):
        self._apply_window_title_bar_theme(self)

    @staticmethod
    def _apply_window_title_bar_theme(window):
        try:
            import ctypes
            hwnd = int(window.winId())
            dwmapi = ctypes.windll.dwmapi
            value = ctypes.c_int(1)
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(20),
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
            # Keep title bar color aligned with controller palette.
            # COLORREF is 0x00BBGGRR.
            caption_color = ctypes.c_uint(0x00795035)  # #355079
            text_color = ctypes.c_uint(0x00FFF7F5)     # #f5f7ff
            # DWMWA_CAPTION_COLOR = 35, DWMWA_TEXT_COLOR = 36 (Win11+)
            dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(35),
                ctypes.byref(caption_color),
                ctypes.sizeof(caption_color)
            )
            dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(36),
                ctypes.byref(text_color),
                ctypes.sizeof(text_color)
            )
        except Exception:
            pass

    @staticmethod
    def _themed_input_dialog_style():
        return """
            QDialog {
                background-color: #23344d;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLineEdit {
                min-height: 30px;
                color: #edf3ff;
                background-color: #1a2740;
                border: 1px solid #4a6288;
                border-radius: 8px;
                padding: 2px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #77a3f2;
            }
            QComboBox {
                min-height: 32px;
                color: #edf3ff;
                background-color: #1a2740;
                border: 1px solid #4a6288;
                border-radius: 8px;
                padding: 2px 8px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 0px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                margin: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #23344d;
                color: #eef4ff;
                border: none;
                selection-background-color: #3f5e8e;
                selection-color: #ffffff;
                outline: 0;
                font-size: 13px;
            }
            QPushButton {
                min-height: 30px;
                border-radius: 8px;
                padding: 0 12px;
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3f5e8e;
            }
        """

    def _prompt_text_dialog(self, title, label, default_text=""):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(str(title))
        dialog.setMinimumSize(250, 190)
        dialog.resize(250, 190)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setLabelText(str(label))
        dialog.setTextValue(str(default_text))
        dialog.setOkButtonText("확인")
        dialog.setCancelButtonText("취소")
        dialog.setStyleSheet(self._themed_input_dialog_style())
        QTimer.singleShot(0, lambda d=dialog: self._apply_window_title_bar_theme(d))
        if dialog.exec():
            return dialog.textValue().strip(), True
        return "", False

    def _prompt_choice_dialog(self, title, label, choices):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(str(title))
        dialog.setMinimumSize(360, 220)
        dialog.resize(360, 220)
        dialog.setLabelText(str(label))
        dialog.setComboBoxEditable(False)
        dialog.setComboBoxItems([str(v) for v in choices])
        dialog.setTextValue(str(choices[0]) if choices else "")
        dialog.setOkButtonText("확인")
        dialog.setCancelButtonText("취소")
        dialog.setStyleSheet(self._themed_input_dialog_style())
        QTimer.singleShot(0, lambda d=dialog: self._apply_window_title_bar_theme(d))
        if dialog.exec():
            return dialog.textValue(), True
        return "", False

    def _add_profile_group_header(self, text):
        item = QListWidgetItem(self.list_widget)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(1, 28))
        lbl = QLabel(text)
        lbl.setObjectName("groupHeaderLabel")
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, lbl)

    def _add_widget_add_row(self):
        item = QListWidgetItem(self.list_widget)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(1, 34))

        row = QWidget()
        row.setObjectName("addWidgetRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        btn = QPushButton("＋", row)
        btn.setObjectName("addWidgetBtn")
        btn.clicked.connect(self.add_profile)
        lbl = QLabel("위젯 추가", row)
        lbl.setObjectName("addWidgetLabel")

        row_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

    def _add_profile_row(self, pid, name, is_running):
        item = QListWidgetItem(self.list_widget)
        item.setData(Qt.ItemDataRole.UserRole, str(pid))

        row = ProfileRowWidget()
        row.setObjectName("profileRow")
        row.setProperty("running", "true" if is_running else "false")
        row.setProperty("hovered", "false")
        row.setProperty("selected", "false")
        row.setMinimumHeight(46)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 4, 2, 4)
        row_layout.setSpacing(8)

        status_dot = QLabel()
        status_dot.setObjectName("statusDot")
        status_dot.setProperty("running", "true" if is_running else "false")

        lbl = QLabel()
        lbl.setObjectName("profileName")
        lbl.setMinimumHeight(20)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        btn_run = QPushButton("실행")
        btn_stop = QPushButton("중지")
        btn_set = QPushButton("설정")
        btn_del = QPushButton("삭제")
        btn_run.setObjectName("runBtn")
        btn_stop.setObjectName("stopBtn")
        btn_set.setObjectName("setBtn")
        btn_del.setObjectName("deleteBtn")

        btns = [btn_run, btn_stop, btn_set, btn_del]
        for btn in btns:
            btn.setProperty("kind", "rowAction")
            btn.setText("")
            btn.setFixedSize(28, 28)
            btn.setIconSize(QSize(13, 13))
            btn.setVisible(False)

        btn_run.setIcon(self._build_action_icon("run", "#dbfff3"))
        btn_stop.setIcon(self._build_action_icon("stop", "#ffe9ef"))
        btn_set.setIcon(self._build_action_icon("settings", "#e3edff"))
        btn_del.setIcon(self._build_action_icon("delete", "#ffe4e9"))
        btn_run.setEnabled(not is_running)
        btn_stop.setEnabled(is_running)

        btn_run.clicked.connect(lambda _, p=str(pid), n=name: self.run_widget(p, n))
        btn_stop.clicked.connect(lambda _, p=str(pid): self.stop_widget(p))
        btn_set.clicked.connect(lambda _, p=str(pid): self.open_widget_settings(p))
        btn_del.clicked.connect(lambda _, p=str(pid): self.delete_profile(p))

        action_wrap = QWidget()
        action_wrap_layout = QHBoxLayout(action_wrap)
        action_wrap_layout.setContentsMargins(0, 0, 0, 0)
        action_wrap_layout.setSpacing(4)
        for btn in btns:
            action_wrap_layout.addWidget(btn)
        action_wrap.setFixedWidth(4 * 28 + 3 * action_wrap_layout.spacing())

        margin_width = row_layout.contentsMargins().left() + row_layout.contentsMargins().right()
        status_width = 10 + row_layout.spacing()
        action_width = action_wrap.width() + row_layout.spacing()
        viewport_w = self.list_widget.viewport().width()
        if viewport_w <= 0:
            viewport_w = max(260, self.width() - 48)
        name_max_width = max(84, viewport_w - margin_width - status_width - action_width - 12)
        elided_name = QFontMetrics(lbl.font()).elidedText(
            str(name), Qt.TextElideMode.ElideRight, name_max_width
        )
        lbl.setText(elided_name)

        row_layout.addWidget(status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(lbl, 1, Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(action_wrap, 0, Qt.AlignmentFlag.AlignVCenter)
        row.set_action_buttons(btns)

        item.setSizeHint(QSize(1, 46))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)
        self.profile_rows[str(pid)] = row

    def load_profiles(self):
        self.list_widget.clear()
        self.profile_rows = {}
        self._add_widget_add_row()
        p_ids = self._current_set_profiles()

        for pid in p_ids:
            name = QSettings("MyHomeApp", f"Profile_{pid}").value("name", "New 세팅")
            self._add_profile_row(pid, str(name), pid in self.widgets)
        self._set_hovered_profile_row(None)

    def open_widget_settings(self, pid):
        pid = str(pid)

        is_running = pid in self.widgets
        s_obj = QSettings("MyHomeApp", f"Profile_{pid}")

        if is_running:
            w = self.widgets[pid]
            current_data = {
                'folder_path': w.folder_path,
                'exec_path': w.exec_path,
                'w': w.width(),
                'h': w.height(),
                'layer_mode': getattr(w, 'layer_mode', DesktopWidget.LAYER_NORMAL),
                'layer_schema_version': int(DesktopWidget.LAYER_SCHEMA_VERSION),
                'is_locked': getattr(w, 'is_locked', False),
                'opacity_pct': w.current_opacity_pct,
                'bg_color_mode': w.bg_color_mode,
                'corner_mode': getattr(w, 'corner_mode', 0),
                'media_fit_mode': int(getattr(w, 'media_fit_mode', 0)),
                'interval': w.interval_ms // 1000,
                'is_muted': w.is_muted,
                'gpu_guard_enabled': getattr(w, 'gpu_guard_enabled', False),
            }
        else:

            current_data = {
                'folder_path': s_obj.value("folder_path", ""),
                'exec_path': s_obj.value("exec_path", ""),
                'w': int(s_obj.value("w", 200)),
                'h': int(s_obj.value("h", 200)),
                'layer_mode': DesktopWidget.coerce_layer_mode(
                    int(s_obj.value("layer_mode", DesktopWidget.LAYER_NORMAL)),
                    int(s_obj.value("layer_schema_version", 0)),
                ),
                'layer_schema_version': int(DesktopWidget.LAYER_SCHEMA_VERSION),
                'is_locked': _as_bool(s_obj.value("is_locked", False), False),
                'opacity_pct': int(s_obj.value("opacity_pct", 100)),
                'bg_color_mode': int(s_obj.value("bg_color_mode", 1)),
                'corner_mode': int(s_obj.value("corner_mode", 0)),
                'media_fit_mode': int(s_obj.value("media_fit_mode", 0)),
                'interval': int(s_obj.value("interval", 5)),
                'is_muted': _as_bool(s_obj.value("is_muted", True), True),
                'gpu_guard_enabled': _as_bool(s_obj.value("gpu_guard_enabled", False), False),
            }

        dialog = SettingsDialog(self, current_data)
        

        if is_running:
            dialog.opacity_slider.valueChanged.connect(self.widgets[pid].preview_opacity)

        if dialog.exec():

            new_folder = dialog.folder_path
            new_exec = dialog.exec_path
            new_w = dialog.width_input.value()
            new_h = dialog.height_input.value()
            new_interval = dialog.sec_input.value() * 1000
            new_opacity = dialog.opacity_slider.value()
            new_bg = dialog.bg_combo.currentIndex()
            new_corner = dialog.corner_combo.currentIndex()
            new_media_fit = dialog.media_mode_combo.currentIndex()
            new_layer = dialog.layer_combo.currentIndex()
            new_lock = dialog.lock_cb.isChecked()
            new_mute = dialog.mute_checkbox.isChecked()
            new_gpu_guard = dialog.gpu_guard_checkbox.isChecked()


            s_obj.setValue("layer_mode", new_layer)
            s_obj.setValue("layer_schema_version", int(DesktopWidget.LAYER_SCHEMA_VERSION))
            s_obj.setValue("is_locked", bool(new_lock))
            s_obj.setValue("folder_path", new_folder)
            s_obj.setValue("exec_path", new_exec)
            s_obj.setValue("w", new_w); s_obj.setValue("h", new_h)
            s_obj.setValue("opacity_pct", new_opacity)
            s_obj.setValue("bg_color_mode", new_bg)
            s_obj.setValue("corner_mode", int(new_corner))
            s_obj.setValue("media_fit_mode", int(new_media_fit))
            s_obj.setValue("interval", new_interval // 1000)
            s_obj.setValue("is_muted", bool(new_mute))
            s_obj.setValue("gpu_guard_enabled", bool(new_gpu_guard))
            s_obj.sync()


            if is_running:
                w = self.widgets[pid]
                

                if w.width() != new_w or w.height() != new_h:
                    w.resize(new_w, new_h)
                
                w.current_opacity_pct = new_opacity
                w.setWindowOpacity(new_opacity / 100.0)
                
                w.bg_color_mode = new_bg
                w.corner_mode = int(new_corner)
                w.media_fit_mode = int(new_media_fit)
                w.apply_mask_and_style()

                w.apply_window_settings(new_layer, new_lock)

                w.exec_path = new_exec
                w.is_muted = new_mute
                w._apply_mute_state()
                w.gpu_guard_enabled = bool(new_gpu_guard)
                if not w.gpu_guard_enabled:
                    w.set_performance_paused(False, reason="guard_disabled")
                elif self._gpu_guard_paused:
                    w.set_performance_paused(True, reason=f"gpu {self._gpu_last_usage:.1f}%", force=True)


                old_folder = w.folder_path
                w.folder_path = new_folder
                w._set_watched_folder(new_folder)
                w.interval_ms = new_interval

                if old_folder != new_folder:

                    w.update_playlist()
                    w.current_idx = -1
                    w.next_media()
                else:
                    if hasattr(w, "_apply_media_scale_mode"):
                        w._apply_media_scale_mode()

                    if w.timer.isActive():
                        w.timer.setInterval(new_interval)
                    



            self.load_profiles()
        
        else:

            if is_running:
                self.widgets[pid].setWindowOpacity(self.widgets[pid].current_opacity_pct / 100.0)

    def _set_hovered_profile_row(self, pid):
        next_pid = str(pid) if pid not in (None, "") else None
        if getattr(self, "_hovered_profile_pid", None) == next_pid:
            return
        self._hovered_profile_pid = next_pid
        for row_pid, row in self.profile_rows.items():
            if isinstance(row, ProfileRowWidget):
                row.set_hovered(row_pid == next_pid)

    def _on_profile_item_entered(self, item):
        raw_pid = item.data(Qt.ItemDataRole.UserRole)
        self._set_hovered_profile_row(raw_pid)

    def highlight_widget(self, item):
        """리스트 아이템 클릭 시 해당 위젯만 강조"""
        raw_pid = item.data(Qt.ItemDataRole.UserRole)
        if raw_pid in (None, ""):
            self.clear_all_highlights()
            return
        target_pid = str(raw_pid)
        
        for pid, widget in self.widgets.items():
            if str(pid) == target_pid:
                widget.show_selection(True)
            else:
                widget.show_selection(False)

        for pid in self.profile_rows.keys():
            self._set_profile_row_selected(pid, pid == target_pid)

    def clear_all_highlights(self):
        """모든 위젯의 강조 레이어 제거"""
        for widget in self.widgets.values():
            widget.show_selection(False)
        for pid in self.profile_rows.keys():
            self._set_profile_row_selected(pid, False)
        self.list_widget.clearSelection()

    def handle_focus_change(self, old, new):
        """컨트롤러 외부나 리스트 외의 곳을 클릭하면 강조 해제"""

        if new is None:
            self.clear_all_highlights()

    def mousePressEvent(self, event):
        self.clear_all_highlights()
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "gpu_cfg_panel") and self.gpu_cfg_panel.isVisible():
            self._place_gpu_cfg_panel()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "gpu_cfg_panel") and self.gpu_cfg_panel.isVisible():
            self._place_gpu_cfg_panel()

    def _move_master_near_anchor(self, anchor_rect):
        if not isinstance(anchor_rect, QRect):
            return

        anchor = QRect(anchor_rect)
        screen = QGuiApplication.screenAt(anchor.center()) or self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return

        ag = screen.availableGeometry()
        gap = 12
        margin = 8
        w = max(100, int(self.width()))
        h = max(100, int(self.height()))

        # Prefer right side of settings dialog; fallback to left when out of bounds.
        x = int(anchor.right()) + gap
        y = int(anchor.top())
        if x + w > int(ag.right()) - margin:
            x = int(anchor.left()) - gap - w

        min_x = int(ag.left()) + margin
        max_x = int(ag.right()) - w - margin
        min_y = int(ag.top()) + margin
        max_y = int(ag.bottom()) - h - margin

        x = max(min_x, min(int(x), max_x))
        y = max(min_y, min(int(y), max_y))
        self.move(int(x), int(y))

    def show_master_window(self, anchor_rect=None, restart=False):
        """컨트롤러를 보이게 하고 필요 시 앵커 옆에 재배치한다."""
        if bool(restart) and self.isVisible():
            self.hide()
            try:
                QApplication.processEvents()
            except Exception:
                pass

        self.showNormal()
        if isinstance(anchor_rect, QRect):
            self._move_master_near_anchor(anchor_rect)
        self.show()
        self.raise_()
        self.activateWindow()

    def _widget_under_global_pos(self, global_pos):
        candidates = []
        for w in self.widgets.values():
            if not isinstance(w, QWidget) or not w.isVisible():
                continue
            if w.geometry().contains(global_pos):
                layer = int(getattr(w, "layer_mode", DesktopWidget.LAYER_NORMAL))
                candidates.append((layer, int(w.winId()), w))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]

    def _poll_alt_click_toggle_lock(self):
        try:
            alt_down = bool(win32api.GetAsyncKeyState(win32con.VK_MENU) & 0x8000)
            left_down = bool(win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
            chord_down = alt_down and left_down

            if chord_down and not self._alt_click_pressed_prev:
                cursor_x, cursor_y = win32api.GetCursorPos()
                target = self._widget_under_global_pos(QPoint(int(cursor_x), int(cursor_y)))
                if target is not None:
                    new_lock = not bool(getattr(target, "is_locked", False))
                    if hasattr(self, "set_temp_group_lock"):
                        self.set_temp_group_lock(target.profile_id, new_lock)
                    else:
                        if hasattr(target, "cancel_active_interaction"):
                            target.cancel_active_interaction()
                        target.apply_window_settings(int(getattr(target, "layer_mode", DesktopWidget.LAYER_NORMAL)), new_lock)
                        target.save_all_settings()
                    self.load_profiles()
                    print(f"[alt-click-lock] profile={target.profile_id} lock={new_lock}")

            self._alt_click_pressed_prev = chord_down
        except Exception:
            # Keep polling robust even if key-state API fails transiently.
            self._alt_click_pressed_prev = False

    def _gpu_guard_targets(self):
        return [
            w for w in self.widgets.values()
            if isinstance(w, DesktopWidget) and bool(getattr(w, "gpu_guard_enabled", False))
        ]

    def _set_gpu_guard_paused(self, paused, usage, reason="", force_targets=False):
        self._gpu_guard_paused = bool(paused)
        self._gpu_last_usage = float(usage)

        targets = set(self._gpu_guard_targets())
        for w in self.widgets.values():
            if not isinstance(w, DesktopWidget):
                continue
            if w in targets:
                w.set_performance_paused(
                    self._gpu_guard_paused,
                    reason=f"{reason} ({self._gpu_last_usage:.1f}%)" if reason else f"{self._gpu_last_usage:.1f}%",
                    force=bool(force_targets and self._gpu_guard_paused),
                )
            else:
                w.set_performance_paused(False, reason="guard_not_target")

    def _poll_gpu_guard(self):
        targets = self._gpu_guard_targets()
        if not targets:
            self._gpu_high_streak = 0
            self._gpu_low_streak = 0
            self._gpu_below_high_streak = 0
            if self._gpu_guard_paused:
                self._set_gpu_guard_paused(False, self._gpu_last_usage, reason="targets_empty")
            return

        usage = self._gpu_sampler.sample_pct()
        if usage is None:
            return
        self._gpu_last_usage = float(usage)

        if not self._gpu_guard_paused:
            if usage >= self._gpu_guard_high_pct:
                self._gpu_high_streak += 1
            else:
                self._gpu_high_streak = 0
            self._gpu_low_streak = 0
            self._gpu_below_high_streak = 0

            if self._gpu_high_streak >= self._gpu_guard_high_hold:
                self._gpu_high_streak = 0
                self._set_gpu_guard_paused(True, usage, reason="gpu_high", force_targets=True)
        else:
            # Keep newly enabled targets in paused state while guard is active.
            self._set_gpu_guard_paused(True, usage, reason="gpu_guard_active", force_targets=False)
            if usage <= self._gpu_guard_low_pct:
                self._gpu_low_streak += 1
            else:
                self._gpu_low_streak = 0
            if usage < self._gpu_guard_high_pct:
                self._gpu_below_high_streak += 1
            else:
                self._gpu_below_high_streak = 0
            self._gpu_high_streak = 0

            if self._gpu_low_streak >= self._gpu_guard_low_hold:
                self._gpu_low_streak = 0
                self._gpu_below_high_streak = 0
                self._set_gpu_guard_paused(False, usage, reason="gpu_recovered")
            elif self._gpu_below_high_streak >= max(6, self._gpu_guard_low_hold * 3):
                # Fallback: avoid "stuck paused" when low threshold is set too aggressively.
                self._gpu_low_streak = 0
                self._gpu_below_high_streak = 0
                self._set_gpu_guard_paused(False, usage, reason="gpu_recovered_soft")

    def add_profile(self):
        p_ids = self._all_profile_ids()
        new_id = self._next_profile_id(p_ids)
        p_ids.append(new_id)

        new_settings = QSettings("MyHomeApp", f"Profile_{new_id}")
        new_settings.setValue("name", "New 세팅")
        new_settings.setValue("w", 200)
        new_settings.setValue("h", 200)
        new_settings.setValue("layer_mode", int(DesktopWidget.LAYER_BACK))
        new_settings.setValue("layer_schema_version", int(DesktopWidget.LAYER_SCHEMA_VERSION))
        new_settings.setValue("corner_mode", 0)
        new_settings.setValue("media_fit_mode", 0)
        new_settings.setValue("run_enabled", True)
        new_settings.sync()

        self.master_settings.setValue("profile_ids", p_ids)
        sid = self.selected_set_id()
        if sid not in self._set_defs and self._set_order:
            sid = self._set_order[0]
        if sid in self._set_defs:
            profiles = list(self._set_defs[sid].get("profiles", []))
            profiles = [new_id] + [pid for pid in profiles if pid != new_id]
            self._set_defs[sid]["profiles"] = profiles
            self.master_settings.setValue(self._set_key(sid, "profiles"), profiles)
        self.master_settings.sync()
        self.run_widget(new_id, "New 세팅")

    def run_widget(self, pid, name):
        spid = str(pid)
        self._set_profile_run_enabled(spid, True)
        if spid not in self.widgets:
            display_name = name if name not in (None, "") else QSettings(
                "MyHomeApp", f"Profile_{spid}"
            ).value("name", "New 세팅")
            self._start_widget_instance(spid, str(display_name))
        self.update_active_status()
        self.load_profiles()

    def stop_widget(self, pid):
        spid = str(pid)
        self._set_profile_run_enabled(spid, False)
        if spid in self._temp_group_ids:
            self._temp_group_ids.remove(spid)
        if spid in self.widgets:
            widget = self.widgets[spid]
            widget.close()
            widget.deleteLater()
            del self.widgets[spid]
        self._sync_temp_group_badges()
        self.update_active_status()
        self.load_profiles()

    def restore_last_session(self):
        self._load_set_state()
        sid = self.selected_set_id()
        if not sid and self._set_order:
            sid = self._set_order[0]
        if sid:
            self.apply_set(sid)


        # Startup visibility policy:
        # - hide controller if at least one widget was restored
        # - show controller if no widget exists to run
        if self.widgets:
            self.hide()
        else:
            self.show()

    def run_all(self):
        sid = self.selected_set_id()
        if sid:
            self.apply_set(sid)

    def delete_profile(self, pid):
        spid = str(pid)
        confirm = QMessageBox.question(self, "삭제 확인", "이 세팅을 완전히 삭제하시겠습니까?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            if spid in self._temp_group_ids:
                self._temp_group_ids.remove(spid)
            if spid in self.widgets:
                widget = self.widgets[spid]
                widget.close()
                widget.deleteLater()
                del self.widgets[spid]
            prof_settings = QSettings("MyHomeApp", f"Profile_{spid}")
            prof_settings.clear()
            prof_settings.sync()
            p_ids = self._all_profile_ids()
            if spid in p_ids:
                p_ids.remove(spid)
                self.master_settings.setValue("profile_ids", p_ids)
            self._remove_profile_from_sets(spid)
            self.master_settings.sync()
            self._sync_temp_group_badges()
            self.update_active_status()
            self.load_profiles()

    def closeEvent(self, event):
        if hasattr(self, "gpu_cfg_panel") and self.gpu_cfg_panel.isVisible():
            self.gpu_cfg_panel.hide()
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

    def quit_app(self):
        if hasattr(self, "_alt_click_poll_timer"):
            self._alt_click_poll_timer.stop()
        if hasattr(self, "_gpu_guard_timer"):
            self._gpu_guard_timer.stop()
        if hasattr(self, "_gpu_sampler"):
            self._gpu_sampler.close()
        self.clear_temp_group(silent=True)
        for w in list(self.widgets.values()):
            w.close()
        QTimer.singleShot(450, self._finalize_quit)

    def _finalize_quit(self):
        try:
            self._load_set_state()
            self._cleanup_orphan_profiles()
        except Exception as e:
            print(f"[orphan-cleanup] failed: {e}")
        app = QApplication.instance()
        if app:
            app.quit()

    def rename_profile(self, item):
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid in (None, ""):
            return
        current_name = QSettings("MyHomeApp", f"Profile_{pid}").value("name", "New 세팅")
        dialog = QInputDialog(self)
        dialog.setWindowTitle("이름 변경")
        dialog.setMinimumSize(250, 190)
        dialog.resize(250, 190)
        dialog.setLabelText("세팅 이름을 입력하세요:")
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setTextValue(str(current_name))
        dialog.setOkButtonText("저장")
        dialog.setCancelButtonText("취소")
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #23344d;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLineEdit {
                min-height: 30px;
                min-width: 0px;
                color: #edf3ff;
                background-color: #1a2740;
                border: 1px solid #4a6288;
                border-radius: 8px;
                padding: 2px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #77a3f2;
            }
            QPushButton {
                min-height: 30px;
                border-radius: 8px;
                padding: 0 12px;
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3f5e8e;
            }
        """)
        QTimer.singleShot(0, lambda d=dialog: self._apply_window_title_bar_theme(d))

        if dialog.exec():
            new_name = dialog.textValue().strip()
            if new_name:
                QSettings("MyHomeApp", f"Profile_{pid}").setValue("name", new_name)
                self.load_profiles()

    def update_active_status(self):
        """현재 켜져 있는 위젯들의 ID 목록을 저장"""
        active_ids = [str(pid) for pid in self.widgets.keys()]
        self.master_settings.setValue("active_profiles", active_ids)
        self.master_settings.sync()


if __name__ == "__main__":

    sys.excepthook = lambda cls, exception, traceback: sys.__excepthook__(cls, exception, traceback)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    master = MasterController()
    # Avoid initial flash before restore_last_session decides visibility.
    master.hide()
        
    try:
        sys.exit(app.exec())
    except Exception as e:
        print("CRITICAL ERROR:", e)
        import traceback
        traceback.print_exc()
        input("엔터를 누르면 종료합니다...") # 에러 확인을 위해 잠시 멈춤



