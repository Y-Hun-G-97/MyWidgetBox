from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPolygon
from PyQt6.QtWidgets import QComboBox, QFrame, QLabel, QListWidget, QWidget
from PyQt6.QtCore import QThread


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


class MediaToolWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, func, kwargs=None, parent=None):
        super().__init__(parent)
        self._func = func
        self._kwargs = dict(kwargs or {})

    def run(self):
        try:
            result = self._func(**self._kwargs)
            if not isinstance(result, dict):
                result = {}
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
