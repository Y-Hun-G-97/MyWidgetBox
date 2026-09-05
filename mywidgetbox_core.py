import ctypes
from ctypes import wintypes
import os
import time

try:
    import win32pdh
except Exception:
    win32pdh = None

_win32ui_mod = None
_win32ui_checked = False
_win32com_client_mod = None
_win32com_client_checked = False


def _get_win32ui():
    global _win32ui_mod, _win32ui_checked
    if not bool(_win32ui_checked):
        try:
            import win32ui as _loaded_win32ui
        except Exception:
            _loaded_win32ui = None
        _win32ui_mod = _loaded_win32ui
        _win32ui_checked = True
    return _win32ui_mod


def _get_win32com_client():
    global _win32com_client_mod, _win32com_client_checked
    if not bool(_win32com_client_checked):
        try:
            import win32com.client as _loaded_win32com_client
        except Exception:
            _loaded_win32com_client = None
        _win32com_client_mod = _loaded_win32com_client
        _win32com_client_checked = True
    return _win32com_client_mod


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


class _NvmlUtilization(ctypes.Structure):
    _fields_ = [
        ("gpu", ctypes.c_uint),
        ("memory", ctypes.c_uint),
    ]


class _ADLPMActivity(ctypes.Structure):
    _fields_ = [
        ("iSize", ctypes.c_int),
        ("iEngineClock", ctypes.c_int),
        ("iMemoryClock", ctypes.c_int),
        ("iVddc", ctypes.c_int),
        ("iActivityPercent", ctypes.c_int),
        ("iCurrentPerformanceLevel", ctypes.c_int),
        ("iCurrentBusSpeed", ctypes.c_int),
        ("iCurrentBusLanes", ctypes.c_int),
        ("iMaximumBusLanes", ctypes.c_int),
        ("iReserved", ctypes.c_int),
    ]


_ADL_MALLOC_CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_size_t)


def _adl_alloc(size):
    try:
        return ctypes.windll.kernel32.LocalAlloc(0x0040, size)
    except Exception:
        return None


_adl_alloc_cb = _ADL_MALLOC_CALLBACK(_adl_alloc)


