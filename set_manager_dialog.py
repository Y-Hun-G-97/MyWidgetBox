from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
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


class RandomSetChooserDialog(QDialog):
    def __init__(self, master, parent=None):
        super().__init__(parent if parent is not None else master)
        self.master = master
        self._title_bar_themed = False
        self.setObjectName("randomSetChooserDialog")
        self.setWindowTitle("랜덤 실행 대상 세트 선택")
        from mywidgetbox_core import apply_windows_dark_title_bar, render_vector_icon
        self.setWindowIcon(render_vector_icon("widget", "#528bf8", 32))
        self.setFixedSize(400, 480)
        self.setStyleSheet("""
            QDialog#randomSetChooserDialog { background-color: #162233; }
            QFrame#card {
                background-color: #1d2c42;
                border: 1px solid #2e4466;
                border-radius: 12px;
            }
            QLabel#dialogTitle {
                color: #eef3ff;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#dialogSubtitle {
                color: #9ab4d6;
                font-size: 12px;
            }
            QScrollArea {
                background: transparent;
                border: 1px solid #263852;
                border-radius: 8px;
            }
            QWidget#scrollContainer {
                background-color: #152233;
            }
            QFrame#setItemRow {
                background-color: #1c2b40;
                border: 1px solid #2b4060;
                border-radius: 8px;
                padding: 4px;
            }
            QFrame#setItemRow:hover {
                background-color: #233650;
                border-color: #43628e;
            }
            QCheckBox {
                color: #e6efff;
                font-size: 13px;
                font-weight: 600;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #4a678f;
                background-color: #111a27;
            }
            QCheckBox::indicator:hover {
                border-color: #60a5fa;
            }
            QCheckBox::indicator:checked {
                background-color: #2563eb;
                border-color: #60a5fa;
            }
            QLabel#setCountBadge {
                color: #7ea3d4;
                background-color: #101c2e;
                border: 1px solid #253954;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
                color: #e6efff;
                background-color: #2a3f60;
                border: 1px solid #4a6591;
            }
            QPushButton:hover { background-color: #35527d; }
            QPushButton#primaryBtn {
                background-color: #3b68d4;
                border: 1px solid #5a85ea;
                font-weight: 700;
            }
            QPushButton#primaryBtn:hover {
                background-color: #4a77e8;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        title = QLabel("랜덤 실행 대상 세트 선택")
        title.setObjectName("dialogTitle")
        card_layout.addWidget(title)

        sub = QLabel("프로그램 시작 시 무작위로 선택될 세트들을 체크하세요.")
        sub.setObjectName("dialogSubtitle")
        sub.setWordWrap(True)
        card_layout.addWidget(sub)

        # Quick select buttons (Select All / Deselect All)
        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)
        select_all_btn = QPushButton("전체 선택")
        select_all_btn.clicked.connect(self._select_all)
        deselect_all_btn = QPushButton("전체 해제")
        deselect_all_btn.clicked.connect(self._deselect_all)
        quick_row.addWidget(select_all_btn)
        quick_row.addWidget(deselect_all_btn)
        quick_row.addStretch()
        card_layout.addLayout(quick_row)

        # Scroll Area with set items
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scrollContainer")
        self.items_layout = QVBoxLayout(self.scroll_content)
        self.items_layout.setContentsMargins(8, 8, 8, 8)
        self.items_layout.setSpacing(6)

        # Load saved candidates
        raw_candidates = set(master._as_list(master.master_settings.value("random_set_candidates", [])))
        default_all = len(raw_candidates) == 0

        self.checkboxes = {}
        for sid in master._set_order:
            sid_str = str(sid)
            data = master._set_defs.get(sid_str, {})
            name = str(data.get("name", f"세트{sid_str}"))
            pids = master._as_list(data.get("profiles", []))

            row_frame = QFrame()
            row_frame.setObjectName("setItemRow")
            r_lay = QHBoxLayout(row_frame)
            r_lay.setContentsMargins(8, 6, 8, 6)
            r_lay.setSpacing(8)

            cb = QCheckBox(name)
            is_checked = default_all or (sid_str in raw_candidates)
            cb.setChecked(is_checked)
            self.checkboxes[sid_str] = cb

            count_badge = QLabel(f"위젯 {len(pids)}개")
            count_badge.setObjectName("setCountBadge")

            r_lay.addWidget(cb, 1)
            r_lay.addWidget(count_badge, 0)
            self.items_layout.addWidget(row_frame)

        self.items_layout.addStretch()
        self.scroll.setWidget(self.scroll_content)
        card_layout.addWidget(self.scroll, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        save_btn = QPushButton("저장")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        card_layout.addLayout(btn_row)

        root.addWidget(card)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._title_bar_themed:
            self._title_bar_themed = True
            from mywidgetbox_core import apply_windows_dark_title_bar
            QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(self))

    def _select_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def _deselect_all(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def _save_and_close(self):
        selected_sids = [sid for sid, cb in self.checkboxes.items() if cb.isChecked()]
        if not selected_sids:
            QMessageBox.warning(self, "선택 확인", "최소 1개 이상의 세트를 선택해야 합니다.")
            return
        self.master.master_settings.setValue("random_set_candidates", selected_sids)
        self.master.master_settings.sync()
        if hasattr(self.master, "_sync_random_set_btn_text"):
            self.master._sync_random_set_btn_text()
        self.accept()



