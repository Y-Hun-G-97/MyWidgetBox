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
            return 25 if fast else 60
        if key == "gif":
            return 15 if fast else 30
        return 5 if fast else 15
    if key == "video":
        return 40 if fast else 80
    if key == "gif":
        return 20 if fast else 50
    return 10 if fast else 20


def cancel_startup_queue(controller):
    if hasattr(controller, "_startup_queue_timer") and controller._startup_queue_timer.isActive():
        controller._startup_queue_timer.stop()
    controller._startup_queue = []
    controller._startup_queue_active = False
    controller._startup_queue_mode = "default"
    if hasattr(controller, "_start_deferred_playbacks"):
        try:
            controller._start_deferred_playbacks()
        except Exception:
            pass


def build_profile_startup_queue(controller, profile_ids):
    ordered = []
    media_priority_enabled = _as_bool(os.environ.get("MYCANVAS_STARTUP_MEDIA_PRIORITY", "1"), True)
    for order_idx, pid in enumerate(profile_ids):
        spid = str(pid)
        if not controller._profile_run_enabled(spid):
            continue
        name = QSettings("MyHomeApp", f"Profile_{spid}").value("name", "New 세팅")
        kind = controller._profile_startup_media_kind(spid)
        if media_priority_enabled:
            if kind == "video":
                priority = 2
            elif kind == "gif":
                priority = 1
            else:
                priority = 0
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
        if hasattr(controller, "_start_deferred_playbacks"):
            controller._start_deferred_playbacks()
        if hasattr(controller, "_sync_all_widget_video_viewports"):
            controller._sync_all_widget_video_viewports()
        if hasattr(controller, "_bootstrap_all_desktop_icon_overlays"):
            controller._bootstrap_all_desktop_icon_overlays()
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
        if hasattr(controller, "_start_deferred_playbacks"):
            controller._start_deferred_playbacks()
        if hasattr(controller, "_sync_all_widget_video_viewports"):
            controller._sync_all_widget_video_viewports()
        if hasattr(controller, "_bootstrap_all_desktop_icon_overlays"):
            controller._bootstrap_all_desktop_icon_overlays()
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
    in_startup_queue = bool(getattr(controller, "_startup_queue_active", False))
    if in_startup_queue and kind_key in ("video", "gif"):
        widget._deferred_playback_active = True
    widget._defer_initial_prepare_on_show = False
    try:
        widget.prepare_media_before_show()
    except Exception:
        pass
    controller.widgets[spid] = widget
    widget.show()
    if not in_startup_queue:
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
    if controller._gpu_guard_paused:
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
    if hasattr(controller, "_sync_temp_group_list_checkboxes"):
        controller._sync_temp_group_list_checkboxes()


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
    pass


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
        if new_layer != cur_layer:
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


def _linear_partition_indices(seq, k):
    """
    동적 계획법(DP)을 사용해 seq 시퀀스를 k개의 부분으로 균등 분할합니다.
    (각 분할 부분의 합 중 최댓값을 최소화하여 가장 균형 잡힌 행 배치를 생성)
    """
    n = len(seq)
    if n == 0 or k <= 0:
        return []
    if k >= n:
        return [[i] for i in range(n)]
    if k == 1:
        return [list(range(n))]

    table = [[0] * (k + 1) for _ in range(n + 1)]
    dividers = [[0] * (k + 1) for _ in range(n + 1)]
    prefix_sums = [0] * (n + 1)
    for i in range(n):
        prefix_sums[i + 1] = prefix_sums[i] + seq[i]

    for i in range(1, n + 1):
        table[i][1] = prefix_sums[i]
    for j in range(1, k + 1):
        table[1][j] = seq[0]

    for i in range(2, n + 1):
        for j in range(2, k + 1):
            min_max = float("inf")
            best_x = 1
            for x in range(1, i):
                cost = max(table[x][j - 1], prefix_sums[i] - prefix_sums[x])
                if cost < min_max:
                    min_max = cost
                    best_x = x
            table[i][j] = min_max
            dividers[i][j] = best_x

    ranges = []
    curr_n = n
    for curr_k in range(k, 1, -1):
        split_pt = dividers[curr_n][curr_k]
        ranges.insert(0, list(range(split_pt, curr_n)))
        curr_n = split_pt
    ranges.insert(0, list(range(0, curr_n)))
    return ranges


