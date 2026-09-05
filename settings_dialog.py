import os
import time

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from mywidgetbox_core import _as_bool, calc_smart_aspect_size, get_media_native_size
from mywidgetbox_ui_primitives import DownwardComboBox, PreventInputWheelScrollFilter

DesktopWidget = None


DesktopWidget = None


def bind_settings_dialog_desktop_widget(desktop_widget_cls):
    global DesktopWidget
    DesktopWidget = desktop_widget_cls


class FolderLayoutChoiceDialog(QDialog):
    def __init__(self, parent=None, folder_path=""):
        super().__init__(parent)
        from mywidgetbox_core import apply_windows_dark_title_bar, render_vector_icon

        self.setObjectName("folderLayoutChoiceDialog")
        self.setWindowTitle("미디어 폴더 추가 방식 선택")
        self.setWindowIcon(render_vector_icon("folder", "#528bf8", 32))
        self.setFixedWidth(460)
        self.choice = None
        self.folder_path = str(folder_path or "").strip()

        self.setStyleSheet("""
            QDialog#folderLayoutChoiceDialog {
                background-color: #162233;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLabel#dialogTitle {
                color: #eef3ff;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#dialogDesc {
                color: #b7cceb;
                font-size: 12px;
            }
            QLabel#folderPathLabel {
                color: #9cbfe8;
                font-size: 11px;
                background-color: #162233;
                border: 1px solid #324765;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton.choiceBtn {
                min-height: 48px;
                border-radius: 9px;
                padding: 8px 14px;
                color: #ffffff;
                background-color: #2b4366;
                border: 1px solid #4a6c9a;
                font-weight: 600;
                font-size: 13px;
                text-align: left;
            }
            QPushButton.choiceBtn:hover {
                background-color: #385684;
                border-color: #638ec7;
            }
            QPushButton#cancelBtn {
                min-height: 32px;
                border-radius: 7px;
                padding: 0 16px;
                color: #d1ddf0;
                background-color: #26364d;
                border: 1px solid #415675;
                font-size: 12px;
            }
            QPushButton#cancelBtn:hover {
                background-color: #314663;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 20)
        layout.setSpacing(14)

        title = QLabel("미디어 폴더 추가 방식")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        desc = QLabel("선택한 폴더의 미디어를 어떻게 표시할지 선택하세요.")
        desc.setObjectName("dialogDesc")
        layout.addWidget(desc)

        if self.folder_path:
            folder_lbl = QLabel(self.folder_path)
            folder_lbl.setObjectName("folderPathLabel")
            folder_lbl.setWordWrap(True)
            layout.addWidget(folder_lbl)

        layout.addSpacing(4)

        slide_btn = QPushButton("▶  슬라이드쇼 방식 (기존)\n   1개 위젯에서 폴더 내 미디어를 순차적으로 전환 재생")
        slide_btn.setProperty("class", "choiceBtn")
        slide_btn.clicked.connect(self._choose_slide)
        layout.addWidget(slide_btn)

        spread_btn = QPushButton("⊞  스프레드 방식 (바둑판식 배열)\n   미디어마다 개별 위젯을 생성하여 바둑판식으로 화면에 나열")
        spread_btn.setProperty("class", "choiceBtn")
        spread_btn.clicked.connect(self._choose_spread)
        layout.addWidget(spread_btn)

        layout.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(self))

    def _choose_slide(self):
        self.choice = "slide"
        self.accept()

    def _choose_spread(self):
        self.choice = "spread"
        self.accept()


_IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
_GIF_EXTS = ('.gif',)
_VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')


def _classify_media(path):
    ext = os.path.splitext(str(path))[1].lower()
    if ext in _GIF_EXTS:
        return "gif"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _IMAGE_EXTS:
        return "image"
    return "other"


class FolderSlideDialog(QDialog):
    def __init__(self, parent=None, folder_path="", media_paths=None, pre_selected_paths=None):
        super().__init__(parent)
        from mywidgetbox_core import apply_windows_dark_title_bar, render_vector_icon

        self.setObjectName("folderSlideDialog")
        self.setWindowTitle("슬라이드 미디어 선택")
        self.setWindowIcon(render_vector_icon("media", "#528bf8", 32))
        self.resize(560, 580)
        self.setFixedWidth(560)
        self.folder_path = str(folder_path or "").strip()
        self.media_paths = [str(p) for p in (media_paths or []) if p and os.path.isfile(p)]
        self.pre_selected_paths = list(pre_selected_paths) if pre_selected_paths is not None else None
        self._pre_set = set(os.path.normcase(os.path.normpath(p)) for p in self.pre_selected_paths) if self.pre_selected_paths is not None else None
        self.result_paths = None
        self._current_filter = "all"
        self._filter_btns = {}

        img_count = sum(1 for p in self.media_paths if _classify_media(p) == "image")
        gif_count = sum(1 for p in self.media_paths if _classify_media(p) == "gif")
        vid_count = sum(1 for p in self.media_paths if _classify_media(p) == "video")
        all_count = len(self.media_paths)

        self.setStyleSheet("""
            QDialog#folderSlideDialog {
                background-color: #162233;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLabel#dialogTitle {
                color: #eef4ff;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#dialogSubtitle {
                color: #a4bedc;
                font-size: 12px;
            }
            QLabel#sectionHeader {
                color: #92bbf8;
                font-size: 12px;
                font-weight: 700;
            }
            QListWidget {
                color: #edf3ff;
                background-color: #111a28;
                border: 1px solid #283a54;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                min-height: 28px;
                padding: 2px 6px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #1a2a40;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 8px;
                padding: 0 12px;
                color: #e8efff;
                background-color: #2b3e5b;
                border: 1px solid #48648c;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #385075;
                border-color: #5d7fae;
                color: #ffffff;
            }
            QPushButton[kind="filterBtn"] {
                min-height: 28px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
                border-radius: 6px;
                background-color: #1f3047;
                border: 1px solid #364e6f;
                color: #cddbf0;
            }
            QPushButton[kind="filterBtn"]:hover {
                background-color: #2b4363;
                color: #ffffff;
            }
            QPushButton[kind="filterBtn"][active="true"] {
                background-color: #4a74e2;
                border-color: #7296f0;
                color: #ffffff;
            }
            QPushButton#primaryBtn {
                background-color: #4872d4;
                border: 1px solid #7397ea;
                font-size: 13px;
                font-weight: 700;
                min-height: 34px;
                padding: 0 18px;
            }
            QPushButton#primaryBtn:hover {
                background-color: #5882e6;
            }
            QPushButton#secondaryBtn {
                min-height: 28px;
                padding: 0 10px;
                font-size: 11px;
                background-color: #1f3047;
                border: 1px solid #364e6f;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #2b4363;
                color: #ffffff;
            }
            QLabel#statusLabel {
                color: #8cc3ff;
                font-weight: 600;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title = QLabel("슬라이드 재생 미디어 선택")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("위젯에서 순차적으로 재생할 미디어 파일들을 선택하세요.")
        subtitle.setObjectName("dialogSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col, 1)

        self.open_folder_btn = QPushButton("폴더 열기")
        self.open_folder_btn.setObjectName("secondaryBtn")
        self.open_folder_btn.setIcon(render_vector_icon("folder", "#cddbf0", 14))
        self.open_folder_btn.setIconSize(QSize(14, 14))
        self.open_folder_btn.setToolTip("탐색기에서 해당 폴더를 엽니다.")
        self.open_folder_btn.clicked.connect(self._open_folder_in_explorer)
        header_row.addWidget(self.open_folder_btn, 0)
        layout.addLayout(header_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        filter_label = QLabel("필터:")
        filter_label.setObjectName("sectionHeader")
        filter_row.addWidget(filter_label)

        for cat_key, cat_name, cat_cnt in [
            ("all", f"전체 ({all_count})", all_count),
            ("image", f"이미지 ({img_count})", img_count),
            ("gif", f"GIF ({gif_count})", gif_count),
            ("video", f"영상 ({vid_count})", vid_count),
        ]:
            btn = QPushButton(cat_name)
            btn.setProperty("kind", "filterBtn")
            btn.setProperty("active", "true" if cat_key == "all" else "false")
            if cat_cnt == 0:
                btn.setEnabled(False)
            btn.clicked.connect(lambda _, k=cat_key: self._apply_filter(k))
            self._filter_btns[cat_key] = btn
            filter_row.addWidget(btn)

        filter_row.addStretch(1)
        select_all_btn = QPushButton("전체 선택")
        select_all_btn.setObjectName("secondaryBtn")
        clear_btn = QPushButton("선택 해제")
        clear_btn.setObjectName("secondaryBtn")
        filter_row.addWidget(select_all_btn)
        filter_row.addWidget(clear_btn)
        layout.addLayout(filter_row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for path in self.media_paths:
            cat = _classify_media(path)
            prefix = "[IMG] " if cat == "image" else ("[GIF] " if cat == "gif" else "[VID] ")
            item = QListWidgetItem(f"{prefix}{os.path.basename(path)}")
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, cat)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if self._pre_set is not None:
                norm_p = os.path.normcase(os.path.normpath(path))
                item.setCheckState(Qt.CheckState.Checked if norm_p in self._pre_set else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        cancel_btn = QPushButton("취소")
        apply_btn = QPushButton("슬라이드 적용")
        apply_btn.setObjectName("primaryBtn")
        action_row.addWidget(cancel_btn)
        action_row.addWidget(apply_btn)
        layout.addLayout(action_row)

        select_all_btn.clicked.connect(lambda: self._set_filtered_checked(True))
        clear_btn.clicked.connect(lambda: self._set_filtered_checked(False))
        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self._accept_if_valid)

        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemChanged.connect(lambda _item: self._refresh_status())
        self._refresh_status()

        QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(self))

    def _open_folder_in_explorer(self):
        if self.folder_path and os.path.isdir(self.folder_path):
            try:
                os.startfile(self.folder_path)
            except Exception:
                pass

    def _on_item_clicked(self, item):
        state = item.checkState()
        item.setCheckState(Qt.CheckState.Unchecked if state == Qt.CheckState.Checked else Qt.CheckState.Checked)

    def _apply_filter(self, category):
        self._current_filter = str(category)
        for cat_key, btn in self._filter_btns.items():
            btn.setProperty("active", "true" if cat_key == self._current_filter else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            cat = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
            if self._current_filter == "all" or cat == self._current_filter:
                item.setHidden(False)
            else:
                item.setHidden(True)
        self._refresh_status()

    def _set_filtered_checked(self, checked):
        state = Qt.CheckState.Checked if bool(checked) else Qt.CheckState.Unchecked
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if not item.isHidden():
                item.setCheckState(state)
        self._refresh_status()

    def _checked_paths(self):
        paths = []
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                paths.append(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        return [p for p in paths if p]

    def _refresh_status(self):
        selected = len(self._checked_paths())
        total = len(self.media_paths)
        self.status_label.setText(f"선택 {selected}개 / 전체 {total}개")
        self.status_label.setStyleSheet("color: #8cc3ff; font-weight: 600;")

    def _accept_if_valid(self):
        paths = self._checked_paths()
        if not paths:
            QMessageBox.warning(self, "슬라이드 미디어", "슬라이드로 재생할 미디어를 하나 이상 선택해주세요.")
            return
        self.result_paths = paths
        self.accept()


class FolderSpreadDialog(QDialog):
    def __init__(self, parent=None, folder_path="", media_paths=None, current_size=None):
        super().__init__(parent)
        from mywidgetbox_core import apply_windows_dark_title_bar, render_vector_icon

        self.setObjectName("folderSpreadDialog")
        self.setWindowTitle("스프레드(바둑판) 위젯 배치 설정")
        self.setWindowIcon(render_vector_icon("widget", "#528bf8", 32))
        self.resize(720, 720)
        self.setFixedWidth(720)
        self._wheel_filter = PreventInputWheelScrollFilter(self)
        self.installEventFilter(self._wheel_filter)
        self.folder_path = str(folder_path or "").strip()
        self.media_paths = [str(p) for p in (media_paths or []) if p and os.path.isfile(p)]
        self.result_data = None
        self._current_filter = "all"
        self._filter_btns = {}

        default_w = 200
        default_h = 200
        if current_size and hasattr(current_size, "width") and hasattr(current_size, "height"):
            if current_size.width() > 50:
                default_w = int(current_size.width())
            if current_size.height() > 50:
                default_h = int(current_size.height())

        count = len(self.media_paths)
        import math
        init_cols = max(1, math.ceil(math.sqrt(count))) if count > 0 else 2
        init_rows = max(1, math.ceil(count / init_cols)) if count > 0 else 2

        img_count = sum(1 for p in self.media_paths if _classify_media(p) == "image")
        gif_count = sum(1 for p in self.media_paths if _classify_media(p) == "gif")
        vid_count = sum(1 for p in self.media_paths if _classify_media(p) == "video")
        all_count = len(self.media_paths)

        self.setStyleSheet("""
            QDialog#folderSpreadDialog {
                background-color: #162233;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLabel#dialogTitle {
                color: #eef4ff;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#dialogSubtitle {
                color: #a4bedc;
                font-size: 12px;
            }
            QLabel#sectionHeader {
                color: #92bbf8;
                font-size: 12px;
                font-weight: 700;
            }
            QFrame#cardFrame {
                background-color: #1d2c42;
                border: 1px solid #2e4466;
                border-radius: 12px;
                padding: 10px;
            }
            QSpinBox {
                min-height: 32px;
                color: #ffffff;
                background-color: #121c2b;
                border: 1.5px solid #2e4466;
                border-radius: 8px;
                padding: 2px 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QSpinBox:disabled {
                color: #4a617e;
                background-color: #0c1420;
                border: 1px dashed #203147;
            }
            QLabel:disabled {
                color: #4a617e;
            }
            QLabel#unitLabel {
                color: #b7cceb;
                font-weight: 700;
                font-size: 13px;
            }
            QLabel#unitLabel:disabled {
                color: #3b4f66;
            }
            QSpinBox:hover {
                border-color: #3d587d;
                background-color: #152438;
            }
            QSpinBox:focus {
                border: 1.5px solid #528bf8;
                background-color: #17283f;
            }
            QSpinBox::up-button,
            QSpinBox::down-button {
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }
            QSpinBox::up-arrow,
            QSpinBox::down-arrow {
                width: 0px;
                height: 0px;
                image: none;
            }
            QComboBox {
                min-height: 32px;
                color: #eaf1fc;
                background-color: #24364f;
                border: 1px solid #3d5578;
                border-radius: 8px;
                padding: 2px 28px 2px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QComboBox:hover {
                background-color: #2d4361;
                border-color: #52739e;
            }
            QComboBox:focus {
                border: 1.5px solid #528bf8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #334866;
                background: transparent;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9bb5d8;
                margin-right: 4px;
            }
            QComboBox::down-arrow:hover {
                border-top-color: #ffffff;
            }
            QComboBox QAbstractItemView {
                background-color: #21324a;
                color: #eef4ff;
                border: 1px solid #3d587d;
                border-radius: 6px;
                selection-background-color: #3f5e8e;
                selection-color: #ffffff;
                outline: 0;
                font-size: 12px;
            }
            QListWidget {
                color: #edf3ff;
                background-color: #111a28;
                border: 1px solid #283a54;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                min-height: 28px;
                padding: 2px 6px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #1a2a40;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 8px;
                padding: 0 12px;
                color: #e8efff;
                background-color: #2b3e5b;
                border: 1px solid #48648c;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #385075;
                border-color: #5d7fae;
                color: #ffffff;
            }
            QPushButton[kind="filterBtn"] {
                min-height: 28px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
                border-radius: 6px;
                background-color: #1f3047;
                border: 1px solid #364e6f;
                color: #cddbf0;
            }
            QPushButton[kind="filterBtn"]:hover {
                background-color: #2b4363;
                color: #ffffff;
            }
            QPushButton[kind="filterBtn"][active="true"] {
                background-color: #4a74e2;
                border-color: #7296f0;
                color: #ffffff;
            }
            QPushButton#primaryBtn {
                background-color: #4872d4;
                border: 1px solid #7397ea;
                font-size: 13px;
                font-weight: 700;
                min-height: 34px;
                padding: 0 18px;
            }
            QPushButton#primaryBtn:hover {
                background-color: #5882e6;
            }
            QPushButton#secondaryBtn {
                min-height: 28px;
                padding: 0 10px;
                font-size: 11px;
                background-color: #1f3047;
                border: 1px solid #364e6f;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #2b4363;
                color: #ffffff;
            }
            QLabel#statusLabel {
                color: #8cc3ff;
                font-weight: 600;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title = QLabel("스프레드(바둑판) 위젯 배치 설정")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("폴더 내 미디어들을 바둑판 형태로 한 번에 배치합니다.")
        subtitle.setObjectName("dialogSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col, 1)

        self.open_folder_btn = QPushButton("폴더 열기")
        self.open_folder_btn.setObjectName("secondaryBtn")
        self.open_folder_btn.setIcon(render_vector_icon("folder", "#cddbf0", 14))
        self.open_folder_btn.setIconSize(QSize(14, 14))
        self.open_folder_btn.setToolTip("탐색기에서 해당 폴더를 엽니다.")
        self.open_folder_btn.clicked.connect(self._open_folder_in_explorer)
        header_row.addWidget(self.open_folder_btn, 0)
        layout.addLayout(header_row)

        # 1. 배치 & 크기 설정 카드
        grid_card = QFrame()
        grid_card.setObjectName("cardFrame")
        grid_layout = QGridLayout(grid_card)
        grid_layout.setContentsMargins(12, 12, 12, 12)
        grid_layout.setHorizontalSpacing(14)
        grid_layout.setVerticalSpacing(10)

        def _make_input_with_unit(spinbox, unit_text):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            spinbox.wheelEvent = lambda event: event.ignore()
            h.addWidget(spinbox, 1)
            unit_lbl = QLabel(unit_text)
            unit_lbl.setObjectName("unitLabel")
            unit_lbl.setStyleSheet("color: #b7cceb; font-weight: 700; font-size: 13px;")
            h.addWidget(unit_lbl, 0)
            w.spinbox = spinbox
            w.unit_lbl = unit_lbl
            w.default_unit = str(unit_text or "")
            return w

        def _set_folder_input_active(wrap, spinbox, label, is_active, auto_text="자동", tooltip=""):
            spinbox.setEnabled(bool(is_active))
            wrap.setEnabled(bool(is_active))
            if label is not None:
                label.setEnabled(bool(is_active))
                label.setToolTip(tooltip if not is_active else "")
            if hasattr(wrap, "unit_lbl"):
                wrap.unit_lbl.setEnabled(bool(is_active))
                if is_active:
                    wrap.unit_lbl.setText(getattr(wrap, "default_unit", "px"))
                    wrap.unit_lbl.setStyleSheet("color: #b7cceb; font-weight: 700; font-size: 13px;")
                else:
                    wrap.unit_lbl.setText(auto_text)
                    wrap.unit_lbl.setStyleSheet("color: #4a617e; font-weight: 600; font-size: 11px;")
            tip = tooltip if not is_active else ""
            wrap.setToolTip(tip)
            spinbox.setToolTip(tip)

        # 위젯 너비 & 높이
        self.lbl_w = QLabel("위젯 너비(W):")
        grid_layout.addWidget(self.lbl_w, 0, 0)
        self.width_input = QSpinBox()
        self.width_input.setRange(50, 4000)
        self.width_input.setValue(default_w)
        self.width_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.width_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.w_wrap = _make_input_with_unit(self.width_input, "px")
        grid_layout.addWidget(self.w_wrap, 0, 1)

        self.lbl_h = QLabel("위젯 높이(H):")
        grid_layout.addWidget(self.lbl_h, 0, 2)
        self.height_input = QSpinBox()
        self.height_input.setRange(50, 4000)
        self.height_input.setValue(default_h)
        self.height_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.height_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.h_wrap = _make_input_with_unit(self.height_input, "px")
        grid_layout.addWidget(self.h_wrap, 0, 3)

        self._syncing_spread_size = False
        def _on_spread_w_changed(val):
            if self._syncing_spread_size or self.fit_combo.currentIndex() != 0:
                return
            self._syncing_spread_size = True
            try:
                self.height_input.setValue(val)
            finally:
                self._syncing_spread_size = False

        self.width_input.valueChanged.connect(_on_spread_w_changed)

        # 행, 열, 간격
        self.lbl_cols = QLabel("가로 열(Cols):")
        grid_layout.addWidget(self.lbl_cols, 1, 0)
        self.cols_input = QSpinBox()
        self.cols_input.setRange(1, 50)
        self.cols_input.setValue(init_cols)
        self.cols_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.cols_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cols_wrap = _make_input_with_unit(self.cols_input, "열")
        grid_layout.addWidget(self.cols_wrap, 1, 1)

        self.lbl_rows = QLabel("세로 행(Rows):")
        grid_layout.addWidget(self.lbl_rows, 1, 2)
        self.rows_input = QSpinBox()
        self.rows_input.setRange(1, 50)
        self.rows_input.setValue(init_rows)
        self.rows_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.rows_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rows_wrap = _make_input_with_unit(self.rows_input, "행")
        grid_layout.addWidget(self.rows_wrap, 1, 3)

        grid_layout.addWidget(QLabel("위젯 간격:"), 2, 0)
        self.margin_input = QSpinBox()
        self.margin_input.setRange(0, 500)
        self.margin_input.setValue(10)
        self.margin_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.margin_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(_make_input_with_unit(self.margin_input, "px"), 2, 1)

        grid_layout.addWidget(QLabel("배경색:"), 2, 2)
        self.bg_combo = DownwardComboBox()
        self.bg_combo.addItems(["투명 (권장)", "검정", "흰색"])
        self.bg_combo.setCurrentIndex(0)
        grid_layout.addWidget(self.bg_combo, 2, 3)

        grid_layout.addWidget(QLabel("모서리 모양:"), 3, 0)
        self.corner_combo = DownwardComboBox()
        self.corner_combo.addItems(["곡선 (둥근)", "직각 (사각)", "원형 (최대)"])
        self.corner_combo.setCurrentIndex(0)
        grid_layout.addWidget(self.corner_combo, 3, 1, 1, 3)

        grid_layout.addWidget(QLabel("비율/맞춤:"), 4, 0)
        self.fit_combo = DownwardComboBox()
        self.fit_combo.addItems([
            "🧩 빈칸 자동 채우기 (자유 비율, 권장)",
            "📏 가로 줄 맞춤 (단정한 앨범형)",
            "📐 세로 줄 맞춤 (세로 짤 돋보임)",
            "🔲 균일 바둑판 (꽉 채움)",
            "🖼️ 균일 바둑판 (원본 비율)",
        ])
        self.fit_combo.setCurrentIndex(0)
        grid_layout.addWidget(self.fit_combo, 4, 1, 1, 3)

        self.auto_calc_hint_lbl = QLabel("✨ 빈칸 자동 채우기: 각 짤의 원래 비율을 살리며, 남는 빈자리에 다음 짤을 쏙쏙 넣어 자연스럽게 채웁니다.")
        self.auto_calc_hint_lbl.setWordWrap(True)
        self.auto_calc_hint_lbl.setStyleSheet("""
            color: #7eb0ff;
            background-color: #15253b;
            border: 1px dashed #3a5c8a;
            border-radius: 7px;
            padding: 6px 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        self.auto_calc_hint_lbl.setVisible(True)
        grid_layout.addWidget(self.auto_calc_hint_lbl, 5, 0, 1, 4)

        def _on_fit_combo_changed(idx):
            if idx == 0:
                _set_folder_input_active(self.w_wrap, self.width_input, self.lbl_w, True)
                _set_folder_input_active(self.h_wrap, self.height_input, self.lbl_h, False, "(비율자동)", "각 짤의 원본 종횡비에 맞춰 높이가 자동 계산됩니다.")
                _set_folder_input_active(self.cols_wrap, self.cols_input, self.lbl_cols, True)
                _set_folder_input_active(self.rows_wrap, self.rows_input, self.lbl_rows, False, "(흐름자동)", "짤들이 아래로 차례차례 채워지므로 행 수는 자동 결정됩니다.")
            elif idx == 1:
                _set_folder_input_active(self.w_wrap, self.width_input, self.lbl_w, False, "(자동맞춤)", "화면 가로 폭에 맞춰 너비가 비례 자동 배분됩니다.")
                _set_folder_input_active(self.h_wrap, self.height_input, self.lbl_h, False, "(자동맞춤)", "잡지 앨범처럼 단정하게 가로줄마다 최적 높이가 자동 계산됩니다.")
                _set_folder_input_active(self.cols_wrap, self.cols_input, self.lbl_cols, False, "(자동분할)", "화면 가득 채우기에 최적화된 개수로 자동 분할됩니다.")
                _set_folder_input_active(self.rows_wrap, self.rows_input, self.lbl_rows, False, "(자동분할)", "화면 높이에 맞춰 최적 행 수가 자동 계산됩니다.")
            elif idx == 2:
                _set_folder_input_active(self.w_wrap, self.width_input, self.lbl_w, False, "(자동맞춤)", "화면 가로 폭에 맞춰 열 너비가 균등 자동 배분됩니다.")
                _set_folder_input_active(self.h_wrap, self.height_input, self.lbl_h, False, "(자동맞춤)", "세로 짤이 큼직하고 시원하게 돋보이도록 높이가 자동 조절됩니다.")
                _set_folder_input_active(self.cols_wrap, self.cols_input, self.lbl_cols, False, "(자동분할)", "화면 너비에 맞춰 최적 열 수가 자동 계산됩니다.")
                _set_folder_input_active(self.rows_wrap, self.rows_input, self.lbl_rows, False, "(자동분할)", "열 내부 짤 개수에 맞춰 자연스럽게 자동 분할됩니다.")
            else:
                _set_folder_input_active(self.w_wrap, self.width_input, self.lbl_w, True)
                _set_folder_input_active(self.h_wrap, self.height_input, self.lbl_h, True)
                _set_folder_input_active(self.cols_wrap, self.cols_input, self.lbl_cols, True)
                _set_folder_input_active(self.rows_wrap, self.rows_input, self.lbl_rows, True)

            hints = {
                0: "✨ 빈칸 자동 채우기: 각 짤의 원래 비율을 살리며, 남는 빈자리에 다음 짤을 쏙쏙 넣어 자연스럽게 채웁니다.",
                1: "✨ 가로 줄 맞춤: 가로 줄마다 높이를 똑같이 맞춰 잡지나 앨범처럼 반듯한 수평선으로 화면을 꽉 채웁니다.",
                2: "✨ 세로 줄 맞춤: 세로 줄마다 너비를 똑같이 맞춰 세로로 긴 짤들이 큼직하고 시원하게 돋보이도록 화면을 꽉 채웁니다.",
                3: "✨ 균일 바둑판 (꽉 채움): 모든 위젯을 동일한 사각형 타일로 통일하고 빈틈없이 채웁니다.",
                4: "✨ 균일 바둑판 (원본 비율): 동일한 사각형 틀에 짤이 잘리지 않도록 원본 비율을 유지하며 배치합니다.",
            }
            self.auto_calc_hint_lbl.setText(hints.get(idx, ""))
            self.auto_calc_hint_lbl.setVisible(True)

        self.fit_combo.currentIndexChanged.connect(_on_fit_combo_changed)
        _on_fit_combo_changed(0)

        grid_layout.addWidget(QLabel("전개 방향:"), 6, 0)
        self.direction_combo = DownwardComboBox()
        self.direction_combo.addItems([
            "↘ 우하단 전개 (좌상단 시작, 기본)",
            "↙ 좌하단 전개 (우상단 시작, 우상단 구석 추천)",
            "↗ 우상단 전개 (좌하단 시작, 작업표시줄 위 추천)",
            "↖ 좌상단 전개 (우하단 시작, 시계 구석 추천)",
        ])
        self.direction_combo.setCurrentIndex(0)
        grid_layout.addWidget(self.direction_combo, 6, 1, 1, 3)


        layout.addWidget(grid_card)

        # 2. 미디어 목록 선택 카드
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        list_label = QLabel("필터:")
        list_label.setObjectName("sectionHeader")
        filter_row.addWidget(list_label)

        for cat_key, cat_name, cat_cnt in [
            ("all", f"전체 ({all_count})", all_count),
            ("image", f"이미지 ({img_count})", img_count),
            ("gif", f"GIF ({gif_count})", gif_count),
            ("video", f"영상 ({vid_count})", vid_count),
        ]:
            btn = QPushButton(cat_name)
            btn.setProperty("kind", "filterBtn")
            btn.setProperty("active", "true" if cat_key == "all" else "false")
            if cat_cnt == 0:
                btn.setEnabled(False)
            btn.clicked.connect(lambda _, k=cat_key: self._apply_filter(k))
            self._filter_btns[cat_key] = btn
            filter_row.addWidget(btn)

        filter_row.addStretch(1)
        select_all_btn = QPushButton("전체 선택")
        select_all_btn.setObjectName("secondaryBtn")
        clear_btn = QPushButton("선택 해제")
        clear_btn.setObjectName("secondaryBtn")
        filter_row.addWidget(select_all_btn)
        filter_row.addWidget(clear_btn)
        layout.addLayout(filter_row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for path in self.media_paths:
            cat = _classify_media(path)
            prefix = "[IMG] " if cat == "image" else ("[GIF] " if cat == "gif" else "[VID] ")
            item = QListWidgetItem(f"{prefix}{os.path.basename(path)}")
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, cat)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        # 상태 안내 레이블
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        # 3. 하단 액션 버튼
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        cancel_btn = QPushButton("취소")
        create_btn = QPushButton("스프레드 생성")
        create_btn.setObjectName("primaryBtn")
        action_row.addWidget(cancel_btn)
        action_row.addWidget(create_btn)
        layout.addLayout(action_row)

        # 이벤트 연결
        select_all_btn.clicked.connect(lambda: self._set_filtered_checked(True))
        clear_btn.clicked.connect(lambda: self._set_filtered_checked(False))
        cancel_btn.clicked.connect(self.reject)
        create_btn.clicked.connect(self._accept_if_valid)

        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self._syncing_grid = False
        def _on_folder_cols_changed(val):
            if self._syncing_grid or val <= 0:
                return
            self._syncing_grid = True
            try:
                sel_count = max(1, len(self._checked_paths()))
                needed_rows = max(1, math.ceil(sel_count / val))
                self.rows_input.setValue(needed_rows)
            finally:
                self._syncing_grid = False
            self._refresh_status()

        def _on_folder_rows_changed(val):
            if self._syncing_grid or val <= 0:
                return
            self._syncing_grid = True
            try:
                sel_count = max(1, len(self._checked_paths()))
                needed_cols = max(1, math.ceil(sel_count / val))
                self.cols_input.setValue(needed_cols)
            finally:
                self._syncing_grid = False
            self._refresh_status()

        self.cols_input.valueChanged.connect(_on_folder_cols_changed)
        self.rows_input.valueChanged.connect(_on_folder_rows_changed)
        self.list_widget.itemChanged.connect(lambda _item: self._refresh_status())
        self._refresh_status()

        QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(self))

    def _open_folder_in_explorer(self):
        if self.folder_path and os.path.isdir(self.folder_path):
            try:
                os.startfile(self.folder_path)
            except Exception:
                pass

    def _on_item_clicked(self, item):
        state = item.checkState()
        item.setCheckState(Qt.CheckState.Unchecked if state == Qt.CheckState.Checked else Qt.CheckState.Checked)

    def _apply_filter(self, category):
        self._current_filter = str(category)
        for cat_key, btn in self._filter_btns.items():
            btn.setProperty("active", "true" if cat_key == self._current_filter else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            cat = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
            if self._current_filter == "all" or cat == self._current_filter:
                item.setHidden(False)
            else:
                item.setHidden(True)
        self._refresh_status()

    def _set_filtered_checked(self, checked):
        state = Qt.CheckState.Checked if bool(checked) else Qt.CheckState.Unchecked
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if not item.isHidden():
                item.setCheckState(state)
        self._refresh_status()

    def _checked_paths(self):
        paths = []
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                paths.append(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        return [path for path in paths if path]

    def _refresh_status(self):
        selected = len(self._checked_paths())
        cells = int(self.rows_input.value()) * int(self.cols_input.value())
        if selected > cells:
            self.status_label.setText(f"선택 {selected}개 / 배치 공간 {cells}칸 ({int(self.cols_input.value())}x{int(self.rows_input.value())})  ⚠️ 공간이 부족합니다 (행/열을 늘려주세요)")
            self.status_label.setStyleSheet("color: #ff9b9b; font-weight: 700;")
        else:
            self.status_label.setText(f"선택 {selected}개 / 배치 공간 {cells}칸 ({int(self.cols_input.value())}x{int(self.rows_input.value())})")
            self.status_label.setStyleSheet("color: #8cc3ff; font-weight: 600;")

    def _accept_if_valid(self):
        paths = self._checked_paths()
        if not paths:
            QMessageBox.warning(self, "스프레드 배치", "생성할 미디어를 하나 이상 선택해주세요.")
            return
        fit_idx = self.fit_combo.currentIndex()
        if fit_idx in (3, 4):
            cells = int(self.rows_input.value()) * int(self.cols_input.value())
            if len(paths) > cells:
                QMessageBox.warning(
                    self,
                    "스프레드 배치",
                    f"선택한 미디어 개수({len(paths)}개)가 설정된 바둑판 칸수({cells}칸)보다 많습니다.\n행 또는 열 개수를 늘려주세요.",
                )
                return

        fit_strategy_map = {
            0: "auto_aspect",
            1: "justified_rows",
            2: "justified_columns",
            3: "crop_fill",
            4: "fit_inside",
        }
        fit_strategy = fit_strategy_map.get(fit_idx, "auto_aspect")
        bg_mode = self.bg_combo.currentIndex()

        self.result_data = {
            "folder_path": self.folder_path,
            "item_paths": paths,
            "w": int(self.width_input.value()),
            "h": int(self.height_input.value()),
            "rows": int(self.rows_input.value()),
            "cols": int(self.cols_input.value()),
            "margin": int(self.margin_input.value()),
            "fit_strategy": fit_strategy,
            "bg_color_mode": bg_mode,
            "corner_mode": self.corner_combo.currentIndex() if hasattr(self, "corner_combo") else 0,
            "spread_direction": ["top-left", "top-right", "bottom-left", "bottom-right"][self.direction_combo.currentIndex()] if hasattr(self, "direction_combo") else "top-left",
        }
        self.accept()



class GrowthAnchorPicker(QWidget):
    anchorChanged = pyqtSignal(str)

    ANCHOR_NAMES = {
        "top-left": "좌상단 고정 (오른쪽/아래로 확장 - 기본)",
        "top-center": "상단중앙 고정 (좌우균등/아래로 확장)",
        "top-right": "우상단 고정 (왼쪽/아래로 확장 - 우상단 구석 추천)",
        "left-center": "좌측중앙 고정 (오른쪽/상하균등 확장)",
        "center": "중앙 고정 (사방으로 균등 확장)",
        "right-center": "우측중앙 고정 (왼쪽/상하균등 확장)",
        "bottom-left": "좌하단 고정 (오른쪽/위로 확장 - 작업표시줄 위 추천)",
        "bottom-center": "하단중앙 고정 (좌우균등/위로 확장)",
        "bottom-right": "우하단 고정 (왼쪽/위로 확장 - 시계 구석 추천)",
    }

    ANCHOR_GRID = [
        [("top-left", "↖"), ("top-center", "↑"), ("top-right", "↗")],
        [("left-center", "←"), ("center", "•"), ("right-center", "→")],
        [("bottom-left", "↙"), ("bottom-center", "↓"), ("bottom-right", "↘")],
    ]

    def __init__(self, parent=None, current_anchor="top-left"):
        super().__init__(parent)
        self._current_anchor = current_anchor if current_anchor in self.ANCHOR_NAMES else "top-left"
        self._buttons = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        grid_frame = QFrame()
        grid_frame.setObjectName("anchorGridFrame")
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(6, 6, 6, 6)
        grid_layout.setSpacing(4)

        for r, row in enumerate(self.ANCHOR_GRID):
            for c, (key, symbol) in enumerate(row):
                btn = QPushButton(symbol)
                btn.setObjectName("anchorBtn")
                btn.setFixedSize(34, 30)
                btn.setProperty("active", "true" if key == self._current_anchor else "false")
                btn.setToolTip(self.ANCHOR_NAMES.get(key, ""))
                btn.clicked.connect(lambda _, k=key: self.set_anchor(k))
                grid_layout.addWidget(btn, r, c)
                self._buttons[key] = btn

        layout.addWidget(grid_frame, 0, Qt.AlignmentFlag.AlignLeft)

        self.hint_label = QLabel(self.ANCHOR_NAMES.get(self._current_anchor, ""))
        self.hint_label.setObjectName("hintCaption")
        self.hint_label.setStyleSheet("color: #8da8cb; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.hint_label)

    def current_anchor(self):
        return self._current_anchor

    def set_anchor(self, key):
        if key not in self.ANCHOR_NAMES:
            key = "top-left"
        self._current_anchor = key
        for k, btn in self._buttons.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.hint_label.setText(self.ANCHOR_NAMES.get(key, ""))
        self.anchorChanged.emit(key)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings_data=None, bulk_mode=False, target_count=1, widget_name=""):
        super().__init__(parent)
        self.bulk_mode = bool(bulk_mode)
        self.target_count = max(1, int(target_count))
        self.widget_name = str(widget_name or (settings_data.get("name", "") if isinstance(settings_data, dict) else "") or "").strip()
        self.setObjectName("settingsDialog")
        if self.bulk_mode:
            self.setWindowTitle(f"위젯 상세 설정 - {self.target_count}개 그룹")
        else:
            if self.widget_name:
                self.setWindowTitle(f"위젯 상세 설정 - {self.widget_name}")
            else:
                self.setWindowTitle("위젯 상세 설정")
        from mywidgetbox_core import render_vector_icon
        self.setWindowIcon(render_vector_icon("settings", "#528bf8", 32))
        self._title_bar_themed = False
        screen = QApplication.primaryScreen()
        avail_h = screen.availableGeometry().height() if screen else 900
        init_h = min(660, max(460, int(avail_h * 0.82)))
        self.resize(720, init_h)
        self.setFixedWidth(720)
        self.setMinimumHeight(420)
        self.setMaximumHeight(max(500, avail_h - 40))
        self._wheel_filter = PreventInputWheelScrollFilter(self)
        self.installEventFilter(self._wheel_filter)
        self.setStyleSheet("""
            
            QFrame#anchorGridFrame {
                background-color: #121c2b;
                border: 1px solid #283a54;
                border-radius: 8px;
            }
            QPushButton#anchorBtn {
                background-color: #1a2a3e;
                border: 1px solid #334a6c;
                border-radius: 6px;
                color: #9cb8dd;
                font-size: 13px;
                font-weight: 700;
                min-height: 28px;
                padding: 0;
            }
            QPushButton#anchorBtn:hover {
                background-color: #263d5c;
                border-color: #528bf8;
                color: #ffffff;
            }
            QPushButton#anchorBtn[active="true"] {
                background-color: #3b68d4;
                border: 1.5px solid #6fa0ff;
                color: #ffffff;
            }
QDialog#settingsDialog {
                background-color: #162233;
            }
            QFrame#settingsHeader {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QLabel#settingsTitle {
                color: #eef4ff;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#settingsSubtitle {
                color: #a4bedc;
                font-size: 12px;
            }
            QFrame#segmentedBar {
                background-color: #121c2b;
                border: 1px solid #283a54;
                border-radius: 10px;
            }
            QPushButton[kind="segmentBtn"] {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 7px;
                color: #8da6c7;
                font-size: 12px;
                font-weight: 700;
                min-height: 34px;
                padding: 0 10px;
            }
            QPushButton[kind="segmentBtn"]:hover {
                background-color: #1a2a40;
                color: #dbe7fa;
            }
            QPushButton[kind="segmentBtn"][active="true"] {
                background-color: #2b446a;
                color: #ffffff;
                border: 1px solid #456c9e;
            }
            QFrame#settingsCard {
                background-color: #1d2c42;
                border: 1px solid #2e4466;
                border-radius: 12px;
            }
            QLabel#settingsSectionTitle {
                color: #92bbf8;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            QFrame#settingsSectionLine {
                background-color: #31486b;
                border: none;
                min-height: 1px;
                max-height: 1px;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLabel#pathLabel {
                color: #d8e6fa;
                background-color: #162436;
                border: 1px solid #324a6b;
                border-radius: 7px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QLabel#hintCaption {
                color: #8fa7c7;
                font-size: 11px;
                padding: 0 2px;
            }
            QFrame#unitInputContainer {
                min-height: 32px;
                background-color: #142133;
                border: 1.5px solid #2f496e;
                border-radius: 8px;
            }
            QFrame#unitInputContainer:hover {
                border-color: #4f76aa;
                background-color: #192a40;
            }
            QFrame#unitInputContainer:focus-within {
                border: 1.5px solid #528bf8;
                background-color: #192c45;
            }
            QFrame#unitInputContainer:disabled {
                background-color: #0b121c;
                border: 1px dashed #203147;
            }
            QLabel#unitBadgeLabel {
                color: #8bb0dc;
                font-size: 11px;
                font-weight: 700;
                padding-right: 6px;
            }
            QLabel#unitBadgeLabel:disabled {
                color: #3b4f66;
                font-weight: 600;
            }
            QSpinBox {
                min-height: 30px;
                color: #ffffff;
                background-color: transparent;
                border: none;
                padding: 2px 6px;
                font-size: 13px;
                font-weight: 700;
            }
            QSpinBox:disabled {
                color: #4a617e;
                background-color: transparent;
            }
            QLabel:disabled {
                color: #4a617e;
            }
            QSpinBox::up-button,
            QSpinBox::down-button {
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }
            QSpinBox::up-arrow,
            QSpinBox::down-arrow {
                width: 0px;
                height: 0px;
                image: none;
            }
            QComboBox {
                min-height: 32px;
                color: #eaf1fc;
                background-color: #24364f;
                border: 1px solid #3d5578;
                border-radius: 8px;
                padding: 2px 30px 2px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QComboBox:hover {
                background-color: #2d4361;
                border-color: #52739e;
            }
            QComboBox:focus {
                border: 1.5px solid #528bf8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid #334866;
                background: transparent;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9bb5d8;
                margin-right: 6px;
            }
            QComboBox::down-arrow:hover {
                border-top-color: #ffffff;
            }
            QComboBox QAbstractItemView {
                background-color: #21324a;
                color: #eef4ff;
                border: 1px solid #3d587d;
                border-radius: 6px;
                selection-background-color: #3f5e8e;
                selection-color: #ffffff;
                outline: 0;
                font-size: 12px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 8px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #395073;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: #8eb8ff;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #121c2b;
                width: 7px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: #314a6e;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4b6f9f;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                color: #e8efff;
                background-color: #2b3e5b;
                border: 1px solid #48648c;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #385075;
                border-color: #5d7fae;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #22334c;
            }
            QPushButton:disabled {
                background-color: #172436;
                border-color: #24354b;
                color: #506580;
            }
            QPushButton#primaryBtn {
                background-color: #4872d4;
                border: 1px solid #7397ea;
            }
            QPushButton#primaryBtn:hover {
                background-color: #5882e6;
            }
            QPushButton#masterBtn {
                background-color: #2b4061;
                border: 1px solid #46658f;
                min-height: 30px;
                font-size: 11px;
            }
            QPushButton#masterBtn:hover {
                background-color: #38537d;
            }
            QCheckBox {
                color: #cddbf0;
                spacing: 7px;
                min-height: 26px;
                font-size: 12px;
                font-weight: 600;
            }
            QCheckBox:hover {
                color: #ffffff;
            }
            QFrame#bulkNoticeCard,
            QFrame#bulkSpreadCard {
                background-color: #19273c;
                border: 1px solid #2f486d;
                border-radius: 9px;
            }
            QCheckBox#keepIndivSizeToggle,
            QCheckBox#spreadRelayoutToggle {
                color: #eef4ff;
                font-size: 12px;
                font-weight: 700;
                spacing: 8px;
            }
            QCheckBox#keepIndivSizeToggle:hover,
            QCheckBox#spreadRelayoutToggle:hover {
                color: #ffffff;
            }
            QLabel#bulkNoticeHint {
                color: #8fa7c7;
                font-size: 11px;
                padding-left: 24px;
            }
            QToolButton#shortcutToggle {
                color: #e8efff;
                background-color: #2b4061;
                border: 1px solid #46658f;
                border-radius: 8px;
                padding: 5px 10px;
                text-align: left;
                font-weight: 600;
                font-size: 11px;
            }
            QToolButton#shortcutToggle:hover {
                background-color: #38537d;
            }
            QToolButton#folderHelpBtn {
                color: #e8efff;
                background: transparent;
                border: none;
                padding: 0px;
                font-weight: 700;
            }
            QFrame#shortcutPanel {
                background-color: #1f3047;
                border: 1px solid #4a6891;
                border-radius: 10px;
            }
            QFrame#folderHelpPanel {
                background-color: #1f3047;
                border: 1px solid #4a6891;
                border-radius: 10px;
            }
            QLabel#shortcutText {
                color: #c6d6f3;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton#fitAspectBtn, QPushButton#fitScreenBtn, QPushButton#editSlideListBtn {
                color: #dbe7fa;
                background-color: #243852;
                border: 1px solid #3c587e;
                border-radius: 8px;
                min-height: 32px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#fitAspectBtn:hover, QPushButton#fitScreenBtn:hover, QPushButton#editSlideListBtn:hover {
                background-color: #35527d;
                border-color: #5d84b8;
                color: #ffffff;
            }
        """)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("settingsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(10)

        title_label = QLabel("위젯 상세 설정")
        title_label.setObjectName("settingsTitle")
        header_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        target_badge = QLabel()
        target_badge.setObjectName("targetBadge")
        if self.bulk_mode:
            target_badge.setText(f"{self.target_count}개 그룹")
            target_badge.setProperty("group", "true")
        else:
            display_name = self.widget_name if self.widget_name else "개별 위젯"
            target_badge.setText(display_name)
            target_badge.setProperty("group", "false")

        target_badge.setStyleSheet("""
            QLabel#targetBadge {
                color: #70a2ff;
                background-color: #101e33;
                border: 1px solid #2d4f82;
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#targetBadge[group="true"] {
                color: #4ade80;
                background-color: #0d281e;
                border: 1px solid #16563c;
            }
        """)
        header_layout.addWidget(target_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch(1)
        root.addWidget(header)

        # Modern Segmented Tab Bar (1:1:1 꽉 찬 세그먼트 컨트롤)
        self.segmented_bar = QFrame()
        self.segmented_bar.setObjectName("segmentedBar")
        seg_layout = QHBoxLayout(self.segmented_bar)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(4)

        from mywidgetbox_core import render_vector_icon

        self._seg_buttons = []
        tab_infos = [
            (" 미디어 & 재생", "media", 0),
            (" 위젯 & 외형", "widget", 1),
            (" 연동 & 시스템", "system", 2),
        ]

        self.stack = QStackedWidget()
        self.stack.setObjectName("settingsStack")

        for label_text, icon_name, idx in tab_infos:
            btn = QPushButton(label_text)
            btn.setProperty("kind", "segmentBtn")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.setIcon(render_vector_icon(icon_name, "#8da6c7" if idx != 0 else "#ffffff", 16))
            btn.setIconSize(QSize(16, 16))
            btn.clicked.connect(lambda _, i=idx: self._switch_tab(i))
            seg_layout.addWidget(btn, 1)
            self._seg_buttons.append(btn)

        root.addWidget(self.segmented_bar, 0)

        # Card container for stacked pages
        stack_card = QFrame()
        stack_card.setObjectName("settingsCard")
        stack_card_layout = QVBoxLayout(stack_card)
        stack_card_layout.setContentsMargins(12, 12, 12, 12)
        stack_card_layout.setSpacing(0)
        stack_card_layout.addWidget(self.stack, 1)
        root.addWidget(stack_card, 1)

        tab_media = QWidget()
        media_form = QFormLayout(tab_media)
        media_form.setContentsMargins(4, 4, 4, 4)
        media_form.setHorizontalSpacing(14)
        media_form.setVerticalSpacing(10)
        media_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        tab_widget = QWidget()
        widget_form = QFormLayout(tab_widget)
        widget_form.setContentsMargins(4, 4, 4, 4)
        widget_form.setHorizontalSpacing(14)
        widget_form.setVerticalSpacing(10)
        widget_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        tab_system = QWidget()
        system_form = QFormLayout(tab_system)
        system_form.setContentsMargins(4, 4, 4, 4)
        system_form.setHorizontalSpacing(14)
        system_form.setVerticalSpacing(10)
        system_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        def _wrap_in_scroll(inner_w):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setWidget(inner_w)
            return scroll

        self.stack.addWidget(_wrap_in_scroll(tab_media))
        self.stack.addWidget(_wrap_in_scroll(tab_widget))
        self.stack.addWidget(_wrap_in_scroll(tab_system))

        self._left_form = media_form
        self._right_form = widget_form
        self._media_form = media_form
        self._widget_form = widget_form
        self._system_form = system_form

        s = settings_data if settings_data else {}
        
        self.folder_path = s.get('folder_path', "")
        self.folder_item_paths = list(s.get('folder_item_paths', []) or [])
        self.pending_spread_config = None
        self.exec_path = s.get('exec_path', "")

        init_folder_display = self.folder_path if self.folder_path else "미지정"
        if self.folder_path and self.folder_item_paths:
            if len(self.folder_item_paths) == 1:
                init_folder_display = f"{self.folder_path} ({os.path.basename(self.folder_item_paths[0])})"
            else:
                init_folder_display = f"{self.folder_path} (선택 {len(self.folder_item_paths)}개)"

        self.folder_label = QLabel(init_folder_display)
        self.folder_label.setObjectName("pathLabel")
        self.folder_label.setWordWrap(True)
        self.folder_label.setToolTip(self.folder_path if self.folder_path else "")
        self.folder_hint_label = None

        self.folder_btn = QPushButton("폴더 선택")
        self.folder_btn.setIcon(render_vector_icon("folder", "#d8e7fa", 16))
        self.folder_btn.setIconSize(QSize(16, 16))

        self.file_btn = QPushButton("파일 선택")
        self.file_btn.setIcon(render_vector_icon("file", "#d8e7fa", 16))
        self.file_btn.setIconSize(QSize(16, 16))

        self.edit_slide_list_btn = QPushButton("목록 편집")
        self.edit_slide_list_btn.setObjectName("editSlideListBtn")
        self.edit_slide_list_btn.setIcon(render_vector_icon("list", "#d8e7fa", 16))
        self.edit_slide_list_btn.setIconSize(QSize(16, 16))

        self.folder_help_btn = QToolButton()
        self.folder_help_btn.setObjectName("folderHelpBtn")
        self.folder_help_btn.setText("")
        self.folder_help_btn.setToolTip("미디어 선택 모드 설명")
        self.folder_help_btn.setCheckable(True)
        self.folder_help_btn.setAutoRaise(True)
        help_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
        if help_icon.isNull():
            help_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarContextHelpButton)
        if help_icon.isNull():
            self.folder_help_btn.setText("?")
            self.folder_help_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            fallback_font = QFont(self.folder_help_btn.font())
            fallback_font.setBold(True)
            fallback_font.setPointSize(max(14, int(fallback_font.pointSize()) + 2))
            self.folder_help_btn.setFont(fallback_font)
            self.folder_help_btn.setFixedSize(32, 32)
        else:
            self.folder_help_btn.setIcon(help_icon)
            self.folder_help_btn.setIconSize(QSize(28, 28))
            self.folder_help_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            self.folder_help_btn.setFixedSize(36, 36)

        self._folder_btn_row_widget = QWidget()
        folder_btn_row = QHBoxLayout(self._folder_btn_row_widget)
        folder_btn_row.setContentsMargins(0, 0, 0, 0)
        folder_btn_row.setSpacing(6)
        folder_btn_row.addWidget(self.folder_btn, 3)
        folder_btn_row.addWidget(self.file_btn, 3)
        folder_btn_row.addWidget(self.edit_slide_list_btn, 4)
        folder_btn_row.addWidget(self.folder_help_btn, 0)

        self.folder_help_panel = QFrame(self)
        self.folder_help_panel.setObjectName("folderHelpPanel")
        self.folder_help_panel.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        )
        self.folder_help_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.folder_help_panel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        folder_help_layout = QVBoxLayout(self.folder_help_panel)
        folder_help_layout.setContentsMargins(10, 8, 10, 10)
        folder_help_layout.setSpacing(6)
        folder_help_text = (
            "미디어 선택 모드 안내\n"
            "- [폴더 선택]: 폴더 내의 미디어를 순차 재생(슬라이드)하거나 바둑판식(스프레드)으로 배치합니다.\n"
            "- [파일 선택]: 원하는 특정 미디어 파일들만 직접 선택하여 고정/재생합니다."
        )
        self.folder_help_text = QLabel(
            folder_help_text
        )
        self.folder_help_text.setObjectName("shortcutText")
        self.folder_help_text.setWordWrap(True)
        folder_help_layout.addWidget(self.folder_help_text)
        self.folder_help_panel.hide()
        self.exec_label = QLabel(os.path.basename(self.exec_path) if self.exec_path else "미지정")
        self.exec_label.setObjectName("pathLabel")
        self.exec_label.setWordWrap(True)
        self.exec_btn = QPushButton("실행파일 선택")
        self._focus_binding_host = s.get("focus_binding_host", None)
        self._focus_capture_deadline = 0.0
        self._focus_capture_timer = QTimer(self)
        self._focus_capture_timer.setInterval(140)
        self._focus_capture_timer.timeout.connect(self._on_focus_capture_tick)
        self._focus_binding_supported = bool(
            self._focus_binding_host
            and hasattr(self._focus_binding_host, "_capture_bindable_foreground_hwnd")
            and hasattr(self._focus_binding_host, "_set_manual_focus_binding_from_hwnd")
            and hasattr(self._focus_binding_host, "_clear_manual_focus_binding")
            and hasattr(self._focus_binding_host, "get_exec_manual_focus_summary")
        )
        focus_summary = str(s.get("focus_binding_summary", "") or "").strip()
        if not focus_summary and self._focus_binding_supported:
            try:
                focus_summary = str(self._focus_binding_host.get_exec_manual_focus_summary() or "").strip()
            except Exception:
                focus_summary = ""
        if not focus_summary:
            focus_summary = "자동 (실행파일 기준)"
        self.focus_binding_label = QLabel(focus_summary)
        self.focus_binding_label.setObjectName("pathLabel")
        self.focus_binding_label.setWordWrap(True)
        self.focus_bind_btn = QPushButton("포커싱 대상 지정")
        self.focus_bind_clear_btn = QPushButton("바인딩 초기화")
        self.focus_bind_btn.setMinimumHeight(30)
        self.focus_bind_clear_btn.setMinimumHeight(30)
        self.focus_bind_btn.setEnabled(self._focus_binding_supported)
        self.focus_bind_clear_btn.setEnabled(self._focus_binding_supported)
        if not self._focus_binding_supported:
            self.focus_bind_btn.setToolTip("실행 중인 위젯에서만 사용 가능합니다.")
            self.focus_bind_clear_btn.setToolTip("실행 중인 위젯에서만 사용 가능합니다.")
        self._focus_bind_row_widget = QWidget()
        focus_bind_row = QHBoxLayout(self._focus_bind_row_widget)
        focus_bind_row.setContentsMargins(0, 0, 0, 0)
        focus_bind_row.setSpacing(6)
        focus_bind_row.addWidget(self.focus_bind_btn)
        focus_bind_row.addWidget(self.focus_bind_clear_btn)
        focus_bind_row.addStretch(1)
        
        def _create_unit_input(spinbox, unit_text, width=140):
            container = QFrame()
            container.setObjectName("unitInputContainer")
            container.setFixedWidth(int(width))
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(8, 0, 8, 0)
            container_layout.setSpacing(4)
            spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spinbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            spinbox.wheelEvent = lambda event: event.ignore()
            unit_label = QLabel(unit_text)
            unit_label.setObjectName("unitBadgeLabel")
            container_layout.addWidget(spinbox, 1)
            container_layout.addWidget(unit_label, 0)
            container.spinbox = spinbox
            container.unit_label = unit_label
            container.default_unit = str(unit_text or "")
            return container

        def _set_input_active_state(container, spinbox, label, is_active, auto_text="자동", tooltip=""):
            spinbox.setEnabled(bool(is_active))
            container.setEnabled(bool(is_active))
            if label is not None:
                label.setEnabled(bool(is_active))
                label.setToolTip(tooltip if not is_active else "")
            if hasattr(container, "unit_label"):
                container.unit_label.setEnabled(bool(is_active))
                if is_active:
                    container.unit_label.setText(getattr(container, "default_unit", "px"))
                    container.unit_label.setStyleSheet("color: #8bb0dc; font-weight: 700; font-size: 11px;")
                else:
                    container.unit_label.setText(auto_text)
                    container.unit_label.setStyleSheet("color: #41556f; font-weight: 600; font-size: 10px;")
            tip = tooltip if not is_active else ""
            container.setToolTip(tip)
            spinbox.setToolTip(tip)

        init_w = int(s.get('w', 200))
        init_h = int(s.get('h', 200))
        self.width_input = QSpinBox(); self.width_input.setRange(50, 5000)
        self.width_input.setValue(init_w)
        self.width_input_box = _create_unit_input(self.width_input, "px", width=140)

        self.height_input = QSpinBox(); self.height_input.setRange(50, 5000)
        self.height_input.setValue(init_h)
        self.height_input_box = _create_unit_input(self.height_input, "px", width=140)

        self.sec_input = QSpinBox(); self.sec_input.setRange(1, 3600)
        self.sec_input.setValue(s.get('interval', 5))
        self.sec_input_box = _create_unit_input(self.sec_input, "초", width=140)

        self.keep_aspect_ratio_cb = QCheckBox("가로세로 비율 고정")
        self.keep_aspect_ratio_cb.setChecked(bool(s.get('keep_aspect_ratio', True)))
        init_anchor = str(s.get('growth_anchor', 'top-left') or 'top-left')
        self.anchor_picker = GrowthAnchorPicker(self, current_anchor=init_anchor)

        self.keep_aspect_ratio_cb.setToolTip("너비나 높이 변경 시 가로세로 비율을 유지하여 자동으로 계산합니다.")

        if self.bulk_mode:
            self.bulk_notice_card = QFrame()
            self.bulk_notice_card.setObjectName("bulkNoticeCard")
            bn_layout = QVBoxLayout(self.bulk_notice_card)
            bn_layout.setContentsMargins(10, 8, 10, 8)
            bn_layout.setSpacing(3)

            self.keep_individual_size_cb = QCheckBox("각 위젯의 기존 크기 유지 (일괄 변경 안 함)")
            self.keep_individual_size_cb.setObjectName("keepIndivSizeToggle")
            self.keep_individual_size_cb.setChecked(True)
            self.keep_individual_size_cb.setToolTip(
                "체크 시 그룹 내 각 위젯들의 고유한 너비/높이를 그대로 유지합니다.\n"
                "체크 해제 시 아래 지정한 너비/높이로 모든 위젯의 크기가 일괄 통일됩니다."
            )
            bn_layout.addWidget(self.keep_individual_size_cb)

            notice_hint = QLabel("그룹 내 위젯들의 고유한 종횡비와 크기를 안전하게 보존합니다.")
            notice_hint.setObjectName("bulkNoticeHint")
            bn_layout.addWidget(notice_hint)

            def _update_bulk_size_inputs_state():
                spread_active = hasattr(self, "spread_relayout_cb") and self.spread_relayout_cb.isChecked()
                keep_indiv = hasattr(self, "keep_individual_size_cb") and self.keep_individual_size_cb.isChecked()
                can_edit_general = (not spread_active) and (not keep_indiv)
                auto_badge = "(스프레드제어)" if spread_active else ("(기존유지)" if keep_indiv else "px")
                tip = "위의 스프레드 재배치 카드에서 크기를 설정합니다." if spread_active else ("각 위젯의 기존 크기가 그대로 유지됩니다." if keep_indiv else "")
                _set_input_active_state(self.width_input_box, self.width_input, None, can_edit_general, auto_badge, tip)
                _set_input_active_state(self.height_input_box, self.height_input, None, can_edit_general, auto_badge, tip)
                if hasattr(self, "ratio_row_widget"):
                    self.ratio_row_widget.setEnabled(can_edit_general)
                if hasattr(self, "anchor_picker"):
                    self.anchor_picker.setEnabled(not spread_active)

            def _on_keep_indiv_size_toggled(checked):
                if checked and hasattr(self, "spread_relayout_cb") and self.spread_relayout_cb.isChecked():
                    self.spread_relayout_cb.setChecked(False)
                _update_bulk_size_inputs_state()

            self.keep_individual_size_cb.toggled.connect(_on_keep_indiv_size_toggled)

            self.bulk_spread_card = QFrame()
            self.bulk_spread_card.setObjectName("bulkSpreadCard")
            bs_layout = QVBoxLayout(self.bulk_spread_card)
            bs_layout.setContentsMargins(10, 8, 10, 8)
            bs_layout.setSpacing(6)

            self.spread_relayout_cb = QCheckBox("선택한 위젯들을 스프레드 방식으로 화면에 재정렬")
            self.spread_relayout_cb.setObjectName("spreadRelayoutToggle")
            self.spread_relayout_cb.setChecked(False)
            self.spread_relayout_cb.setToolTip(
                "체크 시 그룹 내 위젯들을 지정한 스프레드(바둑판/자유비율/전체화면) 알고리즘에 따라\n"
                "바탕화면에서 빈틈없이 깔끔하게 일괄 재배치합니다."
            )
            bs_layout.addWidget(self.spread_relayout_cb)

            self.bulk_spread_opts = QWidget()
            bso_layout = QGridLayout(self.bulk_spread_opts)
            bso_layout.setContentsMargins(0, 4, 0, 0)
            bso_layout.setHorizontalSpacing(10)
            bso_layout.setVerticalSpacing(8)

            bso_layout.addWidget(QLabel("배치 맞춤:"), 0, 0)
            self.bulk_spread_fit_combo = DownwardComboBox()
            self.bulk_spread_fit_combo.addItems([
                "🧩 빈칸 자동 채우기 (자유 비율, 권장)",
                "📏 가로 줄 맞춤 (단정한 앨범형)",
                "📐 세로 줄 맞춤 (세로 짤 돋보임)",
                "🔲 균일 바둑판 (꽉 채움)",
                "🖼️ 균일 바둑판 (원본 비율)",
            ])
            self.bulk_spread_fit_combo.setCurrentIndex(0)
            bso_layout.addWidget(self.bulk_spread_fit_combo, 0, 1, 1, 3)
            self.bulk_spread_auto_hint = QLabel("✨ 빈칸 자동 채우기: 각 짤의 원래 비율을 살리며, 남는 빈자리에 다음 짤을 쏙쏙 넣어 자연스럽게 채웁니다.")
            self.bulk_spread_auto_hint.setWordWrap(True)
            self.bulk_spread_auto_hint.setStyleSheet("""
                color: #7eb0ff;
                background-color: #132133;
                border: 1px dashed #35537d;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.bulk_spread_auto_hint.setVisible(True)
            bso_layout.addWidget(self.bulk_spread_auto_hint, 1, 0, 1, 4)

            # Row 2: 위젯 너비(W) & 높이(H)
            self.bulk_spread_lbl_w = QLabel("위젯 너비(W):")
            bso_layout.addWidget(self.bulk_spread_lbl_w, 2, 0)
            self.bulk_spread_w_spin = QSpinBox()
            self.bulk_spread_w_spin.setRange(50, 5000)
            self.bulk_spread_w_spin.setValue(init_w)
            self.bulk_spread_w_box = _create_unit_input(self.bulk_spread_w_spin, "px", width=120)
            bso_layout.addWidget(self.bulk_spread_w_box, 2, 1)

            self.bulk_spread_lbl_h = QLabel("위젯 높이(H):")
            bso_layout.addWidget(self.bulk_spread_lbl_h, 2, 2)
            self.bulk_spread_h_spin = QSpinBox()
            self.bulk_spread_h_spin.setRange(50, 5000)
            self.bulk_spread_h_spin.setValue(init_h)
            self.bulk_spread_h_box = _create_unit_input(self.bulk_spread_h_spin, "px", width=120)
            bso_layout.addWidget(self.bulk_spread_h_box, 2, 3)

            # Row 3: 가로 열(Cols) & 세로 행(Rows)
            import math
            target_cnt = max(1, getattr(self, "target_count", 4))
            init_cols = max(1, math.ceil(math.sqrt(target_cnt)))
            init_rows = max(1, math.ceil(target_cnt / init_cols))

            self.bulk_spread_lbl_cols = QLabel("가로 열(Cols):")
            bso_layout.addWidget(self.bulk_spread_lbl_cols, 3, 0)
            self.bulk_spread_cols_spin = QSpinBox()
            self.bulk_spread_cols_spin.setRange(1, 50)
            self.bulk_spread_cols_spin.setValue(init_cols)
            self.bulk_spread_cols_box = _create_unit_input(self.bulk_spread_cols_spin, "열", width=120)
            bso_layout.addWidget(self.bulk_spread_cols_box, 3, 1)

            self.bulk_spread_lbl_rows = QLabel("세로 행(Rows):")
            bso_layout.addWidget(self.bulk_spread_lbl_rows, 3, 2)
            self.bulk_spread_rows_spin = QSpinBox()
            self.bulk_spread_rows_spin.setRange(1, 50)
            self.bulk_spread_rows_spin.setValue(init_rows)
            self.bulk_spread_rows_box = _create_unit_input(self.bulk_spread_rows_spin, "행", width=120)
            bso_layout.addWidget(self.bulk_spread_rows_box, 3, 3)

            # Row 4: 위젯 간격 & 전개 방향
            self.bulk_spread_lbl_margin = QLabel("위젯 간격:")
            bso_layout.addWidget(self.bulk_spread_lbl_margin, 4, 0)
            self.bulk_spread_margin_spin = QSpinBox()
            self.bulk_spread_margin_spin.setRange(0, 500)
            self.bulk_spread_margin_spin.setValue(10)
            self.bulk_spread_margin_box = _create_unit_input(self.bulk_spread_margin_spin, "px", width=120)
            bso_layout.addWidget(self.bulk_spread_margin_box, 4, 1)

            bso_layout.addWidget(QLabel("전개 방향:"), 4, 2)
            self.bulk_spread_dir_combo = DownwardComboBox()
            self.bulk_spread_dir_combo.addItems([
                "↘ 우하단 전개 (좌상단 시작, 기본)",
                "↙ 좌하단 전개 (우상단 시작, 우상단 구석 추천)",
                "↗ 우상단 전개 (좌하단 시작, 작업표시줄 위 추천)",
                "↖ 좌상단 전개 (우하단 시작, 시계 구석 추천)",
            ])
            self.bulk_spread_dir_combo.setCurrentIndex(0)
            bso_layout.addWidget(self.bulk_spread_dir_combo, 4, 3)

            bs_layout.addWidget(self.bulk_spread_opts)
            self.bulk_spread_opts.setVisible(False)

            self._syncing_bulk_grid = False
            def _on_bulk_cols_changed(val):
                if self._syncing_bulk_grid or val <= 0:
                    return
                self._syncing_bulk_grid = True
                try:
                    needed_rows = max(1, math.ceil(target_cnt / val))
                    self.bulk_spread_rows_spin.setValue(needed_rows)
                finally:
                    self._syncing_bulk_grid = False

            def _on_bulk_rows_changed(val):
                if self._syncing_bulk_grid or val <= 0:
                    return
                self._syncing_bulk_grid = True
                try:
                    needed_cols = max(1, math.ceil(target_cnt / val))
                    self.bulk_spread_cols_spin.setValue(needed_cols)
                finally:
                    self._syncing_bulk_grid = False

            self.bulk_spread_cols_spin.valueChanged.connect(_on_bulk_cols_changed)
            self.bulk_spread_rows_spin.valueChanged.connect(_on_bulk_rows_changed)

            self._syncing_bulk_wh = False
            def _on_bulk_w_changed(val):
                if self._syncing_bulk_wh:
                    return
                self._syncing_bulk_wh = True
                try:
                    self.width_input.setValue(val)
                finally:
                    self._syncing_bulk_wh = False

            def _on_bulk_h_changed(val):
                if self._syncing_bulk_wh:
                    return
                self._syncing_bulk_wh = True
                try:
                    self.height_input.setValue(val)
                finally:
                    self._syncing_bulk_wh = False

            self.bulk_spread_w_spin.valueChanged.connect(_on_bulk_w_changed)
            self.bulk_spread_h_spin.valueChanged.connect(_on_bulk_h_changed)

            def _on_bulk_spread_relayout_toggled(checked):
                self.bulk_spread_opts.setVisible(checked)
                if checked and hasattr(self, "keep_individual_size_cb") and self.keep_individual_size_cb.isChecked():
                    self.keep_individual_size_cb.setChecked(False)
                _update_bulk_size_inputs_state()

            self.spread_relayout_cb.toggled.connect(_on_bulk_spread_relayout_toggled)

            def _on_bulk_spread_fit_changed(idx):
                if idx == 0:
                    _set_input_active_state(self.bulk_spread_w_box, self.bulk_spread_w_spin, self.bulk_spread_lbl_w, True)
                    _set_input_active_state(self.bulk_spread_h_box, self.bulk_spread_h_spin, self.bulk_spread_lbl_h, False, "(비율자동)", "각 짤의 원본 종횡비에 맞춰 높이가 자동 계산됩니다.")
                    _set_input_active_state(self.bulk_spread_cols_box, self.bulk_spread_cols_spin, self.bulk_spread_lbl_cols, True)
                    _set_input_active_state(self.bulk_spread_rows_box, self.bulk_spread_rows_spin, self.bulk_spread_lbl_rows, False, "(흐름자동)", "짤들이 아래로 차례차례 채워지므로 행 수는 자동 결정됩니다.")
                elif idx == 1:
                    _set_input_active_state(self.bulk_spread_w_box, self.bulk_spread_w_spin, self.bulk_spread_lbl_w, False, "(자동맞춤)", "화면 가로 폭에 맞춰 너비가 비례 자동 배분됩니다.")
                    _set_input_active_state(self.bulk_spread_h_box, self.bulk_spread_h_spin, self.bulk_spread_lbl_h, False, "(자동맞춤)", "잡지 앨범처럼 단정하게 가로줄마다 최적 높이가 자동 계산됩니다.")
                    _set_input_active_state(self.bulk_spread_cols_box, self.bulk_spread_cols_spin, self.bulk_spread_lbl_cols, False, "(자동분할)", "화면 가득 채우기에 최적화된 개수로 자동 분할됩니다.")
                    _set_input_active_state(self.bulk_spread_rows_box, self.bulk_spread_rows_spin, self.bulk_spread_lbl_rows, False, "(자동분할)", "화면 높이에 맞춰 최적 행 수가 자동 계산됩니다.")
                elif idx == 2:
                    _set_input_active_state(self.bulk_spread_w_box, self.bulk_spread_w_spin, self.bulk_spread_lbl_w, False, "(자동맞춤)", "화면 가로 폭에 맞춰 열 너비가 균등 자동 배분됩니다.")
                    _set_input_active_state(self.bulk_spread_h_box, self.bulk_spread_h_spin, self.bulk_spread_lbl_h, False, "(자동맞춤)", "세로 짤이 큼직하고 시원하게 돋보이도록 높이가 자동 조절됩니다.")
                    _set_input_active_state(self.bulk_spread_cols_box, self.bulk_spread_cols_spin, self.bulk_spread_lbl_cols, False, "(자동분할)", "화면 너비에 맞춰 최적 열 수가 자동 계산됩니다.")
                    _set_input_active_state(self.bulk_spread_rows_box, self.bulk_spread_rows_spin, self.bulk_spread_lbl_rows, False, "(자동분할)", "열 내부 짤 개수에 맞춰 자연스럽게 자동 분할됩니다.")
                else:
                    _set_input_active_state(self.bulk_spread_w_box, self.bulk_spread_w_spin, self.bulk_spread_lbl_w, True)
                    _set_input_active_state(self.bulk_spread_h_box, self.bulk_spread_h_spin, self.bulk_spread_lbl_h, True)
                    _set_input_active_state(self.bulk_spread_cols_box, self.bulk_spread_cols_spin, self.bulk_spread_lbl_cols, True)
                    _set_input_active_state(self.bulk_spread_rows_box, self.bulk_spread_rows_spin, self.bulk_spread_lbl_rows, True)

                hints = {
                    0: "✨ 빈칸 자동 채우기: 각 짤의 원래 비율을 살리며, 남는 빈자리에 다음 짤을 쏙쏙 넣어 자연스럽게 채웁니다.",
                    1: "✨ 가로 줄 맞춤: 가로 줄마다 높이를 똑같이 맞춰 잡지나 앨범처럼 반듯한 수평선으로 화면을 꽉 채웁니다.",
                    2: "✨ 세로 줄 맞춤: 세로 줄마다 너비를 똑같이 맞춰 세로로 긴 짤들이 큼직하고 시원하게 돋보이도록 화면을 꽉 채웁니다.",
                    3: "✨ 균일 바둑판 (꽉 채움): 모든 위젯을 동일한 정사각형/직사각형 타일로 통일하고 빈틈없이 꽉 채웁니다.",
                    4: "✨ 균일 바둑판 (원본 비율): 동일한 사각형 틀에 짤이 잘리지 않도록 원본 비율을 유지하며 배치합니다.",
                }
                self.bulk_spread_auto_hint.setText(hints.get(idx, ""))
                self.bulk_spread_auto_hint.setVisible(True)

            self.bulk_spread_fit_combo.currentIndexChanged.connect(_on_bulk_spread_fit_changed)
            _on_bulk_spread_fit_changed(0)

        self._syncing_aspect_size = False
        self._current_aspect_ratio = float(init_w) / max(1, float(init_h))

        def _on_width_changed(val):
            if not getattr(self, "_syncing_bulk_wh", False) and hasattr(self, "bulk_spread_w_spin"):
                self._syncing_bulk_wh = True
                try:
                    self.bulk_spread_w_spin.setValue(val)
                finally:
                    self._syncing_bulk_wh = False
            if self._syncing_aspect_size or not self.keep_aspect_ratio_cb.isChecked():
                return
            self._syncing_aspect_size = True
            try:
                ratio = self._current_aspect_ratio if self._current_aspect_ratio > 0 else 1.0
                new_h = max(50, min(5000, int(round(val / ratio))))
                self.height_input.setValue(new_h)
                if hasattr(self, "bulk_spread_h_spin") and not getattr(self, "_syncing_bulk_wh", False):
                    self._syncing_bulk_wh = True
                    try:
                        self.bulk_spread_h_spin.setValue(new_h)
                    finally:
                        self._syncing_bulk_wh = False
            finally:
                self._syncing_aspect_size = False

        def _on_height_changed(val):
            if not getattr(self, "_syncing_bulk_wh", False) and hasattr(self, "bulk_spread_h_spin"):
                self._syncing_bulk_wh = True
                try:
                    self.bulk_spread_h_spin.setValue(val)
                finally:
                    self._syncing_bulk_wh = False
            if self._syncing_aspect_size or not self.keep_aspect_ratio_cb.isChecked():
                return
            self._syncing_aspect_size = True
            try:
                ratio = self._current_aspect_ratio if self._current_aspect_ratio > 0 else 1.0
                new_w = max(50, min(5000, int(round(val * ratio))))
                self.width_input.setValue(new_w)
                if hasattr(self, "bulk_spread_w_spin") and not getattr(self, "_syncing_bulk_wh", False):
                    self._syncing_bulk_wh = True
                    try:
                        self.bulk_spread_w_spin.setValue(new_w)
                    finally:
                        self._syncing_bulk_wh = False
            finally:
                self._syncing_aspect_size = False

        def _on_aspect_lock_toggled(checked):
            if checked:
                w = self.width_input.value()
                h = max(1, self.height_input.value())
                self._current_aspect_ratio = float(w) / float(h)

        self.fit_aspect_btn = QPushButton("원본 비율 맞춤")
        self.fit_aspect_btn.setObjectName("fitAspectBtn")
        self.fit_aspect_btn.setIcon(render_vector_icon("ratio", "#d8e7fa", 16))
        self.fit_aspect_btn.setIconSize(QSize(16, 16))
        self.fit_aspect_btn.setToolTip("현재 선택된 이미지의 실제 원본 해상도(가로세로 비율)에 맞춰 높이를 자동 조절합니다.")
        self.fit_aspect_btn.clicked.connect(self._on_fit_aspect_clicked)

        self.fit_screen_btn = QPushButton("화면 맞춤")
        self.fit_screen_btn.setObjectName("fitScreenBtn")
        self.fit_screen_btn.setIcon(render_vector_icon("screen", "#d8e7fa", 16))
        self.fit_screen_btn.setIconSize(QSize(16, 16))
        self.fit_screen_btn.setToolTip("현재 모니터 해상도 및 작업표시줄 영역에 맞춰 비율을 유지하며 화면에 꽉 차게 맞춥니다.")
        self.fit_screen_btn.clicked.connect(self._on_fit_screen_clicked)

        self.ratio_row_widget = QWidget()
        ratio_row = QHBoxLayout(self.ratio_row_widget)
        ratio_row.setContentsMargins(0, 0, 0, 0)
        ratio_row.setSpacing(6)
        ratio_row.addWidget(self.keep_aspect_ratio_cb, 0)
        ratio_row.addWidget(self.fit_aspect_btn, 0)
        ratio_row.addWidget(self.fit_screen_btn, 0)
        ratio_row.addStretch(1)


        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        curr_op = s.get('opacity_pct', 100)
        self.opacity_slider.setValue(curr_op)
        self.opacity_slider.setFixedHeight(26)
        self.opacity_slider.setFixedWidth(220)
        self.opacity_slider.wheelEvent = lambda event: event.ignore()
    
        self.opacity_spinbox = QSpinBox()
        self.opacity_spinbox.setRange(10, 100)
        self.opacity_spinbox.setValue(curr_op)
        self.opacity_spinbox_box = _create_unit_input(self.opacity_spinbox, "%", width=96)
        self.opacity_slider.setToolTip("100% = 완전 표시, 10% = 거의 투명")
        self.opacity_spinbox.setToolTip("100% = 완전 표시, 10% = 거의 투명")

        self.opacity_row_widget = QWidget()
        opacity_row = QHBoxLayout(self.opacity_row_widget)
        opacity_row.setContentsMargins(0, 0, 0, 0)
        opacity_row.setSpacing(10)
        opacity_row.addWidget(self.opacity_spinbox_box, 0)
        opacity_row.addWidget(self.opacity_slider, 0)
        opacity_row.addStretch(1)

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
        self.corner_combo.addItems(["곡선", "직각", "원형 (최대)"])
        self.corner_combo.setCurrentIndex(
            DesktopWidget.coerce_corner_mode(s.get('corner_mode', DesktopWidget.CORNER_ROUNDED))
        )
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

        self.slide_auto_aspect_cb = QCheckBox("슬라이드 시 미디어 비율로 자동 맞춤")
        self.slide_auto_aspect_cb.setChecked(_as_bool(s.get('auto_fit_slide_media', False), False))
        self.slide_auto_aspect_cb.setStyleSheet("color: #dbe7fb; font-size: 12px; font-weight: 600;")
        self.slide_auto_aspect_cb.setToolTip("슬라이드 재생 시 다음 이미지/GIF/동영상으로 전환될 때마다 해당 미디어의 실제 비율에 맞춰 위젯 높이를 자동으로 조절합니다.")

        self.video_transition_combo = DownwardComboBox()
        self.video_transition_combo.addItems([
            "싱글 (가벼움, 전환 깜빡임 가능)",
            "듀얼 (매끄러움, 메모리 사용 증가)",
        ])
        vt_mode = DesktopWidget.coerce_video_transition_mode(
            s.get('video_transition_mode', DesktopWidget.VIDEO_TRANSITION_SINGLE)
        )
        self.video_transition_combo.setCurrentIndex(int(vt_mode))
        self.video_transition_combo.setView(QListView())
        self.video_transition_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.video_transition_combo.setStyle(QStyleFactory.create("Fusion"))
        self.video_transition_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.video_transition_combo.setMinimumHeight(36)
        self.video_transition_hint = QLabel(
            "• 싱글: 가볍지만 영상 전환 시 깜빡임 가능\n"
            "• 듀얼: 영상 간 전환이 매끄러움 (메모리 사용)"
        )
        self.video_transition_hint.setObjectName("hintCaption")
        self.video_transition_hint.setWordWrap(True)
        self.video_decode_combo = DownwardComboBox()
        self.video_decode_combo.addItems([
            "원본 해상도 (품질 우선)",
            "자동 (위젯 크기 기준)",
            "1080p 이하",
            "720p 이하",
        ])
        decode_mode = DesktopWidget.coerce_video_decode_mode(
            s.get('video_decode_mode', DesktopWidget.VIDEO_DECODE_ORIGINAL)
        )
        self.video_decode_combo.setCurrentIndex(int(decode_mode))
        self.video_decode_combo.setView(QListView())
        self.video_decode_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.video_decode_combo.setStyle(QStyleFactory.create("Fusion"))
        self.video_decode_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.video_decode_combo.setMinimumHeight(36)
        self.video_decode_hint = QLabel(
            "재생 시 저해상도 프록시를 생성하여 GPU/메모리 부담을 줄입니다."
        )
        self.video_decode_hint.setObjectName("hintCaption")
        self.video_decode_hint.setWordWrap(True)
        self.video_cache_usage_label = QLabel("캐시 사용량: 계산 중...")
        self.video_cache_usage_label.setObjectName("pathLabel")
        self.video_cache_usage_label.setWordWrap(True)
        self.video_cache_usage_label.setToolTip("영상 프록시 캐시 폴더")
        self.video_cache_clear_btn = QPushButton("영상 캐시 정리")
        self.video_cache_clear_btn.setMinimumHeight(30)
        self.video_cache_action_row_widget = QWidget()
        video_cache_action_row = QHBoxLayout(self.video_cache_action_row_widget)
        video_cache_action_row.setContentsMargins(0, 0, 0, 0)
        video_cache_action_row.setSpacing(6)
        video_cache_action_row.addWidget(self.video_cache_clear_btn)
        video_cache_action_row.addStretch(1)
        self.video_dual_fade_ms_spin = QSpinBox()
        self.video_dual_fade_ms_spin.setRange(0, 300)
        self.video_dual_fade_ms_spin.setSingleStep(10)
        self.video_dual_fade_ms_spin.setValue(
            DesktopWidget.coerce_video_dual_fade_ms(
                s.get('video_dual_fade_ms', DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS)
            )
        )
        self.video_dual_fade_box = _create_unit_input(self.video_dual_fade_ms_spin, "ms")
        self.video_dual_fade_hint = QLabel(
            "듀얼 전환 시 페이드 시간(ms)입니다."
        )
        self.video_dual_fade_hint.setObjectName("hintCaption")
        self.video_dual_fade_hint.setWordWrap(True)

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
            "- Ctrl+드래그 / Shift+G: 영역 드래그 다중 선택\n"
            "- Alt+클릭: 마우스 잠금 토글\n"
            "- G: 임시 그룹 토글\n"
            "- Ctrl+G: 임시 그룹 전체 해제\n"
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

        def _add_section_header(form_layout, title_text):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 4, 0, 2)
            row_layout.setSpacing(8)
            title = QLabel(str(title_text))
            title.setObjectName("settingsSectionTitle")
            line = QFrame()
            line.setObjectName("settingsSectionLine")
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Plain)
            row_layout.addWidget(title, 0)
            row_layout.addWidget(line, 1)
            form_layout.addRow(row_widget)

        # Tab 1: 📁 미디어 & 재생
        _add_section_header(media_form, "미디어 소스")
        media_form.addRow("미디어 경로:", self.folder_label)
        media_form.addRow("미디어 선택:", self._folder_btn_row_widget)
        if self.folder_hint_label is not None:
            media_form.addRow("", self.folder_hint_label)

        _add_section_header(media_form, "재생 및 비율")
        media_form.addRow("전환 간격:", self.sec_input_box)
        media_form.addRow("미디어 맞춤:", self.media_mode_combo)
        media_form.addRow("비율 자동 맞춤:", self.slide_auto_aspect_cb)

        _add_section_header(media_form, "동영상 설정")
        media_form.addRow("영상 전환:", self.video_transition_combo)
        media_form.addRow("", self.video_transition_hint)
        media_form.addRow("듀얼 페이드:", self.video_dual_fade_box)
        media_form.addRow("", self.video_dual_fade_hint)
        media_form.addRow("영상 디코드:", self.video_decode_combo)
        media_form.addRow("", self.video_decode_hint)
        self._video_dual_fade_label = media_form.labelForField(self.video_dual_fade_box)
        self._video_dual_fade_hint_label = media_form.labelForField(self.video_dual_fade_hint)

        # Tab 2: 📐 위젯 & 외형
        _add_section_header(widget_form, "크기 및 종횡비")
        if self.bulk_mode and hasattr(self, "bulk_notice_card"):
            widget_form.addRow(self.bulk_notice_card)
            self.width_input.setEnabled(False)
            self.height_input.setEnabled(False)
            self.width_input_box.setEnabled(False)
            self.height_input_box.setEnabled(False)
            if hasattr(self, "ratio_row_widget"):
                self.ratio_row_widget.setEnabled(False)
        if self.bulk_mode and hasattr(self, "bulk_spread_card"):
            widget_form.addRow(self.bulk_spread_card)
        widget_form.addRow("너비:", self.width_input_box)
        widget_form.addRow("높이:", self.height_input_box)
        widget_form.addRow("", self.ratio_row_widget)
        widget_form.addRow("확장 기준점:", self.anchor_picker)


        _add_section_header(widget_form, "표시 및 레이어")
        widget_form.addRow("불투명도:", self.opacity_row_widget)
        widget_form.addRow("레이어:", self.layer_combo)
        widget_form.addRow("클릭 잠금:", self.lock_cb)

        _add_section_header(widget_form, "테마 스타일")
        widget_form.addRow("배경색:", self.bg_combo)
        widget_form.addRow("모서리:", self.corner_combo)

        # Tab 3: ⚡ 연동 & 시스템
        _add_section_header(system_form, "프로그램 실행 연동")
        system_form.addRow("실행 파일:", self.exec_btn)
        system_form.addRow("실행 경로:", self.exec_label)
        system_form.addRow("포커싱 대상:", self.focus_binding_label)
        system_form.addRow("", self._focus_bind_row_widget)

        _add_section_header(system_form, "오디오")
        system_form.addRow("음소거:", self.mute_checkbox)

        _add_section_header(system_form, "저장 공간 관리")
        system_form.addRow("영상 캐시:", self.video_cache_usage_label)
        system_form.addRow("", self.video_cache_action_row_widget)
        
        btns = QHBoxLayout(); apply = QPushButton("저장"); cancel = QPushButton("취소")
        btns.setSpacing(10)
        btns.setContentsMargins(0, 0, 0, 0)
        apply.setObjectName("primaryBtn")
        apply.setFixedSize(86, 32)
        cancel.setFixedSize(86, 32)
        self.master_btn.setFixedSize(146, 32)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(4, 6, 4, 2)
        action_row.setSpacing(10)
        action_row.addWidget(self.shortcut_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        action_row.addWidget(self.master_btn, 0, Qt.AlignmentFlag.AlignLeft)
        action_row.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(apply)
        action_row.addLayout(btns)
        root.addLayout(action_row)
        
        self.folder_btn.clicked.connect(self.select_folder)
        self.file_btn.clicked.connect(self.select_file)
        self.edit_slide_list_btn.clicked.connect(self._on_edit_slide_list_clicked)
        self.folder_help_btn.toggled.connect(self._set_folder_help_panel_visible)
        self.exec_btn.clicked.connect(self.select_exec)
        self.focus_bind_btn.clicked.connect(self._start_focus_capture)
        self.focus_bind_clear_btn.clicked.connect(self._clear_focus_binding)
        self.video_transition_combo.currentIndexChanged.connect(self._sync_video_transition_dependent_ui)
        self.video_cache_clear_btn.clicked.connect(self._clear_video_proxy_cache)
        self.master_btn.clicked.connect(self.open_master)
        apply.clicked.connect(self.accept); cancel.clicked.connect(self.reject)

        if self.bulk_mode:
            self._folder_btn_row_widget.setEnabled(False)
            self.edit_slide_list_btn.setEnabled(False)
            self.exec_btn.setEnabled(False)
            self._focus_bind_row_widget.setEnabled(False)
            self.folder_label.setText("일괄 설정 모드에서는 미디어/실행파일 설정이 제외됩니다.")
            self.folder_label.setStyleSheet("color: #8fa5c4; font-style: italic;")
            self.exec_label.setText("-")
            self.focus_binding_label.setText("-")
            self.master_btn.setVisible(False)

        self._set_folder_help_panel_visible(False)
        self._sync_edit_slide_btn_state()
        QTimer.singleShot(0, self._apply_title_bar_theme)
        QTimer.singleShot(0, self._sync_video_transition_dependent_ui)
        QTimer.singleShot(0, self._refresh_video_proxy_cache_usage)
        QTimer.singleShot(0, self._sync_dialog_height)

    def _sync_edit_slide_btn_state(self):
        if self.bulk_mode:
            self.edit_slide_list_btn.setEnabled(False)
            return
        has_folder = bool(self.folder_path and os.path.isdir(self.folder_path))
        self.edit_slide_list_btn.setEnabled(has_folder)
        if has_folder:
            self.edit_slide_list_btn.setToolTip("슬라이드에 포함/제외할 파일을 선택합니다.")
        else:
            self.edit_slide_list_btn.setToolTip("폴더를 선택하면 슬라이드 목록을 편집할 수 있습니다.")

    def _switch_tab(self, index):
        idx = max(0, min(int(index), len(self._seg_buttons) - 1))
        self.stack.setCurrentIndex(idx)
        from mywidgetbox_core import render_vector_icon
        icons = ["media", "widget", "system"]
        for i, btn in enumerate(self._seg_buttons):
            is_active = (i == idx)
            btn.setProperty("active", "true" if is_active else "false")
            if i < len(icons):
                btn.setIcon(render_vector_icon(icons[i], "#ffffff" if is_active else "#8da6c7", 16))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _set_shortcut_panel_visible(self, expanded):
        expanded = bool(expanded)
        self.shortcut_toggle.blockSignals(True)
        self.shortcut_toggle.setChecked(expanded)
        self.shortcut_toggle.blockSignals(False)
        self.shortcut_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.shortcut_toggle.setText("단축키 안내")
        if expanded:
            self._place_shortcut_panel()
            self.shortcut_panel.show()
            self.shortcut_panel.raise_()
        else:
            self.shortcut_panel.hide()
        self.shortcut_panel.update()

    def _set_folder_help_panel_visible(self, expanded):
        want_visible = bool(expanded)
        self.folder_help_btn.blockSignals(True)
        self.folder_help_btn.setChecked(want_visible)
        self.folder_help_btn.blockSignals(False)
        if want_visible:
            self._place_folder_help_panel()
            self.folder_help_panel.show()
            self.folder_help_panel.raise_()
        else:
            self.folder_help_panel.hide()
        self.folder_help_panel.update()

    def _place_folder_help_panel(self):
        self.folder_help_panel.adjustSize()
        hint = self.folder_help_panel.sizeHint()
        popup_w = max(360, max(360, hint.width()))
        popup_h = hint.height()

        anchor_global = self.folder_help_btn.mapToGlobal(QPoint(0, self.folder_help_btn.height() + 6))
        x = anchor_global.x()
        y = anchor_global.y()

        screen = QGuiApplication.screenAt(anchor_global) or self.screen() or QGuiApplication.primaryScreen()
        if screen:
            ag = screen.availableGeometry()
            max_x = ag.right() - popup_w - 8
            min_x = ag.left() + 8
            x = max(min_x, min(x, max_x))
            available_below = max(120, ag.bottom() - y - 8)
            popup_h = min(popup_h, available_below)

        self.folder_help_panel.setGeometry(x, y, popup_w, popup_h)

    def _sync_dialog_height(self):
        # Release any previous fixed-height lock so collapse/expand can recalculate.
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        if self.layout():
            self.layout().invalidate()
            self.layout().activate()
        try:
            self.adjustSize()
        except Exception:
            pass
        target_height = max(
            420,
            int(self.minimumSizeHint().height()),
            int(self.sizeHint().height()),
        )
        if self.height() != target_height:
            self.resize(self.width(), target_height)
        self.updateGeometry()
        self.update()

    def _set_form_row_visible(self, form_layout, field_widget, visible):
        if form_layout is None or field_widget is None:
            return
        want_visible = bool(visible)
        # Qt6 provides row-level visibility; use it first to avoid stale row spacing.
        try:
            if hasattr(form_layout, "setRowVisible"):
                form_layout.setRowVisible(field_widget, want_visible)
                return
        except Exception:
            pass
        label = None
        try:
            label = form_layout.labelForField(field_widget)
        except Exception:
            label = None
        if isinstance(label, QWidget):
            label.setVisible(want_visible)
        if isinstance(field_widget, QWidget):
            field_widget.setVisible(want_visible)

    def _sync_video_transition_dependent_ui(self):
        is_dual = (
            int(self.video_transition_combo.currentIndex())
            == int(DesktopWidget.VIDEO_TRANSITION_DUAL)
        )
        form_layout = getattr(self, "_media_form", None)
        self._set_form_row_visible(form_layout, self.video_dual_fade_box, bool(is_dual))
        self._set_form_row_visible(form_layout, self.video_dual_fade_hint, bool(is_dual))
        QTimer.singleShot(0, self._sync_dialog_height)

    @staticmethod
    def _format_size_bytes(num_bytes):
        try:
            size = float(max(0, int(num_bytes)))
        except Exception:
            size = 0.0
        units = ["B", "KB", "MB", "GB", "TB"]
        idx = 0
        while size >= 1024.0 and idx < (len(units) - 1):
            size /= 1024.0
            idx += 1
        if idx == 0:
            return f"{int(size)} {units[idx]}"
        return f"{size:.1f} {units[idx]}"

    def _video_proxy_cache_dir(self):
        try:
            return str(DesktopWidget._resolve_video_proxy_dir() or "")
        except Exception:
            base = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
            if not base:
                base = os.path.expanduser("~")
            return os.path.join(base, "MyHomeApp", "video_proxy_cache")

    def _video_proxy_cache_usage(self):
        cache_dir = self._video_proxy_cache_dir()
        total = 0
        count = 0
        if os.path.isdir(cache_dir):
            for root, _dirs, files in os.walk(cache_dir):
                for name in files:
                    fp = os.path.join(root, name)
                    try:
                        total += int(os.path.getsize(fp))
                        count += 1
                    except Exception:
                        pass
        return cache_dir, int(total), int(count)

    @staticmethod
    def _themed_message_box_style():
        return """
            QMessageBox {
                background-color: #23344d;
            }
            QMessageBox QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                min-height: 30px;
                border-radius: 8px;
                padding: 0 12px;
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                font-weight: 600;
            }
            QMessageBox QPushButton:hover {
                background-color: #3f5e8e;
            }
        """

    def _show_themed_message_box(self, icon, title, text, buttons, default_button=QMessageBox.StandardButton.NoButton):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(str(title))
        box.setText(str(text))
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.StandardButton.NoButton:
            box.setDefaultButton(default_button)
        box.setStyleSheet(self._themed_message_box_style())
        try:
            self._apply_title_bar_theme_for_window(box)
        except Exception:
            pass
        return box.exec()

    def _refresh_video_proxy_cache_usage(self):
        cache_dir, total, count = self._video_proxy_cache_usage()
        self.video_cache_usage_label.setText(
            f"{self._format_size_bytes(total)} ({int(count)}개 파일)"
        )
        self.video_cache_usage_label.setToolTip(cache_dir)
        self.video_cache_clear_btn.setEnabled(int(count) > 0)

    def _clear_video_proxy_cache(self):
        cache_dir, total, count = self._video_proxy_cache_usage()
        if int(count) <= 0:
            self._refresh_video_proxy_cache_usage()
            return
        confirm = self._show_themed_message_box(
            QMessageBox.Icon.Question,
            "영상 캐시 정리",
            f"영상 캐시 {self._format_size_bytes(total)} ({int(count)}개 파일)를 삭제할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if int(confirm) != int(QMessageBox.StandardButton.Yes):
            return
        removed = 0
        failed = 0
        if os.path.isdir(cache_dir):
            for root, dirs, files in os.walk(cache_dir, topdown=False):
                for name in files:
                    fp = os.path.join(root, name)
                    try:
                        os.remove(fp)
                        removed += 1
                    except Exception:
                        failed += 1
                for name in dirs:
                    dp = os.path.join(root, name)
                    try:
                        os.rmdir(dp)
                    except Exception:
                        pass
        self._refresh_video_proxy_cache_usage()
        if failed > 0:
            self._show_themed_message_box(
                QMessageBox.Icon.Warning,
                "영상 캐시 정리",
                f"{int(removed)}개 파일 삭제됨, {int(failed)}개 파일은 삭제하지 못했습니다.\n"
                "재생 중인 파일은 잠시 후 다시 시도해 주세요.",
                QMessageBox.StandardButton.Ok,
            )
        else:
            self._show_themed_message_box(
                QMessageBox.Icon.Information,
                "영상 캐시 정리",
                f"{int(removed)}개 파일을 삭제했습니다.",
                QMessageBox.StandardButton.Ok,
            )

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
        self._sync_video_transition_dependent_ui()
        self._refresh_focus_binding_label()
        if self.shortcut_toggle.isChecked():
            self._place_shortcut_panel()
        if self.folder_help_btn.isChecked() and self.folder_help_panel.isVisible():
            self._place_folder_help_panel()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.shortcut_toggle.isChecked() and self.shortcut_panel.isVisible():
            self._place_shortcut_panel()
        if self.folder_help_btn.isChecked() and self.folder_help_panel.isVisible():
            self._place_folder_help_panel()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.shortcut_toggle.isChecked() and self.shortcut_panel.isVisible():
            self._place_shortcut_panel()
        if self.folder_help_btn.isChecked() and self.folder_help_panel.isVisible():
            self._place_folder_help_panel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if hasattr(self, "shortcut_panel") and self.shortcut_panel is not None and self.shortcut_panel.isVisible():
                self._set_shortcut_panel_visible(False)
                event.accept()
                return
            if hasattr(self, "folder_help_panel") and self.folder_help_panel is not None and self.folder_help_panel.isVisible():
                self._set_folder_help_panel_visible(False)
                event.accept()
                return
        super().keyPressEvent(event)

    def done(self, r):
        if hasattr(self, "shortcut_toggle"):
            self.shortcut_toggle.setChecked(False)
        if hasattr(self, "shortcut_panel") and self.shortcut_panel is not None:
            self.shortcut_panel.hide()
        if hasattr(self, "folder_help_btn"):
            self.folder_help_btn.setChecked(False)
        if hasattr(self, "folder_help_panel") and self.folder_help_panel is not None:
            self.folder_help_panel.hide()
        super().done(r)

    def hideEvent(self, event):
        if hasattr(self, "shortcut_toggle"):
            self.shortcut_toggle.setChecked(False)
        if hasattr(self, "shortcut_panel") and self.shortcut_panel is not None:
            self.shortcut_panel.hide()
        if hasattr(self, "folder_help_btn"):
            self.folder_help_btn.setChecked(False)
        if hasattr(self, "folder_help_panel") and self.folder_help_panel is not None:
            self.folder_help_panel.hide()
        super().hideEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "_focus_capture_timer") and self._focus_capture_timer.isActive():
            self._focus_capture_timer.stop()
            self._focus_capture_deadline = 0.0
        if hasattr(self, "shortcut_toggle"):
            self.shortcut_toggle.setChecked(False)
        if hasattr(self, "shortcut_panel") and self.shortcut_panel is not None:
            self.shortcut_panel.hide()
        if hasattr(self, "folder_help_btn"):
            self.folder_help_btn.setChecked(False)
        if hasattr(self, "folder_help_panel") and self.folder_help_panel is not None:
            self.folder_help_panel.hide()
        super().closeEvent(event)

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if path:
            self._apply_selected_folder(path)
            self._set_folder_help_panel_visible(False)

    def _scan_media_paths_for_folder(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            return []
        if DesktopWidget and hasattr(DesktopWidget, "_supported_media_extensions"):
            media_ext = tuple(DesktopWidget._supported_media_extensions())
        else:
            media_ext = (
                ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif",
                ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"
            )
        try:
            names = sorted(os.listdir(folder_path))
        except OSError:
            return []
        paths = []
        for name in names:
            p = os.path.join(folder_path, str(name))
            if os.path.isfile(p) and str(name).lower().endswith(media_ext):
                paths.append(os.path.normpath(p))
        return paths

    def _apply_selected_folder(self, path):
        folder_path = os.path.normpath(str(path or ""))
        media_paths = self._scan_media_paths_for_folder(folder_path)
        if not media_paths:
            QMessageBox.information(
                self,
                "미디어 없음",
                "선택한 폴더에 지원되는 미디어 파일(이미지, GIF, 동영상)이 없습니다.",
            )
            return

        choice_dialog = FolderLayoutChoiceDialog(self, folder_path)
        if choice_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if choice_dialog.choice == "spread":
            spread_dialog = FolderSpreadDialog(
                self,
                folder_path,
                media_paths,
                QSize(int(self.width_input.value()), int(self.height_input.value())),
            )
            if spread_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            self.pending_spread_config = dict(spread_dialog.result_data or {})
            item_paths = list(self.pending_spread_config.get("item_paths", []) or [])
            self.folder_path = folder_path
            self.folder_item_paths = item_paths[:1]
            if "w" in self.pending_spread_config:
                self.width_input.setValue(int(self.pending_spread_config["w"]))
            if "h" in self.pending_spread_config:
                self.height_input.setValue(int(self.pending_spread_config["h"]))
            label_text = f"{folder_path} (스프레드 {len(item_paths)}개)"
            self.folder_label.setText(label_text)
            self.folder_label.setToolTip(folder_path)
            return

        if choice_dialog.choice == "slide":
            slide_dialog = FolderSlideDialog(self, folder_path, media_paths)
            if slide_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            self.pending_spread_config = None
            self.folder_path = folder_path
            chosen_paths = list(slide_dialog.result_paths or [])
            if len(chosen_paths) == len(media_paths):
                self.folder_item_paths = []
            else:
                self.folder_item_paths = chosen_paths
            self._update_folder_label_text()
            return

        self.pending_spread_config = None
        self.folder_path = folder_path
        self.folder_item_paths = []
        self._update_folder_label_text()

    def _update_folder_label_text(self):
        self._sync_edit_slide_btn_state()
        if not self.folder_path:
            self.folder_label.setText("미지정")
            self.folder_label.setToolTip("")
            return

        if self.pending_spread_config:
            count = len(self.pending_spread_config.get("item_paths", []) or [])
            self.folder_label.setText(f"{self.folder_path} (스프레드 {count}개)")
        elif self.folder_item_paths:
            count = len(self.folder_item_paths)
            if count == 1:
                self.folder_label.setText(f"{self.folder_path} ({os.path.basename(self.folder_item_paths[0])})")
            else:
                self.folder_label.setText(f"{self.folder_path} (슬라이드 {count}개)")
        else:
            self.folder_label.setText(self.folder_path)
        self.folder_label.setToolTip(self.folder_path)

    def _on_edit_slide_list_clicked(self):
        target_folder = self.folder_path
        if not target_folder or not os.path.isdir(target_folder):
            if self.folder_item_paths:
                for p in self.folder_item_paths:
                    if p and os.path.isfile(p):
                        target_folder = os.path.dirname(os.path.abspath(p))
                        break
        if not target_folder or not os.path.isdir(target_folder):
            QMessageBox.information(
                self,
                "폴더 없음",
                "슬라이드 목록을 수정할 폴더가 설정되지 않았습니다.\n먼저 '폴더 선택'으로 폴더를 지정해주세요."
            )
            return

        media_paths = self._scan_media_paths_for_folder(target_folder)
        if not media_paths:
            QMessageBox.information(
                self,
                "미디어 없음",
                "해당 폴더에 지원되는 이미지, GIF, 영상 미디어 파일이 없습니다."
            )
            return

        current_selected = list(self.folder_item_paths) if self.folder_item_paths else list(media_paths)
        slide_dialog = FolderSlideDialog(
            self,
            target_folder,
            media_paths,
            pre_selected_paths=current_selected
        )
        if slide_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        chosen_paths = list(slide_dialog.result_paths or [])
        if not chosen_paths:
            return

        self.pending_spread_config = None
        self.folder_path = target_folder
        if len(chosen_paths) == len(media_paths):
            self.folder_item_paths = []
        else:
            self.folder_item_paths = chosen_paths
        self._update_folder_label_text()

    def _apply_media_aspect_to_inputs(self, media_path):
        if not media_path or not os.path.isfile(media_path):
            return False
        sz = get_media_native_size(media_path)
        if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
            iw, ih = sz[0], sz[1]
            curr_w = self.width_input.value()
            curr_h = self.height_input.value()
            target_w, target_h = calc_smart_aspect_size(iw, ih, curr_w, curr_h)
            self._syncing_aspect_size = True
            try:
                self.width_input.setValue(target_w)
                self.height_input.setValue(target_h)
                self._current_aspect_ratio = float(target_w) / max(1.0, float(target_h))
            finally:
                self._syncing_aspect_size = False
            return True
        return False

    def _on_fit_aspect_clicked(self):
        target_path = None
        if self.folder_item_paths:
            for p in self.folder_item_paths:
                if p and os.path.isfile(p):
                    target_path = p
                    break
        if not target_path and self.folder_path and os.path.isdir(self.folder_path):
            scanned = self._scan_media_paths_for_folder(self.folder_path)
            if scanned:
                target_path = scanned[0]

        if not target_path:
            QMessageBox.information(self, "미디어 없음", "선택된 미디어 파일 또는 폴더가 없습니다.")
            return

        if not self._apply_media_aspect_to_inputs(target_path):
            QMessageBox.information(self, "비율 확인 불가", "미디어 파일의 해상도 비율을 확인할 수 없습니다.")

    def _on_fit_screen_clicked(self):
        self._fit_to_screen_geometry(include_taskbar=False)

    def _fit_to_screen_geometry(self, include_taskbar=False):
        screen = None
        if self.parent() and hasattr(self.parent(), "geometry"):
            screen = QApplication.screenAt(self.parent().geometry().center())
        if not screen:
            screen = QApplication.primaryScreen()

        if not screen:
            QMessageBox.information(self, "화면 감지 불가", "현재 화면 정보를 가져올 수 없습니다.")
            return

        if include_taskbar:
            geo = screen.geometry()
        else:
            geo = screen.availableGeometry()

        sw = max(100, int(geo.width()))
        sh = max(100, int(geo.height()))

        target_path = None
        if self.folder_item_paths:
            for p in self.folder_item_paths:
                if p and os.path.isfile(p):
                    target_path = p
                    break
        if not target_path and self.folder_path and os.path.isdir(self.folder_path):
            scanned = self._scan_media_paths_for_folder(self.folder_path)
            if scanned:
                target_path = scanned[0]

        iw, ih = 0, 0
        if target_path and os.path.isfile(target_path):
            sz = get_media_native_size(target_path)
            if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
                iw, ih = sz[0], sz[1]

        if iw <= 0 or ih <= 0:
            iw = max(1, self.width_input.value())
            ih = max(1, self.height_input.value())

        scale = min(float(sw) / float(iw), float(sh) / float(ih))
        target_w = max(50, min(5000, int(round(iw * scale))))
        target_h = max(50, min(5000, int(round(ih * scale))))

        self._syncing_aspect_size = True
        try:
            self.width_input.setValue(target_w)
            self.height_input.setValue(target_h)
            self._current_aspect_ratio = float(target_w) / max(1.0, float(target_h))
        finally:
            self._syncing_aspect_size = False

    def select_file(self):
        filter_str = "미디어 파일 (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.mov *.avi *.mkv *.webm *.m4v);;모든 파일 (*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "미디어 파일 선택", "", filter_str)
        if not paths:
            return
        norm_paths = [os.path.normpath(p) for p in paths if p and os.path.isfile(p)]
        if not norm_paths:
            return
        folder_path = os.path.dirname(norm_paths[0])
        self.pending_spread_config = None
        self.folder_path = folder_path
        self.folder_item_paths = norm_paths
        if len(norm_paths) == 1:
            label_text = f"{folder_path} ({os.path.basename(norm_paths[0])})"
            self._apply_media_aspect_to_inputs(norm_paths[0])
        else:
            label_text = f"{folder_path} (선택 {len(norm_paths)}개)"
            self._apply_media_aspect_to_inputs(norm_paths[0])
        self.folder_label.setText(label_text)
        self.folder_label.setToolTip(folder_path)
        self._set_folder_help_panel_visible(False)

    def select_exec(self):
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "실행 파일 및 바로가기 (*.exe *.lnk *.url);;모든 파일 (*)")
        if path: self.exec_path = path; self.exec_label.setText(os.path.basename(path))

    def _refresh_focus_binding_label(self):
        text = ""
        if self._focus_binding_supported:
            try:
                text = str(self._focus_binding_host.get_exec_manual_focus_summary() or "").strip()
            except Exception:
                text = ""
        else:
            text = str(self.focus_binding_label.text() or "").strip()
        if not text:
            text = "자동 (실행파일 기준)"
        self.focus_binding_label.setText(text)

    def _finish_focus_capture(self, success, message):
        if self._focus_capture_timer.isActive():
            self._focus_capture_timer.stop()
        self._focus_capture_deadline = 0.0
        self.focus_bind_btn.setEnabled(self._focus_binding_supported)
        self.focus_bind_clear_btn.setEnabled(self._focus_binding_supported)
        self._refresh_focus_binding_label()

    def _start_focus_capture(self):
        if not self._focus_binding_supported:
            return
        if self._focus_capture_timer.isActive():
            return
        self.focus_bind_btn.setEnabled(False)
        self.focus_bind_clear_btn.setEnabled(False)
        self.focus_binding_label.setText("대기 중: 12초 안에 대상 창을 한 번 클릭하세요")
        self._focus_capture_deadline = float(time.monotonic()) + 12.0
        self._focus_capture_timer.start()

    def _on_focus_capture_tick(self):
        if not self._focus_binding_supported:
            if self._focus_capture_timer.isActive():
                self._focus_capture_timer.stop()
            self._focus_capture_deadline = 0.0
            return
        if float(time.monotonic()) >= float(self._focus_capture_deadline or 0.0):
            self._finish_focus_capture(False, "시간 내에 대상 창을 찾지 못했습니다.")
            return
        try:
            hwnd = int(self._focus_binding_host._capture_bindable_foreground_hwnd() or 0)
        except Exception:
            hwnd = 0
        if hwnd <= 0:
            return
        try:
            ok = bool(self._focus_binding_host._set_manual_focus_binding_from_hwnd(hwnd, persist=True))
        except Exception:
            ok = False
        if bool(ok):
            self._finish_focus_capture(True, "포커싱 대상이 저장되었습니다.")
        else:
            self._finish_focus_capture(False, "선택한 창을 포커싱 대상으로 저장하지 못했습니다.")

    def _clear_focus_binding(self):
        if not self._focus_binding_supported:
            return
        try:
            self._focus_binding_host._clear_manual_focus_binding(persist=True, clear_bound=True)
        except Exception:
            pass

    @staticmethod
    def _apply_title_bar_theme_for_window(window):
        try:
            import ctypes
            hwnd = int(window.winId())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(20),
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        except Exception:
            pass

    def open_master(self):

        master = self.parent().manager if hasattr(self.parent(), 'manager') else None
        
        if master:
            anchor_rect = self.frameGeometry()
            QTimer.singleShot(
                0,
                lambda m=master, a=QRect(anchor_rect): m.show_master_window(anchor_rect=a, restart=True),
            )
            self.reject()

    def get_spread_relayout_config(self):
        """임시 그룹 일괄 설정에서 선택한 스프레드 재배치 설정 반환 (미선택 시 None)"""
        if not (self.bulk_mode and hasattr(self, "spread_relayout_cb") and self.spread_relayout_cb.isChecked()):
            return None
        fit_idx = self.bulk_spread_fit_combo.currentIndex()
        fit_strategy_map = {
            0: "auto_aspect",
            1: "justified_rows",
            2: "justified_columns",
            3: "crop_fill",
            4: "fit_inside",
        }
        fit_strategy = fit_strategy_map.get(fit_idx, "auto_aspect")

        dir_idx = self.bulk_spread_dir_combo.currentIndex()
        dir_map = {
            0: "top-left",
            1: "top-right",
            2: "bottom-left",
            3: "bottom-right",
        }
        return {
            "fit_strategy": fit_strategy,
            "cols": int(self.bulk_spread_cols_spin.value()),
            "rows": int(self.bulk_spread_rows_spin.value()),
            "margin": int(self.bulk_spread_margin_spin.value()),
            "direction": dir_map.get(dir_idx, "top-left"),
            "w": int(self.bulk_spread_w_spin.value()),
            "h": int(self.bulk_spread_h_spin.value()),
        }