class GpuUsageSampler:
    """Universal Windows GPU utilization sampler (NVIDIA NVML 3D+NVDEC, AMD ADL, and Windows PDH)."""

    def __init__(self):
        self._nvml = None
        self._nvml_handles = []
        self._adl = None
        self._adl_num_adapters = 0
        self._query = None
        self._counters = []
        self._last_refresh = 0.0
        self._init_backend()

    @property
    def _backend(self):
        backends = []
        if self._nvml:
            backends.append("nvml")
        if self._adl:
            backends.append("adl")
        if self._counters:
            backends.append("pdh")
        return "+".join(backends) if backends else "none"

    def _init_backend(self):
        # 1. NVIDIA NVML (Hardware ASIC 3D + Video Decoder, multi-GPU)
        try:
            nvml_path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvml.dll")
            nvml = ctypes.CDLL(nvml_path) if os.path.isfile(nvml_path) else ctypes.CDLL("nvml.dll")
            if nvml.nvmlInit_v2() == 0:
                dev_count = ctypes.c_uint(0)
                handles = []
                if nvml.nvmlDeviceGetCount_v2(ctypes.byref(dev_count)) == 0 and dev_count.value > 0:
                    for i in range(dev_count.value):
                        h = ctypes.c_void_p()
                        if nvml.nvmlDeviceGetHandleByIndex_v2(i, ctypes.byref(h)) == 0:
                            handles.append(h)
                if handles:
                    self._nvml = nvml
                    self._nvml_handles = handles
                else:
                    try:
                        nvml.nvmlShutdown()
                    except Exception:
                        pass
        except Exception:
            self._nvml = None
            self._nvml_handles = []

        # 2. AMD ADL (AMD Radeon Display Library, multi-GPU)
        try:
            adl_dll = None
            for name in ("atiadlxx.dll", "atiadlxy.dll"):
                p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", name)
                if os.path.isfile(p):
                    try:
                        adl_dll = ctypes.CDLL(p)
                        break
                    except Exception:
                        continue
            if adl_dll is not None and hasattr(adl_dll, "ADL_Main_Control_Create"):
                if adl_dll.ADL_Main_Control_Create(_adl_alloc_cb, 1) == 0:
                    num_adapters = ctypes.c_int(0)
                    try:
                        if hasattr(adl_dll, "ADL_Adapter_NumberOfAdapters_Get"):
                            adl_dll.ADL_Adapter_NumberOfAdapters_Get(ctypes.byref(num_adapters))
                    except Exception:
                        pass
                    self._adl = adl_dll
                    self._adl_num_adapters = max(1, int(num_adapters.value or 1))
        except Exception:
            self._adl = None
            self._adl_num_adapters = 0

        # 3. Windows PDH fallback (Generic / Intel iGPU / other GPUs)
        if not self._nvml and not self._adl and win32pdh is not None:
            self._rebuild_query()

    def close(self):
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml = None
            self._nvml_handles = []
        if self._adl is not None:
            try:
                if hasattr(self._adl, "ADL_Main_Control_Destroy"):
                    self._adl.ADL_Main_Control_Destroy()
            except Exception:
                pass
            self._adl = None
            self._adl_num_adapters = 0
        if self._query is not None and win32pdh is not None:
            try:
                win32pdh.CloseQuery(self._query)
            except Exception:
                pass
        self._query = None
        self._counters = []

    def _rebuild_query(self):
        if self._query is not None and win32pdh is not None:
            try:
                win32pdh.CloseQuery(self._query)
            except Exception:
                pass
        self._query = None
        self._counters = []
        if win32pdh is None:
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
            if self._query is not None and win32pdh is not None:
                try:
                    win32pdh.CloseQuery(self._query)
                except Exception:
                    pass
            self._query = None
            self._counters = []

    def sample_pct(self):
        max_reported = 0.0
        sampled_any = False

        # 1. Sample NVIDIA (3D Core + Video Decoder NVDEC across all NVIDIA GPUs)
        if self._nvml is not None and self._nvml_handles:
            try:
                for handle in self._nvml_handles:
                    util = _NvmlUtilization()
                    gpu_3d = 0.0
                    gpu_dec = 0.0
                    if self._nvml.nvmlDeviceGetUtilizationRates(handle, ctypes.byref(util)) == 0:
                        gpu_3d = float(util.gpu)
                    dec_val = ctypes.c_uint(0)
                    sp = ctypes.c_uint(0)
                    try:
                        if self._nvml.nvmlDeviceGetDecoderUtilization(handle, ctypes.byref(dec_val), ctypes.byref(sp)) == 0:
                            gpu_dec = float(dec_val.value)
                    except Exception:
                        pass
                    node_val = max(gpu_3d, gpu_dec)
                    if node_val > max_reported:
                        max_reported = node_val
                    sampled_any = True
            except Exception:
                pass

        # 2. Sample AMD (Activity % across all AMD GPUs)
        if self._adl is not None:
            try:
                act = _ADLPMActivity()
                act.iSize = ctypes.sizeof(_ADLPMActivity)
                for i in range(max(1, self._adl_num_adapters)):
                    if hasattr(self._adl, "ADL_Overdrive5_CurrentActivity_Get"):
                        if self._adl.ADL_Overdrive5_CurrentActivity_Get(i, ctypes.byref(act)) == 0:
                            p = float(act.iActivityPercent)
                            if p > max_reported:
                                max_reported = p
                            sampled_any = True
            except Exception:
                pass

        if sampled_any:
            return max(0.0, min(100.0, max_reported))

        # 3. Fallback: Windows PDH (Generic / Intel / other GPUs)
        if win32pdh is not None:
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
            if valid_count > 0:
                return max(0.0, min(100.0, total))

        return None


def get_media_native_size(path):
    """
    고속으로 이미지/GIF 및 동영상(MP4, MOV, MKV, WEBM 등)의 실제 픽셀 해상도 (width, height)를 반환합니다.
    """
    if not path or not isinstance(path, str):
        return None
    import os
    if not os.path.isfile(path):
        return None

    ext = os.path.splitext(path)[1].lower()
    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".ts"}

    if ext in video_exts:
        try:
            import cv2
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    return (w, h)
        except Exception:
            pass

    try:
        from PyQt6.QtGui import QImageReader
        reader = QImageReader(path)
        sz = reader.size()
        if sz.isValid() and sz.width() > 0 and sz.height() > 0:
            return (sz.width(), sz.height())
    except Exception:
        pass

    if ext in video_exts:
        try:
            client = _get_win32com_client()
            if client is not None:
                shell = client.Dispatch("Shell.Application")
                folder_obj = shell.NameSpace(os.path.dirname(os.path.abspath(path)))
                file_obj = folder_obj.ParseName(os.path.basename(path))
                for idx in (316, 314, 312, 310, 285, 287):
                    val = str(folder_obj.GetDetailsOf(file_obj, idx) or "").strip()
                    if val.isdigit() and int(val) > 0:
                        h_val = str(folder_obj.GetDetailsOf(file_obj, idx + 2) or "").strip()
                        if h_val.isdigit() and int(h_val) > 0:
                            return (int(val), int(h_val))
        except Exception:
            pass

    return None