def _sub_layout_justified_rows(pairs, bounds, margin=10, weights=None):
    import math
    bx, by, bw, bh = bounds
    count = len(pairs)
    if count == 0:
        return []
    aspects = [max(0.2, min(5.0, float(p[1]))) for p in pairs]
    if weights and len(weights) == count:
        seq = [aspects[i] * max(0.4, min(2.5, float(weights[i]))) for i in range(count)]
    else:
        seq = aspects
    total_seq = max(0.1, sum(seq))
    ideal_rows = max(1, int(round(math.sqrt((float(bh) * total_seq) / float(bw)))))
    k_rows = min(count, ideal_rows)
    rows_data = _linear_partition_indices(seq, k_rows)

    is_small = [
        bool(weights and len(weights) == count and weights[i] <= 0.78 and 0.6 <= aspects[i] <= 1.6)
        for i in range(count)
    ]

    out = []
    raw_heights = []
    row_units = []

    for row_items in rows_data:
        units = []
        i = 0
        while i < len(row_items):
            itm = row_items[i]
            if is_small[itm] and i + 1 < len(row_items) and is_small[row_items[i + 1]]:
                units.append(('stack2', itm, row_items[i + 1]))
                i += 2
            else:
                units.append(('single', itm))
                i += 1
        row_units.append(units)

        sum_asp = 0.0
        for u in units:
            if u[0] == 'single':
                sum_asp += aspects[u[1]]
            else:
                asp_sub = max(aspects[u[1]], aspects[u[2]]) * 0.5
                sum_asp += asp_sub
        sum_asp = max(0.1, sum_asp)

        row_margin_total = (len(units) - 1) * margin
        row_avail_w = max(50, bw - row_margin_total)
        row_h = max(35, int(round(row_avail_w / sum_asp)))
        raw_heights.append(row_h)

    avail_h = max(50, bh - (len(rows_data) - 1) * margin)
    sum_raw_h = max(1, sum(raw_heights))
    scale_y = min(1.4, max(0.6, float(avail_h) / float(sum_raw_h)))
    final_heights = [max(35, int(round(h * scale_y))) for h in raw_heights]
    diff = avail_h - sum(final_heights)
    if final_heights:
        final_heights[-1] = max(35, final_heights[-1] + diff)

    cur_y = by
    for r_idx, units in enumerate(row_units):
        row_h = final_heights[r_idx]
        row_margin_total = (len(units) - 1) * margin
        row_avail_w = max(50, bw - row_margin_total)

        sum_asp = 0.0
        unit_asps = []
        for u in units:
            if u[0] == 'single':
                a = aspects[u[1]]
            else:
                a = max(aspects[u[1]], aspects[u[2]]) * 0.5
            unit_asps.append(a)
            sum_asp += a
        sum_asp = max(0.1, sum_asp)

        unit_widths = [max(35, int(round(row_avail_w * (a / sum_asp)))) for a in unit_asps]
        w_diff = row_avail_w - sum(unit_widths)
        if unit_widths:
            unit_widths[-1] = max(35, unit_widths[-1] + w_diff)

        cur_x = bx
        for u_idx, u in enumerate(units):
            uw = unit_widths[u_idx]
            if u[0] == 'single':
                orig_idx = pairs[u[1]][0]
                out.append((orig_idx, cur_x, cur_y, uw, row_h))
            else:
                orig_1 = pairs[u[1]][0]
                orig_2 = pairs[u[2]][0]
                sub_h = max(35, (row_h - margin) // 2)
                sub_h2 = max(35, row_h - sub_h - margin)
                out.append((orig_1, cur_x, cur_y, uw, sub_h))
                out.append((orig_2, cur_x, cur_y + sub_h + margin, uw, sub_h2))
            cur_x += uw + margin
        cur_y += row_h + margin
    return out


def _sub_layout_justified_cols(pairs, bounds, margin=10, weights=None):
    import math
    bx, by, bw, bh = bounds
    count = len(pairs)
    if count == 0:
        return []
    aspects = [max(0.2, min(5.0, float(p[1]))) for p in pairs]
    inv_aspects = [1.0 / a for a in aspects]
    if weights and len(weights) == count:
        seq = [inv_aspects[i] * max(0.4, min(2.5, float(weights[i]))) for i in range(count)]
    else:
        seq = inv_aspects
    total_inv = max(0.1, sum(seq))
    ideal_cols = max(1, int(round(math.sqrt((float(bw) * total_inv) / float(bh)))))
    k_cols = min(count, ideal_cols)
    cols_data = _linear_partition_indices(seq, k_cols)

    is_small = [
        bool(weights and len(weights) == count and weights[i] <= 0.78 and 0.6 <= aspects[i] <= 1.6)
        for i in range(count)
    ]

    out = []
    raw_widths = []
    col_units = []

    for col_items in cols_data:
        units = []
        i = 0
        while i < len(col_items):
            itm = col_items[i]
            if is_small[itm] and i + 1 < len(col_items) and is_small[col_items[i + 1]]:
                units.append(('pair_h', itm, col_items[i + 1]))
                i += 2
            else:
                units.append(('single', itm))
                i += 1
        col_units.append(units)

        sum_inv = 0.0
        for u in units:
            if u[0] == 'single':
                sum_inv += inv_aspects[u[1]]
            else:
                inv_sub = max(inv_aspects[u[1]], inv_aspects[u[2]]) * 0.5
                sum_inv += inv_sub
        sum_inv = max(0.1, sum_inv)

        col_margin_total = (len(units) - 1) * margin
        col_avail_h = max(50, bh - col_margin_total)
        col_w = max(35, int(round(col_avail_h / sum_inv)))
        raw_widths.append(col_w)

    avail_w = max(50, bw - (len(cols_data) - 1) * margin)
    sum_raw_w = max(1, sum(raw_widths))
    scale_x = min(1.4, max(0.6, float(avail_w) / float(sum_raw_w)))
    final_widths = [max(35, int(round(w * scale_x))) for w in raw_widths]
    diff_w = avail_w - sum(final_widths)
    if final_widths:
        final_widths[-1] = max(35, final_widths[-1] + diff_w)

    cur_x = bx
    for c_idx, units in enumerate(col_units):
        col_w = final_widths[c_idx]
        col_margin_total = (len(units) - 1) * margin
        col_avail_h = max(50, bh - col_margin_total)

        sum_inv = 0.0
        unit_invs = []
        for u in units:
            if u[0] == 'single':
                inv = inv_aspects[u[1]]
            else:
                inv = max(inv_aspects[u[1]], inv_aspects[u[2]]) * 0.5
            unit_invs.append(inv)
            sum_inv += inv
        sum_inv = max(0.1, sum_inv)

        unit_heights = [max(35, int(round(col_avail_h * (inv / sum_inv)))) for inv in unit_invs]
        h_diff = col_avail_h - sum(unit_heights)
        if unit_heights:
            unit_heights[-1] = max(35, unit_heights[-1] + h_diff)

        cur_y = by
        for u_idx, u in enumerate(units):
            uh = unit_heights[u_idx]
            if u[0] == 'single':
                orig_idx = pairs[u[1]][0]
                if is_small[u[1]]:
                    sub_w = max(35, (col_w - margin) // 2)
                    sub_h = max(35, int(round(sub_w * inv_aspects[u[1]])))
                    out.append((orig_idx, cur_x + (col_w - sub_w) // 2, cur_y + (uh - sub_h) // 2, sub_w, sub_h))
                else:
                    out.append((orig_idx, cur_x, cur_y, col_w, uh))
            else:
                orig_1 = pairs[u[1]][0]
                orig_2 = pairs[u[2]][0]
                sub_w = max(35, (col_w - margin) // 2)
                sub_w2 = max(35, col_w - sub_w - margin)
                out.append((orig_1, cur_x, cur_y, sub_w, uh))
                out.append((orig_2, cur_x + sub_w + margin, cur_y, sub_w2, uh))
            cur_y += uh + margin
        cur_x += col_w + margin
    return out


def calculate_spread_layout(
    item_paths,
    w=200,
    h=200,
    cols=2,
    rows=2,
    margin=10,
    fit_strategy="auto_aspect",
    spread_direction="top-left",
    start_x=None,
    start_y=None,
    screen_geo=None,
    **kwargs,
):
    """
    미디어 경로 목록과 스프레드 설정에 따라 각 위젯의 최적 (x, y, w, h) 좌표 목록을 반환.
    반환값: list of (pos_x, pos_y, item_w, item_h)
    """
    import math
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QCursor
    from mywidgetbox_core import get_media_native_size, get_screen_work_area, is_windows_taskbar_autohide

    item_paths = list(item_paths or [])
    count = len(item_paths)
    if count == 0:
        return []

    w = max(50, int(w))
    h = max(50, int(h))
    cols = max(1, int(cols))
    rows = max(1, int(rows))
    margin = max(0, int(margin))
    smart_weight = bool(kwargs.get("smart_weight", True))

    item_sizes = [get_media_native_size(p) if p else None for p in item_paths]
    areas = []
    for sz in item_sizes:
        if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
            areas.append(float(sz[0] * sz[1]))
        else:
            areas.append(2000000.0)

    sorted_areas = sorted(areas) if areas else []
    median_area = max(100000.0, sorted_areas[len(sorted_areas) // 2]) if sorted_areas else 2000000.0

    if smart_weight:
        weights = [max(0.5, min(2.2, (a / median_area) ** 0.28)) for a in areas]
    else:
        weights = [1.0] * count

    is_small = [
        bool(
            smart_weight
            and weights[i] <= 0.78
            and 0.65 <= (item_sizes[i][0] / max(1, item_sizes[i][1]) if item_sizes[i] and item_sizes[i][1] > 0 else 1.0) <= 1.45
        )
        for i in range(count)
    ]

    if not screen_geo:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        screen_geo = get_screen_work_area(screen) if screen else QRect(0, 0, 1920, 1080)

    S_w = max(400, screen_geo.width())
    S_h = max(300, screen_geo.height())

    is_fullscreen_strategy = fit_strategy in (
        "fullscreen_autofill", "mosaic_puzzle", "modular_tetris", "treemap_collage",
        "justified_rows", "justified_columns"
    )

    if is_fullscreen_strategy:
        start_x = screen_geo.left()
        start_y = screen_geo.top()
        spread_direction = "top-left"
    else:
        if start_x is None:
            total_w = cols * w + (cols - 1) * margin
            start_x = max(screen_geo.left() + 40, screen_geo.left() + (screen_geo.width() - total_w) // 2)
        if start_y is None:
            total_h = rows * h + (rows - 1) * margin
            start_y = max(screen_geo.top() + 40, screen_geo.top() + (screen_geo.height() - total_h) // 2)

    spread_direction = str(spread_direction or "top-left") if not is_fullscreen_strategy else "top-left"
    positions = [None] * count

    if fit_strategy == "auto_aspect":
        # 1. 아이템별 원본 비율 크기 및 열 Span 산출
        item_data = []
        for i, p in enumerate(item_paths):
            sz = item_sizes[i]
            if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
                aspect = sz[0] / max(1, sz[1])
            else:
                aspect = 1.0

            if aspect >= 1.55 and cols >= 2:
                span_cols = 2
                item_w = 2 * w + margin
                item_h = max(50, int(round(item_w / aspect)))
            else:
                span_cols = 1
                item_w = w
                item_h = max(50, int(round(w / aspect)))
            item_data.append((span_cols, item_w, item_h))

        # 2. 열별 누적 높이 추적 및 홀 필링 테트리스 배치
        col_xs = [0] * cols
        for c in range(cols):
            if "right" in spread_direction:
                col_xs[c] = start_x - (c * (w + margin)) - w
            else:
                col_xs[c] = start_x + (c * (w + margin))

        col_heights = [start_y] * cols
        unplaced = list(range(count))

        while unplaced:
            if "bottom" in spread_direction:
                best_c = max(range(cols), key=lambda c: col_heights[c])
                min_h = col_heights[best_c]
            else:
                best_c = min(range(cols), key=lambda c: col_heights[c])
                min_h = col_heights[best_c]

            # 스마트 가중치: 작은 SD/치비 짤 2개가 있으면 열 너비 안에 좌우 나란히(하프 블록) 배치
            if smart_weight and any(is_small):
                small_candidates = [i for i in unplaced if is_small[i]]
                if len(small_candidates) >= 2:
                    i1 = small_candidates[0]
                    i2 = small_candidates[1]
                    unplaced.remove(i1)
                    unplaced.remove(i2)

                    sub_w = max(35, (w - margin) // 2)
                    sub_w2 = max(35, w - sub_w - margin)
                    asp1 = item_sizes[i1][0] / max(1, item_sizes[i1][1]) if item_sizes[i1] and item_sizes[i1][1] > 0 else 1.0
                    asp2 = item_sizes[i2][0] / max(1, item_sizes[i2][1]) if item_sizes[i2] and item_sizes[i2][1] > 0 else 1.0
                    sub_h1 = max(35, int(round(sub_w / asp1)))
                    sub_h2 = max(35, int(round(sub_w2 / asp2)))
                    block_h = max(sub_h1, sub_h2)

                    if "bottom" in spread_direction:
                        pos_y1 = col_heights[best_c] - sub_h1
                        pos_y2 = col_heights[best_c] - sub_h2
                        col_heights[best_c] -= (block_h + margin)
                    else:
                        pos_y1 = col_heights[best_c]
                        pos_y2 = col_heights[best_c]
                        col_heights[best_c] += (block_h + margin)

                    if "right" in spread_direction:
                        pos_x1 = start_x - (best_c * (w + margin)) - sub_w
                        pos_x2 = pos_x1 - sub_w2 - margin
                    else:
                        pos_x1 = col_xs[best_c]
                        pos_x2 = col_xs[best_c] + sub_w + margin

                    positions[i1] = (pos_x1, pos_y1, sub_w, sub_h1)
                    positions[i2] = (pos_x2, pos_y2, sub_w2, sub_h2)
                    continue

            chosen_idx = None
            wide_candidates = [i for i in unplaced if item_data[i][0] == 2]
            single_candidates = [i for i in unplaced if item_data[i][0] == 1]

            chosen_pair_c = None
            if wide_candidates and cols >= 2:
                for c in range(cols - 1):
                    diff = abs(col_heights[c] - col_heights[c + 1])
                    if diff <= 30:
                        if "bottom" in spread_direction:
                            pair_top = min(col_heights[c], col_heights[c + 1])
                            if abs(pair_top - min_h) <= 40:
                                chosen_pair_c = c
                                break
                        else:
                            pair_top = max(col_heights[c], col_heights[c + 1])
                            if abs(pair_top - min_h) <= 40:
                                chosen_pair_c = c
                                break

            if chosen_pair_c is not None and wide_candidates:
                chosen_idx = wide_candidates[0]
                unplaced.remove(chosen_idx)
                span_cols, item_w, item_h = item_data[chosen_idx]
                c = chosen_pair_c
                if "bottom" in spread_direction:
                    target_y = min(col_heights[c], col_heights[c + 1])
                    pos_x = start_x - ((c + 1) * (w + margin)) if "right" in spread_direction else col_xs[c]
                    pos_y = target_y - item_h
                    new_y = pos_y - margin
                    col_heights[c] = new_y
                    col_heights[c + 1] = new_y
                else:
                    target_y = max(col_heights[c], col_heights[c + 1])
                    pos_x = start_x - ((c + 1) * (w + margin)) if "right" in spread_direction else col_xs[c]
                    pos_y = target_y
                    new_y = target_y + item_h + margin
                    col_heights[c] = new_y
                    col_heights[c + 1] = new_y
                positions[chosen_idx] = (pos_x, pos_y, item_w, item_h)
            else:
                chosen_idx = single_candidates[0] if single_candidates else unplaced[0]
                unplaced.remove(chosen_idx)
                span_cols, item_w, item_h = item_data[chosen_idx]

                if smart_weight and is_small and is_small[chosen_idx]:
                    sub_w = max(35, (w - margin) // 2)
                    asp = item_sizes[chosen_idx][0] / max(1, item_sizes[chosen_idx][1]) if item_sizes[chosen_idx] and item_sizes[chosen_idx][1] > 0 else 1.0
                    sub_h = max(35, int(round(sub_w / asp)))
                    item_w = sub_w
                    item_h = sub_h
                    offset_x = (w - item_w) // 2
                else:
                    offset_x = 0

                if span_cols == 1:
                    if "bottom" in spread_direction:
                        pos_x = (start_x - (best_c * (w + margin)) - w + offset_x) if "right" in spread_direction else (col_xs[best_c] + offset_x)
                        pos_y = col_heights[best_c] - item_h
                        col_heights[best_c] -= (item_h + margin)
                    else:
                        pos_x = (start_x - (best_c * (w + margin)) - w + offset_x) if "right" in spread_direction else (col_xs[best_c] + offset_x)
                        pos_y = col_heights[best_c]
                        col_heights[best_c] += (item_h + margin)
                else:
                    pair_c = min(best_c, cols - 2) if best_c < cols - 1 else max(0, cols - 2)
                    if "bottom" in spread_direction:
                        target_y = min(col_heights[pair_c], col_heights[pair_c + 1])
                        pos_x = start_x - ((pair_c + 1) * (w + margin)) if "right" in spread_direction else col_xs[pair_c]
                        pos_y = target_y - item_h
                        new_y = pos_y - margin
                        col_heights[pair_c] = new_y
                        col_heights[pair_c + 1] = new_y
                    else:
                        target_y = max(col_heights[pair_c], col_heights[pair_c + 1])
                        pos_x = start_x - ((pair_c + 1) * (w + margin)) if "right" in spread_direction else col_xs[pair_c]
                        pos_y = target_y
                        new_y = target_y + item_h + margin
                        col_heights[pair_c] = new_y
                        col_heights[pair_c + 1] = new_y
                positions[chosen_idx] = (pos_x, pos_y, item_w, item_h)

    elif fit_strategy == "grid_span":
        item_spans = []
        item_sizes = []
        for p in item_paths:
            span_x, span_y = 1, 1
            sz = get_media_native_size(p) if p else None
            if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
                aspect = sz[0] / max(1, sz[1])
                if aspect >= 1.45:
                    span_x = 2
                    span_y = 1
                elif aspect <= 0.68:
                    span_x = 1
                    span_y = 2
            span_x = min(span_x, cols)
            cur_w = span_x * w + (span_x - 1) * margin
            cur_h = span_y * h + (span_y - 1) * margin
            item_spans.append((span_x, span_y))
            item_sizes.append((cur_w, cur_h))

        grid_occupied = set()

        def is_cell_free(r, c, sx, sy):
            if c + sx > cols:
                return False
            for dr in range(sy):
                for dc in range(sx):
                    if (r + dr, c + dc) in grid_occupied:
                        return False
            return True

        def occupy_cells(r, c, sx, sy):
            for dr in range(sy):
                for dc in range(sx):
                    grid_occupied.add((r + dr, c + dc))

        for idx in range(count):
            sx, sy = item_spans[idx]
            iw, ih = item_sizes[idx]
            placed = False
            r = 0
            while not placed:
                for c in range(cols - sx + 1):
                    if is_cell_free(r, c, sx, sy):
                        occupy_cells(r, c, sx, sy)
                        pos_x = start_x - (c * (w + margin)) - iw if "right" in spread_direction else start_x + (c * (w + margin))
                        pos_y = start_y - (r * (h + margin)) - ih if "bottom" in spread_direction else start_y + (r * (h + margin))
                        positions[idx] = (pos_x, pos_y, iw, ih)
                        placed = True
                        break
                r += 1
    elif fit_strategy in ("fullscreen_autofill", "mosaic_puzzle", "modular_tetris", "treemap_collage"):
        # 🎨 다이나믹 퍼즐 콜라주 (대·중·소 블록이 맞물려 화면 전체 100% 빈틈없이 채움)
        import random
        aspect_screen = float(S_w) / float(max(1, S_h))

        aspects = []
        for p in item_paths:
            sz = get_media_native_size(p) if p else None
            asp = (sz[0] / max(1, sz[1])) if (sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0) else 1.0
            aspects.append(max(0.3, min(3.0, asp)))

        if count == 1:
            positions[0] = (start_x, start_y, S_w, S_h)
        else:
            rng = random.Random(42)

            # 1. 화면 비율 기반 최적 기본 격자 (R 행 x C 열) 산출
            ideal_R = max(1, int(round(math.sqrt(count / aspect_screen))))
            ideal_C = max(1, int(math.ceil(count / ideal_R)))
            target_cells = ideal_C * ideal_R
            while target_cells < count:
                ideal_C += 1
                target_cells = ideal_C * ideal_R

            R = ideal_R
            C = ideal_C

            # 기본 1x1 단위 블록 할당
            item_spans = [[1, 1] for _ in range(count)]
            diff = target_cells - count

            # 여유 칸이 있으면 원본 비율에 맞춰 2x2 대형 대표 짤, 2x1 가로 짤, 1x2 세로 짤로 승격
            if diff >= 3 and count >= 8 and R >= 2 and C >= 2:
                for idx in range(count):
                    if diff >= 3 and 0.85 <= aspects[idx] <= 1.15 and (not smart_weight or weights[idx] >= 0.9):
                        item_spans[idx] = [2, 2]
                        diff -= 3
                    if diff < 3:
                        break

            if diff >= 1 and C >= 2:
                for idx in range(count):
                    if diff >= 1 and aspects[idx] >= 1.4 and item_spans[idx] == [1, 1]:
                        item_spans[idx] = [2, 1]
                        diff -= 1
                    if diff == 0:
                        break

            if diff >= 1 and R >= 2:
                for idx in range(count):
                    if diff >= 1 and aspects[idx] <= 0.7 and item_spans[idx] == [1, 1]:
                        item_spans[idx] = [1, 2]
                        diff -= 1
                    if diff == 0:
                        break

            # 잔여 차이가 남아있다면 1x1을 2x1로 승격
            if diff > 0 and C >= 2:
                for idx in range(count):
                    if diff >= 1 and item_spans[idx] == [1, 1]:
                        item_spans[idx] = [2, 1]
                        diff -= 1
                    if diff == 0:
                        break

            unit_w = (S_w - (C - 1) * margin) // C
            unit_h = (S_h - (R - 1) * margin) // R
            rem_w = S_w - (C * unit_w + (C - 1) * margin)
            rem_h = S_h - (R * unit_h + (R - 1) * margin)

            col_widths = [unit_w + (1 if c < rem_w else 0) for c in range(C)]
            row_heights = [unit_h + (1 if r < rem_h else 0) for r in range(R)]

            col_xs = [0] * C
            for c in range(1, C):
                col_xs[c] = col_xs[c - 1] + col_widths[c - 1] + margin

            row_ys = [0] * R
            for r in range(1, R):
                row_ys[r] = row_ys[r - 1] + row_heights[r - 1] + margin

            grid = [[None] * C for _ in range(R)]

            def can_place(r, c, sx, sy):
                if r + sy > R or c + sx > C:
                    return False
                for dr in range(sy):
                    for dc in range(sx):
                        if grid[r + dr][c + dc] is not None:
                            return False
                return True

            def place(r, c, sx, sy, itm):
                for dr in range(sy):
                    for dc in range(sx):
                        grid[r + dr][c + dc] = itm

            hero_items = [i for i in range(count) if item_spans[i] == [2, 2]]
            wide_items = [i for i in range(count) if item_spans[i] in ([2, 1], [3, 1])]
            tall_items = [i for i in range(count) if item_spans[i] == [1, 2]]
            single_items = [i for i in range(count) if item_spans[i] == [1, 1]]

            # 2x2 대형 대표 짤을 화면 전체에 리듬감 있게 분산 배치
            candidate_hero_spots = []
            for r in range(0, R - 1, 2):
                for c in range(0, C - 1, 3):
                    candidate_hero_spots.append((r, c))
            rng.shuffle(candidate_hero_spots)

            for itm in hero_items:
                placed = False
                for r, c in candidate_hero_spots:
                    if can_place(r, c, 2, 2):
                        place(r, c, 2, 2, itm)
                        placed = True
                        break
                if not placed:
                    for r in range(R):
                        for c in range(C):
                            if can_place(r, c, 2, 2):
                                place(r, c, 2, 2, itm)
                                placed = True
                                break
                        if placed:
                            break
                if not placed:
                    item_spans[itm] = [1, 1]
                    single_items.append(itm)

            # 가로 2x1 짤 배치
            for itm in wide_items:
                sx, sy = item_spans[itm]
                placed = False
                for r in range(R):
                    for c in range(C):
                        if can_place(r, c, sx, sy):
                            place(r, c, sx, sy, itm)
                            placed = True
                            break
                    if placed:
                        break
                if not placed:
                    item_spans[itm] = [1, 1]
                    single_items.append(itm)

            # 세로 1x2 짤 배치
            for itm in tall_items:
                sx, sy = item_spans[itm]
                placed = False
                for r in range(R):
                    for c in range(C):
                        if can_place(r, c, sx, sy):
                            place(r, c, sx, sy, itm)
                            placed = True
                            break
                    if placed:
                        break
                if not placed:
                    item_spans[itm] = [1, 1]
                    single_items.append(itm)

            # 남은 모든 빈칸에 1x1 일반 짤 채우기 (빈틈 0% 보장)
            single_idx = 0
            for r in range(R):
                for c in range(C):
                    if grid[r][c] is None:
                        if single_idx < len(single_items):
                            itm = single_items[single_idx]
                            single_idx += 1
                            place(r, c, 1, 1, itm)
                        else:
                            if c > 0 and grid[r][c - 1] is not None:
                                grid[r][c] = grid[r][c - 1]
                            elif r > 0 and grid[r - 1][c] is not None:
                                grid[r][c] = grid[r - 1][c]

            # 최종 위치 (x, y, w, h) 변환
            for itm in range(count):
                placed_cells = [(r, c) for r in range(R) for c in range(C) if grid[r][c] == itm]
                if not placed_cells:
                    continue
                min_r = min(r for r, c in placed_cells)
                max_r = max(r for r, c in placed_cells)
                min_c = min(c for r, c in placed_cells)
                max_c = max(c for r, c in placed_cells)
                sx = max_c - min_c + 1
                sy = max_r - min_r + 1

                bx = start_x + col_xs[min_c]
                by = start_y + row_ys[min_r]
                bw = sum(col_widths[min_c + dc] for dc in range(sx)) + (sx - 1) * margin
                bh = sum(row_heights[min_r + dr] for dr in range(sy)) + (sy - 1) * margin
                positions[itm] = (bx, by, bw, bh)

    elif fit_strategy == "justified_rows":
        # 📏 가로 줄 맞춤 (단정한 앨범형, 행 단위 균등 분배)
        pairs = []
        for i, p in enumerate(item_paths):
            sz = item_sizes[i]
            asp = (sz[0] / max(1, sz[1])) if (sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0) else 1.0
            pairs.append((i, asp))
        for orig_i, x, y, iw, ih in _sub_layout_justified_rows(pairs, (start_x, start_y, S_w, S_h), margin, weights=weights if smart_weight else None):
            positions[orig_i] = (x, y, iw, ih)
    elif fit_strategy == "justified_columns":
        # 📐 세로 줄 맞춤 (열 단위 정돈, 세로 짤 돋보임)
        pairs = []
        for i, p in enumerate(item_paths):
            sz = item_sizes[i]
            asp = (sz[0] / max(1, sz[1])) if (sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0) else 1.0
            pairs.append((i, asp))
        for orig_i, x, y, iw, ih in _sub_layout_justified_cols(pairs, (start_x, start_y, S_w, S_h), margin, weights=weights if smart_weight else None):
            positions[orig_i] = (x, y, iw, ih)
    else:
        # 고정 격자 (crop_fill, fit_inside)
        for idx in range(count):
            c = idx % cols
            r = idx // cols
            pos_x = start_x - (c * (w + margin)) - w if "right" in spread_direction else start_x + (c * (w + margin))
            pos_y = start_y - (r * (h + margin)) - h if "bottom" in spread_direction else start_y + (r * (h + margin))
            positions[idx] = (pos_x, pos_y, w, h)

    # -------------------------------------------------------------
    # 1. 화면 높이/너비 맞춤 자동 압축 (Auto Scale-down)
    # 그림이 너무 많아 전체 배치 높이가 화면 높이를 넘치면,
    # 맨 아래 그림이 잘리지 않도록 화면 안에 100% 쏙 들어가게 정밀 축소합니다.
    # -------------------------------------------------------------
    valid_positions = [p for p in positions if p and len(p) == 4]
    if valid_positions and screen_geo:
        s_left = screen_geo.left()
        s_top = screen_geo.top()
        s_width = screen_geo.width()
        s_height = screen_geo.height()
        s_right = s_left + s_width
        s_bottom = s_top + s_height

        min_x = min(p[0] for p in valid_positions)
        max_x = max(p[0] + p[2] for p in valid_positions)
        min_y = min(p[1] for p in valid_positions)
        max_y = max(p[1] + p[3] for p in valid_positions)

        total_w = max_x - min_x
        total_h = max_y - min_y

        scale = 1.0
        if total_h > s_height:
            scale = min(scale, float(s_height) / float(total_h))
        if total_w > s_width:
            scale = min(scale, float(s_width) / float(total_w))

        if scale < 0.999:
            scaled_positions = []
            for p in positions:
                if not p or len(p) != 4:
                    scaled_positions.append(None)
                    continue
                px, py, pw, ph = p
                rel_x = px - min_x
                rel_y = py - min_y
                nw = max(35, int(round(pw * scale)))
                nh = max(35, int(round(ph * scale)))
                nx = int(round(min_x + rel_x * scale))
                ny = int(round(min_y + rel_y * scale))
                scaled_positions.append((nx, ny, nw, nh))
            positions = scaled_positions

            # 스케일 다운 후 바운딩 박스 재계산
            valid_positions = [p for p in positions if p and len(p) == 4]
            min_x = min(p[0] for p in valid_positions)
            max_x = max(p[0] + p[2] for p in valid_positions)
            min_y = min(p[1] for p in valid_positions)
            max_y = max(p[1] + p[3] for p in valid_positions)

        # -------------------------------------------------------------
        # 2. 화면 경계 이탈 방지 안전 클램핑 (Screen Safety Clamping)
        # -------------------------------------------------------------
        shift_x = 0
        shift_y = 0

        # 우측 경계 초과 시 화면 안으로 시프트
        if max_x > s_right:
            shift_x = s_right - max_x
        # 좌측 경계 초과 시 보정
        if min_x + shift_x < s_left:
            shift_x = s_left - min_x

        # 하단 경계 초과 시 화면 안으로 시프트
        if max_y > s_bottom:
            shift_y = s_bottom - max_y
        # 상단 경계 초과 시 보정
        if min_y + shift_y < s_top:
            shift_y = s_top - min_y

        if shift_x != 0 or shift_y != 0:
            positions = [
                (p[0] + shift_x, p[1] + shift_y, p[2], p[3]) if p else None
                for p in positions
            ]

    return positions
