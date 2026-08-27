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


class GpuUsageSampler:
    """Windows GPU utilization sampler via PDH counters."""

    def __init__(self):
        self._query = None
        self._counters = []
        self._last_refresh = 0.0
        self._enabled = win32pdh is not None
        if self._enabled:
            self._rebuild_query()

    def close(self):
        if self._query is not None and win32pdh is not None:
            try:
                win32pdh.CloseQuery(self._query)
            except Exception:
                pass
        self._query = None
        self._counters = []

    def _rebuild_query(self):
        self.close()
        if not self._enabled or win32pdh is None:
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
            self.close()

    def sample_pct(self):
        if not self._enabled or win32pdh is None:
            return None
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
        if valid_count == 0:
            return None
        # Normalize to a familiar 0..100 scale.
        return max(0.0, min(100.0, total))


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