def calc_smart_aspect_size(iw, ih, base_w=200, base_h=200, min_size=50, max_size=5000):
    """
    미디어의 실제 해상도 (iw, ih)와 기준 크기 (base_w, base_h)를 바탕으로,
    - 가로형 미디어 (iw >= ih): 높이를 base_h로 유지하고 너비를 가로로 시원하게 확장
    - 세로형 미디어 (ih > iw): 너비를 base_w로 유지하고 높이를 세로로 길게 확장
    하여 쪼그라들지 않는 최적의 (target_w, target_h)를 반환합니다.
    """
    try:
        iw = float(iw)
        ih = float(ih)
        base_w = max(min_size, float(base_w))
        base_h = max(min_size, float(base_h))
        if iw <= 0 or ih <= 0:
            return (int(base_w), int(base_h))

        if iw >= ih:
            calc_w = int(round(base_h * (iw / ih)))
            calc_w = max(min_size, min(max_size, calc_w))
            return (calc_w, int(base_h))
        else:
            calc_h = int(round(base_w * (ih / iw)))
            calc_h = max(min_size, min(max_size, calc_h))
            return (int(base_w), calc_h)
    except Exception:
        return (int(base_w), int(base_h))


def apply_windows_dark_title_bar(window):
    """
    Windows DWM API를 호출하여 창의 타이틀바(헤더 바)를 다크 테마 톤으로 변경합니다.
    """
    if not window:
        return False
    try:
        import ctypes
        hwnd = int(window.winId()) if hasattr(window, "winId") else 0
        if not hwnd:
            return False
        # DWMWA_USE_IMMERSIVE_DARK_MODE (20 for Win11/Win10 20H1+, 19 for older Win10)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
        val = ctypes.c_int(1)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val),
            ctypes.sizeof(val)
        )
        if res != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
                ctypes.byref(val),
                ctypes.sizeof(val)
            )
        return True
    except Exception:
        return False


def ask_dark_input(parent, title, prompt, default_text="", ok_text="저장", cancel_text="취소"):
    """
    일관된 다크 테마 스타일을 갖춘 텍스트 입력 모달을 띄우고 (text, True/False)를 반환합니다.
    """
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QIcon

    dlg = QDialog(parent)
    dlg.setWindowTitle(str(title or "입력"))
    dlg.setWindowIcon(QIcon())
    dlg.setFixedWidth(360)
    dlg.setStyleSheet("""
        QDialog {
            background-color: #1a273b;
        }
        QLabel#inputTitle {
            color: #eef3ff;
            font-size: 14px;
            font-weight: 700;
        }
        QLineEdit#darkInputField {
            color: #ffffff;
            background-color: #121c2c;
            border: 1px solid #354b6e;
            border-radius: 6px;
            padding: 7px 10px;
            font-size: 13px;
            selection-background-color: #4a74e2;
        }
        QLineEdit#darkInputField:focus {
            border: 1px solid #5a8ef0;
            background-color: #152236;
        }
        QPushButton {
            min-height: 32px;
            min-width: 80px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 14px;
        }
        QPushButton#cancelBtn {
            color: #dbe7fb;
            background-color: #2b3e5b;
            border: 1px solid #48648c;
        }
        QPushButton#cancelBtn:hover {
            background-color: #364e72;
            border-color: #6385b5;
            color: #ffffff;
        }
        QPushButton#saveBtn {
            color: #ffffff;
            background-color: #4a74e2;
            border: 1px solid #7296f0;
        }
        QPushButton#saveBtn:hover {
            background-color: #5d86f0;
        }
    """)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(20, 20, 20, 18)
    layout.setSpacing(14)

    prompt_label = QLabel(str(prompt or "입력하세요:"))
    prompt_label.setObjectName("inputTitle")
    layout.addWidget(prompt_label)

    line_edit = QLineEdit(str(default_text or ""), dlg)
    line_edit.setObjectName("darkInputField")
    line_edit.selectAll()
    layout.addWidget(line_edit)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    btn_row.addStretch(1)

    cancel_btn = QPushButton(str(cancel_text or "취소"))
    cancel_btn.setObjectName("cancelBtn")

    save_btn = QPushButton(str(ok_text or "저장"))
    save_btn.setObjectName("saveBtn")
    save_btn.setDefault(True)

    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

    cancel_btn.clicked.connect(dlg.reject)
    save_btn.clicked.connect(dlg.accept)
    line_edit.returnPressed.connect(dlg.accept)

    apply_windows_dark_title_bar(dlg)
    QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(dlg))

    if dlg.exec() == QDialog.DialogCode.Accepted:
        return line_edit.text().strip(), True
    return "", False


