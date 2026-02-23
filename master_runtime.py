# Consolidated master runtime utilities
import os
import sys

from PyQt6.QtCore import QFileInfo, Qt, QSettings
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QFileIconProvider

from mycanvas_core import _as_bool, _get_win32com_client


def frozen_executable_path():
    if not bool(getattr(sys, "frozen", False)):
        return ""
    try:
        exe_path = str(getattr(sys, "executable", "") or "").strip()
        if not exe_path:
            return ""
        exe_path = os.path.abspath(exe_path)
    except Exception:
        return ""
    if not os.path.isfile(exe_path):
        return ""
    return exe_path


def windows_startup_folder_path():
    try:
        appdata = str(os.environ.get("APPDATA", "") or "").strip()
    except Exception:
        appdata = ""
    if not appdata:
        return ""
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def startup_shortcut_icon_path(exe_path):
    exe = str(exe_path or "").strip()
    if not exe:
        return ""
    exe_dir = os.path.dirname(exe)
    exe_name = os.path.splitext(os.path.basename(exe))[0]
    icon_names = ["icon.ico"]
    if exe_name:
        icon_names.append(f"{exe_name}.ico")
    icon_names.extend(["MyCanvas.ico"])
    seen = set()
    for name in icon_names:
        candidate = os.path.join(exe_dir, name)
        norm = os.path.normcase(os.path.normpath(candidate))
        if norm in seen:
            continue
        seen.add(norm)
        if os.path.isfile(candidate):
            return candidate
    return exe


def startup_shortcut_pref_key():
    return "startup_shortcut_enabled_v1"


def startup_shortcut_path(_controller, exe_path=""):
    resolved_exe = str(exe_path or "").strip()
    if not resolved_exe:
        resolved_exe = frozen_executable_path()
    if not resolved_exe:
        return ""
    startup_dir = windows_startup_folder_path()
    if not startup_dir:
        return ""
    exe_name = os.path.splitext(os.path.basename(resolved_exe))[0] or "MyCanvas"
    return os.path.join(startup_dir, f"{exe_name}.lnk")


def startup_shortcut_enabled(controller):
    raw = controller.master_settings.value(startup_shortcut_pref_key(), None)
    if raw is None:
        return _as_bool(os.environ.get("MYCANVAS_ENSURE_STARTUP_SHORTCUT", "0"), False)
    return _as_bool(raw, False)


def fast_startup_enabled():
    return _as_bool(os.environ.get("MYCANVAS_FAST_STARTUP", "1"), True)


def minimal_validation_enabled():
    return _as_bool(os.environ.get("MYCANVAS_MIN_VALIDATION", "1"), True)


def fast_set_switch_enabled():
    return _as_bool(os.environ.get("MYCANVAS_FAST_SET_SWITCH", "1"), True)


