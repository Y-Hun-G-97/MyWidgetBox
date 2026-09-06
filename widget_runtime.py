import os
import time

from PyQt6.QtCore import QSettings, QTimer, Qt
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

    selected_items = []
    for raw in list(getattr(widget, "folder_item_paths", []) or []):
        p = str(raw or "").strip()
        if p and os.path.isfile(p):
            selected_items.append(os.path.normpath(p))
    if selected_items:
        media_ext = tuple(widget._supported_media_extensions())
        candidates = [
            path for path in selected_items
            if str(path).lower().endswith(media_ext)
            and os.path.normcase(os.path.dirname(path)) == os.path.normcase(os.path.normpath(folder))
        ]
        filtered_selected = [path for path in candidates if path not in widget.quarantined_media]
        if filtered_selected:
            widget.playlist = filtered_selected
            return
        # 선택된 파일들이 모두 손상/격리된 경우 루프 방지
        now_ts = time.monotonic()
        last_reset = float(getattr(widget, "_quarantine_last_reset_ts", 0.0) or 0.0)
        if now_ts - last_reset < 15.0:
            widget.playlist = []
            return
        widget._quarantine_last_reset_ts = now_ts
        widget.quarantined_media.clear()
        widget._save_quarantined_media()
        widget.playlist = candidates
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

    # If everything got quarantined, recover with cooldown guard to prevent endless crash loops.
    now_ts = time.monotonic()
    last_reset = float(getattr(widget, "_quarantine_last_reset_ts", 0.0) or 0.0)
    if now_ts - last_reset < 15.0:
        widget.playlist = []
        return
    widget._quarantine_last_reset_ts = now_ts
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
    if bool(getattr(widget, "_suppress_pos_save", False)):
        return
    settings = widget.settings
    settings.setValue("folder_path", widget.folder_path)
    settings.setValue("folder_item_paths", list(getattr(widget, "folder_item_paths", []) or []))
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
    settings.setValue("keep_aspect_ratio", bool(getattr(widget, "keep_aspect_ratio", True)))
    settings.setValue("auto_fit_slide_media", bool(getattr(widget, "auto_fit_slide_media", False)))
    settings.setValue("growth_anchor", str(getattr(widget, "growth_anchor", "top-left") or "top-left"))
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
    p_name = str(getattr(widget, "profile_name", "") or "")
    if not p_name and hasattr(widget, "profile_id"):
        try:
            p_name = str(QSettings("MyHomeApp", f"Profile_{widget.profile_id}").value("name", f"위젯 {widget.profile_id}"))
        except Exception:
            p_name = f"위젯 {widget.profile_id}"
    return {
        "name": p_name,
        "w": widget.width(),
        "h": widget.height(),
        "keep_aspect_ratio": bool(getattr(widget, "keep_aspect_ratio", True)),
        "auto_fit_slide_media": bool(getattr(widget, "auto_fit_slide_media", False)),
        "growth_anchor": str(getattr(widget, "growth_anchor", "top-left") or "top-left"),
        "is_muted": widget.is_muted,
        "gpu_guard_enabled": widget.gpu_guard_enabled,
        "folder_path": widget.folder_path,
        "folder_item_paths": list(getattr(widget, "folder_item_paths", []) or []),
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



def resize_widget_with_anchor(widget, new_w, new_h, anchor=None):
    if anchor is None:
        anchor = str(getattr(widget, "growth_anchor", "top-left") or "top-left")

    old_w = int(widget.width())
    old_h = int(widget.height())
    new_w = max(24, int(new_w))
    new_h = max(24, int(new_h))

    dw = new_w - old_w
    dh = new_h - old_h

    if dw == 0 and dh == 0:
        return

    old_pos = widget.pos()
    old_x, old_y = old_pos.x(), old_pos.y()

    dx = 0
    dy = 0

    # Horizontal delta
    if anchor in ("top-center", "bottom-center", "center"):
        dx = -int(round(dw / 2.0))
    elif anchor in ("top-right", "right-center", "bottom-right"):
        dx = -dw

    # Vertical delta
    if anchor in ("left-center", "center", "right-center"):
        dy = -int(round(dh / 2.0))
    elif anchor in ("bottom-left", "bottom-center", "bottom-right"):
        dy = -dh

    widget.resize(new_w, new_h)
    if dx != 0 or dy != 0:
        new_x = old_x + dx
        new_y = old_y + dy
        widget.move(new_x, new_y)
        if hasattr(widget, "_save_position"):
            widget._save_position()


def apply_settings_dialog_result(widget, dialog, old_folder, old_exec):
    w_val = dialog.width_input.value()
    h_val = dialog.height_input.value()
    widget.base_slide_w = w_val
    widget.base_slide_h = h_val
    anchor_val = dialog.anchor_picker.current_anchor() if hasattr(dialog, "anchor_picker") else "top-left"
    widget.growth_anchor = anchor_val
    resize_widget_with_anchor(widget, w_val, h_val, anchor=anchor_val)
    widget.keep_aspect_ratio = bool(getattr(dialog, "keep_aspect_ratio_cb", None) and dialog.keep_aspect_ratio_cb.isChecked())
    widget.auto_fit_slide_media = bool(getattr(dialog, "slide_auto_aspect_cb", None) and dialog.slide_auto_aspect_cb.isChecked())
    widget.is_muted = dialog.mute_checkbox.isChecked()
    widget._apply_mute_state()
    widget.gpu_guard_enabled = dialog.gpu_guard_checkbox.isChecked()
    widget.exec_path = dialog.exec_path
    if widget._normalize_exec_path(old_exec) != widget._normalize_exec_path(widget.exec_path):
        widget._clear_bound_exec_window()
        widget._clear_manual_focus_binding(persist=False, clear_bound=False)
    old_folder_item_paths = list(getattr(widget, "folder_item_paths", []) or [])
    widget.folder_path = str(dialog.folder_path or "").strip()
    widget.folder_item_paths = list(getattr(dialog, "folder_item_paths", []) or [])
    source_changed = old_folder != widget.folder_path or old_folder_item_paths != widget.folder_item_paths
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


def _apply_slide_auto_aspect_if_enabled(widget, media_path):
    if not getattr(widget, "auto_fit_slide_media", False):
        return
    if bool(getattr(widget, "is_moving", False)) or bool(getattr(widget, "is_resizing", False)) or getattr(widget, "start_pos", None) is not None:
        return
    if not media_path or not os.path.isfile(media_path):
        return
    try:
        from mywidgetbox_core import calc_smart_aspect_size, get_media_native_size
        sz = get_media_native_size(media_path)
        if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
            iw, ih = sz[0], sz[1]
            base_w = getattr(widget, "base_slide_w", widget.width())
            base_h = getattr(widget, "base_slide_h", widget.height())
            target_w, target_h = calc_smart_aspect_size(iw, ih, base_w, base_h)
            if widget.width() != target_w or widget.height() != target_h:
                resize_widget_with_anchor(widget, target_w, target_h)
                if hasattr(widget, "apply_mask_and_style"):
                    widget.apply_mask_and_style()
    except Exception:
        pass


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
            _apply_slide_auto_aspect_if_enabled(widget, source_path)
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

        _apply_slide_auto_aspect_if_enabled(widget, runtime_path)

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
        # Ctrl + 좌클릭 시: 영역 드래그 다중 선택(Box Select) 시작
        if bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier) or (hasattr(widget, "_is_ctrl_down") and widget._is_ctrl_down()):
            if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "start_marquee_selection"):
                widget.cancel_active_interaction()
                widget.manager.start_marquee_selection(e.globalPosition().toPoint())
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