def ask_dark_confirm(parent, title, message, yes_text="삭제", no_text="취소", is_danger=True):
    """
    완벽한 다크 테마와 일관된 버튼 레이아웃을 갖춘 확인 모달을 띄우고 True/False를 반환합니다.
    """
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QIcon

    dlg = QDialog(parent)
    dlg.setWindowTitle(str(title or "확인"))
    dlg.setWindowIcon(QIcon())
    dlg.setFixedWidth(380)
    dlg.setStyleSheet("""
        QDialog {
            background-color: #1a273b;
        }
        QLabel#confirmTitle {
            color: #eef3ff;
            font-size: 15px;
            font-weight: 700;
        }
        QLabel#confirmMessage {
            color: #c7d8f0;
            font-size: 13px;
            line-height: 1.4;
        }
        QPushButton {
            min-height: 34px;
            min-width: 90px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 16px;
        }
        QPushButton#cancelBtn {
            color: #dbe7fb;
            background-color: #2b3e5b;
            border: 1px solid #48648c;
        }
        QPushButton#cancelBtn:hover {
            background-color: #364e72;
            border-color: #6385b5;
            color: #ffffff;
        }
        QPushButton#actionBtn {
            color: #ffffff;
            background-color: #4a74e2;
            border: 1px solid #7296f0;
        }
        QPushButton#actionBtn:hover {
            background-color: #5d86f0;
        }
        QPushButton#actionBtn[danger="true"] {
            color: #ffe8ec;
            background-color: #8c3242;
            border: 1px solid #b84d62;
        }
        QPushButton#actionBtn[danger="true"]:hover {
            background-color: #a43c4f;
            border-color: #cf5e74;
            color: #ffffff;
        }
    """)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(20, 20, 20, 18)
    layout.setSpacing(14)

    title_label = QLabel(str(title or "확인"))
    title_label.setObjectName("confirmTitle")
    layout.addWidget(title_label)

    msg_label = QLabel(str(message or ""))
    msg_label.setObjectName("confirmMessage")
    msg_label.setWordWrap(True)
    layout.addWidget(msg_label)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    btn_row.addStretch(1)

    cancel_btn = QPushButton(str(no_text or "취소"))
    cancel_btn.setObjectName("cancelBtn")

    action_btn = QPushButton(str(yes_text or "확인"))
    action_btn.setObjectName("actionBtn")
    action_btn.setProperty("danger", "true" if bool(is_danger) else "false")

    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(action_btn)
    layout.addLayout(btn_row)

    cancel_btn.clicked.connect(dlg.reject)
    action_btn.clicked.connect(dlg.accept)
    action_btn.setDefault(True)

    QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(dlg))
    return dlg.exec() == QDialog.DialogCode.Accepted


_vector_icon_cache = {}


