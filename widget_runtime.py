import os

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QApplication, QMenu

from media_runtime import scan_media_paths


# --- Playlist and settings sync ---
def update_playlist(widget):
    folder = str(getattr(widget, "folder_path", "") or "").strip()
    if not folder or not os.path.isdir(folder):
        # Prevent stale media list when folder path is invalid/missing.
        widget.playlist = []
        return

    candidates = scan_media_paths(
        folder,
        widget._supported_media_extensions(),
    )
    if not candidates:
        widget.playlist = []
        return

    filtered = [path for path in candidates if path not in widget.quarantined_media]
    if filtered:
        widget.playlist = filtered
        return

    # If everything got quarantined, recover gracefully instead of staying empty forever.
    widget.quarantined_media.clear()
    widget._save_quarantined_media()
    widget.playlist = candidates


def set_watched_folder(widget, folder_path):
    old_files = widget.folder_watcher.files()
    if old_files:
        widget.folder_watcher.removePaths(old_files)
    old_dirs = widget.folder_watcher.directories()
    if old_dirs:
        widget.folder_watcher.removePaths(old_dirs)
    if folder_path and os.path.isdir(folder_path):
        widget.folder_watcher.addPath(folder_path)


def on_folder_changed_signal(widget, _path):
    widget.folder_refresh_timer.start()


def refresh_playlist_from_folder_change(widget):
    if not widget.folder_path:
        return

    prev_playlist = list(widget.playlist)
    current_path = None
    if 0 <= widget.current_idx < len(widget.playlist):
        current_path = widget.playlist[widget.current_idx]

    update_playlist(widget)
    set_watched_folder(widget, widget.folder_path)

    if not widget.playlist:
        if widget.stack.currentIndex() != 0:
            widget.current_idx = -1
            widget.next_media()
        return

    if current_path and current_path in widget.playlist:
        widget.current_idx = widget.playlist.index(current_path)
        widget._sync_current_media_cycle_policy()
        return

    if prev_playlist != widget.playlist:
        next_hint = 0
        if current_path and current_path in prev_playlist:
            removed_index = prev_playlist.index(current_path)
            next_hint = min(removed_index, len(widget.playlist) - 1)
        elif widget.current_idx >= 0:
            next_hint = min(widget.current_idx, len(widget.playlist) - 1)

        widget.current_idx = next_hint - 1
        widget.next_media()

def schedule_settings_sync(widget, delay_ms=None):
    if not hasattr(widget, "_settings_sync_timer"):
        return
    try:
        delay = int(widget._settings_sync_delay_ms if delay_ms is None else delay_ms)
    except Exception:
        delay = int(getattr(widget, "_settings_sync_delay_ms", 700))
    delay = max(0, delay)
    if delay <= 0:
        flush_settings_sync(widget)
        return
    widget._settings_sync_timer.start(delay)


def flush_settings_sync(widget):
    if hasattr(widget, "_settings_sync_timer") and widget._settings_sync_timer.isActive():
        widget._settings_sync_timer.stop()
    try:
        widget.settings.sync()
    except Exception:
        pass