def _is_left_button_down(event):
    buttons = Qt.MouseButton.NoButton
    if event is not None and hasattr(event, "buttons"):
        try:
            buttons = event.buttons()
        except Exception:
            buttons = Qt.MouseButton.NoButton
    if buttons == Qt.MouseButton.NoButton:
        try:
            buttons = QApplication.mouseButtons()
        except Exception:
            buttons = Qt.MouseButton.NoButton
    return bool(buttons & Qt.MouseButton.LeftButton)


def _drag_start_threshold(widget):
    threshold = max(1, int(getattr(widget, "_drag_threshold", 5)))
    try:
        threshold = max(threshold, int(QApplication.startDragDistance()))
    except Exception:
        pass
    return int(threshold)


def mouse_move_event(widget, e):
    if not _is_left_button_down(e):
        if (
            widget.start_pos is not None
            or bool(getattr(widget, "is_moving", False))
            or bool(getattr(widget, "is_resizing", False))
        ):
            widget.cancel_active_interaction()
        else:
            widget._refresh_resize_ui()
        return

    if bool(getattr(widget, "is_locked", False)):
        if widget.start_pos is not None or widget.is_moving or widget.is_resizing:
            widget.cancel_active_interaction()
        else:
            widget._refresh_resize_ui()
        return
    if widget.is_resizing:
        widget._apply_corner_resize(e.globalPosition().toPoint())
        widget._show_size_hud()
        return

    widget._refresh_resize_ui()
    if widget.start_pos is not None:
        current_global = e.globalPosition().toPoint()
        delta = current_global - widget.start_pos
        if delta.manhattanLength() >= _drag_start_threshold(widget):
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
            if has_exec_target or has_manual_focus:
                widget._launch_or_focus_exec(widget.exec_path)
    widget._set_drag_topmost(False)
    widget.start_pos = None
    widget.is_moving = False
    widget._reset_axis_snap()
    widget._hide_size_hud()
    widget._refresh_resize_ui()


