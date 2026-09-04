from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QRect, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDial,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QSlider,
    QWidget,
)


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

    def wheelEvent(self, event):
        # 팝업 드롭다운이 열려있는 상태에서는 목록 스크롤 허용, 닫혀있을 때는 휠로 인한 선택 변경 방지
        if self.view() and self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


class PreventInputWheelScrollFilter(QObject):
    """
    QSpinBox, QSlider, QComboBox 등 입력 컨트롤 위에서 마우스 휠을 굴렸을 때
    숫자나 선택값이 의도치 않게 변경되거나 상위 QScrollArea 스크롤이 차단되는 현상을
    원천 방지하는 이벤트 필터.
    휠 이벤트를 부모 QScrollArea의 viewport로 토스하여 끊김 없는 페이지 스크롤을 유지합니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._handling = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if self._handling:
                return False

            # 콤보박스 드롭다운 목록이 열려있을 때는 목록 자체 스크롤 정상 허용
            if isinstance(obj, QComboBox):
                if hasattr(obj, "view"):
                    v = obj.view()
                    if v and v.isVisible():
                        return False

            is_input = (
                isinstance(obj, (QAbstractSpinBox, QSlider, QDial, QComboBox))
                or (isinstance(obj, QLineEdit) and isinstance(obj.parentWidget(), QAbstractSpinBox))
            )
            if is_input:
                self._handling = True
                try:
                    # 상위 스크롤 영역을 찾아 viewport로 휠 이벤트 전달
                    p = obj.parentWidget()
                    while p is not None:
                        if isinstance(p, QAbstractScrollArea):
                            QCoreApplication.sendEvent(p.viewport(), event)
                            return True
                        p = p.parentWidget()
                    # 상위 스크롤 영역이 없더라도 휠로 인한 값 변경은 차단
                    return True
                finally:
                    self._handling = False
        return super().eventFilter(obj, event)


class TreeBranchLine(QWidget):
    """
    부모-자식 계층을 시각적으로 이어주는 들여쓰기 트리 브랜치 가이드 라인 위젯
    (is_last: 마지막 자식일 때는 L자형, 중간 자식일 때는 ├자형)
    """
    def __init__(self, is_last=False, parent=None):
        super().__init__(parent)
        self._is_last = bool(is_last)
        self.setFixedWidth(22)

    def set_is_last(self, is_last):
        self._is_last = bool(is_last)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#3d567c"), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        mid_x = 10
        mid_y = int(self.height() / 2)

        # Vertical line from top
        painter.drawLine(mid_x, 0, mid_x, mid_y if self._is_last else self.height())
        # Horizontal branch to the right
        painter.drawLine(mid_x, mid_y, self.width(), mid_y)
        painter.end()


class ProfileRowWidget(QFrame):
    clicked = pyqtSignal(str)
    doubleClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self._selected = False
        self._action_buttons = []
        self._pid = ""
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

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            if self._pid:
                self.doubleClicked.emit(self._pid)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            action_wrap = getattr(self, "_action_wrap", None)
            cb = getattr(self, "_checkbox", None)
            if action_wrap and action_wrap.isVisible() and action_wrap.geometry().contains(pos):
                return
            if cb and cb.geometry().contains(pos):
                return
            if cb:
                cb.setChecked(not cb.isChecked())
            if self._pid:
                self.clicked.emit(self._pid)


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


class MarqueeSelectionOverlay(QWidget):
    """마우스 드래그 영역(박스)으로 위젯들을 일괄 임시 그룹화하는 전역 투명 오버레이 창"""
    def __init__(self, manager=None):
        super().__init__(None)
        self.manager = manager
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.start_pos = None
        self.current_pos = None

    def start_selection(self, global_start_pos):
        screens = QApplication.screens()
        if not screens:
            return
        combined = QRect()
        for s in screens:
            combined = combined.united(s.geometry())
        self.setGeometry(combined)

        self.start_pos = global_start_pos
        self.current_pos = global_start_pos
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabMouse()
        self.update()

    def mouseMoveEvent(self, e):
        self.current_pos = e.globalPosition().toPoint()
        self.update()

    def mouseReleaseEvent(self, e):
        self.releaseMouse()
        self.hide()
        if self.start_pos and self.current_pos:
            rect = QRect(self.start_pos, self.current_pos).normalized()
            if self.manager and hasattr(self.manager, "finish_marquee_selection"):
                self.manager.finish_marquee_selection(rect)
        self.start_pos = None
        self.current_pos = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.releaseMouse()
            self.hide()
            self.start_pos = None
            self.current_pos = None
        super().keyPressEvent(e)

    def paintEvent(self, e):
        if not self.start_pos or not self.current_pos:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        local_start = self.mapFromGlobal(self.start_pos)
        local_curr = self.mapFromGlobal(self.current_pos)
        rect = QRect(local_start, local_curr).normalized()

        if rect.width() <= 1 and rect.height() <= 1:
            return

        fill_color = QColor(64, 158, 255, 40)
        border_pen = QPen(QColor(80, 175, 255, 230), 1.5, Qt.PenStyle.DashLine)
        border_pen.setDashPattern([5, 3])

        painter.setBrush(QBrush(fill_color))
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, 4, 4)


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = str(text or "")
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(30)
        self.setToolTip(self._full_text)

    def setText(self, text):
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self.update()

    def text(self):
        return self._full_text

    def paintEvent(self, event):
        painter = QPainter(self)
        fm = self.fontMetrics()
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, max(10, self.width()))
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        painter.drawText(self.rect(), int(self.alignment()), elided)