def save_all_settings(widget, sync=None):
    settings = widget.settings
    settings.setValue("folder_path", widget.folder_path)
    settings.setValue("exec_path", widget.exec_path)
    settings.setValue("exec_manual_focus_enabled", bool(getattr(widget, "_exec_manual_focus_enabled", False)))
    settings.setValue("exec_manual_focus_proc_path", str(getattr(widget, "_exec_manual_focus_proc_path", "") or ""))
    settings.setValue("exec_manual_focus_proc_name", str(getattr(widget, "_exec_manual_focus_proc_name", "") or ""))
    settings.setValue("exec_manual_focus_title", str(getattr(widget, "_exec_manual_focus_title", "") or ""))
    settings.setValue("exec_manual_focus_class", str(getattr(widget, "_exec_manual_focus_class", "") or ""))
    settings.setValue("interval", widget.interval_ms // 1000)
    settings.setValue("bg_color_mode", widget.bg_color_mode)
    settings.setValue(
        "corner_mode",
        int(widget.coerce_corner_mode(getattr(widget, "corner_mode", widget.CORNER_ROUNDED))),
    )
    settings.setValue("media_fit_mode", int(getattr(widget, "media_fit_mode", 0)))
    settings.setValue("video_transition_mode", int(getattr(widget, "video_transition_mode", widget.VIDEO_TRANSITION_SINGLE)))
    settings.setValue("video_decode_mode", int(getattr(widget, "video_decode_mode", widget.VIDEO_DECODE_ORIGINAL)))
    settings.setValue("video_dual_fade_ms", int(getattr(widget, "_video_swap_fade_duration_ms", widget.VIDEO_DUAL_FADE_DEFAULT_MS)))
    settings.setValue("is_muted", bool(widget.is_muted))
    settings.setValue("gpu_guard_enabled", bool(widget.gpu_guard_enabled))
    settings.setValue("layer_mode", int(getattr(widget, "layer_mode", widget.LAYER_NORMAL)))
    settings.setValue("layer_schema_version", int(widget.LAYER_SCHEMA_VERSION))
    settings.setValue("is_locked", bool(getattr(widget, "is_locked", False)))
    settings.setValue("opacity_pct", widget.current_opacity_pct)
    settings.setValue("w", widget.width())
    settings.setValue("h", widget.height())
    settings.setValue("pos", widget._global_top_left())
    settings.setValue("size", widget.size())
    widget._save_position_metadata()
    widget._save_quarantined_media()

    if sync is True:
        flush_settings_sync(widget)
    elif sync is None:
        schedule_settings_sync(widget)

def build_settings_dialog_data(widget):
    return {
        "w": widget.width(),
        "h": widget.height(),
        "is_muted": widget.is_muted,
        "gpu_guard_enabled": widget.gpu_guard_enabled,
        "folder_path": widget.folder_path,
        "exec_path": widget.exec_path,
        "focus_binding_summary": widget.get_exec_manual_focus_summary(),
        "focus_binding_host": widget,
        "interval": widget.interval_ms // 1000,
        "bg_color_mode": widget.bg_color_mode,
        "corner_mode": widget.coerce_corner_mode(getattr(widget, "corner_mode", widget.CORNER_ROUNDED)),
        "media_fit_mode": int(getattr(widget, "media_fit_mode", 0)),
        "video_transition_mode": int(getattr(widget, "video_transition_mode", widget.VIDEO_TRANSITION_SINGLE)),
        "video_decode_mode": int(getattr(widget, "video_decode_mode", widget.VIDEO_DECODE_ORIGINAL)),
        "video_dual_fade_ms": int(getattr(widget, "_video_swap_fade_duration_ms", widget.VIDEO_DUAL_FADE_DEFAULT_MS)),
        "opacity_pct": widget.current_opacity_pct,
        "layer_mode": getattr(widget, "layer_mode", widget.LAYER_NORMAL),
        "layer_schema_version": int(widget.LAYER_SCHEMA_VERSION),
        "is_locked": getattr(widget, "is_locked", False),
    }


def apply_settings_dialog_result(widget, dialog, old_folder, old_exec):
    widget.resize(dialog.width_input.value(), dialog.height_input.value())
    widget.is_muted = dialog.mute_checkbox.isChecked()
    widget._apply_mute_state()
    widget.gpu_guard_enabled = dialog.gpu_guard_checkbox.isChecked()
    widget.exec_path = dialog.exec_path
    if widget._normalize_exec_path(old_exec) != widget._normalize_exec_path(widget.exec_path):
        widget._clear_bound_exec_window()
        widget._clear_manual_focus_binding(persist=False, clear_bound=False)
    widget.folder_path = str(dialog.folder_path or "").strip()
    source_changed = old_folder != widget.folder_path
    widget._set_watched_folder(widget.folder_path)
    widget.interval_ms = dialog.sec_input.value() * 1000
    widget.bg_color_mode = dialog.bg_combo.currentIndex()
    widget.corner_mode = widget.coerce_corner_mode(dialog.corner_combo.currentIndex())
    widget.media_fit_mode = int(dialog.media_mode_combo.currentIndex())
    widget.video_transition_mode = widget.coerce_video_transition_mode(
        dialog.video_transition_combo.currentIndex()
    )
    widget.video_decode_mode = widget.coerce_video_decode_mode(
        dialog.video_decode_combo.currentIndex()
    )
    widget._video_swap_fade_duration_ms = widget.coerce_video_dual_fade_ms(
        dialog.video_dual_fade_ms_spin.value()
    )
    widget.apply_window_settings(dialog.layer_combo.currentIndex(), dialog.lock_cb.isChecked())
    widget.apply_mask_and_style()
    widget._sync_current_media_cycle_policy()

    if source_changed:
        widget.update_playlist()
        widget.current_idx = -1
        widget.next_media()
    else:
        widget._apply_media_scale_mode()

    widget.current_opacity_pct = dialog.opacity_slider.value()
    widget.setWindowOpacity(widget.current_opacity_pct / 100.0)
    if not widget.gpu_guard_enabled:
        widget.set_performance_paused(False, reason="guard_disabled")
    widget.save_all_settings()

# --- Media playback and video events ---
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


def next_media(widget, prefer_preload=True):
    # 1. existing timer/playback stop to avoid overlap
    widget._media_resetting = True
    widget.timer.stop()
    widget._clear_active_gif_loop_watch()
    widget._cancel_pending_gif_swap()
    widget._media_resetting = False

    if not widget.playlist:
        widget._stop_all_video_players(clear_source=True)
        if widget.movie:
            widget.movie.stop()
            widget.movie.deleteLater()
            widget.movie = None
        widget.current_static_pixmap = None
        widget.current_media_path = None
        widget.stack.setCurrentIndex(0)
        widget._refresh_icon_overlay_for_current_media()
        return

    attempts = len(widget.playlist)
    while attempts > 0 and widget.playlist:
        # 2. advance index
        next_idx = (widget.current_idx + 1) % len(widget.playlist)
        source_path = str(widget.playlist[next_idx] or "")

        if bool(prefer_preload) and widget._try_start_dual_video_preload(source_path):
            widget.current_idx = int(next_idx)
            widget.current_media_path = source_path
            widget._refresh_icon_overlay_for_current_media()
            if widget._performance_paused:
                widget.set_performance_paused(True, reason="guard_active", force=True)
            return

        widget._stop_all_video_players(clear_source=True)
        if widget.movie:
            widget.movie.stop()
            widget.movie.deleteLater()
            widget.movie = None
        widget.current_static_pixmap = None
        widget.current_media_path = None
        widget.current_idx = int(next_idx)
        runtime_path = str(source_path)
        runtime_is_video = widget._is_video_path(runtime_path)
        widget.current_media_path = runtime_path

        # 3. branch by extension
        if runtime_is_video:
            widget._set_video_active_slot(int(getattr(widget, "_video_active_slot", 0)))
            widget._play_video_path_on_active_player(runtime_path)
            return

        if widget._is_gif_path(runtime_path):
            if not widget._start_gif_direct(runtime_path):
                widget._record_media_failure(source_path, "invalid_gif")
                if source_path in widget.quarantined_media:
                    widget.playlist.pop(widget.current_idx)
                    widget.current_idx -= 1
                attempts -= 1
                continue
            widget._refresh_icon_overlay_for_current_media()
            return

        widget.stack.setCurrentIndex(1)
        pix = QPixmap(runtime_path)
        if pix.isNull():
            widget._record_media_failure(source_path, "invalid_image")
            if source_path in widget.quarantined_media:
                widget.playlist.pop(widget.current_idx)
                widget.current_idx -= 1
            attempts -= 1
            continue

        widget.current_static_pixmap = pix
        update_static_pixmap_size(widget)
        if widget._is_single_media_mode_active():
            if widget.timer.isActive():
                widget.timer.stop()
        else:
            widget.timer.start(widget.interval_ms)
        widget._refresh_icon_overlay_for_current_media()
        return

    widget.current_media_path = None
    widget.stack.setCurrentIndex(0)
    widget._refresh_icon_overlay_for_current_media()


def update_static_pixmap_size(widget):
    if widget.current_static_pixmap and not widget.current_static_pixmap.isNull():
        target = widget._safe_target_size(getattr(widget, "img_label", None), widget.size())
        fill_mode = widget._is_media_fill_mode()
        expand_mode = getattr(
            Qt.AspectRatioMode,
            "KeepAspectRatioByExpanding",
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        if fill_mode:
            scaled = widget.current_static_pixmap.scaled(
                target,
                expand_mode,
                Qt.TransformationMode.SmoothTransformation,
            )
            if int(scaled.width()) > int(target.width()) or int(scaled.height()) > int(target.height()):
                cut_w = min(int(target.width()), int(scaled.width()))
                cut_h = min(int(target.height()), int(scaled.height()))
                cut_x = max(0, (int(scaled.width()) - int(cut_w)) // 2)
                cut_y = max(0, (int(scaled.height()) - int(cut_h)) // 2)
                scaled = scaled.copy(int(cut_x), int(cut_y), int(cut_w), int(cut_h))
        else:
            scaled = widget.current_static_pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        widget.img_label.setPixmap(scaled)

from PyQt6.QtMultimedia import QMediaPlayer


def check_video_status(widget, s, player=None):
    src_player = player if isinstance(player, QMediaPlayer) else widget.sender()
    if isinstance(src_player, QMediaPlayer):
        pending_slot = int(getattr(widget, "_video_dual_pending_slot", -1))
        if pending_slot >= 0:
            pending_player = widget._video_player_for_slot(pending_slot)
            if src_player is pending_player:
                if s == QMediaPlayer.MediaStatus.InvalidMedia:
                    widget._video_dbg(
                        "pending_invalid_status",
                        seq=int(getattr(widget, "_video_dual_pending_seq", 0)),
                        pending_media=widget._debug_media_name(getattr(widget, "_video_dual_pending_path", "")),
                    )
                    widget._fallback_from_dual_pending("pending_invalid_media")
                return
        if src_player is not widget.media_player:
            return
    if widget._media_resetting:
        return
    if s in (
        QMediaPlayer.MediaStatus.LoadedMedia,
        QMediaPlayer.MediaStatus.BufferingMedia,
        QMediaPlayer.MediaStatus.BufferedMedia,
    ):
        widget._apply_mute_state()
        return
    if s == QMediaPlayer.MediaStatus.EndOfMedia:
        if int(getattr(widget, "_video_dual_pending_slot", -1)) >= 0:
            widget._video_dbg(
                "active_end",
                seq=int(getattr(widget, "_video_dual_pending_seq", 0)),
                pending_ready=bool(getattr(widget, "_video_dual_pending_ready", False)),
                frame_ready=bool(getattr(widget, "_video_dual_pending_frame_ready", False)),
                pending_frozen=bool(getattr(widget, "_video_dual_pending_frozen", False)),
                current=widget._debug_media_name(getattr(widget, "current_media_path", "")),
            )
            if widget._is_dual_pending_swap_ready():
                if widget._swap_to_dual_pending():
                    return
            widget._video_dual_waiting_for_swap = True
            if hasattr(widget, "_video_dual_end_wait_timer"):
                widget._video_dual_end_wait_timer.start()
            return
        if widget._is_single_media_mode_active() and widget._is_native_video_infinite_loop_active():
            try:
                widget.media_player.play()
            except Exception:
                pass
            return
        if widget._restart_current_video_loop():
            return
        widget.next_media()
        return
    if s == QMediaPlayer.MediaStatus.InvalidMedia:
        widget._skip_current_media("invalid_video_status")


def on_video_error(widget, error, error_string, player=None):
    src_player = player if isinstance(player, QMediaPlayer) else widget.sender()
    if isinstance(src_player, QMediaPlayer):
        pending_slot = int(getattr(widget, "_video_dual_pending_slot", -1))
        if pending_slot >= 0:
            pending_player = widget._video_player_for_slot(pending_slot)
            if src_player is pending_player:
                widget._video_dbg(
                    "pending_error",
                    seq=int(getattr(widget, "_video_dual_pending_seq", 0)),
                    error=str(error_string or error),
                    pending_media=widget._debug_media_name(getattr(widget, "_video_dual_pending_path", "")),
                )
                widget._fallback_from_dual_pending(f"pending_error:{error_string or error}")
                return
        if src_player is not widget.media_player:
            return
    if widget._media_resetting:
        return
    if error == QMediaPlayer.Error.NoError:
        return
    reason = error_string if error_string else str(error)
    widget._video_dbg(
        "active_error",
        error=reason,
        current=widget._debug_media_name(getattr(widget, "current_media_path", "")),
    )
    widget._skip_current_media(f"video_error:{reason}")


def on_video_position_changed(widget, position_ms, player=None):
    src_player = player if isinstance(player, QMediaPlayer) else widget.sender()
    if not isinstance(src_player, QMediaPlayer):
        return
    pending_slot = int(getattr(widget, "_video_dual_pending_slot", -1))
    if pending_slot >= 0:
        pending_player = widget._video_player_for_slot(pending_slot)
        if src_player is pending_player:
            try:
                pos = int(position_ms)
            except Exception:
                pos = -1
            if pos > 0:
                widget._video_dual_pending_ready = True
                # Preload watchdog is only for "no progress" cases.
                if hasattr(widget, "_video_dual_preload_timer") and widget._video_dual_preload_timer.isActive():
                    widget._video_dual_preload_timer.stop()
                if bool(getattr(widget, "_video_dual_waiting_for_swap", False)) and widget._is_dual_pending_swap_ready():
                    widget._video_dbg(
                        "pending_ready_during_wait",
                        seq=int(getattr(widget, "_video_dual_pending_seq", 0)),
                        pos_ms=int(pos),
                        pending_media=widget._debug_media_name(getattr(widget, "_video_dual_pending_path", "")),
                    )
                    widget._video_dual_waiting_for_swap = False
                    if hasattr(widget, "_video_dual_end_wait_timer") and widget._video_dual_end_wait_timer.isActive():
                        widget._video_dual_end_wait_timer.stop()
                    widget._swap_to_dual_pending()
            return
    if src_player is not widget.media_player:
        return
    if widget._media_resetting:
        return
    if int(widget.stack.currentIndex()) != 2:
        return
    if int(getattr(widget, "_video_dual_pending_slot", -1)) >= 0:
        return
    if not widget._is_dual_video_transition_enabled():
        return
    if bool(getattr(widget, "_performance_paused", False)):
        return
    current_path = str(getattr(widget, "current_media_path", "") or "")
    if not widget._is_video_path(current_path):
        return
    try:
        pos = int(position_ms)
    except Exception:
        pos = -1
    if pos < 0:
        return
    try:
        duration = int(src_player.duration())
    except Exception:
        duration = 0
    if duration <= 0:
        return
    remain_ms = int(duration - pos)
    if remain_ms > int(widget._dual_preload_lookahead_ms(duration)):
        return
    current_key = widget._normalize_exec_path(current_path)
    if current_key and current_key == str(getattr(widget, "_video_dual_preload_triggered_for_path", "")):
        return
    next_idx, next_path = widget._next_playlist_entry()
    if next_idx < 0 or not next_path:
        return
    if not widget._is_video_path(next_path):
        return
    if widget._normalize_exec_path(next_path) == widget._normalize_exec_path(current_path):
        return
    if widget._try_start_dual_video_preload(next_path):
        widget._video_dual_preload_triggered_for_path = current_key
        widget.current_idx = int(next_idx)
        widget.current_media_path = next_path
        widget._refresh_icon_overlay_for_current_media()
        widget._video_dbg(
            "lookahead_trigger",
            seq=int(getattr(widget, "_video_dual_pending_seq", 0)),
            remain_ms=int(remain_ms),
            duration_ms=int(duration),
            from_media=widget._debug_media_name(current_path),
            to_media=widget._debug_media_name(next_path),
        )
        if widget._performance_paused:
            widget.set_performance_paused(True, reason="guard_active", force=True)


def on_video_frame_changed(widget, frame, slot=-1):
    pending_slot = int(getattr(widget, "_video_dual_pending_slot", -1))
    if pending_slot < 0:
        return
    if int(slot) != int(pending_slot):
        return
    is_valid = False
    try:
        is_valid = bool(frame.isValid())
    except Exception:
        is_valid = frame is not None
    if not is_valid:
        return
    widget._video_dual_pending_frame_ready = True
    widget._video_dual_pending_ready = True
    if hasattr(widget, "_video_dual_preload_timer") and widget._video_dual_preload_timer.isActive():
        widget._video_dual_preload_timer.stop()
    if not bool(getattr(widget, "_video_dual_pending_frozen", False)):
        pending_player = widget._video_player_for_slot(pending_slot)
        if isinstance(pending_player, QMediaPlayer):
            try:
                pending_player.pause()
                widget._video_dual_pending_frozen = True
                widget._video_dbg(
                    "pending_frame_ready",
                    seq=int(getattr(widget, "_video_dual_pending_seq", 0)),
                    slot=int(pending_slot),
                    pending_media=widget._debug_media_name(getattr(widget, "_video_dual_pending_path", "")),
                )
            except Exception:
                widget._video_dual_pending_frozen = False
    if bool(getattr(widget, "_video_dual_waiting_for_swap", False)) and widget._is_dual_pending_swap_ready():
        widget._video_dual_waiting_for_swap = False
        if hasattr(widget, "_video_dual_end_wait_timer") and widget._video_dual_end_wait_timer.isActive():
            widget._video_dual_end_wait_timer.stop()
        widget._swap_to_dual_pending()

# --- Input and lifecycle events ---
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu


def mouse_press_event(widget, e):
    if e.button() == Qt.MouseButton.LeftButton:
        if bool(getattr(widget, "is_locked", False)):
            widget.cancel_active_interaction()
            return
        widget._reset_axis_snap()
        local_pos = e.position().toPoint() if hasattr(e, "position") else widget.mapFromGlobal(e.globalPosition().toPoint())
        if widget._is_shift_down() and not getattr(widget, "is_locked", False):
            corner = widget._corner_hit_test(local_pos)
            if corner:
                widget.is_resizing = True
                widget.resize_corner = corner
                widget.resize_start_pos = e.globalPosition().toPoint()
                widget.resize_start_geo = widget.geometry()
                widget.start_pos = None
                widget.is_moving = False
                widget._set_resize_cursor(corner)
                widget._show_size_hud()
                widget._refresh_resize_ui()
                return
        widget.start_pos = e.globalPosition().toPoint()
        widget.is_moving = False


def mouse_move_event(widget, e):
    if bool(getattr(widget, "is_locked", False)):
        if widget.start_pos or widget.is_moving or widget.is_resizing:
            widget.cancel_active_interaction()
        else:
            widget._refresh_resize_ui()
        return
    if widget.is_resizing:
        widget._apply_corner_resize(e.globalPosition().toPoint())
        widget._show_size_hud()
        return

    widget._refresh_resize_ui()
    if widget.start_pos:
        current_global = e.globalPosition().toPoint()
        delta = current_global - widget.start_pos
        if delta.manhattanLength() > widget._drag_threshold:
            if not widget.is_moving:
                widget._set_drag_topmost(True)
            widget.is_moving = True
            prev_x = widget.x()
            prev_y = widget.y()
            raw_x = widget.x() + delta.x()
            raw_y = widget.y() + delta.y()
            snap_x = widget._apply_axis_snap("x", raw_x, current_global.x())
            snap_y = widget._apply_axis_snap("y", raw_y, current_global.y())
            widget._move_exact((snap_x, snap_y))
            moved_dx = widget.x() - prev_x
            moved_dy = widget.y() - prev_y
            if moved_dx or moved_dy:
                if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "move_temp_group_by_delta"):
                    widget.manager.move_temp_group_by_delta(widget.profile_id, moved_dx, moved_dy)
            widget._show_size_hud()
            widget.start_pos = current_global


def mouse_release_event(widget, e):
    if e.button() == Qt.MouseButton.LeftButton:
        if bool(getattr(widget, "is_locked", False)):
            widget.cancel_active_interaction()
            return
        if widget.is_resizing:
            widget.is_resizing = False
            widget.resize_corner = None
            widget.resize_start_pos = None
            widget._reset_axis_snap()
            widget.save_all_settings()
            if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "save_temp_group_positions"):
                widget.manager.save_temp_group_positions(widget.profile_id)
            widget._hide_size_hud()
            widget._refresh_resize_ui()
            return
        if getattr(widget, "is_moving", False):
            widget.save_all_settings()
            if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "save_temp_group_positions"):
                widget.manager.save_temp_group_positions(widget.profile_id)
            widget._hide_size_hud()
        else:
            has_manual_focus = bool(getattr(widget, "_exec_manual_focus_enabled", False))
            has_exec_target = bool(widget.exec_path and os.path.exists(widget.exec_path))
            if not has_exec_target and not has_manual_focus:
                widget.start_pos = None
                widget.is_moving = False
                widget._set_drag_topmost(False)
                widget._reset_axis_snap()
                widget._hide_size_hud()
                widget._refresh_resize_ui()
                return
            widget._launch_or_focus_exec(widget.exec_path)
    widget._set_drag_topmost(False)
    widget.start_pos = None
    widget.is_moving = False
    widget._reset_axis_snap()
    widget._hide_size_hud()
    widget._refresh_resize_ui()


def wheel_event(widget, e):
    if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
        wheel_delta = e.angleDelta().y()
        steps = int(wheel_delta / 120) if wheel_delta else 0
        if steps == 0 and wheel_delta != 0:
            steps = 1 if wheel_delta > 0 else -1
        if steps != 0:
            if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "adjust_temp_group_opacity"):
                widget.manager.adjust_temp_group_opacity(widget.profile_id, steps * 5)
            else:
                new_opacity = max(10, min(100, widget.current_opacity_pct + (steps * 5)))
                if new_opacity != widget.current_opacity_pct:
                    widget.current_opacity_pct = new_opacity
                    widget.setWindowOpacity(widget.current_opacity_pct / 100.0)
                    widget.save_all_settings()
        return

    if not widget.playlist:
        return

    if e.angleDelta().y() > 0:
        widget.current_idx = (widget.current_idx - 2) % len(widget.playlist)

    widget.next_media(prefer_preload=False)