def _is_alt_pressed(e):
    if bool(e.modifiers() & Qt.KeyboardModifier.AltModifier):
        return True
    try:
        import win32api, win32con
        if bool(win32api.GetAsyncKeyState(win32con.VK_MENU) & 0x8000):
            return True
        if bool(win32api.GetAsyncKeyState(win32con.VK_LMENU) & 0x8000):
            return True
        if bool(win32api.GetAsyncKeyState(win32con.VK_RMENU) & 0x8000):
            return True
    except Exception:
        pass
    return False


def _is_ctrl_pressed(e):
    if bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier):
        return True
    try:
        import win32api, win32con
        if bool(win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000):
            return True
        if bool(win32api.GetAsyncKeyState(win32con.VK_LCONTROL) & 0x8000):
            return True
        if bool(win32api.GetAsyncKeyState(win32con.VK_RCONTROL) & 0x8000):
            return True
    except Exception:
        pass
    return False


def wheel_event(widget, e):
    wheel_delta = e.angleDelta().y()
    if wheel_delta == 0:
        wheel_delta = e.angleDelta().x()

    steps = int(wheel_delta / 120) if wheel_delta else 0
    if steps == 0 and wheel_delta != 0:
        steps = 1 if wheel_delta > 0 else -1

    if _is_ctrl_pressed(e):
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

    if _is_alt_pressed(e):
        if steps != 0:
            if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "adjust_temp_group_layer"):
                widget.manager.adjust_temp_group_layer(widget.profile_id, steps)
            else:
                cur_layer = int(getattr(widget, "layer_mode", 1))
                new_layer = max(0, min(2, cur_layer + steps))
                layer_names = {0: "배경 (최하단)", 1: "일반 (기본)", 2: "최상위 (항상 위)"}
                if new_layer != cur_layer:
                    widget.layer_mode = new_layer
                    widget.apply_window_settings(new_layer, widget.is_locked)
                    widget.save_all_settings()
                if hasattr(widget, "_show_action_hud"):
                    name = layer_names.get(new_layer, str(new_layer))
                    widget._show_action_hud(f"레이어: {name}")
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


def fit_to_screen(widget, include_taskbar=False):
    screen = QApplication.screenAt(widget.geometry().center())
    if not screen:
        screen = QApplication.primaryScreen()
    if not screen:
        return

    from mywidgetbox_core import get_screen_work_area
    geo = get_screen_work_area(screen, force_full=include_taskbar)

    sw = max(100, int(geo.width()))
    sh = max(100, int(geo.height()))

    iw, ih = 0, 0
    p = widget.get_current_media_path() if hasattr(widget, "get_current_media_path") else ""
    if p and os.path.isfile(p):
        from mywidgetbox_core import get_media_native_size
        sz = get_media_native_size(p)
        if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
            iw, ih = sz[0], sz[1]

    keep_aspect = bool(getattr(widget, "keep_aspect_ratio", True))
    if keep_aspect:
        if iw <= 0 or ih <= 0:
            iw = max(1, widget.width())
            ih = max(1, widget.height())

        scale = min(float(sw) / float(iw), float(sh) / float(ih))
        target_w = max(50, min(5000, int(round(iw * scale))))
        target_h = max(50, min(5000, int(round(ih * scale))))

        pos_x = geo.left() + (sw - target_w) // 2
        pos_y = geo.top() + (sh - target_h) // 2
    else:
        # 비율 맞춤 해제: 종횡비 무시하고 화면 전체를 100% 꽉 채움
        target_w = sw
        target_h = sh
        pos_x = geo.left()
        pos_y = geo.top()

    cur_geo = widget.geometry()
    is_already_fit = (
        abs(cur_geo.width() - target_w) <= 2
        and abs(cur_geo.height() - target_h) <= 2
        and abs(cur_geo.x() - pos_x) <= 2
        and abs(cur_geo.y() - pos_y) <= 2
    )

    if is_already_fit and hasattr(widget, "_prev_restore_geo") and widget._prev_restore_geo:
        prev = widget._prev_restore_geo
        widget._prev_restore_geo = None
        widget.setGeometry(prev)
    else:
        widget._prev_restore_geo = cur_geo
        widget.setGeometry(pos_x, pos_y, target_w, target_h)

    widget.save_all_settings()
    widget.apply_mask_and_style()
    if hasattr(widget, "_show_size_hud"):
        widget._show_size_hud()