def render_vector_icon(name, color="#a4bedc", size=16):
    """
    Figma / Feather 스타일의 미니멀 모던 벡터 아이콘을 QIcon으로 생성합니다.
    자주 호출되는 아이콘은 전역 메모리에 캐시하여 렌더링 오버헤드를 제거합니다.
    """
    cache_key = (str(name), str(color).lower(), int(size))
    if cache_key in _vector_icon_cache:
        return _vector_icon_cache[cache_key]

    import math
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF
    from PyQt6.QtCore import Qt, QPointF, QRectF

    sz = max(12, int(size))
    pixmap = QPixmap(sz, sz)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    c = QColor(color)
    pen = QPen(c)
    pen.setWidthF(max(1.2, sz / 12.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    s = float(sz)
    pad = s * 0.12

    if name in ("run", "play"):
        poly = QPolygonF([
            QPointF(s * 0.32, s * 0.22),
            QPointF(s * 0.76, s * 0.50),
            QPointF(s * 0.32, s * 0.78),
        ])
        painter.setBrush(QBrush(c))
        painter.drawPolygon(poly)

    elif name in ("stop", "square"):
        rect = QRectF(s * 0.26, s * 0.26, s * 0.48, s * 0.48)
        painter.setBrush(QBrush(c))
        painter.drawRoundedRect(rect, s * 0.08, s * 0.08)

    elif name in ("media", "image"):
        rect = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)
        painter.drawRoundedRect(rect, s * 0.15, s * 0.15)
        poly = QPolygonF([
            QPointF(s * 0.42, s * 0.35),
            QPointF(s * 0.68, s * 0.50),
            QPointF(s * 0.42, s * 0.65),
        ])
        painter.setBrush(QBrush(c))
        painter.drawPolygon(poly)

    elif name in ("widget", "layout", "grid"):
        gap = s * 0.10
        bw = (s - 2 * pad - gap) / 2.0
        bh = bw
        r = s * 0.08
        painter.drawRoundedRect(QRectF(pad, pad, bw, bh), r, r)
        painter.drawRoundedRect(QRectF(pad + bw + gap, pad, bw, bh), r, r)
        painter.drawRoundedRect(QRectF(pad, pad + bh + gap, bw, bh), r, r)
        painter.drawRoundedRect(QRectF(pad + bw + gap, pad + bh + gap, bw, bh), r, r)

    elif name in ("system", "settings", "sliders", "gear"):
        y1, y2, y3 = s * 0.30, s * 0.50, s * 0.70
        painter.drawLine(QPointF(pad, y1), QPointF(s - pad, y1))
        painter.drawLine(QPointF(pad, y2), QPointF(s - pad, y2))
        painter.drawLine(QPointF(pad, y3), QPointF(s - pad, y3))
        painter.setBrush(QBrush(c))
        painter.drawEllipse(QPointF(s * 0.38, y1), s * 0.08, s * 0.08)
        painter.drawEllipse(QPointF(s * 0.65, y2), s * 0.08, s * 0.08)
        painter.drawEllipse(QPointF(s * 0.45, y3), s * 0.08, s * 0.08)

    elif name in ("trash", "delete", "remove_can"):
        # Modern trash can with lid
        painter.drawLine(QPointF(s * 0.20, s * 0.30), QPointF(s * 0.80, s * 0.30))
        painter.drawLine(QPointF(s * 0.38, s * 0.20), QPointF(s * 0.62, s * 0.20))
        poly = QPolygonF([
            QPointF(s * 0.26, s * 0.32),
            QPointF(s * 0.32, s * 0.82),
            QPointF(s * 0.68, s * 0.82),
            QPointF(s * 0.74, s * 0.32),
        ])
        painter.drawPolygon(poly)
        painter.drawLine(QPointF(s * 0.42, s * 0.44), QPointF(s * 0.42, s * 0.70))
        painter.drawLine(QPointF(s * 0.58, s * 0.44), QPointF(s * 0.58, s * 0.70))

    elif name in ("close", "x", "cancel"):
        painter.drawLine(QPointF(s * 0.28, s * 0.28), QPointF(s * 0.72, s * 0.72))
        painter.drawLine(QPointF(s * 0.72, s * 0.28), QPointF(s * 0.28, s * 0.72))

    elif name in ("plus", "add"):
        painter.drawLine(QPointF(s * 0.50, s * 0.22), QPointF(s * 0.50, s * 0.78))
        painter.drawLine(QPointF(s * 0.22, s * 0.50), QPointF(s * 0.78, s * 0.50))

    elif name in ("folder", "directory"):
        poly = QPolygonF([
            QPointF(pad, s * 0.32),
            QPointF(s * 0.40, s * 0.32),
            QPointF(s * 0.50, s * 0.42),
            QPointF(s - pad, s * 0.42),
            QPointF(s - pad, s - pad),
            QPointF(pad, s - pad),
        ])
        painter.drawPolygon(poly)
        painter.drawLine(QPointF(pad, s * 0.42), QPointF(s * 0.50, s * 0.42))

    elif name in ("file", "document"):
        poly = QPolygonF([
            QPointF(pad * 1.3, pad),
            QPointF(s - pad * 2.0, pad),
            QPointF(s - pad * 1.3, pad * 2.0),
            QPointF(s - pad * 1.3, s - pad),
            QPointF(pad * 1.3, s - pad),
        ])
        painter.drawPolygon(poly)
        painter.drawLine(QPointF(s - pad * 2.0, pad), QPointF(s - pad * 2.0, pad * 2.0))
        painter.drawLine(QPointF(s - pad * 2.0, pad * 2.0), QPointF(s - pad * 1.3, pad * 2.0))

    elif name in ("list", "playlist", "items"):
        for y_pct in (0.32, 0.50, 0.68):
            y = s * y_pct
            painter.setBrush(QBrush(c))
            painter.drawEllipse(QPointF(pad + s * 0.05, y), s * 0.05, s * 0.05)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(pad + s * 0.20, y), QPointF(s - pad, y))

    elif name in ("ratio", "aspect", "scale"):
        rect = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)
        painter.drawRoundedRect(rect, s * 0.12, s * 0.12)
        painter.drawLine(QPointF(s * 0.32, s * 0.68), QPointF(s * 0.68, s * 0.32))
        painter.drawLine(QPointF(s * 0.48, s * 0.32), QPointF(s * 0.68, s * 0.32))
        painter.drawLine(QPointF(s * 0.68, s * 0.32), QPointF(s * 0.68, s * 0.52))

    elif name in ("help", "question"):
        rect = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)
        painter.drawEllipse(rect)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")

    elif name in ("chevron", "chevron_down", "arrow_down", "down"):
        poly = QPolygonF([
            QPointF(pad, s * 0.38),
            QPointF(s * 0.50, s * 0.65),
            QPointF(s - pad, s * 0.38),
        ])
        painter.drawPolyline(poly)

    elif name in ("chevron_up", "arrow_up", "up"):
        poly = QPolygonF([
            QPointF(pad, s * 0.65),
            QPointF(s * 0.50, s * 0.38),
            QPointF(s - pad, s * 0.65),
        ])
        painter.drawPolyline(poly)

    elif name in ("screen", "monitor", "display"):
        rect = QRectF(pad, pad * 1.2, s - 2 * pad, (s - 2 * pad) * 0.70)
        painter.drawRoundedRect(rect, s * 0.08, s * 0.08)
        painter.drawLine(QPointF(s * 0.50, pad * 1.2 + (s - 2 * pad) * 0.70), QPointF(s * 0.50, s - pad * 1.2))
        painter.drawLine(QPointF(s * 0.32, s - pad * 1.2), QPointF(s * 0.68, s - pad * 1.2))

    elif name in ("chevron_right", "arrow_right"):
        poly = QPolygonF([
            QPointF(s * 0.38, pad),
            QPointF(s * 0.65, s * 0.50),
            QPointF(s * 0.38, s - pad),
        ])
        painter.drawPolyline(poly)

    else:
        painter.setBrush(QBrush(c))
        painter.drawEllipse(QRectF(pad, pad, s - 2 * pad, s - 2 * pad))

    painter.end()
    icon = QIcon(pixmap)
    _vector_icon_cache[cache_key] = icon
    return icon