def drag_enter_event(widget, event):
    path = widget._extract_first_local_drop_path(event)
    if path and (os.path.isdir(path) or os.path.isfile(path)):
        event.acceptProposedAction()
    else:
        event.ignore()


def drag_move_event(widget, event):
    path = widget._extract_first_local_drop_path(event)
    if path and (os.path.isdir(path) or os.path.isfile(path)):
        event.acceptProposedAction()
    else:
        event.ignore()


def drag_leave_event(_widget, event):
    event.accept()


def drop_event(widget, event):
    path = widget._extract_first_local_drop_path(event)
    if widget._apply_drop_target(path):
        event.acceptProposedAction()
    else:
        event.ignore()


def context_menu_event(widget, e):
    menu = QMenu(widget)
    menu.setStyleSheet("QMenu { background-color: #333; color: white; border: 1px solid #555; } QMenu::item:selected { background-color: #555; }")
    action_settings = menu.addAction("위젯 설정")
    action_settings.triggered.connect(widget.open_settings)
    action_master = menu.addAction("위젯 컨트롤러")
    action_master.triggered.connect(widget.open_master_controller)
    menu.exec(e.globalPos())


def open_master_controller(widget):
    if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "show_master_window"):
        widget.manager.show_master_window()

from PyQt6.QtCore import QTimer
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QApplication


