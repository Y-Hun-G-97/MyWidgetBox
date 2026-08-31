# Consolidated master operations (startup queue, runtime widgets, temp group, exec claims)
import os

from PyQt6.QtCore import QSettings

from mywidgetbox_core import _as_bool


def startup_delay_for_kind(kind, mode="default"):
    key = str(kind or "").strip().lower()
    fast = _as_bool(os.environ.get("MYCANVAS_FAST_STARTUP", "1"), True)
    queue_mode = str(mode or "").strip().lower()
    if queue_mode == "set_switch" and _as_bool(os.environ.get("MYCANVAS_FAST_SET_SWITCH", "1"), True):
        if key == "video":
            return 150 if fast else 240
        if key == "gif":
            return 90 if fast else 160
        return 10 if fast else 30
    if key == "video":
        return 200 if fast else 300
    if key == "gif":
        return 130 if fast else 210
    return 20 if fast else 50


def cancel_startup_queue(controller):
    if hasattr(controller, "_startup_queue_timer") and controller._startup_queue_timer.isActive():
        controller._startup_queue_timer.stop()
    controller._startup_queue = []
    controller._startup_queue_active = False
    controller._startup_queue_mode = "default"


def build_profile_startup_queue(controller, profile_ids):
    ordered = []
    for order_idx, pid in enumerate(profile_ids):
        spid = str(pid)
        if not controller._profile_run_enabled(spid):
            continue
        name = QSettings("MyHomeApp", f"Profile_{spid}").value("name", "New 세팅")
        kind = controller._profile_startup_media_kind(spid)
        if kind == "video":
            priority = 1
        elif kind == "gif":
            priority = 2
        else:
            priority = 0
        ordered.append((int(priority), int(order_idx), spid, str(name), str(kind)))
    ordered.sort(key=lambda x: (x[0], x[1]))
    return [(pid, name, kind) for _prio, _idx, pid, name, kind in ordered]


def build_set_startup_queue(controller, set_id):
    sid = str(set_id)
    data = controller._set_defs.get(sid, {})
    return controller._build_profile_startup_queue(data.get("profiles", []))


def begin_startup_queue(controller, entries, mode="default"):
    controller._cancel_startup_queue()
    controller._startup_queue_mode = str(mode or "default").strip().lower() or "default"
    controller._startup_queue = list(entries)
    controller._startup_queue_active = bool(controller._startup_queue)
    if not controller._startup_queue_active:
        controller.update_active_status()
        controller.load_profiles()
        controller._refresh_apply_button_state()
        controller._startup_queue_mode = "default"
        return
    controller._run_next_startup_item()


def run_next_startup_item(controller):
    if not bool(getattr(controller, "_startup_queue_active", False)):
        return
    if not controller._startup_queue:
        controller._startup_queue_active = False
        controller.update_active_status()
        controller.load_profiles()
        controller._refresh_apply_button_state()
        controller._startup_queue_mode = "default"
        return

    pid, name, kind = controller._startup_queue.pop(0)
    controller._start_widget_instance(pid, name, startup_kind=kind)
    controller.update_active_status(sync=False)

    if not controller._startup_queue:
        controller._startup_queue_active = False
        controller.update_active_status(sync=True)
        controller.load_profiles()
        controller._refresh_apply_button_state()
        controller._startup_queue_mode = "default"
        return
    controller._startup_queue_timer.start(controller._startup_delay_for_kind(kind, controller._startup_queue_mode))

from PyQt6.QtCore import QTimer


def sync_all_widget_video_viewports(controller):
    for widget in list(controller.widgets.values()):
        if not hasattr(widget, "_sync_video_viewport_update_mode"):
            continue
        try:
            widget._sync_video_viewport_update_mode()
        except Exception:
            pass