def resolve_app_icon(controller_cls):
    # Fast path: only check the most likely locations.
    quick_candidates = []
    try:
        exe_path = str(getattr(sys, "executable", "") or "").strip()
        if exe_path:
            exe_dir = os.path.dirname(os.path.abspath(exe_path))
            quick_candidates.append(os.path.join(exe_dir, "MyCanvas.ico"))
            quick_candidates.append(os.path.join(exe_dir, "icon.ico"))
    except Exception:
        pass
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir:
            quick_candidates.append(os.path.join(script_dir, "MyCanvas.ico"))
            quick_candidates.append(os.path.join(script_dir, "icon.ico"))
    except Exception:
        pass

    seen = set()
    for candidate in quick_candidates:
        key = os.path.normcase(os.path.normpath(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        try:
            if os.path.isfile(candidate):
                icon = QIcon(candidate)
                if not icon.isNull():
                    return icon
        except Exception:
            continue

    # Slow fallback path only when fast-start mode is disabled.
    if not bool(controller_cls._fast_startup_enabled()):
        runtime_dirs = []
        try:
            meipass = str(getattr(sys, "_MEIPASS", "") or "").strip()
            if meipass:
                runtime_dirs.append(meipass)
        except Exception:
            pass
        try:
            exe_path = str(getattr(sys, "executable", "") or "").strip()
            if exe_path:
                runtime_dirs.append(os.path.dirname(os.path.abspath(exe_path)))
        except Exception:
            pass
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir:
                runtime_dirs.append(script_dir)
        except Exception:
            pass
        try:
            cwd = os.getcwd()
            if cwd:
                runtime_dirs.append(cwd)
        except Exception:
            pass
        ordered_dirs = []
        seen_dirs = set()
        for path in runtime_dirs:
            key = os.path.normcase(os.path.normpath(str(path)))
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            ordered_dirs.append(str(path))
        icon_names = []
        try:
            exe_name = os.path.splitext(
                os.path.basename(str(getattr(sys, "executable", "") or "").strip())
            )[0]
            if exe_name:
                icon_names.append(f"{exe_name}.ico")
        except Exception:
            pass
        icon_names.extend(["MyCanvas.ico", "icon.ico"])
        seen_paths = set()
        for folder in ordered_dirs:
            for name in icon_names:
                candidate = os.path.join(folder, name)
                key = os.path.normcase(os.path.normpath(candidate))
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                try:
                    if os.path.isfile(candidate):
                        icon = QIcon(candidate)
                        if not icon.isNull():
                            return icon
                except Exception:
                    continue

        try:
            exe_path = str(getattr(sys, "executable", "") or "").strip()
            if exe_path and os.path.isfile(exe_path):
                exe_icon = QFileIconProvider().icon(QFileInfo(exe_path))
                if not exe_icon.isNull():
                    return exe_icon
        except Exception:
            pass

    fallback = QIcon("MyCanvas.ico")
    if not fallback.isNull():
        return fallback
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.green)
    return QIcon(pixmap)


def ensure_windows_startup_shortcut(controller, force=False):
    if (not bool(force)) and (not startup_shortcut_enabled(controller)):
        return
    exe_path = frozen_executable_path()
    win32com_client = _get_win32com_client()
    if not exe_path or win32com_client is None:
        return
    shortcut_path = startup_shortcut_path(controller, exe_path)
    if not shortcut_path:
        return
    startup_dir = os.path.dirname(shortcut_path)
    try:
        os.makedirs(startup_dir, exist_ok=True)
    except Exception:
        return
    exe_name = os.path.splitext(os.path.basename(exe_path))[0] or "MyCanvas"
    icon_path = startup_shortcut_icon_path(exe_path)
    marker = ""
    try:
        norm_exe = os.path.normcase(os.path.normpath(str(exe_path)))
        marker = f"{norm_exe}|{int(os.path.getmtime(exe_path))}"
    except Exception:
        marker = str(exe_path)
    marker_key = "startup_shortcut_marker_v1"
    marker_settings = None
    try:
        marker_settings = QSettings("MyHomeApp", "MasterV3")
        old_marker = str(marker_settings.value(marker_key, "") or "")
        if old_marker == marker:
            try:
                if os.path.isfile(shortcut_path):
                    return
            except Exception:
                return
    except Exception:
        marker_settings = None
    try:
        shell = win32com_client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = exe_path
        shortcut.WorkingDirectory = os.path.dirname(exe_path)
        shortcut.Arguments = ""
        shortcut.IconLocation = f"{icon_path},0"
        shortcut.Description = f"{exe_name} auto start"
        shortcut.Save()
        if marker_settings is not None:
            try:
                marker_settings.setValue(marker_key, marker)
                marker_settings.sync()
            except Exception:
                pass
    except Exception:
        pass


def remove_windows_startup_shortcut(controller):
    shortcut_path = startup_shortcut_path(controller, frozen_executable_path())
    if shortcut_path:
        try:
            if os.path.isfile(shortcut_path):
                os.remove(shortcut_path)
        except Exception:
            pass
    try:
        controller.master_settings.remove("startup_shortcut_marker_v1")
        controller.master_settings.sync()
    except Exception:
        pass

import os
import sys


def sync_startup_shortcut_toggle(controller):
    if not hasattr(controller, "startup_shortcut_cb"):
        return
    available = bool(getattr(sys, "frozen", False))
    enabled_pref = bool(controller._startup_shortcut_enabled()) if available else False
    prev = controller.startup_shortcut_cb.blockSignals(True)
    controller.startup_shortcut_cb.setEnabled(available)
    controller.startup_shortcut_cb.setChecked(enabled_pref)
    controller.startup_shortcut_cb.blockSignals(prev)
    if not hasattr(controller, "startup_shortcut_hint_lbl"):
        return
    if not available:
        controller.startup_shortcut_hint_lbl.setText("개발 실행에서는 비활성화됩니다. exe에서만 동작합니다.")
        return
    shortcut_path = controller._startup_shortcut_path(controller._frozen_executable_path())
    registered = False
    if shortcut_path:
        try:
            registered = os.path.isfile(shortcut_path)
        except Exception:
            registered = False
    controller.startup_shortcut_hint_lbl.setText("현재 등록됨" if registered else "현재 미등록")


def set_startup_shortcut_enabled(controller, enabled, persist=True):
    enable_flag = bool(enabled)
    if persist:
        controller.master_settings.setValue(controller._startup_shortcut_pref_key(), enable_flag)
        controller.master_settings.sync()
    if enable_flag:
        controller._ensure_windows_startup_shortcut(force=True)
    else:
        controller._remove_windows_startup_shortcut()
    sync_startup_shortcut_toggle(controller)


def on_startup_shortcut_toggled(controller, checked):
    if not bool(getattr(sys, "frozen", False)):
        sync_startup_shortcut_toggle(controller)
        return
    set_startup_shortcut_enabled(controller, bool(checked), persist=True)


def apply_gpu_guard_thresholds(controller, high_pct, low_pct, persist=True):
    try:
        high = float(high_pct)
    except Exception:
        high = 90.0
    try:
        low = float(low_pct)
    except Exception:
        low = 70.0

    high = max(1.0, min(100.0, high))
    low = max(0.0, min(99.0, low))
    if low >= high:
        low = max(0.0, high - 1.0)

    controller._gpu_guard_high_pct = high
    controller._gpu_guard_low_pct = low
    sync_gpu_threshold_inputs(controller)

    if persist:
        controller.master_settings.setValue("gpu_guard_high_pct", int(round(high)))
        controller.master_settings.setValue("gpu_guard_low_pct", int(round(low)))
        if hasattr(controller, "_master_settings_sync_timer"):
            schedule_master_settings_sync(controller)
        else:
            controller.master_settings.sync()


def sync_gpu_threshold_inputs(controller):
    if not hasattr(controller, "gpu_pause_slider") or not hasattr(controller, "gpu_resume_slider"):
        return
    pause_val = int(round(controller._gpu_guard_high_pct))
    resume_val = int(round(controller._gpu_guard_low_pct))
    prev = controller.gpu_pause_slider.blockSignals(True)
    controller.gpu_pause_slider.setValue(pause_val)
    controller.gpu_pause_slider.blockSignals(prev)
    prev = controller.gpu_resume_slider.blockSignals(True)
    controller.gpu_resume_slider.setValue(resume_val)
    controller.gpu_resume_slider.blockSignals(prev)
    if hasattr(controller, "gpu_pause_value_lbl"):
        controller.gpu_pause_value_lbl.setText(f"{pause_val}%")
    if hasattr(controller, "gpu_resume_value_lbl"):
        controller.gpu_resume_value_lbl.setText(f"{resume_val}%")


def on_gpu_threshold_inputs_changed(controller):
    apply_gpu_guard_thresholds(
        controller,
        controller.gpu_pause_slider.value(),
        controller.gpu_resume_slider.value(),
        persist=True,
    )
    sync_gpu_threshold_inputs(controller)

def schedule_master_settings_sync(controller, delay_ms=None):
    if not hasattr(controller, "_master_settings_sync_timer"):
        return
    try:
        delay = int(controller._master_settings_sync_delay_ms if delay_ms is None else delay_ms)
    except Exception:
        delay = int(getattr(controller, "_master_settings_sync_delay_ms", 650))
    delay = max(0, delay)
    if delay <= 0:
        flush_master_settings_sync(controller)
        return
    controller._master_settings_sync_timer.start(delay)


def flush_master_settings_sync(controller):
    if hasattr(controller, "_master_settings_sync_timer") and controller._master_settings_sync_timer.isActive():
        controller._master_settings_sync_timer.stop()
    try:
        controller.master_settings.sync()
    except Exception:
        pass


def update_active_status(controller, sync=True):
    """현재 켜져 있는 위젯들의 ID 목록을 저장"""
    active_ids = [str(pid) for pid in controller.widgets.keys()]
    controller.master_settings.setValue("active_profiles", active_ids)
    if bool(sync):
        flush_master_settings_sync(controller)
    else:
        schedule_master_settings_sync(controller)
