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