def snap_fill_available_space(widget):
    cur_geo = widget.geometry()
    screens = QApplication.screens()
    best_screen = None
    best_intersect_area = -1
    for s in screens:
        inter = s.geometry().intersected(cur_geo)
        area = inter.width() * inter.height()
        if area > best_intersect_area:
            best_intersect_area = area
            best_screen = s

    if not best_screen:
        best_screen = QApplication.screenAt(cur_geo.center()) or QApplication.primaryScreen()
    if not best_screen:
        return

    from mywidgetbox_core import get_screen_work_area
    screen_geo = get_screen_work_area(best_screen)

    # 1. 위젯 시작 위치가 화면 밖으로 벗어난 경우 화면 내로 안전 보정
    wx = max(screen_geo.left(), min(screen_geo.right() - 50, cur_geo.x()))
    wy = max(screen_geo.top(), min(screen_geo.bottom() - 50, cur_geo.y()))
    ww, wh = cur_geo.width(), cur_geo.height()
    if wx != cur_geo.x() or wy != cur_geo.y():
        widget.move(wx, wy)

    other_geos = []
    if hasattr(widget, "manager") and widget.manager and hasattr(widget.manager, "widgets"):
        for pid, w_obj in widget.manager.widgets.items():
            if w_obj != widget and hasattr(w_obj, "isVisible") and w_obj.isVisible():
                other_geos.append(w_obj.geometry())

    max_right = screen_geo.right() + 1
    for og in other_geos:
        if max(wy, og.top()) < min(wy + wh, og.bottom() + 1):
            if og.left() >= wx + ww - 2:
                if og.left() < max_right:
                    max_right = og.left()

    max_bottom = screen_geo.bottom() + 1
    for og in other_geos:
        if max(wx, og.left()) < min(wx + ww, og.right() + 1):
            if og.top() >= wy + wh - 2:
                if og.top() < max_bottom:
                    max_bottom = og.top()

    # 화면 경계 초과 방지 상한선 클램핑
    avail_w = max(50, min(screen_geo.width(), max_right - wx))
    avail_h = max(50, min(screen_geo.height(), max_bottom - wy))

    keep_aspect = bool(getattr(widget, "keep_aspect_ratio", True))
    if keep_aspect:
        iw, ih = 0, 0
        p = widget.get_current_media_path() if hasattr(widget, "get_current_media_path") else ""
        if p and os.path.isfile(p):
            from mywidgetbox_core import get_media_native_size
            sz = get_media_native_size(p)
            if sz and len(sz) == 2 and sz[0] > 0 and sz[1] > 0:
                iw, ih = sz[0], sz[1]

        if iw <= 0 or ih <= 0:
            iw = max(1, ww)
            ih = max(1, wh)

        scale = min(float(avail_w) / float(iw), float(avail_h) / float(ih))
        new_w = max(50, min(avail_w, int(round(iw * scale))))
        new_h = max(50, min(avail_h, int(round(ih * scale))))
    else:
        new_w = max(50, min(avail_w, avail_w))
        new_h = max(50, min(avail_h, avail_h))

    widget.resize(new_w, new_h)
    widget.save_all_settings()
    widget.apply_mask_and_style()
    if hasattr(widget, "_show_size_hud"):
        widget._show_size_hud()


def context_menu_event(widget, e):
    from mywidgetbox_core import render_vector_icon
    menu = QMenu(widget)
    menu.setStyleSheet("""
        QMenu {
            background-color: #162438;
            color: #edf3ff;
            border: 1px solid #334d73;
            border-radius: 8px;
            padding: 4px;
        }
        QMenu::item {
            padding: 6px 14px 6px 10px;
            border-radius: 5px;
            font-size: 12px;
            font-weight: 600;
        }
        QMenu::item:selected {
            background-color: #2b456a;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background: #2a3d59;
            margin: 4px 6px;
        }
    """)

    act_fit = menu.addAction(render_vector_icon("screen", "#7da5dc", 14), "화면 크기 맞춤")
    act_fit.triggered.connect(lambda: fit_to_screen(widget, include_taskbar=False))

    act_snap = menu.addAction(render_vector_icon("widget", "#92bbf8", 14), "인접 빈 공간 밀착 채우기")
    act_snap.triggered.connect(lambda: snap_fill_available_space(widget))

    menu.addSeparator()

    action_settings = menu.addAction(render_vector_icon("settings", "#93c5fd", 14), "위젯 상세 설정")
    action_settings.triggered.connect(widget.open_settings)
    action_master = menu.addAction(render_vector_icon("list", "#cddbf0", 14), "위젯 컨트롤러")
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
    if not bool(getattr(widget, "_suppress_pos_save", False)):
        widget.save_all_settings(sync=(not skip_sync))
