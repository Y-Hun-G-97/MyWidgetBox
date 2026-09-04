# 🎨 MyWidgetBox UI/UX 디자인 시스템 & 기능 개발 가이드라인

> **[안내]**  
> 본 가이드의 전체 백과사전식 세부 기술 명세, 데이터 모델 및 알고리즘 분석은 **[`PROJECT_SPEC_AND_DESIGN_SYSTEM.md`](./PROJECT_SPEC_AND_DESIGN_SYSTEM.md)**에 완전하게 집대성되어 있습니다.  
> 코드 수정 및 기능 추가 시 두 문서를 함께 필수 참조하십시오.

---

## 📑 목차
1. [프로젝트 아키텍처 및 핵심 파일 역할](#1-프로젝트-아키텍처-및-핵심-파일-역할)
2. [전체 기능 명세 (Functional Specifications)](#2-전체-기능-명세-functional-specifications)
3. [UI/UX 디자인 시스템 (Design Tokens & Styles)](#3-uiux-디자인-시스템-design-tokens--styles)
4. [벡터 아이콘 시스템 (Vector Icon System)](#4-벡터-아이콘-시스템-vector-icon-system)
5. [컴포넌트별 레이아웃 & 배치 규칙](#5-컴포넌트별-레이아웃--배치-규칙)
6. [개발자 및 AI 10대 불변 규칙 (10 Inviolable Invariants)](#6-개발자-및-ai-10대-불변-규칙-10-inviolable-invariants)

---

## 1. 프로젝트 아키텍처 및 핵심 파일 역할

| 파일명 | 역할 및 핵심 책임 |
| :--- | :--- |
| **`MyWidgetBox.py`** | 메인 컨트롤러(`MasterController`), 데스크톱 위젯(`DesktopWidget`), 아코디언 세트 트리, QSS 메인 스타일시트, GPU 모니터링 루틴 |
| **`settings_dialog.py`** | 위젯 상세 설정 다이얼로그(`SettingsDialog`), 스프레드 배치 다이얼로그(`SpreadDialog`), 기준점 피커(`GrowthAnchorPicker`) |
| **`widget_runtime.py`** | 위젯 상호작용 런타임 (마우스 드래그/리사이즈, 휠 제스처, Alt/Ctrl 단축키, 미디어 루프 및 디코드 처리) |
| **`master_operations.py`** | 임시 그룹 일괄 조작(투명도, 레이어, 위치 동기화), 시작 큐(`StartupQueue`), GPU 가드 타겟 관리 |
| **`master_sets.py`** | 세트 생성, 복사, 이름 변경, 삭제/흡수, 순서 변경, 세트 전환 로직 |
| **`set_manager_dialog.py`** | 세트 관리 전용 모달 창 (세트 목록 확인, 복사, 삭제) |
| **`mywidgetbox_core.py`** | 벡터 아이콘 렌더러(`render_vector_icon`), Windows 다크 타이틀바, 미디어 고속 메타데이터 추출, GPU 샘플러 |
| **`mywidgetbox_ui_primitives.py`** | 콤보박스(`DownwardComboBox`), 가이드라인(`TreeBranchLine`), 마퀴 오버레이(`MarqueeSelectionOverlay`), `ElidedLabel` |
| **`desktop_icons.py`** | Windows 셸 바탕화면 아이콘 가상 복제 오버레이(`DesktopIconCloneOverlay`) 및 최하단 Z-Order 레이어링 처리 |

---

## 2. 전체 기능 명세 (Functional Specifications)

### 1) 세트(Set) 관리 시스템
- **최소 1개 세트 불변식**: 시스템에는 최소 1개의 세트가 항상 유지되어야 합니다. 마지막 1개 세트는 삭제할 수 없으며 삭제 버튼(`[🗑]`)이 비활성화(회색 `#55667e`)됩니다.
- **세트 삭제 및 흡수**: 프로필이 들어있는 세트를 삭제할 때 사용자에게 **[첫번째 세트로 흡수]** 또는 **[프로필도 함께 삭제]**를 선택하게 합니다.
- **세트 헤더 액션 버튼 배치**:
  - `[▼/▶]` 접기/펼치기 토글
  - `[세트 적용]` 현재 세트를 바탕화면에 즉시 반영 (이미 적용 중이면 `[적용 중]` 녹색 뱃지 표시)
  - `[▲] [▼]` 세트 순서 위/아래 이동
  - `[⚙]` 세트 관리 다이얼로그 열기 (이름 변경, 복사, 세트 삭제 수행)

### 2) 데스크톱 위젯 제스처 & 단축키
- **투명도 조절**: 위젯 위에서 `Ctrl + 마우스 휠` ➔ 5% 단위로 투명도(10% ~ 100%) 증감. (임시 그룹 선택 시 그룹 전체 일괄 변경)
- **레이어 변경**: 위젯 위에서 `Alt + 마우스 휠` ➔ 레이어 변경 (0: 배경, 1: 일반, 2: 최상위) 및 즉각적인 액션 HUD 표시.
  - *Win32 하드웨어 키보드 실시간 감지(`win32api.GetAsyncKeyState(VK_MENU)`)*와 *가로 휠 스크롤 폴백*이 필수 적용되어야 함.
- **미디어 순환**: 휠 단독 조작 ➔ 다음/이전 미디어 즉시 전환.
- **더블클릭**: 위젯 상세 설정 창 열기 (임시 그룹인 경우 일괄 설정 창 오픈).
- **마우스 잠금 (Click-through)**: `WindowTransparentForInput` 플래그를 적용하여 클릭을 바탕화면으로 통과시킴. (컨트롤러나 단축키로 해제 가능)

### 3) 스프레드 배치 시스템 (Spread Placement)
- **📸 사진첩 행 정돈**: 가로 라인을 정돈하며 각 짤의 종횡비율을 100% 온전히 보존하여 양쪽 벽면에 칼같이 맞추어 정렬하는 구글 포토 스타일.
- **🖥️ 모니터 자동 맞춤**: 작업표시줄 상태를 감지하여 모니터 전체 해상도 기반으로 최적의 열과 크기를 완전 자동 계산.
- **📌 핀터레스트 컬럼**: 직접 지정한 열과 너비에 맞춰 세로 기둥을 따라 물 흐르듯 떨어지는 자연스러운 카드형 메이슨리.
- **🔲 균일 바둑판 - 크롭 채우기 / 🖼️ 균일 바둑판 - 원본 비율 유지**: 전통적인 동일 사각형 격자 배치.
- **임시 그룹 일괄 스프레드 재배치 (Bulk Spread Relayout)**:
  - 임시 그룹 일괄 설정 창에서 선택한 위젯들을 스프레드 알고리즘(하이브리드/전체화면/테트리스/바둑판)으로 바탕화면에 즉시 재정렬 지원.
- **화면 높이 맞춤 자동 압축 (Auto Scale-down Fit-Inside)**:
  - 이미지가 60개 이상 대량일 때 세로 누적 높이가 화면 높이를 초과하면, 모든 타일을 화면 높이(2560x1440)에 맞게 2D 스케일 다운하여 맨 아래 타일까지 단 1px도 잘리지 않고 화면 전체에 쏙 들어가도록 압축 배치.
- **화면 경계 이탈 방지 안전 클램핑 (Screen Safety Clamping)**:
  - 타일 배치가 화면 우측 또는 바닥 경계를 벗어나는 경우, 전체 배치 바운딩 박스를 계산하여 화면 안쪽으로 자동 시프트하여 1px도 화면 밖으로 잘려나가지 않도록 보장.
- **세트 위젯 무결성 보존**:
  - 폴더 스프레드 전개 시 기존 세트에 있던 다른 위젯들을 절대 강제 삭제하지 않고 온전히 보존하며, 스프레드 위젯들을 세트에 안전하게 추가.

### 4) 백그라운드 최적화 & 성능 보호
- **GPU 가드**: GPU 사용률이 설정 임계치(기본 90%)를 초과하면 위젯 미디어를 일시정지하고, 회복(기본 70%) 시 자동 재생.
- **다른 앱 전체화면 시 미디어 일시정지 (Pause on Fullscreen)**:
  - 게임, 전체화면 영상(유튜브 F11 등), 전체화면 작업 창 실행 시 Win32 화면 감지를 통해 뒷단 위젯 미디어(GIF 프레임 타이머 및 비디오)를 자동 일시정지.
  - 전체화면 해제 시 즉시 원래 재생 상태로 복구.
- **Windows 시작프로그램 등록**: 작업 스케줄러(`ScheduledTask`) 및 시작프로그램 폴더(`.lnk`) 이중화 기반 자동 기동 지원.
- **Alt+클릭 잠금 토글 간섭 방지**: 포토샵, 게임 등 타 작업 프로그램 사용 중 바탕화면 위젯 오작동 원천 차단.

---

## 3. UI/UX 디자인 시스템 (Design Tokens & Styles)

MyWidgetBox는 **모던 다크 네이비 / 사이버 메탈릭 블루 테마**를 사용합니다.  
기본 회색이나 흰색, 운영체제 기본 컨트롤 스타일을 그대로 노출하는 것은 엄격히 금지됩니다.

### 1) 컬러 토큰 (Color Palette)

| 토큰명 | HEX / RGBA 코드 | 용도 및 가이드라인 |
| :--- | :--- | :--- |
| **`bg-app`** | `#162233` | 메인 창, 다이얼로그 최상위 배경 |
| **`bg-surface`** | `#121c2b` | 입력창(SpinBox 컨테이너), 세그먼트 바, 세트 바디 배경 |
| **`bg-card`** | `#162438` / `#1d2c42` | 세트 카드, 설정 그룹 카드 배경 |
| **`bg-card-hover`** | `#213550` / `#263d5c` | 카드 및 행 호버 배경 |
| **`border-subtle`** | `#283a54` / `#2e4466` | 일반 컨테이너 및 인풋 테두리 (1px solid) |
| **`border-focused`** | `#528bf8` | 포커스 및 활성화 테두리 (1.5px solid) |
| **`primary-btn`** | `#3b68d4` (Hover: `#4a77e8`) | 주요 실행 버튼, 적용 버튼 배경 |
| **`primary-btn-border`**| `#5a85ea` | 주요 버튼 테두리 |
| **`secondary-btn`** | `#283a54` (Hover: `#33486a`) | 보조 버튼, 서브 액션 버튼 |
| **`danger-btn`** | `#8f3741` (Hover: `#a3434e`) | 삭제, 제거, 위험 액션 버튼 (글자: `#ffe4e9`) |
| **`success-badge`** | `#10b981` | '적용 중', '실행 중' 상태 뱃지 및 인디케이터 |
| **`text-primary`** | `#ffffff` / `#f5f7ff` | 타이틀, 활성 텍스트, 카드 제목 (13~17px, bold) |
| **`text-secondary`** | `#d6e2f7` / `#e4ecfb` | 일반 필드 라벨, 폼 라벨, 체크박스 텍스트 |
| **`text-accent`** | `#92bbf8` | 섹션 헤더 제목, 강조 카테고리 텍스트 |
| **`text-muted`** | `#8fa7c7` / `#7ea3d4` | 보조 캡션, 인풋 단위(px, 초), 뱃지 텍스트 |
| **`text-disabled`** | `#506580` / `#55667e` | 비활성화 텍스트 및 비활성 아이콘 |

---

### 2) 타이포그래피 규칙 (Typography Hierarchy)

- **폰트 패밀리**: `'Segoe UI', 'Malgun Gothic', '맑은 고딕', -apple-system, sans-serif`
- **계층별 크기 및 굵기**:
  - **대형 타이틀 (`#settingsTitle`, `#appTitle`)**: `font-size: 17px; font-weight: 700; color: #f5f7ff;`
  - **섹션 제목 (`#settingsSectionTitle`, `#groupHeaderLabel`)**: `font-size: 12px; font-weight: 700; color: #92bbf8; letter-spacing: 0.3px;`
  - **세트/카드 제목 (`#setGroupTitle`, `#profileName`)**: `font-size: 13px; font-weight: 700; color: #ffffff;`
  - **일반 폼 라벨 (QLabel in QFormLayout)**: `font-size: 12px; font-weight: 600; color: #d6e2f7;`
  - **체크박스 텍스트 (QCheckBox)**: `font-size: 11~12px; font-weight: 600; color: #e4ecfb;`
  - **값 뱃지/수치 (`#gpuCfgValue`, `#unitBadgeLabel`)**: `font-size: 11~12px; font-weight: 700; color: #edf3ff;`
  - **설명 힌트 (`#gpuCfgHint`, `#hintCaption`)**: `font-size: 10~11px; font-weight: 400; color: #8fa7c7; line-height: 1.4;`

---

## 4. 벡터 아이콘 시스템 (Vector Icon System)

모든 아이콘은 비트맵 이미지가 아닌 **`mywidgetbox_core.py`의 `render_vector_icon`**을 사용하여 런타임에 렌더링합니다.

### 1) 아이콘 생성 함수 규격
```python
from mywidgetbox_core import render_vector_icon

# 기본 시그니처
icon = render_vector_icon(name, color="#a4bedc", size=16)
```

### 2) 등록된 표준 아이콘 키 & 용도

| 아이콘 키 (name) | 형태 | 표준 크기 / 표준 색상 | 사용처 |
| :--- | :--- | :--- | :--- |
| **`"folder"`** | 폴더 | 16px / `#528bf8`(활성), `#8da8cb`(기본) | 세트 헤더 폴더 아이콘 |
| **`"settings"` / `"gear"`** | 슬라이더/기어 | 13~14px / `#8da8cb` | 설정 열기, 세트 관리 버튼 |
| **`"trash"` / `"delete"`** | 휴지통 | 13px / `#e06c75`(활성), `#55667e`(비활성) | 위젯 삭제, 세트 삭제 |
| **`"play"` / `"run"`** | 재생 삼각형 | 12~14px / `#58c796` | 위젯 실행, 세트 적용 |
| **`"stop"` / `"square"`** | 정지 사각형 | 12~14px / `#e06c75` | 위젯 정지, 일괄 정지 |
| **`"plus"` / `"add"`** | 십자(+) | 12~14px / `#9cb5d8` | 새 세트 추가, 위젯 추가 |
| **`"chevron_down"`** | 아래 화살표(∨) | 12px / `#9cb5d8` | 아코디언 펼치기, 순서 내리기 |
| **`"chevron_up"`** | 위 화살표(∧) | 12px / `#9cb5d8` | 순서 올리기 |
| **`"chevron_right"`** | 오른쪽 화살표(>) | 12px / `#9cb5d8` | 아코디언 접기 상태 |
| **`"grid"` / `"layout"`** | 4분할 그리드 | 14px / `#8da8cb` | 스프레드 배치 모드 |
| **`"screen"` / `"monitor"`**| 모니터 화면 | 14px / `#8da8cb` | 화면 맞춤, 전체화면 맞춤 |
| **`"aspect"` / `"ratio"`** | 대각 종횡비 | 14px / `#8da8cb` | 종횡비 고정, 자동 계산 |

---

## 5. 컴포넌트별 레이아웃 & 배치 규칙

### 1) 마스터 컨트롤러 (`MasterController`)
- **세트 헤더 액션 버튼 배치 순서**:
  - `[토글 버튼] ➔ [폴더 아이콘] ➔ [말줄임 제목] ➔ [개수 뱃지] ➔ [적용 뱃지/버튼] ➔ [▲] ➔ [▼] ➔ [⚙]` (세트 관리는 [⚙]에서 수행)
- **규격**:
  - 행 액션 버튼(`QPushButton[kind="rowAction"]`): 크기 `26x26px`, 아이콘 `12~13px`, 호버 배경 `#375074`

### 2) 설정 다이얼로그 (`SettingsDialog`)
- **창 크기**: 기본 `580x660px` (고정 너비 580px, 내용에 따라 세로 스크롤)
- **세그먼트 탭**:
  - `[ 📁 미디어 & 재생 ]` `[ 📐 위젯 & 외형 ]` `[ ⚡ 연동 & 시스템 ]`
- **단위 입력 필드 (`_create_unit_input`)**:
  - `QSpinBox` + 단위 라벨(`px`, `초`)이 하나의 둥근 컨테이너(`QFrame#unitInputContainer`)로 감싸져야 함.
  - 너비 `140px`, 높이 `32px`, 포커스 시 `#528bf8` 1.5px 보더.
- **그룹 일괄 설정 모드 (`bulk_mode=True`)**:
  - `[크기 및 종횡비]` 섹션 상단에 **안내 카드(`QFrame#bulkNoticeCard`)** 형태로 배치하여 일반 폼 필드와 시각적으로 구분.
  - `[✓] 각 위젯의 기존 크기 유지 (일괄 변경 안 함)` 체크 시 `width_input`과 `height_input`은 비활성화 처리.

### 3) 체크박스(QCheckBox) 스타일 표준 규칙
- **[절대 주의] `QCheckBox::indicator` 스타일을 CSS로 임의 오버라이드하지 마십시오.**  
  인디케이터 스타일을 건드리면 네이티브 V자 체크 표시(✓)가 사라집니다.  
  반드시 텍스트 색상(`color`), 폰트 크기(`font-size`), 간격(`spacing`)만 스타일링합니다.
```css
/* 표준 QCheckBox 스타일 규격 */
QCheckBox {
    color: #e4ecfb;
    font-size: 11~12px;
    font-weight: 600;
    spacing: 6~7px;
    min-height: 22~24px;
}
QCheckBox:hover {
    color: #ffffff;
}
```

---

## 6. 개발자 및 AI 10대 불변 규칙 (10 Inviolable Invariants)

향후 코드를 작성하거나 수정할 때 **아래 10가지 규칙은 절대 어겨서는 안 됩니다**:

1. **인디케이터 스타일 파괴 금지**: `QCheckBox::indicator`를 섣불리 오버라이드하여 OS 표준 V자 체크마크를 날려먹지 마십시오.
2. **단일 진실 공급원 준수**: 본 문서에 정의된 컬러 토큰, 폰트 크기, 간격 규칙을 벗어난 날것(Raw) 스타일을 추가하지 마십시오.
3. **모달 팝업 계층 안전성**: `QMessageBox`나 다이얼로그를 띄울 때는 항상 `parent=self` 또는 현재 활성화된 모달 다이얼로그를 부모로 전달하여 팝업이 뒤로 숨는 버그를 원천 차단하십시오.
4. **Win32 하드웨어 키 감지 보장**: Alt/Ctrl 등 수식자 키 휠 제스처는 Qt 이벤트뿐만 아니라 `win32api.GetAsyncKeyState` 실시간 하드웨어 감지를 반드시 병행하십시오.
5. **가로/세로 휠 듀얼 폴백**: 마우스 휠 이벤트는 항상 `e.angleDelta().y() or e.angleDelta().x()`로 양방향 델타를 모두 수용하십시오.
6. **최소 1개 세트 보존**: 시스템에는 최소 1개의 세트가 항상 유지되어야 하며, 세트 관리 창([⚙])에서도 마지막 1개 세트의 삭제는 차단되어야 합니다.
7. **개별 크기 보존 원칙**: 다수의 위젯을 임시 그룹으로 묶어 일괄 설정을 열었을 때, 사용자의 명시적 요청 없이 위젯들의 고유 W/H를 강제로 덮어쓰지 마십시오.
8. **백그라운드 미디어 정지 원칙**: 다른 앱이 전체화면으로 실행 중일 때는 백그라운드에서 불필요하게 GIF/비디오가 재생되지 않도록 자동 일시정지 상태를 유지하십시오.
9. **벡터 아이콘 강제**: UI 아이콘은 임의의 이미지 파일을 쓰지 말고 `render_vector_icon()` 벡터 렌더러를 사용하십시오.
10. **빌드 전 무결성 검증**: 코드를 수정한 후에는 반드시 `python -m py_compile` 문법 검사와 단위 테스트를 실행하고, `build_release.cmd`로 정상 릴리스 빌드까지 마친 후 사용자에게 보고하십시오.