def prepare_first_show(widget):
    if not bool(getattr(widget, "_initial_media_prepared", False)):
        if bool(getattr(widget, "_defer_initial_prepare_on_show", False)):
            widget._defer_initial_prepare_on_show = False
            QTimer.singleShot(0, widget.prepare_media_before_show)
        else:
            widget.prepare_media_before_show()


def handle_post_show(widget):
    widget._sync_video_viewport_update_mode()
    # Hidden pre-warm can still use a stale child size on some starts.
    # Re-apply once visible so static image size matches final widget geometry.
    widget._apply_media_scale_mode()
    if widget._should_clone_desktop_icons() or widget._should_punch_desktop_icons():
        widget.apply_mask_and_style()
        widget._schedule_desktop_icon_overlay_bootstrap(retries=4, delay_ms=60)


def handle_resize(widget):
    if hasattr(widget, "desktop_icon_clone_overlay"):
        widget.desktop_icon_clone_overlay.setGeometry(widget.rect())
        if widget.desktop_icon_clone_overlay.isVisible():
            widget.desktop_icon_clone_overlay.raise_()
    if hasattr(widget, "selection_overlay"):
        widget.selection_overlay.setGeometry(widget.rect())
        widget.selection_overlay.raise_()
    if hasattr(widget, "resize_overlay"):
        widget.resize_overlay.setGeometry(widget.rect())
        if widget.resize_overlay.isVisible():
            widget.resize_overlay.raise_()
    if hasattr(widget, "group_badge"):
        widget._place_group_badge()
        if widget.group_badge.isVisible():
            widget.group_badge.raise_()
    if hasattr(widget, "size_hud") and widget.size_hud.isVisible():
        widget._refresh_size_hud()
    if hasattr(widget, "action_hud") and widget.action_hud.isVisible():
        widget._refresh_action_hud()

    widget._apply_media_scale_mode()
    widget.apply_mask_and_style()
    widget._refresh_resize_ui()
    widget._refresh_group_badge()


