# Consolidated master runtime utilities
import base64
import os
import subprocess
import sys

from PyQt6.QtCore import QFileInfo, Qt, QSettings
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QFileIconProvider

from mywidgetbox_core import _as_bool


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
    icon_names = []
    if exe_name:
        icon_names.append(f"{exe_name}.ico")
    icon_names.extend(["MyWidgetBox.ico", "icon.ico", "MyCanvas.ico"])
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
        raw = os.environ.get(
            "MYCANVAS_ENSURE_STARTUP_TASK",
            os.environ.get("MYCANVAS_ENSURE_STARTUP_SHORTCUT", "0"),
        )
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
            quick_candidates.append(os.path.join(exe_dir, "MyWidgetBox.ico"))
            quick_candidates.append(os.path.join(exe_dir, "icon.ico"))
            quick_candidates.append(os.path.join(exe_dir, "MyCanvas.ico"))
    except Exception:
        pass
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir:
            quick_candidates.append(os.path.join(script_dir, "MyWidgetBox.ico"))
            quick_candidates.append(os.path.join(script_dir, "icon.ico"))
            quick_candidates.append(os.path.join(script_dir, "MyCanvas.ico"))
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
        icon_names.extend(["MyWidgetBox.ico", "icon.ico", "MyCanvas.ico"])
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

    fallback = QIcon("MyWidgetBox.ico")
    if not fallback.isNull():
        return fallback
    fallback_prev = QIcon("MyCanvas.ico")
    if not fallback_prev.isNull():
        return fallback_prev
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.green)
    return QIcon(pixmap)


def _powershell_executable():
    system_root = str(os.environ.get("SystemRoot", r"C:\Windows") or r"C:\Windows").strip() or r"C:\Windows"
    candidate = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    if os.path.isfile(candidate):
        return candidate
    return "powershell.exe"


