import os
import time

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from mycanvas_core import _as_bool
from mycanvas_ui_primitives import DownwardComboBox

DesktopWidget = None


def bind_settings_dialog_desktop_widget(desktop_widget_cls):
    global DesktopWidget
    DesktopWidget = desktop_widget_cls

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
            QLabel#settingsSectionTitle {
                color: #a7c1eb;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }
            QFrame#settingsSectionLine {
                background-color: #3f567a;
                border: none;
                min-height: 1px;
                max-height: 1px;
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
            QToolButton#folderHelpBtn {
                color: #e8efff;
                background: transparent;
                border: none;
                padding: 0px;
                font-weight: 700;
            }
            QToolButton#folderHelpBtn:hover {
                background: transparent;
            }
            QToolButton#folderHelpBtn:checked {
                background: transparent;
            }
            QFrame#shortcutPanel {
                background-color: #233854;
                border: 1px solid #5879a9;
                border-radius: 10px;
            }
            QFrame#folderHelpPanel {
                background-color: #20324b;
                border: 1px solid #4f6e97;
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
        self._left_form = left_form
        self._right_form = right_form

        content_row.addWidget(left_panel, 5)
        content_row.addWidget(right_panel, 5)

        s = settings_data if settings_data else {}
        
        self.folder_path = s.get('folder_path', "")
        self.exec_path = s.get('exec_path', "")

        self.folder_label = QLabel(self.folder_path if self.folder_path else "미지정")
        self.folder_label.setObjectName("pathLabel")
        self.folder_label.setWordWrap(True)
        self.folder_label.setToolTip(self.folder_path if self.folder_path else "")
        self.folder_hint_label = None
        self.folder_btn = QPushButton("폴더 선택")
        self.folder_help_btn = QToolButton()
        self.folder_help_btn.setObjectName("folderHelpBtn")
        self.folder_help_btn.setText("")
        self.folder_help_btn.setToolTip("미디어 폴더 모드 설명")
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
        folder_btn_row.addWidget(self.folder_btn, 1)
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
            "미디어 폴더 모드 안내\n"
            "- 폴더 내부 이미지/영상 파일을 이름 순서대로 재생합니다."
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
            "싱글: 가볍지만 영상 전환 시 깜빡일 수 있습니다.\n"
            "듀얼: 영상→영상 전환이 매끄럽지만 메모리 사용량이 증가합니다."
        )
        self.video_transition_hint.setObjectName("pathLabel")
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
            "재생 시 원본 대신 저해상도 프록시를 자동 생성/사용해 GPU/메모리 사용량을 줄입니다."
        )
        self.video_decode_hint.setObjectName("pathLabel")
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
        self.video_dual_fade_ms_spin.setSuffix(" ms")
        self.video_dual_fade_ms_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.video_dual_fade_ms_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.video_dual_fade_ms_spin.setValue(
            DesktopWidget.coerce_video_dual_fade_ms(
                s.get('video_dual_fade_ms', DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS)
            )
        )
        self.video_dual_fade_hint = QLabel(
            "듀얼 전환 시 짧은 페이드 길이입니다. 값이 클수록 더 부드럽게 보일 수 있습니다."
        )
        self.video_dual_fade_hint.setObjectName("pathLabel")
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

        def _add_section_header(form_layout, title_text):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 8, 0, 2)
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

        _add_section_header(left_form, "실행 / 연동")
        left_form.addRow("미디어 폴더:", self._folder_btn_row_widget)
        left_form.addRow("", self.folder_label)
        if self.folder_hint_label is not None:
            left_form.addRow("", self.folder_hint_label)
        left_form.addRow("실행 파일:", self.exec_btn)
        left_form.addRow("", self.exec_label)
        left_form.addRow("포커싱 대상:", self.focus_binding_label)
        left_form.addRow("", self._focus_bind_row_widget)

        _add_section_header(left_form, "위젯")
        left_form.addRow("너비:", self.width_input)
        left_form.addRow("높이:", self.height_input)
        left_form.addRow("불투명도(%):", self.opacity_spinbox)
        left_form.addRow("", self.opacity_slider)
        left_form.addRow("레이어:", self.layer_combo)
        left_form.addRow("클릭 잠금:", self.lock_cb)

        _add_section_header(left_form, "외형")
        left_form.addRow("배경색:", self.bg_combo)
        left_form.addRow("모서리:", self.corner_combo)

        _add_section_header(right_form, "재생 / 전환")
        right_form.addRow("전환 간격(초):", self.sec_input)
        right_form.addRow("미디어 맞춤:", self.media_mode_combo)
        right_form.addRow("영상 전환:", self.video_transition_combo)
        right_form.addRow("", self.video_transition_hint)
        right_form.addRow("듀얼 페이드:", self.video_dual_fade_ms_spin)
        right_form.addRow("", self.video_dual_fade_hint)

        _add_section_header(right_form, "영상 품질 / 캐시")
        right_form.addRow("영상 디코드:", self.video_decode_combo)
        right_form.addRow("", self.video_decode_hint)
        right_form.addRow("영상 캐시:", self.video_cache_usage_label)
        right_form.addRow("", self.video_cache_action_row_widget)

        _add_section_header(right_form, "오디오 / 성능")
        right_form.addRow("음소거:", self.mute_checkbox)
        right_form.addRow("성능 보호:", self.gpu_guard_checkbox)
        self._video_dual_fade_label = right_form.labelForField(self.video_dual_fade_ms_spin)
        self._video_dual_fade_hint_label = right_form.labelForField(self.video_dual_fade_hint)
        
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
        self.folder_help_btn.toggled.connect(self._set_folder_help_panel_visible)
        self.exec_btn.clicked.connect(self.select_exec)
        self.focus_bind_btn.clicked.connect(self._start_focus_capture)
        self.focus_bind_clear_btn.clicked.connect(self._clear_focus_binding)
        self.video_transition_combo.currentIndexChanged.connect(self._sync_video_transition_dependent_ui)
        self.video_cache_clear_btn.clicked.connect(self._clear_video_proxy_cache)
        self.master_btn.clicked.connect(self.open_master)
        apply.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        self._set_folder_help_panel_visible(False)
        QTimer.singleShot(0, self._apply_title_bar_theme)
        QTimer.singleShot(0, self._sync_video_transition_dependent_ui)
        QTimer.singleShot(0, self._refresh_video_proxy_cache_usage)
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

    def _set_folder_help_panel_visible(self, expanded):
        want_visible = bool(expanded)
        self.folder_help_btn.blockSignals(True)
        self.folder_help_btn.setChecked(want_visible)
        self.folder_help_btn.blockSignals(False)
        if want_visible:
            self._place_folder_help_panel()
            self.folder_help_panel.show()
            self.folder_help_panel.raise_()
            self.folder_help_panel.activateWindow()
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
        form_layout = getattr(self, "_right_form", None)
        self._set_form_row_visible(form_layout, self.video_dual_fade_ms_spin, bool(is_dual))
        self._set_form_row_visible(form_layout, self.video_dual_fade_hint, bool(is_dual))
        # Defer resize until combo popup settles to reduce repaint artifacts.
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

    def closeEvent(self, event):
        if hasattr(self, "_focus_capture_timer") and self._focus_capture_timer.isActive():
            self._focus_capture_timer.stop()
            self._focus_capture_deadline = 0.0
        if hasattr(self, "shortcut_panel") and self.shortcut_panel.isVisible():
            self.shortcut_panel.hide()
        if hasattr(self, "folder_help_panel") and self.folder_help_panel.isVisible():
            self.folder_help_panel.hide()
        super().closeEvent(event)

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if path:
            self.folder_path = path
            self.folder_label.setText(path)
            self.folder_label.setToolTip(path)
            self._set_folder_help_panel_visible(False)

    def select_exec(self):
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "실행 파일 (*.exe *.lnk);;모든 파일 (*)")
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