def handle_move(widget):
    if widget._should_clone_desktop_icons() or widget._should_punch_desktop_icons():
        widget.apply_mask_and_style()


def prepare_close(widget):
    widget.timer.stop()
    widget._clear_active_gif_loop_watch()
    widget._cancel_pending_gif_swap()
    widget._cancel_video_crossfade()
    widget._cancel_video_dual_pending(clear_source=True)
    widget._stop_exec_launch_learning()
    widget._clear_bound_exec_window()
    widget._stop_all_video_players(clear_source=True)

    if isinstance(getattr(widget, "_video_primary_player", None), QMediaPlayer):
        widget._video_primary_player.deleteLater()
    if isinstance(getattr(widget, "_video_secondary_player", None), QMediaPlayer):
        widget._video_secondary_player.deleteLater()
    widget.audio_output.deleteLater()
    if widget.movie:
        widget.movie.stop()
        widget.movie.deleteLater()

    if hasattr(widget, "folder_refresh_timer"):
        widget.folder_refresh_timer.stop()
    if hasattr(widget, "folder_watcher"):
        old_dirs = widget.folder_watcher.directories()
        if old_dirs:
            widget.folder_watcher.removePaths(old_dirs)
        old_files = widget.folder_watcher.files()
        if old_files:
            widget.folder_watcher.removePaths(old_files)
    app = QApplication.instance()
    if app:
        app.removeEventFilter(widget)
    if hasattr(widget, "_desktop_icon_mask_timer") and widget._desktop_icon_mask_timer.isActive():
        widget._desktop_icon_mask_timer.stop()
    if hasattr(widget, "_desktop_icon_bootstrap_timer") and widget._desktop_icon_bootstrap_timer.isActive():
        widget._desktop_icon_bootstrap_timer.stop()
    widget._set_clone_overlay_items([])
    if hasattr(widget, "_settings_sync_timer") and widget._settings_sync_timer.isActive():
        widget._settings_sync_timer.stop()

    skip_sync = bool(getattr(widget.manager, "_bulk_set_switch_active", False))
    widget.save_all_settings(sync=(not skip_sync))
