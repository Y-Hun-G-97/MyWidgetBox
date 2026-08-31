import os
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QStackedWidget,
    QScrollArea, QFrame, QSizePolicy
)

from mywidgetbox_core import apply_windows_dark_title_bar, render_vector_icon


class GuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("guideDialog")
        self.setWindowTitle("MyWidgetBox 사용 설명서")
        self.setWindowIcon(render_vector_icon("help", "#528bf8", 32))
        apply_windows_dark_title_bar(self)
        self.resize(860, 640)
        self.setMinimumSize(780, 560)

        # Assets guide directory path
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._guide_dir = os.path.join(base_dir, "assets", "guide")

        self.setStyleSheet("""
            QDialog#guideDialog {
                background-color: #121c2b;
            }
            QFrame#guideSidebar {
                background-color: #162438;
                border-right: 1px solid #283e5c;
            }
            QListWidget#guideNav {
                background: transparent;
                border: none;
                outline: none;
                padding: 10px 6px;
            }
            QListWidget#guideNav::item {
                color: #a4bedc;
                background-color: transparent;
                border-radius: 8px;
                padding: 10px 14px;
                margin-bottom: 4px;
                font-size: 13px;
                font-weight: 600;
            }
            QListWidget#guideNav::item:hover {
                color: #ffffff;
                background-color: #1f334d;
            }
            QListWidget#guideNav::item:selected {
                color: #ffffff;
                background-color: #2b4973;
                font-weight: 700;
            }
            QScrollArea#guideScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#guideContentContainer {
                background-color: #121c2b;
            }
            QFrame#guideCard {
                background-color: #18273d;
                border: 1px solid #263c5a;
                border-radius: 12px;
                padding: 16px;
            }
            QLabel#guideMainTitle {
                color: #eef4ff;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#guideSubTitle {
                color: #8da8cb;
                font-size: 13px;
                margin-bottom: 10px;
            }
            QLabel#guideSectionTitle {
                color: #528bf8;
                font-size: 15px;
                font-weight: 700;
                margin-top: 6px;
            }
            QLabel#guideBodyText {
                color: #dbe7fa;
                font-size: 13px;
                line-height: 1.5;
            }
            QFrame#guideTipBox {
                background-color: rgba(82, 139, 248, 0.12);
                border: 1px solid #3b68d4;
                border-radius: 8px;
                padding: 10px 14px;
            }
            QLabel#guideTipTitle {
                color: #6ea0ff;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#guideTipContent {
                color: #c7dcff;
                font-size: 12px;
            }
            QLabel#guideImageHolder {
                background-color: #0b131e;
                border: 1px solid #233752;
                border-radius: 10px;
                padding: 6px;
            }
            QPushButton#navBtn {
                min-height: 32px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                color: #e8efff;
                background-color: #243852;
                border: 1px solid #3a567e;
                padding: 0 16px;
            }
            QPushButton#navBtn:hover {
                background-color: #314b6e;
                border-color: #528bf8;
                color: #ffffff;
            }
            QPushButton#navBtn:disabled {
                background-color: #162233;
                border-color: #1e3047;
                color: #4a617d;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 좌측 사이드바 (목차)
        sidebar = QFrame()
        sidebar.setObjectName("guideSidebar")
        sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 14, 8, 14)
        sidebar_layout.setSpacing(10)

        app_title = QLabel("📖 사용 설명서")
        app_title.setStyleSheet("color: #eef3ff; font-size: 15px; font-weight: 800; padding: 4px 10px;")
        sidebar_layout.addWidget(app_title)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("guideNav")

        chapters = [
            ("📁 세트 & 위젯 기본 구조", "chapter_1"),
            ("⊞ 스프레드 (폴더 일괄 배치)", "chapter_2"),
            ("🎮 바로가기 (명조/게임 연동)", "chapter_3"),
            ("⚡ 일괄 조작 & 임시 그룹", "chapter_4"),
            ("⚙ 상세 설정 & 단축키 안내", "chapter_5"),
        ]

        for title, _ in chapters:
            item = QListWidgetItem(title)
            self.nav_list.addItem(item)

        sidebar_layout.addWidget(self.nav_list, 1)
        layout.addWidget(sidebar)

        # 우측 본문 영역
        content_pane = QWidget()
        content_pane_layout = QVBoxLayout(content_pane)
        content_pane_layout.setContentsMargins(20, 16, 20, 14)
        content_pane_layout.setSpacing(12)

        self.stack = QStackedWidget()
        self._build_chapter_1()
        self._build_chapter_2()
        self._build_chapter_3()
        self._build_chapter_4()
        self._build_chapter_5()

        content_pane_layout.addWidget(self.stack, 1)

        # 하단 네비게이션 버튼
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        bottom_bar.setSpacing(10)

        self.prev_btn = QPushButton("◀ 이전 챕터")
        self.prev_btn.setObjectName("navBtn")
        self.prev_btn.clicked.connect(self._go_prev)

        self.next_btn = QPushButton("다음 챕터 ▶")
        self.next_btn.setObjectName("navBtn")
        self.next_btn.clicked.connect(self._go_next)

        close_btn = QPushButton("설명서 닫기")
        close_btn.setObjectName("navBtn")
        close_btn.clicked.connect(self.accept)

        bottom_bar.addWidget(self.prev_btn)
        bottom_bar.addWidget(self.next_btn)
        bottom_bar.addStretch(1)
        bottom_bar.addWidget(close_btn)

        content_pane_layout.addLayout(bottom_bar)
        layout.addWidget(content_pane, 1)

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.nav_list.setCurrentRow(0)

    def _on_nav_changed(self, row):
        self.stack.setCurrentIndex(row)
        self.prev_btn.setEnabled(row > 0)
        self.next_btn.setEnabled(row < self.stack.count() - 1)

    def _go_prev(self):
        curr = self.nav_list.currentRow()
        if curr > 0:
            self.nav_list.setCurrentRow(curr - 1)

    def _go_next(self):
        curr = self.nav_list.currentRow()
        if curr < self.stack.count() - 1:
            self.nav_list.setCurrentRow(curr + 1)

    def _create_scrollable_page(self):
        scroll = QScrollArea()
        scroll.setObjectName("guideScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("guideContentContainer")
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(4, 4, 12, 10)
        vbox.setSpacing(14)
        scroll.setWidget(container)
        return scroll, vbox

    def _load_guide_pixmap(self, filename, max_w=430):
        img_path = os.path.join(self._guide_dir, filename)
        if os.path.isfile(img_path):
            pix = QPixmap(img_path)
            if not pix.isNull():
                if pix.width() > max_w:
                    return pix.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
                return pix
        return None

    def _create_tip_box(self, title, content):
        box = QFrame()
        box.setObjectName("guideTipBox")
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        blayout = QVBoxLayout(box)
        blayout.setContentsMargins(12, 8, 12, 8)
        blayout.setSpacing(4)
        t_lbl = QLabel(f"💡 {title}")
        t_lbl.setObjectName("guideTipTitle")
        c_lbl = QLabel(content)
        c_lbl.setObjectName("guideTipContent")
        c_lbl.setWordWrap(True)
        blayout.addWidget(t_lbl)
        blayout.addWidget(c_lbl)
        return box

    # ---------------- 챕터 1: 세트 & 위젯 기본 구조 ----------------
    def _build_chapter_1(self):
        page, layout = self._create_scrollable_page()

        title = QLabel("1. 세트 & 위젯 기본 구조")
        title.setObjectName("guideMainTitle")
        sub = QLabel("MyWidgetBox의 세트(부모)와 위젯(자식) 계층 구조 및 기본 조작법을 알아봅니다.")
        sub.setObjectName("guideSubTitle")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)

        pix = self._load_guide_pixmap("guide_1_accordion.png", 420)
        if pix:
            img_lbl = QLabel()
            img_lbl.setObjectName("guideImageHolder")
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setPixmap(pix)
            layout.addWidget(img_lbl)

        card = QFrame()
        card.setObjectName("guideCard")
        clayout = QVBoxLayout(card)
        clayout.setSpacing(8)

        sec1 = QLabel("📁 세트(Set)란 무엇인가요?")
        sec1.setObjectName("guideSectionTitle")
        body1 = QLabel("여러 개의 바탕화면 위젯들을 하나의 테마 단위로 묶어 관리하는 컨테이너입니다. 예를 들어 '4분할배경 세트', '루뺘 캐릭터 세트'처럼 용도에 따라 자유롭게 세트를 만들어 전환할 수 있습니다.")
        body1.setObjectName("guideBodyText")
        body1.setWordWrap(True)

        sec2 = QLabel("🚀 세트 적용 및 접기/펼치기")
        sec2.setObjectName("guideSectionTitle")
        body2 = QLabel("• <b>세트 접기/펼치기</b>: 세트 좌측의 화살표 [ ∨ / 〉]를 누르면 소속 위젯들을 펼치거나 접을 수 있습니다.<br>• <b>세트 적용</b>: [ 세트 적용 ] 버튼을 누르면 해당 세트의 위젯들로 바탕화면이 즉시 교체 적용됩니다.<br>• <b>새로운 세트 생성</b>: 상단 우측의 [ + 새로운 세트 ] 버튼을 눌러 새 세트를 생성할 수 있습니다.<br>• <b>세트 관리</b>: 세트 우측의 설정 버튼을 누르면 세트 이름 변경, 복사, 삭제 창이 열립니다.")
        body2.setObjectName("guideBodyText")
        body2.setWordWrap(True)

        clayout.addWidget(sec1)
        clayout.addWidget(body1)
        clayout.addWidget(sec2)
        clayout.addWidget(body2)
        layout.addWidget(card)

        layout.addWidget(self._create_tip_box("시작 세트 안내", "프로그램을 새로 켜면 현재 바탕화면에 적용되어 있는 활성 세트만 자동으로 펼쳐져 깔끔하게 시작됩니다."))
        layout.addStretch(1)
        self.stack.addWidget(page)

    # ---------------- 챕터 2: 스프레드 (폴더 일괄 배치) ----------------
    def _build_chapter_2(self):
        page, layout = self._create_scrollable_page()

        title = QLabel("2. 스프레드 (폴더 일괄 배치)")
        title.setObjectName("guideMainTitle")
        sub = QLabel("폴더 안의 수많은 이미지/GIF들을 클릭 한 번으로 바둑판식으로 화면에 자동 정렬합니다.")
        sub.setObjectName("guideSubTitle")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)

        pix = self._load_guide_pixmap("guide_2_spread.png", 440)
        if pix:
            img_lbl = QLabel()
            img_lbl.setObjectName("guideImageHolder")
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setPixmap(pix)
            layout.addWidget(img_lbl)

        card = QFrame()
        card.setObjectName("guideCard")
        clayout = QVBoxLayout(card)
        clayout.setSpacing(8)

        sec1 = QLabel("⊞ 스프레드 사용 방법 & 전개 방향 (예: 루뺘 폴더)")
        sec1.setObjectName("guideSectionTitle")
        body1 = QLabel("1. 세트 내 <b>[ 새로운 위젯 추가 ]</b>를 누르고 <b>폴더 열기</b>를 선택합니다.<br>2. 이미지가 담긴 폴더(예: <code>루뺘 폴더</code>)를 선택합니다.<br>3. 팝업에서 <b>[ ⊞ 스프레드 방식 ]</b>을 선택하면 위와 같은 스프레드 설정 창이 열립니다.<br>4. 행/열, 위젯 크기, 간격 및 <b>[ 전개 방향 (우상단 시작 시 좌하단 전개 등) ]</b>을 정한 뒤 <b>[ 위젯 생성 ]</b>을 누르면 선택한 미디어들이 화면에 완벽한 바둑판 형태로 자동 배치됩니다.")
        body1.setObjectName("guideBodyText")
        body1.setWordWrap(True)

        clayout.addWidget(sec1)
        clayout.addWidget(body1)
        layout.addWidget(card)

        layout.addWidget(self._create_tip_box("스프레드 팁", "모니터 우상단이나 우하단 모서리에 바둑판을 짤 때는 '전개 방향'을 ↙좌하단 또는 ↖좌상단으로 선택하면 화면 밖으로 밀려나지 않고 깔끔하게 배치됩니다."))
        layout.addStretch(1)
        self.stack.addWidget(page)

    # ---------------- 챕터 3: 바로가기 연동 (명조/게임 실행) ----------------
    def _build_chapter_3(self):
        page, layout = self._create_scrollable_page()

        title = QLabel("3. 바로가기 연동 (게임/프로그램 실행)")
        title.setObjectName("guideMainTitle")
        sub = QLabel("바탕화면 위젯을 클릭했을 때 명조, 스팀, 디스코드 등 원하는 게임이나 프로그램을 즉시 실행합니다.")
        sub.setObjectName("guideSubTitle")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)

        pix = self._load_guide_pixmap("guide_3_shortcut.png", 420)
        if pix:
            img_lbl = QLabel()
            img_lbl.setObjectName("guideImageHolder")
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setPixmap(pix)
            layout.addWidget(img_lbl)

        card = QFrame()
        card.setObjectName("guideCard")
        clayout = QVBoxLayout(card)
        clayout.setSpacing(8)

        sec1 = QLabel("🎮 실행 경로(바로가기) 설정 방법")
        sec1.setObjectName("guideSectionTitle")
        body1 = QLabel("1. 위젯 행 우측의 <b>[ 설정 ]</b> 버튼을 눌러 위젯 상세 설정 창을 엽니다.<br>2. 상단 탭에서 <b>[ 상호작용 ]</b>으로 이동합니다.<br>3. <b>실행할 파일/바로가기 경로</b> 항목 우측의 <b>[ 찾아보기 ]</b>를 클릭합니다.<br>4. 실행하고자 하는 게임 바로가기(<code>.lnk</code>)나 실행 파일<br>(예: <code>Wuthering Waves launcher.exe</code>)을 선택합니다.<br>5. <b>[ 저장 ]</b>을 누르면 이제 바탕화면의 위젯을 클릭할 때마다 게임이 바로 실행됩니다!")
        body1.setObjectName("guideBodyText")
        body1.setWordWrap(True)

        clayout.addWidget(sec1)
        clayout.addWidget(body1)
        layout.addWidget(card)

        layout.addWidget(self._create_tip_box("런처 및 스팀 게임 연동", "바탕화면에 있는 바로가기 아이콘(.lnk)이나 URL 바로가기(Steam 바로가기 등)도 그대로 지정하여 연동할 수 있습니다."))
        layout.addStretch(1)
        self.stack.addWidget(page)

    # ---------------- 챕터 4: 일괄 조작 & 임시 그룹 ----------------
    def _build_chapter_4(self):
        page, layout = self._create_scrollable_page()

        title = QLabel("4. 일괄 조작 & 임시 그룹")
        title.setObjectName("guideMainTitle")
        sub = QLabel("여러 위젯을 동시에 체크하여 한 번에 실행/정지/설정/삭제하고, 바탕화면에서 함께 이동합니다.")
        sub.setObjectName("guideSubTitle")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)

        pix = self._load_guide_pixmap("guide_4_bulk.png", 420)
        if pix:
            img_lbl = QLabel()
            img_lbl.setObjectName("guideImageHolder")
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setPixmap(pix)
            layout.addWidget(img_lbl)

        card = QFrame()
        card.setObjectName("guideCard")
        clayout = QVBoxLayout(card)
        clayout.setSpacing(8)

        sec1 = QLabel("⚡ 일괄 제어 툴바 활용")
        sec1.setObjectName("guideSectionTitle")
        body1 = QLabel("• <b>체크박스 선택</b>: 세트 내 위젯 카드 앞의 체크박스를 누르거나 카드를 클릭하여 다중 선택합니다.<br>• <b>[ ▶ 실행 ]</b>: 정지되어 있는 선택 위젯들만 쏙 골라 일괄 실행합니다.<br>• <b>[ ⏹ 정지 ]</b>: 켜져 있는 선택 위젯들만 일괄 정지합니다.<br>• <b>[ 설정 ]</b>: 선택한 모든 위젯의 크기, 투명도, 회전, 마우스 투과 설정을 한 번에 변경합니다.<br>• <b>[ 🗑 삭제 ]</b>: 선택한 위젯들을 일괄 삭제합니다.")
        body1.setObjectName("guideBodyText")
        body1.setWordWrap(True)

        sec2 = QLabel("🤝 임시 그룹(바탕화면 동시 이동) 연동")
        sec2.setObjectName("guideSectionTitle")
        body2 = QLabel("체크박스로 위젯들을 2개 이상 선택하면 자동으로 <b>임시 그룹</b>으로 결속됩니다.<br>이 상태에서 바탕화면의 위젯 중 하나를 마우스로 드래그하면 <b>체크된 모든 위젯이 상대적 위치를 유지하며 한꺼번에 같이 이동</b>합니다!")
        body2.setObjectName("guideBodyText")
        body2.setWordWrap(True)

        clayout.addWidget(sec1)
        clayout.addWidget(body1)
        clayout.addWidget(sec2)
        clayout.addWidget(body2)
        layout.addWidget(card)

        layout.addWidget(self._create_tip_box("단축키 팁", "체크된 상태에서 Alt + 클릭 잠금을 사용하면 선택된 모든 위젯이 한 번에 잠금/해제됩니다."))
        layout.addStretch(1)
        self.stack.addWidget(page)

    # ---------------- 챕터 5: 상세 설정 & 단축키 안내 ----------------
    def _build_chapter_5(self):
        page, layout = self._create_scrollable_page()

        title = QLabel("5. 상세 설정 & 단축키 안내")
        title.setObjectName("guideMainTitle")
        sub = QLabel("알아두면 유용한 단축키와 고급 기능들을 한눈에 확인하세요.")
        sub.setObjectName("guideSubTitle")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)

        card = QFrame()
        card.setObjectName("guideCard")
        clayout = QVBoxLayout(card)
        clayout.setSpacing(10)

        sec1 = QLabel("📍 위젯 크기 확장 기준점 (Growth Anchor 9방향)")
        sec1.setObjectName("guideSectionTitle")
        body1 = QLabel("위젯 설정의 <b>[ 확장 기준점 ]</b> 3x3 그리드에서 원하는 꼭짓점(우상단, 우하단, 중앙 등)을 선택할 수 있습니다.<br>• <b>우상단 고정(↗)</b>: 우상단 모서리가 고정되어 크기가 늘어날 때 <b>왼쪽/아래로 확장</b>됩니다.<br>• <b>우하단 고정(↘)</b>: 시계 구석에서 크기 변경 시 <b>왼쪽/위로 확장</b>됩니다.<br>• <b>중앙 고정(•)</b>: 화면 가운데서 크기 변경 시 <b>사방으로 균등하게 확장</b>됩니다.")
        body1.setObjectName("guideBodyText")
        body1.setWordWrap(True)

        sec2 = QLabel("⌨️ 핵심 단축키 요약")
        sec2.setObjectName("guideSectionTitle")
        keys_text = QLabel("""
• <b>Alt + 클릭 (바탕화면 위젯)</b>: 위젯 이동 잠금 / 잠금 해제 토글 (체크된 임시 그룹 위젯 일괄 잠금)<br>
• <b>Ctrl + 마우스 휠 (위젯 위)</b>: 위젯 투명도 5% 단위 즉시 조절<br>
• <b>Alt + 마우스 휠 (위젯 위)</b>: 위젯 레이어(배경 ↔ 일반 ↔ 최상위) 즉시 단계 조절<br>
• <b>위젯 카드 더블클릭 (컨트롤러)</b>: 위젯 이름 즉시 변경 다이얼로그 호출<br>
• <b>위젯 카드 클릭 (컨트롤러)</b>: 바탕화면 해당 위젯에 네온 테두리 하이라이트 점멸
        """)
        keys_text.setObjectName("guideBodyText")
        keys_text.setWordWrap(True)

        sec3 = QLabel("🛡️ 마우스 투과 (클릭 무시) 모드")
        sec3.setObjectName("guideSectionTitle")
        body3 = QLabel("위젯 상세 설정에서 <b>마우스 투과</b>를 켜면 위젯이 바탕화면 배경처럼 작동하여 뒤의 아이콘이나 창을 가리지 않고 클릭할 수 있습니다. (설정 해제는 컨트롤러의 설정 버튼에서 언제든 가능합니다)")
        body3.setObjectName("guideBodyText")
        body3.setWordWrap(True)

        sec4 = QLabel("⚡ GPU 부하 모니터링 & 자동 절전")
        sec4.setObjectName("guideSectionTitle")
        body4 = QLabel("상단 우측의 <b>[ GPU ]</b> 버튼을 눌러 고사양 게임 실행 시 위젯 애니메이션/영상을 자동으로 일시 정지시켜 프레임 드랍을 원천 차단할 수 있습니다.")
        body4.setObjectName("guideBodyText")
        body4.setWordWrap(True)

        clayout.addWidget(sec1)
        clayout.addWidget(body1)
        clayout.addWidget(sec2)
        clayout.addWidget(keys_text)
        clayout.addWidget(sec3)
        clayout.addWidget(body3)
        clayout.addWidget(sec4)
        clayout.addWidget(body4)
        layout.addWidget(card)

        layout.addStretch(1)
        self.stack.addWidget(page)