def start_widget_instance(controller, pid, name, startup_kind=""):
    spid = str(pid)
    if spid in controller.widgets:
        return False
    widget_cls = getattr(controller, "_desktop_widget_cls", None)
    if widget_cls is None:
        return False
    widget = widget_cls(spid, name, controller)
    kind_key = str(startup_kind or "").strip().lower()
    defer_prepare = bool(
        getattr(controller, "_startup_queue_active", False)
        and kind_key in ("video", "gif")
    )
    widget._defer_initial_prepare_on_show = bool(defer_prepare)
    if not defer_prepare:
        try:
            widget.prepare_media_before_show()
        except Exception:
            pass
    controller.widgets[spid] = widget
    widget.show()
    controller._sync_all_widget_video_viewports()
    try:
        widget = controller.widgets[spid]
        QTimer.singleShot(
            0,
            lambda w=widget: (
                w._schedule_desktop_icon_overlay_bootstrap(retries=4, delay_ms=50)
                if hasattr(w, "_schedule_desktop_icon_overlay_bootstrap")
                else None
            ),
        )
    except Exception:
        pass
    if spid in controller._temp_group_ids:
        controller.widgets[spid]._refresh_group_badge()
    if controller._gpu_guard_paused and bool(getattr(controller.widgets[spid], "gpu_guard_enabled", False)):
        controller.widgets[spid].set_performance_paused(
            True, reason=f"gpu {controller._gpu_last_usage:.1f}%", force=True
        )
    return True


def stop_widgets_bulk(controller, target_ids):
    target = {str(pid) for pid in target_ids}
    if not target:
        return False
    changed = False
    controller._bulk_set_switch_active = True
    try:
        for pid in list(target):
            widget = controller.widgets.get(pid)
            if widget is None:
                continue
            widget.close()
            widget.deleteLater()
            controller.widgets.pop(pid, None)
            changed = True
    finally:
        controller._bulk_set_switch_active = False
    if changed:
        controller._sync_all_widget_video_viewports()
    return changed


def stop_all_widgets_bulk(controller):
    controller._cancel_startup_queue()
    controller.clear_temp_group(silent=True)
    return controller._stop_widgets_bulk(list(controller.widgets.keys()))

from PyQt6.QtCore import QRect


def _is_widget_like(widget):
    return widget is not None and hasattr(widget, "profile_id")


def is_temp_group_member(controller, pid):
    spid = str(pid)
    return spid in controller._temp_group_ids


def sync_temp_group_badges(controller):
    for widget in controller.widgets.values():
        if _is_widget_like(widget) and hasattr(widget, "_refresh_group_badge"):
            widget._refresh_group_badge()


def toggle_temp_group_member(controller, pid):
    spid = str(pid)
    if not spid or spid not in controller.widgets:
        return False
    if spid in controller._temp_group_ids:
        controller._temp_group_ids.remove(spid)
        grouped = False
    else:
        controller._temp_group_ids.add(spid)
        grouped = True
    sync_temp_group_badges(controller)
    return grouped


def clear_temp_group(controller, silent=False):
    _ = bool(silent)
    if not controller._temp_group_ids:
        return 0
    count = len(controller._temp_group_ids)
    controller._temp_group_ids.clear()
    sync_temp_group_badges(controller)
    return count


def temp_group_shortcut_targets(controller, source_pid):
    spid = str(source_pid)
    source_widget = controller.widgets.get(spid)
    if not _is_widget_like(source_widget):
        return []
    if spid not in controller._temp_group_ids:
        return [source_widget]

    targets = []
    for pid in controller._temp_group_ids:
        widget = controller.widgets.get(str(pid))
        if _is_widget_like(widget):
            targets.append(widget)
    if not targets:
        return [source_widget]

    targets.sort(key=lambda w: (0 if str(getattr(w, "profile_id", "")) == spid else 1, str(getattr(w, "profile_id", ""))))
    return targets


def temp_group_move_targets(controller, source_pid):
    spid = str(source_pid)
    if spid not in controller._temp_group_ids:
        return []
    targets = []
    for pid in controller._temp_group_ids:
        if pid == spid:
            continue
        widget = controller.widgets.get(pid)
        if not _is_widget_like(widget):
            continue
        if not widget.isVisible():
            continue
        if bool(getattr(widget, "is_locked", False)):
            continue
        targets.append(widget)
    return targets


