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

    if not screen_geo:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        screen_geo = get_screen_work_area(screen) if screen else QRect(0, 0, 1920, 1080)

    S_w = max(400, screen_geo.width())
    S_h = max(300, screen_geo.height())

    is_fullscreen_strategy = fit_strategy in (
        "fullscreen_autofill", "modular_tetris", "treemap_collage", "justified_rows"
    )

    if is_fullscreen_strategy:
        start_x = screen_geo.left()
        start_y = screen_geo.top()
        spread_direction = "top-left"

    if fit_strategy == "fullscreen_autofill":
        sum_area_factor = 0.0
        for p in item_paths:
            sz = get_media_native_size(p) if p else None
            if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
                aspect = sz[0] / max(1, sz[1])
            else:
                aspect = 1.0
            span = 2 if aspect >= 1.55 else 1
            sum_area_factor += (span * span) / max(0.2, aspect)

        w_ideal = math.sqrt((S_w * S_h) / max(1.0, sum_area_factor))
        cols = max(2, int(round(S_w / max(50.0, w_ideal + margin))))
        w = max(50, int((S_w - (cols - 1) * margin) / cols))
        h = w
    elif not is_fullscreen_strategy:
        if start_x is None:
            total_w = cols * w + (cols - 1) * margin
            start_x = max(screen_geo.left() + 40, screen_geo.left() + (screen_geo.width() - total_w) // 2)
        if start_y is None:
            total_h = rows * h + (rows - 1) * margin
            start_y = max(screen_geo.top() + 40, screen_geo.top() + (screen_geo.height() - total_h) // 2)

    spread_direction = str(spread_direction or "top-left") if not is_fullscreen_strategy else "top-left"
    positions = [None] * count

    if fit_strategy in ("auto_aspect", "fullscreen_autofill"):
        # 1. 아이템별 원본 비율 크기 및 열 Span 산출
        item_data = []
        for p in item_paths:
            sz = get_media_native_size(p) if p else None
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

                if span_cols == 1:
                    if "bottom" in spread_direction:
                        pos_x = start_x - (best_c * (w + margin)) - item_w if "right" in spread_direction else col_xs[best_c]
                        pos_y = col_heights[best_c] - item_h
                        col_heights[best_c] -= (item_h + margin)
                    else:
                        pos_x = start_x - (best_c * (w + margin)) - item_w if "right" in spread_direction else col_xs[best_c]
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

        # 전체화면 꽉 채움 모드: 바닥 빈 공간 수직 밀착 스냅 보정
        if fit_strategy == "fullscreen_autofill":
            screen_bottom = screen_geo.top() + S_h
            for c in range(cols):
                # 해당 열에 위치한 위젯들 중 가장 아래쪽에 있는 위젯 찾기
                col_widgets = []
                for idx, pos in enumerate(positions):
                    if pos and abs(pos[0] - col_xs[c]) < 10:
                        col_widgets.append((idx, pos))
                if col_widgets:
                    bottom_idx, bottom_pos = max(col_widgets, key=lambda it: it[1][1] + it[1][3])
                    diff_bottom = screen_bottom - (bottom_pos[1] + bottom_pos[3])
                    if 0 < diff_bottom <= 120:  # 바닥 틈이 미세하게 남았을 때 완벽 밀착!
                        positions[bottom_idx] = (
                            bottom_pos[0],
                            bottom_pos[1],
                            bottom_pos[2],
                            bottom_pos[3] + diff_bottom,
                        )

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
    elif fit_strategy == "modular_tetris":
        # 🎮 테트리스 모듈러 (대·중·소 블록이 어우러져 사각형 100% 빈틈없이 채움)
        item_spans = []
        for idx, p in enumerate(item_paths):
            span_x, span_y = 1, 1
            sz = get_media_native_size(p) if p else None
            aspect = (sz[0] / max(1, sz[1])) if (sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0) else 1.0
            if aspect >= 1.45:
                span_x, span_y = 2, 1
            elif aspect <= 0.68:
                span_x, span_y = 1, 2
            elif 0.82 <= aspect <= 1.25 and (idx % 6 == 1) and count >= 10:
                # 약 15~20% 비율로 2x2 대형 블록 생성 (리듬감 부여)
                span_x, span_y = 2, 2
            item_spans.append((span_x, span_y))

        total_cells = sum(sx * sy for sx, sy in item_spans)
        aspect_ratio = float(S_w) / float(S_h)
        tetris_cols = max(3, int(round(math.sqrt(total_cells * aspect_ratio))))
        tetris_rows = max(2, int(math.ceil(total_cells / float(tetris_cols))))

        unit_w = max(35, int((S_w - (tetris_cols - 1) * margin) / tetris_cols))
        unit_h = max(35, int((S_h - (tetris_rows - 1) * margin) / tetris_rows))

        grid_occupied = set()

        def is_free(r, c, sx, sy):
            if c + sx > tetris_cols:
                return False
            for dr in range(sy):
                for dc in range(sx):
                    if (r + dr, c + dc) in grid_occupied:
                        return False
            return True

        def mark_occ(r, c, sx, sy):
            for dr in range(sy):
                for dc in range(sx):
                    grid_occupied.add((r + dr, c + dc))

        unplaced = list(range(count))
        while unplaced:
            first_empty = None
            max_r = max((r for r, c in grid_occupied), default=-1) + 2
            for r in range(max(tetris_rows, max_r + 2)):
                for c in range(tetris_cols):
                    if (r, c) not in grid_occupied:
                        first_empty = (r, c)
                        break
                if first_empty:
                    break
            if not first_empty:
                break
            er, ec = first_empty

            chosen_item = None
            for cand in unplaced:
                sx, sy = item_spans[cand]
                if is_free(er, ec, sx, sy):
                    chosen_item = cand
                    break

            if chosen_item is None:
                chosen_item = unplaced[0]
                item_spans[chosen_item] = (1, 1)

            unplaced.remove(chosen_item)
            sx, sy = item_spans[chosen_item]
            mark_occ(er, ec, sx, sy)
            pos_x = start_x + ec * (unit_w + margin)
            pos_y = start_y + er * (unit_h + margin)
            item_w = sx * unit_w + (sx - 1) * margin
            item_h = sy * unit_h + (sy - 1) * margin
            positions[chosen_item] = (pos_x, pos_y, item_w, item_h)

    elif fit_strategy == "treemap_collage":
        # 🗺️ 갤러리 트리맵 콜라주 (화면 전체 100% 무드보드 재귀 분할)
        weights = []
        for p in item_paths:
            sz = get_media_native_size(p) if p else None
            aspect = (sz[0] / max(1, sz[1])) if (sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0) else 1.0
            w_factor = 1.5 if (aspect >= 1.5 or aspect <= 0.65) else 1.0
            weights.append(w_factor)

        def split_treemap(item_indices, rx, ry, rw, rh):
            if not item_indices:
                return
            if len(item_indices) == 1:
                idx = item_indices[0]
                positions[idx] = (rx, ry, max(35, rw), max(35, rh))
                return

            total_weight = sum(weights[i] for i in item_indices)
            half = total_weight / 2.0
            acc = 0.0
            split_idx = 1
            for i, itm in enumerate(item_indices[:-1]):
                acc += weights[itm]
                if acc >= half:
                    split_idx = i + 1
                    break

            left_items = item_indices[:split_idx]
            right_items = item_indices[split_idx:]
            left_w = sum(weights[i] for i in left_items)

            if rw >= rh:
                cut = int(round(rw * (left_w / max(0.1, total_weight))))
                cut = max(35, min(rw - 35, cut))
                half_m = margin // 2
                split_treemap(left_items, rx, ry, cut - half_m, rh)
                split_treemap(right_items, rx + cut + half_m, ry, rw - cut - half_m, rh)
            else:
                cut = int(round(rh * (left_w / max(0.1, total_weight))))
                cut = max(35, min(rh - 35, cut))
                half_m = margin // 2
                split_treemap(left_items, rx, ry, rw, cut - half_m)
                split_treemap(right_items, rx, ry + cut + half_m, rw, rh - cut - half_m)

        split_treemap(list(range(count)), start_x, start_y, S_w, S_h)

    elif fit_strategy == "justified_rows":
        # 📸 사진첩 행 정돈 (구글 포토 스타일, 가로 행 높이 동적 조절)
        aspects = []
        for p in item_paths:
            sz = get_media_native_size(p) if p else None
            asp = (sz[0] / max(1, sz[1])) if (sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0) else 1.0
            aspects.append(max(0.3, min(3.0, asp)))

        ideal_rows = max(2, int(round(math.sqrt(count / max(0.5, float(S_w) / float(S_h))))))
        target_row_h = max(50, int((S_h - (ideal_rows - 1) * margin) / ideal_rows))

        rows_data = []
        cur_row = []
        cur_width = 0
        for i in range(count):
            asp = aspects[i]
            est_w = target_row_h * asp
            cur_row.append(i)
            cur_width += est_w + margin
            if cur_width >= S_w * 0.90 and len(cur_row) >= 2:
                rows_data.append(cur_row)
                cur_row = []
                cur_width = 0
        if cur_row:
            rows_data.append(cur_row)

        cur_y = start_y
        for r_idx, row_items in enumerate(rows_data):
            sum_asp = sum(aspects[i] for i in row_items)
            row_margin_total = (len(row_items) - 1) * margin
            row_avail_w = S_w - row_margin_total
            row_h = max(40, int(round(row_avail_w / max(0.1, sum_asp))))

            cur_x = start_x
            for c_idx, itm in enumerate(row_items):
                if c_idx == len(row_items) - 1:
                    itm_w = (start_x + S_w) - cur_x
                else:
                    itm_w = max(35, int(round(row_h * aspects[itm])))
                positions[itm] = (cur_x, cur_y, itm_w, row_h)
                cur_x += itm_w + margin
            cur_y += row_h + margin
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

        # -------------------------------------------------------------
        # 3. 전체화면 모드인 경우 하단 수직 밀착 (Vertical Bottom Snap)
        # -------------------------------------------------------------
        if fit_strategy == "fullscreen_autofill":
            col_bottom_items = {}
            for idx, p in enumerate(positions):
                if not p:
                    continue
                px, py, pw, ph = p
                c_key = int(round((px - s_left) / max(1, pw)))
                item_bottom = py + ph
                if c_key not in col_bottom_items or item_bottom > col_bottom_items[c_key][1]:
                    col_bottom_items[c_key] = (idx, item_bottom, py, ph)

            for c_key, (b_idx, item_bottom, py, ph) in col_bottom_items.items():
                diff_bottom = s_bottom - item_bottom
                if 0 < diff_bottom <= 60:
                    px, py, pw, ph = positions[b_idx]
                    positions[b_idx] = (px, py, pw, ph + diff_bottom)

    return positions