def _run_powershell(script, timeout_sec=15):
    encoded = base64.b64encode(str(script or "").encode("utf-16-le")).decode("ascii")
    try:
        run_kwargs = {
            "capture_output": True,
            "timeout": max(1, int(timeout_sec)),
            "check": False,
        }
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
        if creationflags:
            run_kwargs["creationflags"] = creationflags
        startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
        if callable(startupinfo_cls):
            startupinfo = startupinfo_cls()
            show_flag = int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0) or 0)
            if show_flag:
                startupinfo.dwFlags |= show_flag
            if hasattr(startupinfo, "wShowWindow"):
                startupinfo.wShowWindow = 0
            run_kwargs["startupinfo"] = startupinfo
        return subprocess.run(
            [
                _powershell_executable(),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            **run_kwargs,
        )
    except Exception:
        return None


def _ps_single_quote(value):
    return str(value or "").replace("'", "''")


def _current_windows_user():
    username = str(os.environ.get("USERNAME", "") or "").strip()
    if not username:
        return ""
    domain = str(os.environ.get("USERDOMAIN", "") or "").strip()
    if domain:
        return f"{domain}\\{username}"
    return username


def _startup_task_name(_controller=None, exe_path=""):
    _ = str(exe_path or "")
    return "MyWidgetBox Auto Start"


def _startup_task_registered(controller, exe_path=""):
    task_name = _startup_task_name(controller, exe_path=exe_path)
    script = f"""
$ErrorActionPreference = 'Stop'
Import-Module ScheduledTasks -ErrorAction Stop
$task = Get-ScheduledTask -TaskName '{_ps_single_quote(task_name)}' -ErrorAction SilentlyContinue
if ($null -eq $task) {{
    exit 1
}}
exit 0
"""
    result = _run_powershell(script)
    return bool(result is not None and result.returncode == 0)


def _remove_legacy_startup_shortcut(controller, exe_path=""):
    shortcut_path = startup_shortcut_path(controller, exe_path=exe_path or frozen_executable_path())
    if not shortcut_path:
        return
    try:
        if os.path.isfile(shortcut_path):
            os.remove(shortcut_path)
    except Exception:
        pass


def ensure_windows_startup_shortcut(controller, force=False):
    if (not bool(force)) and (not startup_shortcut_enabled(controller)):
        return False
    exe_path = frozen_executable_path()
    user_name = _current_windows_user()
    if not exe_path:
        return False
    working_dir = os.path.dirname(exe_path)
    exe_name = os.path.splitext(os.path.basename(exe_path))[0] or "MyWidgetBox"
    task_name = _startup_task_name(controller, exe_path=exe_path)
    description = f"{exe_name} auto start"
    icon_path = startup_shortcut_icon_path(exe_path)

    # 1. 작업 스케줄러 (Scheduled Task) 등록 시도
    script = f"""
$ErrorActionPreference = 'Stop'
Import-Module ScheduledTasks -ErrorAction Stop
$action = New-ScheduledTaskAction -Execute '{_ps_single_quote(exe_path)}' -WorkingDirectory '{_ps_single_quote(working_dir)}'
$trigger = New-ScheduledTaskTrigger -AtLogOn
try {{
    $principal = New-ScheduledTaskPrincipal -UserId '{_ps_single_quote(user_name)}' -LogonType Interactive -RunLevel Limited
}} catch {{
    $principal = New-ScheduledTaskPrincipal -LogonType Interactive -RunLevel Limited
}}
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName '{_ps_single_quote(task_name)}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description '{_ps_single_quote(description)}' -Force | Out-Null
exit 0
"""
    result = _run_powershell(script)
    success = bool(result is not None and result.returncode == 0)
    if success:
        _remove_legacy_startup_shortcut(controller, exe_path=exe_path)
        return True

    # 2. 작업 스케줄러 등록 실패 시: 시작프로그램 폴더(.lnk) 생성 안전 fallback
    lnk_path = startup_shortcut_path(controller, exe_path=exe_path)
    if lnk_path:
        lnk_script = f"""
$ErrorActionPreference = 'Stop'
$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut('{_ps_single_quote(lnk_path)}')
$sc.TargetPath = '{_ps_single_quote(exe_path)}'
$sc.WorkingDirectory = '{_ps_single_quote(working_dir)}'
$sc.Description = '{_ps_single_quote(description)}'
if (Test-Path '{_ps_single_quote(icon_path)}') {{
    $sc.IconLocation = '{_ps_single_quote(icon_path)},0'
}}
$sc.Save()
exit 0
"""
        lnk_result = _run_powershell(lnk_script)
        if lnk_result is not None and lnk_result.returncode == 0 and os.path.isfile(lnk_path):
            return True

    return False


def remove_windows_startup_shortcut(controller):
    exe_path = frozen_executable_path()
    task_name = _startup_task_name(controller, exe_path=exe_path)
    script = f"""
$ErrorActionPreference = 'Stop'
Import-Module ScheduledTasks -ErrorAction Stop
$task = Get-ScheduledTask -TaskName '{_ps_single_quote(task_name)}' -ErrorAction SilentlyContinue
if ($null -ne $task) {{
    Unregister-ScheduledTask -TaskName '{_ps_single_quote(task_name)}' -Confirm:$false | Out-Null
}}
exit 0
"""
    _ = _run_powershell(script)
    _remove_legacy_startup_shortcut(controller, exe_path=exe_path)
    try:
        controller.master_settings.remove("startup_shortcut_marker_v1")
        controller.master_settings.sync()
    except Exception:
        pass
    return True


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
    registered = _startup_task_registered(controller, exe_path=controller._frozen_executable_path())
    controller.startup_shortcut_hint_lbl.setText(
        "현재 작업 스케줄러 등록됨" if registered else "현재 미등록"
    )


def set_startup_shortcut_enabled(controller, enabled, persist=True):
    enable_flag = bool(enabled)
    if enable_flag:
        enabled_state = bool(controller._ensure_windows_startup_shortcut(force=True))
    else:
        controller._remove_windows_startup_shortcut()
        enabled_state = False
    if persist:
        controller.master_settings.setValue(controller._startup_shortcut_pref_key(), bool(enabled_state))
        controller.master_settings.sync()
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