def move_temp_group_by_delta(controller, source_pid, dx, dy):
    if not dx and not dy:
        return
    src = controller.widgets.get(str(source_pid))
    if _is_widget_like(src) and bool(getattr(src, "is_locked", False)):
        return
    for widget in temp_group_move_targets(controller, source_pid):
        widget._move_exact((widget.x() + int(dx), widget.y() + int(dy)))


def resize_temp_group_by_edges(controller, source_pid, left_step, top_step, right_step, bottom_step):
    try:
        d_left = int(left_step)
        d_top = int(top_step)
        d_right = int(right_step)
        d_bottom = int(bottom_step)
    except Exception:
        return
    if not (d_left or d_top or d_right or d_bottom):
        return

    src = controller.widgets.get(str(source_pid))
    if _is_widget_like(src) and bool(getattr(src, "is_locked", False)):
        return

    for widget in temp_group_move_targets(controller, source_pid):
        old_left = int(widget.x())
        old_top = int(widget.y())
        old_right = int(widget.x() + widget.width())
        old_bottom = int(widget.y() + widget.height())

        new_left = int(old_left + d_left)
        new_top = int(old_top + d_top)
        new_right = int(old_right + d_right)
        new_bottom = int(old_bottom + d_bottom)

        min_w = max(50, int(widget.minimumWidth()))
        min_h = max(50, int(widget.minimumHeight()))

        width = int(new_right - new_left)
        height = int(new_bottom - new_top)

        if width < int(min_w):
            if d_left != 0 and d_right == 0:
                new_left = int(new_right - int(min_w))
            else:
                new_right = int(new_left + int(min_w))
            width = int(min_w)
        if height < int(min_h):
            if d_top != 0 and d_bottom == 0:
                new_top = int(new_bottom - int(min_h))
            else:
                new_bottom = int(new_top + int(min_h))
            height = int(min_h)

        widget.setGeometry(QRect(int(new_left), int(new_top), int(width), int(height)))


def save_temp_group_positions(controller, source_pid):
    for widget in temp_group_move_targets(controller, source_pid):
        widget.save_all_settings()


def set_temp_group_mute(controller, source_pid, muted):
    targets = temp_group_shortcut_targets(controller, source_pid)
    if not targets:
        return
    for idx, widget in enumerate(targets):
        widget.set_mute_shortcut_state(bool(muted), log=(idx == 0))


def set_temp_group_gpu_guard(controller, source_pid, enabled):
    targets = temp_group_shortcut_targets(controller, source_pid)
    if not targets:
        return
    for idx, widget in enumerate(targets):
        widget.set_gpu_guard_shortcut_state(bool(enabled), log=(idx == 0), show_hud=True)


def set_temp_group_corner_mode(controller, source_pid, mode):
    widget_cls = getattr(controller, "_desktop_widget_cls", None)
    if widget_cls is not None and hasattr(widget_cls, "coerce_corner_mode"):
        mode_int = widget_cls.coerce_corner_mode(mode)
    else:
        mode_int = int(mode)
    targets = temp_group_shortcut_targets(controller, source_pid)
    if not targets:
        return
    for idx, widget in enumerate(targets):
        widget.set_corner_mode_shortcut_state(mode_int, log=(idx == 0))


def adjust_temp_group_opacity(controller, source_pid, delta_pct):
    try:
        delta = int(delta_pct)
    except Exception:
        delta = 0
    if delta == 0:
        return
    targets = temp_group_shortcut_targets(controller, source_pid)
    if not targets:
        return
    for widget in targets:
        old_val = int(getattr(widget, "current_opacity_pct", 100))
        new_val = max(10, min(100, old_val + delta))
        if new_val == old_val:
            continue
        widget.current_opacity_pct = new_val
        widget.setWindowOpacity(new_val / 100.0)
        widget.save_all_settings()


