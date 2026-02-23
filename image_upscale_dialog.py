import os
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from image_upscale_tool import find_ffmpeg_binary, upscale_image_file
from mycanvas_ui_primitives import DownwardComboBox, MediaToolWorker


class ImageUpscaleDialog(QDialog):
    def __init__(self, parent=None, title_bar_theme_fn=None):
        super().__init__(parent)
        self.setObjectName("imageToolDialog")
        self.setWindowTitle("이미지 업스케일")
        self.setWindowIcon(QIcon())
        self.resize(760, 520)
        self.setMinimumSize(700, 500)
        self._worker = None
        self._worker_action = ""
        self._ffmpeg_path = ""
        self._title_bar_themed = False
        self._title_bar_theme_fn = title_bar_theme_fn if callable(title_bar_theme_fn) else None
        self.setStyleSheet("""
            QDialog#imageToolDialog {
                background-color: #1d2a3d;
            }
            QFrame#toolCard {
                background-color: #23344d;
                border: 1px solid #3f567a;
                border-radius: 12px;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
            }
            QLabel#toolTitle {
                color: #eef3ff;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#toolSubtitle {
                color: #c2d1ea;
                font-size: 12px;
            }
            QLabel#sectionTitle {
                color: #a7c1eb;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#statusLabel {
                color: #d8e6ff;
                font-size: 12px;
                font-weight: 600;
            }
            QLineEdit, QSpinBox, QComboBox {
                min-height: 32px;
                color: #edf3ff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                border-radius: 9px;
                padding: 2px 10px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #77a3f2;
            }
            QPlainTextEdit {
                color: #e6eefc;
                background-color: #1a2740;
                border: 1px solid #4a6288;
                border-radius: 10px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 9px;
                font-size: 12px;
                font-weight: 600;
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #3f5e8e;
            }
            QPushButton#primaryBtn {
                background-color: #4f79de;
                border: 1px solid #7e9eeb;
            }
            QPushButton#primaryBtn:hover {
                background-color: #5d86e6;
            }
            QCheckBox {
                color: #e6eefc;
                spacing: 6px;
                min-height: 24px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QFrame(self)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(2)
        title = QLabel("이미지 업스케일")
        title.setObjectName("toolTitle")
        subtitle = QLabel("ffmpeg 기반 업스케일 기능만 제공합니다.")
        subtitle.setObjectName("toolSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        card = QFrame(self)
        card.setObjectName("toolCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        root.addWidget(card, 1)

        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.setContentsMargins(0, 0, 0, 0)
        ffmpeg_row.setSpacing(8)
        ffmpeg_row.addWidget(QLabel("ffmpeg:"), 0)
        self.ffmpeg_path_label = QLabel("검색 중...")
        self.ffmpeg_path_label.setWordWrap(True)
        self.ffmpeg_refresh_btn = QPushButton("재검색")
        self.ffmpeg_refresh_btn.setFixedWidth(86)
        ffmpeg_row.addWidget(self.ffmpeg_path_label, 1)
        ffmpeg_row.addWidget(self.ffmpeg_refresh_btn, 0)
        card_layout.addLayout(ffmpeg_row)

        src_form = QFormLayout()
        src_form.setContentsMargins(0, 0, 0, 0)
        src_form.setHorizontalSpacing(10)
        src_form.setVerticalSpacing(8)
        self.src_path_edit = QLineEdit()
        self.src_path_edit.setPlaceholderText("입력 이미지 선택")
        src_btn = QPushButton("이미지 선택")
        src_btn.setFixedWidth(100)
        src_row = QHBoxLayout()
        src_row.setContentsMargins(0, 0, 0, 0)
        src_row.setSpacing(6)
        src_row.addWidget(self.src_path_edit, 1)
        src_row.addWidget(src_btn, 0)
        src_widget = QWidget()
        src_widget.setLayout(src_row)
        src_form.addRow("입력 이미지:", src_widget)
        card_layout.addLayout(src_form)

        up_title = QLabel("업스케일 옵션")
        up_title.setObjectName("sectionTitle")
        card_layout.addWidget(up_title)

        up_form = QFormLayout()
        up_form.setContentsMargins(0, 0, 0, 0)
        up_form.setHorizontalSpacing(10)
        up_form.setVerticalSpacing(8)
        self.up_out_edit = QLineEdit()
        self.up_out_edit.setPlaceholderText("업스케일 결과 이미지 경로")
        up_out_btn = QPushButton("저장 경로")
        up_out_btn.setFixedWidth(100)
        up_out_row = QHBoxLayout()
        up_out_row.setContentsMargins(0, 0, 0, 0)
        up_out_row.setSpacing(6)
        up_out_row.addWidget(self.up_out_edit, 1)
        up_out_row.addWidget(up_out_btn, 0)
        up_out_widget = QWidget()
        up_out_widget.setLayout(up_out_row)
        up_form.addRow("출력 이미지:", up_out_widget)

        self.up_scale_combo = DownwardComboBox()
        self.up_scale_combo.addItem("1.5x", 1.5)
        self.up_scale_combo.addItem("2x (추천)", 2.0)
        self.up_scale_combo.addItem("4x", 4.0)
        self.up_scale_combo.setCurrentIndex(1)
        self.up_scale_combo.setView(QListView())
        self.up_scale_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.up_scale_combo.setStyle(QStyleFactory.create("Fusion"))
        up_form.addRow("배율:", self.up_scale_combo)

        self.up_sharpen_cb = QCheckBox("샤픈 강화 (윤곽 선명도)")
        self.up_sharpen_cb.setChecked(True)
        up_form.addRow("추가 옵션:", self.up_sharpen_cb)

        self.up_run_btn = QPushButton("업스케일 실행")
        self.up_run_btn.setObjectName("primaryBtn")
        up_form.addRow("", self.up_run_btn)
        card_layout.addLayout(up_form)

        self.status_label = QLabel("대기 중")
        self.status_label.setObjectName("statusLabel")
        card_layout.addWidget(self.status_label)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(150)
        card_layout.addWidget(self.log_edit, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        self.close_btn = QPushButton("닫기")
        bottom.addStretch(1)
        bottom.addWidget(self.close_btn)
        card_layout.addLayout(bottom)

        src_btn.clicked.connect(self._pick_src_image)
        up_out_btn.clicked.connect(self._pick_upscale_output)
        self.ffmpeg_refresh_btn.clicked.connect(self._refresh_ffmpeg_path)
        self.up_run_btn.clicked.connect(self._run_upscale)
        self.close_btn.clicked.connect(self.reject)

        if parent is not None and hasattr(parent, "app_icon"):
            try:
                self.setWindowIcon(parent.app_icon)
            except Exception:
                pass
        QTimer.singleShot(0, self._refresh_ffmpeg_path)
        QTimer.singleShot(0, self._apply_title_bar_theme)

    def _append_log(self, text):
        line = str(text or "").strip()
        if not line:
            return
        self.log_edit.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {line}")

    def _show_message(self, icon, title, text):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(str(title or "알림"))
        msg = str(text or "").strip()
        if not msg:
            msg = "상세 메시지가 비어 있습니다."
        box.setText(msg)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        box.setStyleSheet(
            """
            QMessageBox {
                background-color: #1d2a3d;
            }
            QMessageBox QLabel {
                color: #eef3ff;
                min-width: 420px;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                min-width: 88px;
                min-height: 30px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                padding: 0 10px;
            }
            QMessageBox QPushButton:hover {
                background-color: #3f5e8e;
            }
            """
        )
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "_apply_window_title_bar_theme"):
                parent._apply_window_title_bar_theme(box)
            elif callable(self._title_bar_theme_fn):
                self._title_bar_theme_fn(box)
        except Exception:
            pass
        box.exec()

    def _set_busy(self, busy, status_text=""):
        state = bool(busy)
        controls = [
            self.src_path_edit,
            self.up_out_edit,
            self.up_scale_combo,
            self.up_sharpen_cb,
            self.ffmpeg_refresh_btn,
            self.up_run_btn,
            self.close_btn,
        ]
        for w in controls:
            w.setEnabled(not state)
        if status_text:
            self.status_label.setText(str(status_text))

    def _refresh_ffmpeg_path(self):
        self._ffmpeg_path = str(find_ffmpeg_binary() or "")
        if self._ffmpeg_path:
            self.ffmpeg_path_label.setText(self._ffmpeg_path)
            self._append_log(f"ffmpeg 확인: {self._ffmpeg_path}")
        else:
            self.ffmpeg_path_label.setText("미발견")
            self._append_log("ffmpeg를 찾지 못했습니다.")

    def _pick_src_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "입력 이미지 선택",
            "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff);;모든 파일 (*)",
        )
        if not path:
            return
        self.src_path_edit.setText(path)
        root, ext = os.path.splitext(path)
        ext = ext if ext else ".png"
        self.up_out_edit.setText(f"{root}_upscaled{ext}")

    def _pick_upscale_output(self):
        src = str(self.src_path_edit.text() or "").strip()
        base_dir = os.path.dirname(src) if src else ""
        default_name = "upscaled.png"
        if src:
            src_root, src_ext = os.path.splitext(os.path.basename(src))
            default_name = f"{src_root}_upscaled{src_ext if src_ext else '.png'}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "업스케일 출력 경로",
            os.path.join(base_dir, default_name),
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;WEBP (*.webp);;BMP (*.bmp);;모든 파일 (*)",
        )
        if path:
            self.up_out_edit.setText(path)

    def _start_worker(self, action_name, func, kwargs, require_ffmpeg=False):
        if self._worker is not None and self._worker.isRunning():
            self._show_message(QMessageBox.Icon.Warning, "작업 중", "이미 작업이 진행 중입니다.")
            return
        payload = dict(kwargs or {})
        if bool(require_ffmpeg):
            if not self._ffmpeg_path:
                self._refresh_ffmpeg_path()
            if not self._ffmpeg_path:
                self._show_message(
                    QMessageBox.Icon.Critical,
                    "ffmpeg 미발견",
                    "ffmpeg를 찾지 못했습니다.\nffmpeg.exe를 MyCanvas.exe 폴더 또는 PATH에 배치하세요.",
                )
                return
            payload["ffmpeg_path"] = self._ffmpeg_path
        self._worker_action = str(action_name)
        self._worker = MediaToolWorker(func, payload, self)
        self._worker.succeeded.connect(self._on_worker_success)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._set_busy(True, f"{self._worker_action} 실행 중...")
        self._append_log(f"{self._worker_action} 시작")
        self._worker.start()

    def _run_upscale(self):
        src = str(self.src_path_edit.text() or "").strip()
        out = str(self.up_out_edit.text() or "").strip()
        if not src:
            self._show_message(QMessageBox.Icon.Warning, "입력 필요", "입력 이미지를 선택하세요.")
            return
        if not out:
            self._show_message(QMessageBox.Icon.Warning, "출력 필요", "업스케일 출력 경로를 지정하세요.")
            return
        self._start_worker(
            "이미지 업스케일",
            upscale_image_file,
            {
                "input_path": src,
                "output_path": out,
                "scale": float(self.up_scale_combo.currentData() or 2.0),
                "sharpen": bool(self.up_sharpen_cb.isChecked()),
            },
            require_ffmpeg=True,
        )

    def _on_worker_success(self, result):
        out = ""
        if isinstance(result, dict):
            out = str(result.get("output_path", "") or "").strip()
        if out:
            self._append_log(f"{self._worker_action} 완료: {out}")
        else:
            self._append_log(f"{self._worker_action} 완료")
        self.status_label.setText(f"{self._worker_action} 완료")
        self._show_message(QMessageBox.Icon.Information, "완료", f"{self._worker_action}이 완료되었습니다.")

    def _on_worker_failed(self, message):
        raw = str(message or "").strip()
        if not raw:
            raw = "알 수 없는 오류"
        self._append_log(f"{self._worker_action} 실패: {raw}")
        self.status_label.setText(f"{self._worker_action} 실패")
        self._show_message(QMessageBox.Icon.Critical, "실패", raw)

    def _on_worker_finished(self):
        self._set_busy(False)
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        if self.status_label.text().strip().endswith("실행 중..."):
            self.status_label.setText("대기 중")

    def _apply_title_bar_theme(self):
        if self._title_bar_themed:
            return
        self._title_bar_themed = True
        parent = self.parent()
        if parent is not None and hasattr(parent, "_apply_window_title_bar_theme"):
            try:
                parent._apply_window_title_bar_theme(self)
                return
            except Exception:
                pass
        if callable(self._title_bar_theme_fn):
            try:
                self._title_bar_theme_fn(self)
            except Exception:
                pass

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._show_message(QMessageBox.Icon.Warning, "작업 중", "현재 작업이 끝난 뒤 창을 닫아주세요.")
            event.ignore()
            return
        super().closeEvent(event)
