from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

class SetManagerDialog(QDialog):
    def __init__(self, master, target_sid=None, parent=None):
        super().__init__(parent if parent is not None else master)
        self.master = master
        self.target_sid = str(target_sid) if target_sid else str(master.selected_set_id() or "")
        if not self.target_sid and getattr(master, "_set_order", None):
            self.target_sid = str(master._set_order[0])
        self._title_bar_themed = False
        self.setObjectName("setManagerDialog")
        self.setWindowTitle("세트 관리")
        from mywidgetbox_core import render_vector_icon
        self.setWindowIcon(render_vector_icon("widget", "#528bf8", 32))
        self.setFixedSize(360, 198)
        self.setStyleSheet("""
            QDialog#setManagerDialog { background-color: #162233; }
            QFrame#setCard {
                background-color: #1d2c42;
                border: 1px solid #2e4466;
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

        from PyQt6.QtCore import QTimer
        from mywidgetbox_core import apply_windows_dark_title_bar
        QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(self))

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
        sid = str(self.target_sid) if self.target_sid else str(self.master.selected_set_id() or "")
        data = self.master._set_defs.get(sid, {})
        name = str(data.get("name", f"세트{sid}" if sid else "세트"))
        count = len(data.get("profiles", []))
        self.info_label.setText(f"대상 세트: {name}  |  위젯 {count}개")
        self.delete_btn.setEnabled(len(self.master._set_order) > 1)

    def _copy_set(self):
        items = self.master.get_set_items()
        if not items:
            return
        target_sid = str(self.target_sid) if self.target_sid else str(self.master.selected_set_id() or "")
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
        sid = str(self.target_sid) if self.target_sid else str(self.master.selected_set_id() or "")
        if not sid:
            return
        if self.master.delete_set(sid, parent=self):
            self.accept()