def adjust_temp_group_layer(controller, source_pid, step):
    try:
        step_val = int(step)
    except Exception:
        step_val = 0
    if step_val == 0:
        return
    targets = temp_group_shortcut_targets(controller, source_pid)
    if not targets:
        return
    layer_names = {0: "배경 (최하단)", 1: "일반 (기본)", 2: "최상위 (항상 위)"}
    for widget in targets:
        cur_layer = int(getattr(widget, "layer_mode", 1))
        new_layer = max(0, min(2, cur_layer + step_val))
        if new_layer == cur_layer:
            continue
        widget.layer_mode = new_layer
        widget.apply_window_settings(new_layer, widget.is_locked)
        widget.save_all_settings()
        if hasattr(widget, "_show_action_hud"):
            name = layer_names.get(new_layer, str(new_layer))
            widget._show_action_hud(f"레이어: {name}")


def set_temp_group_lock(controller, source_pid, lock):
    targets = temp_group_shortcut_targets(controller, source_pid)
    if not targets:
        return 0
    lock_val = bool(lock)
    widget_cls = getattr(controller, "_desktop_widget_cls", None)
    default_layer = int(getattr(widget_cls, "LAYER_NORMAL", 1))
    for widget in targets:
        if hasattr(widget, "cancel_active_interaction"):
            widget.cancel_active_interaction()
    for widget in targets:
        widget.apply_window_settings(int(getattr(widget, "layer_mode", default_layer)), lock_val)
        widget.save_all_settings()
        if hasattr(widget, "show_lock_hud"):
            widget.show_lock_hud(lock_val)
    sync_temp_group_badges(controller)
    return len(targets)

import win32gui


def cleanup_exec_window_claims(controller):
    claims = getattr(controller, "_exec_window_claims", None)
    if not isinstance(claims, dict):
        controller._exec_window_claims = {}
        return
    alive_profiles = set([str(pid) for pid in getattr(controller, "widgets", {}).keys()])
    for hwnd, owner in list(claims.items()):
        try:
            h = int(hwnd)
        except Exception:
            claims.pop(hwnd, None)
            continue
        if h <= 0:
            claims.pop(hwnd, None)
            continue
        try:
            if not win32gui.IsWindow(int(h)):
                claims.pop(hwnd, None)
                continue
        except Exception:
            claims.pop(hwnd, None)
            continue
        if str(owner) not in alive_profiles:
            claims.pop(hwnd, None)


def get_exec_window_owner(controller, hwnd):
    cleanup_exec_window_claims(controller)
    try:
        h = int(hwnd)
    except Exception:
        return ""
    return str(controller._exec_window_claims.get(h, "") or "")


def claim_exec_window(controller, profile_id, hwnd):
    cleanup_exec_window_claims(controller)
    spid = str(profile_id)
    try:
        h = int(hwnd)
    except Exception:
        return False
    if h <= 0:
        return False
    owner = str(controller._exec_window_claims.get(h, "") or "")
    if owner and owner != spid:
        return False
    for key, value in list(controller._exec_window_claims.items()):
        if str(value) == spid and int(key) != h:
            controller._exec_window_claims.pop(key, None)
    controller._exec_window_claims[int(h)] = spid
    return True


def release_exec_window_claim(controller, profile_id=None, hwnd=None):
    cleanup_exec_window_claims(controller)
    if hwnd is not None:
        try:
            h = int(hwnd)
        except Exception:
            h = 0
        if h > 0:
            if profile_id is None:
                controller._exec_window_claims.pop(h, None)
            else:
                if str(controller._exec_window_claims.get(h, "") or "") == str(profile_id):
                    controller._exec_window_claims.pop(h, None)
        return
    if profile_id is None:
        return
    spid = str(profile_id)
    for key, value in list(controller._exec_window_claims.items()):
        if str(value) == spid:
            controller._exec_window_claims.pop(key, None)