def is_windows_taskbar_autohide():
    """Windows 작업표시줄 자동 숨김(Auto-hide) 활성화 여부 실시간 확인 (Win32 SHAppBarMessage)"""
    try:
        import ctypes
        from ctypes import wintypes

        class APPBARDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uCallbackMessage", wintypes.UINT),
                ("uEdge", wintypes.UINT),
                ("rc", wintypes.RECT),
                ("lParam", wintypes.LPARAM),
            ]

        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        # ABM_GETSTATE = 4
        state = ctypes.windll.shell32.SHAppBarMessage(4, ctypes.byref(abd))
        # ABS_AUTOHIDE = 1
        return bool(state & 1)
    except Exception:
        return False


def get_screen_work_area(screen, force_full=False):
    """
    모니터의 실제 유효 작업 영역(QRect)을 반환.
    - force_full=True 이거나 작업표시줄이 자동 숨김(Auto-hide) 상태인 경우: 모니터 전체 해상도 100% (screen.geometry()) 반환
    - 일반 고정 작업표시줄인 경우: 작업표시줄 영역을 제외한 screen.availableGeometry() 반환
    """
    if not screen:
        from PyQt6.QtCore import QRect
        return QRect(0, 0, 1920, 1080)

    if bool(force_full) or is_windows_taskbar_autohide():
        return screen.geometry()

    avail = screen.availableGeometry()
    full = screen.geometry()
    if avail.width() >= full.width() and avail.height() >= full.height():
        return full

    return avail



