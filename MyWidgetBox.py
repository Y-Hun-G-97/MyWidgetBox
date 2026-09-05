# -*- coding: utf-8 -*-
import sys
import os
import json
import math
import time
import hashlib
import shutil
import subprocess
import threading
from collections import deque

import ctypes
from ctypes import wintypes
import win32api
import win32gui
import win32con
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtMultimedia import *
try:
    from PyQt6.QtMultimediaWidgets import QVideoWidget, QGraphicsVideoItem
except Exception:
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    QGraphicsVideoItem = None

from mywidgetbox_core import (
    GpuUsageSampler,
    _as_bool,
    _get_win32com_client,
    _get_win32ui,
    calc_smart_aspect_size,
    get_media_native_size,
    apply_windows_dark_title_bar,
    render_vector_icon,
    ask_dark_confirm,
)
from desktop_icons import (
    DesktopIconCloneOverlay,
    build_desktop_caption_path_map,
    desktop_icon_render_signature_of_rects,
    fetch_desktop_shell_items,
    is_recycle_caption,
    query_desktop_icon_rects_screen,
    resolve_desktop_listview_hwnd,
)
from media_runtime import (
    VideoProxyService,
    find_ffprobe_beside_ffmpeg,
    find_runtime_binary,
    probe_video_height,
    runtime_binary_dirs,
)
from mywidgetbox_ui_primitives import (
    ElidedLabel,
    MarqueeSelectionOverlay,
    OverlayWidget,
    ProfileListWidget,
    ProfileRowWidget,
    ResizeHandleOverlay,
    SetNameLabel,
    TreeBranchLine,
)
from set_manager_dialog import SetManagerDialog
from settings_dialog import (
    FolderLayoutChoiceDialog,
    FolderSlideDialog,
    FolderSpreadDialog,
    SettingsDialog,
    bind_settings_dialog_desktop_widget as _bind_settings_dialog_desktop_widget,
)
from widget_runtime import (
    apply_settings_dialog_result as _apply_settings_dialog_result_impl,
    build_settings_dialog_data as _build_settings_dialog_data_impl,
    check_video_status as _check_video_status_impl,
    context_menu_event as _context_menu_event_impl,
    drag_enter_event as _drag_enter_event_impl,
    drag_leave_event as _drag_leave_event_impl,
    drag_move_event as _drag_move_event_impl,
    drop_event as _drop_event_impl,
    fit_to_screen as _fit_to_screen_impl,
    flush_settings_sync as _flush_settings_sync_impl,
    handle_move as _handle_move_impl,
    handle_post_show as _handle_post_show_impl,
    handle_resize as _handle_resize_impl,
    mouse_move_event as _mouse_move_event_impl,
    mouse_press_event as _mouse_press_event_impl,
    mouse_release_event as _mouse_release_event_impl,
    next_media as _next_media_impl,
    on_folder_changed_signal as _on_folder_changed_signal_impl,
    on_video_error as _on_video_error_impl,
    on_video_frame_changed as _on_video_frame_changed_impl,
    on_video_position_changed as _on_video_position_changed_impl,
    open_master_controller as _open_master_controller_impl,
    prepare_close as _prepare_close_impl,
    prepare_first_show as _prepare_first_show_impl,
    refresh_playlist_from_folder_change as _refresh_playlist_from_folder_change_impl,
    save_all_settings as _save_all_settings_impl,
    schedule_settings_sync as _schedule_settings_sync_impl,
    set_watched_folder as _set_watched_folder_impl,
    snap_fill_available_space as _snap_fill_available_space_impl,
    update_playlist as _update_playlist_impl,
    update_static_pixmap_size as _update_static_pixmap_size_impl,
    wheel_event as _wheel_event_impl,
)
from master_runtime import (
    apply_gpu_guard_thresholds as _mc_apply_gpu_guard_thresholds_impl,
    ensure_windows_startup_shortcut as _mc_ensure_windows_startup_shortcut_impl,
    fast_set_switch_enabled as _mc_fast_set_switch_enabled_impl,
    fast_startup_enabled as _mc_fast_startup_enabled_impl,
    flush_master_settings_sync as _mc_flush_master_settings_sync_impl,
    frozen_executable_path as _mc_frozen_executable_path_impl,
    minimal_validation_enabled as _mc_minimal_validation_enabled_impl,
    on_gpu_threshold_inputs_changed as _mc_on_gpu_threshold_inputs_changed_impl,
    on_startup_shortcut_toggled as _mc_on_startup_shortcut_toggled_impl,
    remove_windows_startup_shortcut as _mc_remove_windows_startup_shortcut_impl,
    resolve_app_icon as _mc_resolve_app_icon_impl,
    schedule_master_settings_sync as _mc_schedule_master_settings_sync_impl,
    set_startup_shortcut_enabled as _mc_set_startup_shortcut_enabled_impl,
    startup_shortcut_enabled as _mc_startup_shortcut_enabled_impl,
    startup_shortcut_icon_path as _mc_startup_shortcut_icon_path_impl,
    startup_shortcut_path as _mc_startup_shortcut_path_impl,
    startup_shortcut_pref_key as _mc_startup_shortcut_pref_key_impl,
    sync_gpu_threshold_inputs as _mc_sync_gpu_threshold_inputs_impl,
    sync_startup_shortcut_toggle as _mc_sync_startup_shortcut_toggle_impl,
    update_active_status as _mc_update_active_status_impl,
    windows_startup_folder_path as _mc_windows_startup_folder_path_impl,
)
from master_sets import (
    all_profile_ids as _mset_all_profile_ids_impl,
    apply_set as _mset_apply_set_impl,
    as_list as _mset_as_list_impl,
    cleanup_orphan_profiles as _mset_cleanup_orphan_profiles_impl,
    clone_profile_settings as _mset_clone_profile_settings_impl,
    copy_profiles_from_set as _mset_copy_profiles_from_set_impl,
    copy_set as _mset_copy_set_impl,
    create_empty_set as _mset_create_empty_set_impl,
    current_set_profiles as _mset_current_set_profiles_impl,
    default_set_name as _mset_default_set_name_impl,
    delete_set as _mset_delete_set_impl,
    get_set_items as _mset_get_set_items_impl,
    load_set_state as _mset_load_set_state_impl,
    migrate_profile_run_flags as _mset_migrate_profile_run_flags_impl,
    next_profile_id as _mset_next_profile_id_impl,
    next_set_id as _mset_next_set_id_impl,
    normalize_ids as _mset_normalize_ids_impl,
    on_profile_order_changed as _mset_on_profile_order_changed_impl,
    profile_run_enabled as _mset_profile_run_enabled_impl,
    remove_profile_from_sets as _mset_remove_profile_from_sets_impl,
    rename_set as _mset_rename_set_impl,
    selected_set_id as _mset_selected_set_id_impl,
    set_current_profiles as _mset_set_current_profiles_impl,
    set_current_set_id as _mset_set_current_set_id_impl,
    set_key as _mset_set_key_impl,
    set_profile_run_enabled as _mset_set_profile_run_enabled_impl,
)
from master_operations import (
    begin_startup_queue as _mqueue_begin_startup_queue_impl,
    build_profile_startup_queue as _mqueue_build_profile_startup_queue_impl,
    build_set_startup_queue as _mqueue_build_set_startup_queue_impl,
    cancel_startup_queue as _mqueue_cancel_startup_queue_impl,
    claim_exec_window as _mclaim_claim_exec_window_impl,
    cleanup_exec_window_claims as _mclaim_cleanup_exec_window_claims_impl,
    get_exec_window_owner as _mclaim_get_exec_window_owner_impl,
    is_temp_group_member as _mtg_is_temp_group_member_impl,
    move_temp_group_by_delta as _mtg_move_temp_group_by_delta_impl,
    release_exec_window_claim as _mclaim_release_exec_window_claim_impl,
    resize_temp_group_by_edges as _mtg_resize_temp_group_by_edges_impl,
    run_next_startup_item as _mqueue_run_next_startup_item_impl,
    save_temp_group_positions as _mtg_save_temp_group_positions_impl,
    set_temp_group_corner_mode as _mtg_set_temp_group_corner_mode_impl,
    set_temp_group_gpu_guard as _mtg_set_temp_group_gpu_guard_impl,
    set_temp_group_lock as _mtg_set_temp_group_lock_impl,
    set_temp_group_mute as _mtg_set_temp_group_mute_impl,
    startup_delay_for_kind as _mqueue_startup_delay_for_kind_impl,
    start_widget_instance as _mwr_start_widget_instance_impl,
    stop_all_widgets_bulk as _mwr_stop_all_widgets_bulk_impl,
    stop_widgets_bulk as _mwr_stop_widgets_bulk_impl,
    sync_all_widget_video_viewports as _mwr_sync_all_widget_video_viewports_impl,
    sync_temp_group_badges as _mtg_sync_temp_group_badges_impl,
    temp_group_move_targets as _mtg_temp_group_move_targets_impl,
    temp_group_shortcut_targets as _mtg_temp_group_shortcut_targets_impl,
    toggle_temp_group_member as _mtg_toggle_temp_group_member_impl,
    adjust_temp_group_layer as _mtg_adjust_temp_group_layer_impl,
    adjust_temp_group_opacity as _mtg_adjust_temp_group_opacity_impl,
    clear_temp_group as _mtg_clear_temp_group_impl,
)

class DesktopWidget(QMainWindow):
    _desktop_icon_listview_hwnd = 0
    _desktop_icon_cache_hwnd = 0
    _desktop_icon_cache_ts = 0.0
    _desktop_icon_cache_rects = []
    _desktop_icon_cache_max_age = 0.28
    _desktop_caption_path_cache_ts = 0.0
    _desktop_caption_path_cache = {}
    _desktop_icon_alpha_cache = {}
    _desktop_icon_pixmap_cache = {}
    _desktop_icon_image_cache = {}
    _desktop_text_alpha_cache = {}
    _desktop_icon_title_font_cache = None
    _desktop_icon_title_font_cache_ts = 0.0
    _desktop_sys_himl_large = 0
    _desktop_shell_items_cache_ts = 0.0
    _desktop_shell_items_cache = {}
    _desktop_shell_items_cache_list = []
    _desktop_icon_edit_info = {}
    _desktop_icon_render_signature = ()
    LAYER_BACK = 0
    LAYER_NORMAL = 1
    LAYER_TOPMOST = 2
    LAYER_SCHEMA_VERSION = 4
    CORNER_ROUNDED = 0
    CORNER_SQUARE = 1
    CORNER_ROUND = 2
    VIDEO_TRANSITION_SINGLE = 0
    VIDEO_TRANSITION_DUAL = 1
    VIDEO_DUAL_FADE_DEFAULT_MS = 90
    VIDEO_DECODE_ORIGINAL = 0
    VIDEO_DECODE_AUTO = 1
    VIDEO_DECODE_1080P = 2
    VIDEO_DECODE_720P = 3

    @classmethod
    def coerce_layer_mode(cls, raw_layer, schema_version=None):
        try:
            val = int(raw_layer)
        except Exception:
            return int(cls.LAYER_NORMAL)
        try:
            schema = int(schema_version) if schema_version is not None else int(cls.LAYER_SCHEMA_VERSION)
        except Exception:
            schema = 0
        if schema >= int(cls.LAYER_SCHEMA_VERSION):
            return max(int(cls.LAYER_BACK), min(int(cls.LAYER_TOPMOST), int(val)))
        # v3 layout: 0(retired), 1(back/icon-above), 2(normal), 3(top)
        if schema == 3:
            v3_map = {
                0: int(cls.LAYER_BACK),
                1: int(cls.LAYER_BACK),
                2: int(cls.LAYER_NORMAL),
                3: int(cls.LAYER_TOPMOST),
            }
            return int(v3_map.get(int(val), int(cls.LAYER_NORMAL)))
        # v2 layout: 0(bottom), 1(icon-above), 2(normal), 3(top)
        if schema == 2:
            v2_map = {
                0: int(cls.LAYER_BACK),
                1: int(cls.LAYER_BACK),
                2: int(cls.LAYER_NORMAL),
                3: int(cls.LAYER_TOPMOST),
            }
            return int(v2_map.get(int(val), int(cls.LAYER_NORMAL)))
        # Legacy v1 migration: 0(back), 1(normal), 2(top)
        legacy_map = {
            0: int(cls.LAYER_BACK),
            1: int(cls.LAYER_NORMAL),
            2: int(cls.LAYER_TOPMOST),
            3: int(cls.LAYER_TOPMOST),
        }
        return int(legacy_map.get(int(val), int(cls.LAYER_NORMAL)))

    @classmethod
    def coerce_video_transition_mode(cls, raw_mode):
        try:
            mode = int(raw_mode)
        except Exception:
            mode = int(cls.VIDEO_TRANSITION_SINGLE)
        if mode not in (int(cls.VIDEO_TRANSITION_SINGLE), int(cls.VIDEO_TRANSITION_DUAL)):
            mode = int(cls.VIDEO_TRANSITION_SINGLE)
        return int(mode)

    @classmethod
    def coerce_corner_mode(cls, raw_mode):
        try:
            mode = int(raw_mode)
        except Exception:
            mode = int(cls.CORNER_ROUNDED)
        valid = {
            int(cls.CORNER_ROUNDED),
            int(cls.CORNER_SQUARE),
            int(cls.CORNER_ROUND),
        }
        if mode not in valid:
            mode = int(cls.CORNER_ROUNDED)
        return int(mode)

    @classmethod
    def coerce_video_dual_fade_ms(cls, raw_value):
        try:
            value = int(raw_value)
        except Exception:
            value = int(cls.VIDEO_DUAL_FADE_DEFAULT_MS)
        return max(0, min(300, int(value)))

    @classmethod
    def coerce_video_decode_mode(cls, raw_mode):
        try:
            mode = int(raw_mode)
        except Exception:
            mode = int(cls.VIDEO_DECODE_ORIGINAL)
        valid = {
            int(cls.VIDEO_DECODE_ORIGINAL),
            int(cls.VIDEO_DECODE_AUTO),
            int(cls.VIDEO_DECODE_1080P),
            int(cls.VIDEO_DECODE_720P),
        }
        if mode not in valid:
            mode = int(cls.VIDEO_DECODE_ORIGINAL)
        return int(mode)

    def __init__(self, profile_id, name, manager):
        super().__init__()
        self.profile_id = profile_id
        self.manager = manager
        self.settings = QSettings("MyHomeApp", f"Profile_{profile_id}")
        try:
            settings_sync_ms = int(os.environ.get("MYCANVAS_SETTINGS_SYNC_MS", "700") or "700")
        except Exception:
            settings_sync_ms = 700
        self._settings_sync_delay_ms = max(120, min(3000, int(settings_sync_ms)))
        self._settings_sync_timer = QTimer(self)
        self._settings_sync_timer.setSingleShot(True)
        self._settings_sync_timer.timeout.connect(self._flush_settings_sync)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow) 
        self.keep_aspect_ratio = _as_bool(self.settings.value("keep_aspect_ratio", True), True)
        self.auto_fit_slide_media = _as_bool(self.settings.value("auto_fit_slide_media", False), False)
        self.base_slide_w = int(self.settings.value("w", 200))
        self.base_slide_h = int(self.settings.value("h", 200))

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(50, 50)
        self.setAcceptDrops(True)
        
        self.container = QWidget(); self.container.setObjectName("mainContainer")
        self.container.setMinimumSize(0, 0)
        self.container.setAcceptDrops(True)
        self.setCentralWidget(self.container)
        self.main_layout = QVBoxLayout(self.container); self.main_layout.setContentsMargins(0,0,0,0)
        
        self.stack = QStackedWidget()
        self.stack.setMinimumSize(0, 0)
        self.stack.setAcceptDrops(True)
        self.main_layout.addWidget(self.stack)

        self.selection_overlay = OverlayWidget(self)
        self.selection_overlay.hide()
        self.resize_overlay = ResizeHandleOverlay(self)
        self.resize_overlay.hide()
        self.desktop_icon_clone_overlay = DesktopIconCloneOverlay(self)
        self.desktop_icon_clone_overlay.hide()
        self.size_hud = QLabel(self)
        self.size_hud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.size_hud.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_hud.setStyleSheet(
            "QLabel { color: white; background-color: rgba(0, 0, 0, 150); "
            "border: 1px solid rgba(255, 255, 255, 80); border-radius: 8px; padding: 4px 10px; }"
        )
        self.size_hud.hide()
        self.action_hud = QLabel(self)
        self.action_hud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.action_hud.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.action_hud.setStyleSheet(
            "QLabel { color: white; background-color: rgba(0, 0, 0, 150); "
            "border: 1px solid rgba(255, 255, 255, 80); border-radius: 8px; padding: 3px 10px; }"
        )
        self.action_hud.hide()
        self.action_hud_timer = QTimer(self)
        self.action_hud_timer.setSingleShot(True)
        self.action_hud_timer.timeout.connect(self.action_hud.hide)
        self.group_badge = QLabel("G", self)
        self.group_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.group_badge.setStyleSheet(
            "QLabel { color: #eff7ff; background-color: rgba(40, 86, 146, 180); "
            "border: 1px solid rgba(145, 192, 255, 170); border-radius: 9px; padding: 1px 6px; "
            "font-size: 10pt; font-weight: 700; }"
        )
        self.group_badge.hide()
        self._size_hud_top_padding = 10
        self.resize_corner = None
        self.is_resizing = False
        self.resize_start_pos = None
        self.resize_start_geo = QRect()
        self.is_moving = False
        self._drag_topmost_active = False
        self._drag_restore_layer = None
        self._drag_restore_lock = None
        self._cursor_inside = False
        self._drag_threshold = 5
        self._axis_snap_threshold = 4
        self._axis_snap_release = 8
        self._snap_lock_x = None
        self._snap_lock_y = None
        self._snap_origin_pointer_x = None
        self._snap_origin_pointer_y = None
        self._shortcut_last_ms = {}


        self.placeholder = QWidget()
        self.placeholder.setMinimumSize(0, 0)
        self.placeholder.setAcceptDrops(True)
        self.placeholder.setStyleSheet("background: #222; border-radius: 20px;")
        p_layout = QVBoxLayout(self.placeholder); p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_label = QLabel("NEW"); new_label.setStyleSheet("font-size: 40px; font-weight: bold; color: rgba(255,255,255,0.4); background: transparent;")
        hint_label = QLabel("우클릭으로 설정"); hint_label.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.3); background: transparent;")
        p_layout.addWidget(new_label); p_layout.addWidget(hint_label)
        self.stack.addWidget(self.placeholder)


        self.img_label = QLabel(); self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setMinimumSize(0, 0)
        self.img_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.img_label.setAcceptDrops(True)
        self.stack.addWidget(self.img_label)
        
        self.video_scene = None
        self.video_item = None
        self.video_item_dual = None
        self._video_graphics_mode = bool(QGraphicsVideoItem is not None)
        if self._video_graphics_mode:
            self.video_widget = QGraphicsView()
            self.video_widget.setFrameShape(QFrame.Shape.NoFrame)
            self.video_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.video_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.video_widget.setInteractive(False)
            self.video_widget.setStyleSheet("QGraphicsView { background: transparent; border: none; }")
            self.video_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.video_widget.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
            try:
                self.video_widget.setOptimizationFlag(
                    QGraphicsView.OptimizationFlag.DontSavePainterState,
                    True,
                )
                self.video_widget.setOptimizationFlag(
                    QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing,
                    True,
                )
            except Exception:
                pass
            self.video_scene = QGraphicsScene(self.video_widget)
            self.video_scene.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
            try:
                self.video_scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
            except Exception:
                pass
            self.video_widget.setScene(self.video_scene)
            self.video_item = QGraphicsVideoItem()
            self.video_scene.addItem(self.video_item)
            self.video_item_dual = QGraphicsVideoItem()
            self.video_scene.addItem(self.video_item_dual)
            try:
                self.video_item.setOpacity(1.0)
                self.video_item.setZValue(2.0)
                self.video_item_dual.setOpacity(0.0)
                self.video_item_dual.setZValue(1.0)
            except Exception:
                pass
            try:
                vp = self.video_widget.viewport()
                if isinstance(vp, QWidget):
                    vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    vp.setAutoFillBackground(False)
            except Exception:
                pass
        else:
            self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(0, 0)
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_widget.setAcceptDrops(True)
        self.stack.addWidget(self.video_widget)
        self._sync_video_viewport_update_mode()

        self.setMouseTracking(True)
        self.container.setMouseTracking(True)
        self.stack.setMouseTracking(True)
        self.placeholder.setMouseTracking(True)
        self.img_label.setMouseTracking(True)
        self.video_widget.setMouseTracking(True)

        self.placeholder.installEventFilter(self)
        self.img_label.installEventFilter(self)
        self.video_widget.installEventFilter(self)
        self.container.installEventFilter(self)
        self.stack.installEventFilter(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput(); self.media_player.setAudioOutput(self.audio_output)
        if self._video_graphics_mode and self.video_item is not None:
            self.media_player.setVideoOutput(self.video_item)
        else:
            self.media_player.setVideoOutput(self.video_widget)
        self._video_primary_player = self.media_player
        self._video_secondary_player = None
        if self._video_graphics_mode and self.video_item_dual is not None:
            try:
                self._video_secondary_player = QMediaPlayer()
                self._video_secondary_player.setAudioOutput(None)
                self._video_secondary_player.setVideoOutput(self.video_item_dual)
            except Exception:
                self._video_secondary_player = None
        self._last_unmuted_volume = 1.0
        self._audio_output_attached = True
        self.media_player.mediaStatusChanged.connect(
            lambda status, p=self._video_primary_player: self.check_video_status(status, p)
        )
        self.media_player.errorOccurred.connect(
            lambda error, text, p=self._video_primary_player: self._on_video_error(error, text, p)
        )
        self.media_player.positionChanged.connect(
            lambda pos, p=self._video_primary_player: self._on_video_position_changed(pos, p)
        )
        if self._video_secondary_player is not None:
            self._video_secondary_player.mediaStatusChanged.connect(
                lambda status, p=self._video_secondary_player: self.check_video_status(status, p)
            )
            self._video_secondary_player.errorOccurred.connect(
                lambda error, text, p=self._video_secondary_player: self._on_video_error(error, text, p)
            )
            self._video_secondary_player.positionChanged.connect(
                lambda pos, p=self._video_secondary_player: self._on_video_position_changed(pos, p)
            )
        self._video_primary_sink = None
        self._video_secondary_sink = None
        if self._video_graphics_mode:
            try:
                self._video_primary_sink = self.video_item.videoSink() if self.video_item is not None else None
            except Exception:
                self._video_primary_sink = None
            try:
                self._video_secondary_sink = self.video_item_dual.videoSink() if self.video_item_dual is not None else None
            except Exception:
                self._video_secondary_sink = None
            if self._video_primary_sink is not None:
                try:
                    self._video_primary_sink.videoFrameChanged.connect(
                        lambda frame, slot=0: self._on_video_frame_changed(frame, slot)
                    )
                except Exception:
                    pass
            if self._video_secondary_sink is not None:
                try:
                    self._video_secondary_sink.videoFrameChanged.connect(
                        lambda frame, slot=1: self._on_video_frame_changed(frame, slot)
                    )
                except Exception:
                    pass
        self._video_active_slot = 0
        self._video_dual_pending_slot = -1
        self._video_dual_pending_path = ""
        self._video_dual_pending_ready = False
        self._video_dual_pending_frame_ready = False
        self._video_dual_pending_frozen = False
        self._video_dual_waiting_for_swap = False
        self._video_dual_preload_triggered_for_path = ""
        self._video_dual_pending_seq = 0
        self._video_dual_pending_started_mono = 0.0
        self._video_transition_seq = 0
        self._video_debug_enabled = _as_bool(os.environ.get("MYWIDGET_DEBUG_VIDEO", "0"), False)
        self._video_swap_fade_duration_ms = int(self.VIDEO_DUAL_FADE_DEFAULT_MS)
        self._video_crossfade_group = None
        self._video_proxy_source_height_cache = {}
        self._video_proxy_failed_keys = set()
        self._video_proxy_ffmpeg_path = None
        self._video_proxy_ffprobe_path = None
        self._video_proxy_dir = self._resolve_video_proxy_dir()
        self._video_proxy_build_queue = deque()
        self._video_proxy_building_keys = set()
        self._video_proxy_build_lock = threading.Lock()
        self._video_proxy_build_worker_running = False
        self._video_proxy_service = VideoProxyService(self)
        self._video_dual_preload_timer = QTimer(self)
        self._video_dual_preload_timer.setSingleShot(True)
        self._video_dual_preload_timer.setInterval(2600)
        self._video_dual_preload_timer.timeout.connect(self._on_video_dual_preload_timeout)
        self._video_dual_end_wait_timer = QTimer(self)
        self._video_dual_end_wait_timer.setSingleShot(True)
        self._video_dual_end_wait_timer.setInterval(700)
        self._video_dual_end_wait_timer.timeout.connect(self._on_video_dual_end_wait_timeout)

        self.timer = QTimer(self); self.timer.timeout.connect(self.next_media)
        self.movie = None; self.playlist = []; self.current_idx = -1; self.start_pos = None
        self.current_static_pixmap = None
        self.current_media_path = None
        self.media_fail_counts = {}
        self.quarantined_media = set()
        self.max_media_failures = 1
        self._failure_scheduled = False
        self._media_resetting = False
        self.gpu_guard_enabled = False
        self.media_fit_mode = 0  # 0: 원본 유지(전체 표시), 1: 위젯 채우기(중앙 크롭)
        self.video_transition_mode = int(self.VIDEO_TRANSITION_SINGLE)
        self.video_decode_mode = int(self.VIDEO_DECODE_ORIGINAL)
        self._performance_paused = False
        self._perf_paused_video = False
        self._perf_paused_gif = False
        self._perf_gif_timer_was_active = False
        self._gif_loop_watch_active = False
        self._gif_loop_last_frame = -1
        self._gif_loop_min_deadline = 0.0
        self._gif_loop_fallback_timer = QTimer(self)
        self._gif_loop_fallback_timer.setSingleShot(True)
        self._gif_loop_fallback_timer.timeout.connect(self._on_gif_loop_fallback_timeout)
        self._gif_swap_pending_movie = None
        self._gif_swap_pending_path = ""
        self._gif_swap_pending_duration_ms = 0
        self._gif_swap_timeout = QTimer(self)
        self._gif_swap_timeout.setSingleShot(True)
        self._gif_swap_timeout.setInterval(3200)
        self._gif_swap_timeout.timeout.connect(self._on_gif_swap_timeout)
        self._desktop_icon_clone_enabled = True
        self._desktop_icon_mask_timer = QTimer(self)
        self._desktop_icon_mask_timer.setInterval(420)
        self._desktop_icon_mask_timer.timeout.connect(self._refresh_desktop_icon_mask)
        self._desktop_icon_clone_refresh_min_interval_ms = 110
        self._desktop_icon_clone_last_refresh_mono = 0.0
        self._desktop_icon_clone_refresh_timer = QTimer(self)
        self._desktop_icon_clone_refresh_timer.setSingleShot(True)
        self._desktop_icon_clone_refresh_timer.setInterval(120)
        self._desktop_icon_clone_refresh_timer.timeout.connect(self._run_deferred_desktop_icon_clone_refresh)
        self._desktop_icon_bootstrap_timer = QTimer(self)
        self._desktop_icon_bootstrap_timer.setSingleShot(True)
        self._desktop_icon_bootstrap_timer.setInterval(120)
        self._desktop_icon_bootstrap_timer.timeout.connect(self._run_desktop_icon_overlay_bootstrap)
        self._desktop_icon_bootstrap_retries = 0
        self._desktop_icon_last_edit_rect_local = QRect()
        self._container_style_cache_key = None
        self._placeholder_style_cache_key = None
        self.folder_watcher = QFileSystemWatcher(self)
        self.folder_watcher.directoryChanged.connect(self._on_folder_changed_signal)
        self.folder_watcher.fileChanged.connect(self._on_folder_changed_signal)
        self.folder_refresh_timer = QTimer(self)
        self.folder_refresh_timer.setSingleShot(True)
        self.folder_refresh_timer.setInterval(250)
        self.folder_refresh_timer.timeout.connect(self._refresh_playlist_from_folder_change)
        self._exec_bound_hwnd = 0
        self._exec_bound_pid = 0
        self._exec_launch_learning = None
        self._exec_manual_focus_enabled = False
        self._exec_manual_focus_proc_path = ""
        self._exec_manual_focus_proc_name = ""
        self._exec_manual_focus_title = ""
        self._exec_manual_focus_class = ""
        self._exec_launch_learn_timer = QTimer(self)
        self._exec_launch_learn_timer.setInterval(700)
        self._exec_launch_learn_timer.timeout.connect(self._on_exec_launch_learn_tick)

        self._initial_media_pending = False
        self._initial_media_prepared = False
        self._defer_initial_prepare_on_show = False
        self.load_settings()
        if self.folder_path:
            self.update_playlist()
            self._initial_media_pending = bool(self.playlist)

    def setWindowOpacity(self, level):
        try:
            value = float(level)
        except Exception:
            value = 1.0
        value = max(0.0, min(1.0, value))
        super().setWindowOpacity(value)

    def _desktop_icon_overlay_base_condition(self):
        if int(getattr(self, "layer_mode", self.LAYER_NORMAL)) != int(self.LAYER_BACK):
            return False
        if not bool(getattr(self, "is_locked", False)):
            return False
        return True

    @classmethod
    def _media_path_suffix(cls, path):
        raw = str(path or "").strip()
        if not raw:
            return ""
        target = str(raw or "")
        ext = str(os.path.splitext(target)[1] or "").lower()
        return str(ext or "")

    @staticmethod
    def _video_extensions():
        return (".mp4", ".avi", ".mov", ".m4v", ".webm", ".mkv", ".m3u8")

    @staticmethod
    def _image_extensions():
        return (".png", ".jpg", ".jpeg", ".gif", ".ico", ".jfif", ".webp")

    @classmethod
    def _is_video_path(cls, path):
        suffix = cls._media_path_suffix(path)
        return bool(suffix in cls._video_extensions())

    @classmethod
    def _is_gif_path(cls, path):
        return cls._media_path_suffix(path) == ".gif"

    @classmethod
    def _is_image_path(cls, path):
        return cls._media_path_suffix(path) in cls._image_extensions()

    @classmethod
    def _to_media_qurl(cls, path):
        raw = str(path or "").strip()
        if not raw:
            return QUrl()
        return QUrl.fromLocalFile(raw)

    def _is_current_media_video(self):
        if int(self.stack.currentIndex()) == 2:
            return True
        return self._is_video_path(getattr(self, "current_media_path", ""))

    def _refresh_icon_overlay_for_current_media(self):
        # Media-type switch (video <-> image/gif) can change icon-overlay strategy.
        # Apply immediately to avoid one-frame artifacts/flicker.
        try:
            self.apply_mask_and_style()
        except Exception:
            self._sync_desktop_icon_mask_timer()

    def _should_clone_desktop_icons(self):
        if not (bool(getattr(self, "_desktop_icon_clone_enabled", True)) and self._desktop_icon_overlay_base_condition()):
            return False
        # Fallback for environments where graphics-video path is unavailable.
        if self._is_current_media_video() and not bool(getattr(self, "_video_graphics_mode", False)):
            return False
        return True

    def _should_punch_desktop_icons(self):
        if self._should_clone_desktop_icons():
            return False
        return self._desktop_icon_overlay_base_condition()

    def _desktop_icon_edit_rect_local(self, force=False):
        top_left = self._global_top_left()
        wx = int(top_left.x())
        wy = int(top_left.y())
        ww = int(self.width())
        wh = int(self.height())
        if ww <= 0 or wh <= 0:
            return QRect()
        widget_screen_rect = QRect(wx, wy, ww, wh)
        try:
            self.__class__._desktop_icon_rects_screen(force=bool(force))
        except Exception:
            pass
        info = self.__class__._desktop_icon_edit_info_screen()
        if not isinstance(info, dict):
            return QRect()
        edit_rect = info.get("rect")
        if not isinstance(edit_rect, QRect):
            return QRect()
        hit = edit_rect.intersected(widget_screen_rect)
        if int(hit.width()) <= 0 or int(hit.height()) <= 0:
            return QRect()
        return hit.translated(-wx, -wy)

    def _sync_desktop_icon_mask_timer(self):
        if not hasattr(self, "_desktop_icon_mask_timer"):
            return
        enabled = (self._should_clone_desktop_icons() or self._should_punch_desktop_icons()) and self.isVisible()
        if enabled:
            target_interval = 280
            if self._should_clone_desktop_icons():
                target_interval = 280
            elif self._should_punch_desktop_icons():
                target_interval = 350
            try:
                if int(self._desktop_icon_mask_timer.interval()) != int(target_interval):
                    self._desktop_icon_mask_timer.setInterval(int(target_interval))
            except Exception:
                pass
            if not self._desktop_icon_mask_timer.isActive():
                self._desktop_icon_mask_timer.start()
            return
        if self._desktop_icon_mask_timer.isActive():
            self._desktop_icon_mask_timer.stop()

    def _schedule_desktop_icon_overlay_bootstrap(self, retries=3, delay_ms=120):
        if not hasattr(self, "_desktop_icon_bootstrap_timer"):
            return
        if not (self._should_clone_desktop_icons() or self._should_punch_desktop_icons()):
            self._desktop_icon_bootstrap_retries = 0
            if self._desktop_icon_bootstrap_timer.isActive():
                self._desktop_icon_bootstrap_timer.stop()
            return
        try:
            retry_count = max(0, min(8, int(retries)))
        except Exception:
            retry_count = 3
        self._desktop_icon_bootstrap_retries = max(int(self._desktop_icon_bootstrap_retries), int(retry_count))
        try:
            wait_ms = max(20, int(delay_ms))
        except Exception:
            wait_ms = 120
        self._desktop_icon_bootstrap_timer.start(int(wait_ms))

    def _run_desktop_icon_overlay_bootstrap(self):
        if not self.isVisible():
            return
        if self._should_clone_desktop_icons():
            self._refresh_desktop_icon_clone_overlay(force=True)
        elif self._should_punch_desktop_icons():
            self.apply_mask_and_style()
        self._sync_desktop_icon_mask_timer()
        if int(getattr(self, "_desktop_icon_bootstrap_retries", 0)) > 0:
            self._desktop_icon_bootstrap_retries = int(self._desktop_icon_bootstrap_retries) - 1
            if hasattr(self, "_desktop_icon_bootstrap_timer"):
                self._desktop_icon_bootstrap_timer.start(140)

    def _set_clone_overlay_items(self, items):
        if not hasattr(self, "desktop_icon_clone_overlay"):
            return
        overlay = self.desktop_icon_clone_overlay
        if not isinstance(overlay, QWidget):
            return
        if not items:
            overlay.set_items([])
            overlay.hide()
            return
        overlay.setGeometry(self.rect())
        overlay.set_items(items)
        overlay.show()
        overlay.raise_()

    def _run_deferred_desktop_icon_clone_refresh(self):
        self._refresh_desktop_icon_clone_overlay(force=False)

    def _refresh_desktop_icon_clone_overlay(self, force=False):
        if not self._should_clone_desktop_icons() or not self.isVisible():
            if hasattr(self, "_desktop_icon_clone_refresh_timer") and self._desktop_icon_clone_refresh_timer.isActive():
                self._desktop_icon_clone_refresh_timer.stop()
            self._set_clone_overlay_items([])
            return
        now = float(time.monotonic())
        if not bool(force):
            last_refresh = float(getattr(self, "_desktop_icon_clone_last_refresh_mono", 0.0) or 0.0)
            min_interval_ms = int(getattr(self, "_desktop_icon_clone_refresh_min_interval_ms", 110) or 110)
            elapsed_ms = (now - last_refresh) * 1000.0
            if elapsed_ms < float(min_interval_ms):
                if hasattr(self, "_desktop_icon_clone_refresh_timer"):
                    wait_ms = max(16, int(round(float(min_interval_ms) - elapsed_ms)))
                    if (
                        (not self._desktop_icon_clone_refresh_timer.isActive())
                        or int(self._desktop_icon_clone_refresh_timer.remainingTime()) > int(wait_ms)
                    ):
                        self._desktop_icon_clone_refresh_timer.start(int(wait_ms))
                return
        else:
            if hasattr(self, "_desktop_icon_clone_refresh_timer") and self._desktop_icon_clone_refresh_timer.isActive():
                self._desktop_icon_clone_refresh_timer.stop()
        self._desktop_icon_clone_last_refresh_mono = now
        items = self._desktop_icon_clone_items_local(force=bool(force))
        self._set_clone_overlay_items(items)

    def _refresh_desktop_icon_mask(self):
        clone_mode = self._should_clone_desktop_icons()
        punch_mode = self._should_punch_desktop_icons()
        if (not clone_mode and not punch_mode) or not self.isVisible():
            self._set_clone_overlay_items([])
            self._desktop_icon_last_edit_rect_local = QRect()
            self._sync_desktop_icon_mask_timer()
            return
        if clone_mode:
            self._refresh_desktop_icon_clone_overlay(force=False)
            edit_local_rect = self._desktop_icon_edit_rect_local(force=False)
            if not (isinstance(edit_local_rect, QRect) and int(edit_local_rect.width()) > 0 and int(edit_local_rect.height()) > 0):
                edit_local_rect = QRect()
            prev_edit_rect = getattr(self, "_desktop_icon_last_edit_rect_local", QRect())
            if not isinstance(prev_edit_rect, QRect):
                prev_edit_rect = QRect()
            if prev_edit_rect != edit_local_rect:
                self._desktop_icon_last_edit_rect_local = QRect(edit_local_rect)
                self.apply_mask_and_style()
            return
        self._desktop_icon_last_edit_rect_local = QRect()
        self.apply_mask_and_style()

    @classmethod
    def _clear_desktop_icon_render_caches(cls):
        try:
            cls._desktop_icon_alpha_cache.clear()
        except Exception:
            cls._desktop_icon_alpha_cache = {}
        try:
            cls._desktop_icon_pixmap_cache.clear()
        except Exception:
            cls._desktop_icon_pixmap_cache = {}
        try:
            cls._desktop_icon_image_cache.clear()
        except Exception:
            cls._desktop_icon_image_cache = {}

    @classmethod
    def _desktop_icon_render_signature_of_rects(cls, rects):
        return desktop_icon_render_signature_of_rects(rects)

    @classmethod
    def _resolve_desktop_listview_hwnd(cls, refresh=False):
        resolved = resolve_desktop_listview_hwnd(
            cached_hwnd=int(getattr(cls, "_desktop_icon_listview_hwnd", 0) or 0),
            refresh=bool(refresh),
        )
        cls._desktop_icon_listview_hwnd = int(resolved or 0)
        return int(resolved or 0)

    @classmethod
    def _query_desktop_icon_rects_screen(cls, listview_hwnd):
        layouts, edit_info = query_desktop_icon_rects_screen(
            int(listview_hwnd),
            shell_items_by_name_func=lambda refresh=False: cls._desktop_shell_items_by_name(refresh=bool(refresh)),
            shell_items_in_order_func=lambda refresh=False: cls._desktop_shell_items_in_order(refresh=bool(refresh)),
        )
        cls._desktop_icon_edit_info = dict(edit_info or {})
        return list(layouts or [])

    @classmethod
    def _desktop_icon_rects_screen(cls, force=False):
        now = float(time.monotonic())
        cache_hwnd = int(getattr(cls, "_desktop_icon_cache_hwnd", 0) or 0)
        cache_ts = float(getattr(cls, "_desktop_icon_cache_ts", 0.0) or 0.0)
        cache_rects = list(getattr(cls, "_desktop_icon_cache_rects", []) or [])
        try:
            cache_max_age = max(0.05, float(getattr(cls, "_desktop_icon_cache_max_age", 0.28) or 0.28))
        except Exception:
            cache_max_age = 0.28
        if (
            not force
            and cache_hwnd
            and (now - cache_ts) <= cache_max_age
        ):
            try:
                if win32gui.IsWindow(int(cache_hwnd)):
                    return cache_rects
            except Exception:
                pass
        listview_hwnd = cls._resolve_desktop_listview_hwnd(refresh=bool(force))
        if not listview_hwnd:
            cls._desktop_icon_cache_hwnd = 0
            cls._desktop_icon_cache_ts = now
            cls._desktop_icon_cache_rects = []
            cls._desktop_icon_edit_info = {}
            cls._desktop_icon_render_signature = ()
            return []
        rects = cls._query_desktop_icon_rects_screen(int(listview_hwnd))
        new_sig = cls._desktop_icon_render_signature_of_rects(rects)
        prev_sig = tuple(getattr(cls, "_desktop_icon_render_signature", ()) or ())
        if prev_sig and prev_sig != new_sig:
            cls._clear_desktop_icon_render_caches()
        cls._desktop_icon_render_signature = tuple(new_sig)
        cls._desktop_icon_cache_hwnd = int(listview_hwnd)
        cls._desktop_icon_cache_ts = now
        cls._desktop_icon_cache_rects = list(rects)
        return list(rects)

    @classmethod
    def _desktop_icon_edit_info_screen(cls):
        info = dict(getattr(cls, "_desktop_icon_edit_info", {}) or {})
        rect = info.get("rect")
        if isinstance(rect, QRect) and int(rect.width()) > 0 and int(rect.height()) > 0:
            return info
        return {}

    @classmethod
    def _desktop_caption_path_map(cls, refresh=False):
        now = float(time.monotonic())
        cache_ts = float(getattr(cls, "_desktop_caption_path_cache_ts", 0.0) or 0.0)
        cached = dict(getattr(cls, "_desktop_caption_path_cache", {}) or {})
        if not refresh and cached and (now - cache_ts) <= 6.0:
            return cached
        mapping = build_desktop_caption_path_map()
        cls._desktop_caption_path_cache = dict(mapping)
        cls._desktop_caption_path_cache_ts = now
        return dict(mapping)

    @classmethod
    def _desktop_caption_to_path(cls, caption):
        key = str(caption or "").strip().lower()
        if not key:
            return ""
        table = cls._desktop_caption_path_map(refresh=False)
        path = str(table.get(key, "") or "")
        if path:
            return path
        # Handle trailing ellipsis fallback from narrow icon labels.
        key2 = key.rstrip(".").strip()
        if key2:
            path = str(table.get(key2, "") or "")
            if path:
                return path
        return ""

    @classmethod
    def _desktop_shell_items_by_name(cls, refresh=False):
        now = float(time.monotonic())
        cache_ts = float(getattr(cls, "_desktop_shell_items_cache_ts", 0.0) or 0.0)
        cached = dict(getattr(cls, "_desktop_shell_items_cache", {}) or {})
        cached_list = list(getattr(cls, "_desktop_shell_items_cache_list", []) or [])
        if not refresh and cached and cached_list and (now - cache_ts) <= 2.0:
            return cached
        out, ordered = fetch_desktop_shell_items(_get_win32com_client())
        cls._desktop_shell_items_cache = dict(out)
        cls._desktop_shell_items_cache_list = list(ordered)
        cls._desktop_shell_items_cache_ts = now
        return dict(out)

    @classmethod
    def _desktop_shell_items_in_order(cls, refresh=False):
        now = float(time.monotonic())
        cache_ts = float(getattr(cls, "_desktop_shell_items_cache_ts", 0.0) or 0.0)
        cached = list(getattr(cls, "_desktop_shell_items_cache_list", []) or [])
        if not refresh and cached and (now - cache_ts) <= 2.0:
            return cached
        cls._desktop_shell_items_by_name(refresh=bool(refresh))
        return list(getattr(cls, "_desktop_shell_items_cache_list", []) or [])

    @staticmethod
    def _is_recycle_caption(caption):
        return is_recycle_caption(caption)

    @classmethod
    def _desktop_icon_identity(cls, caption):
        caption_key = str(caption or "").strip().lower()
        path = cls._desktop_caption_to_path(caption)
        stock_recycle = cls._is_recycle_caption(caption)
        if path and os.path.exists(path):
            icon_key = str(os.path.normcase(path))
            return icon_key, str(path), False
        if stock_recycle:
            return "stock::recycler", "", True
        return f"caption::{caption_key}", "", False

    @staticmethod
    def _as_win_handle(value):
        try:
            return int(ctypes.c_void_p(int(value)).value or 0)
        except Exception:
            return 0

    @classmethod
    def _resolve_desktop_sys_himl_large(cls):
        cached = cls._as_win_handle(getattr(cls, "_desktop_sys_himl_large", 0) or 0)
        if cached:
            return int(cached)
        try:
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_uint),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80),
                ]

            shfi = SHFILEINFOW()
            shgfi_sysiconindex = int(0x000004000)
            shgfi_large = int(0x000000000)
            shell32 = ctypes.windll.shell32
            shell32.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.POINTER(SHFILEINFOW),
                ctypes.c_uint,
                ctypes.c_uint,
            ]
            shell32.SHGetFileInfoW.restype = ctypes.c_void_p
            himl_raw = shell32.SHGetFileInfoW(
                    ctypes.c_wchar_p("C:\\"),
                    0,
                    ctypes.byref(shfi),
                    ctypes.sizeof(shfi),
                    int(shgfi_sysiconindex | shgfi_large),
                )
            himl = cls._as_win_handle(himl_raw)
            cls._desktop_sys_himl_large = int(himl)
            return int(himl)
        except Exception:
            cls._desktop_sys_himl_large = 0
            return 0

    @classmethod
    def _icon_image_for_sys_index(cls, image_index, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            idx = int(image_index)
        except Exception:
            idx = -1
        cache_key = ("sysidx", int(idx), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)
        if idx < 0:
            img = QImage()
            cls._desktop_icon_image_cache[cache_key] = QImage(img)
            return QImage(img)

        himl = cls._resolve_desktop_sys_himl_large()
        if not himl:
            img = QImage()
            cls._desktop_icon_image_cache[cache_key] = QImage(img)
            return QImage(img)

        image = QImage()
        hicon = 0
        hbm_color = 0
        hbm_mask = 0
        win32ui_mod = _get_win32ui()
        try:
            comctl32 = ctypes.windll.comctl32
            comctl32.ImageList_GetIcon.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint]
            comctl32.ImageList_GetIcon.restype = ctypes.c_void_p
            hicon = cls._as_win_handle(comctl32.ImageList_GetIcon(int(himl), int(idx), 0))
            if hicon:
                icon_info = win32gui.GetIconInfo(int(hicon))
                if isinstance(icon_info, tuple) and len(icon_info) >= 5:
                    hbm_mask = cls._as_win_handle(icon_info[3])
                    hbm_color = cls._as_win_handle(icon_info[4])

            if hbm_color and win32ui_mod is not None:
                bmp = win32ui_mod.CreateBitmapFromHandle(int(hbm_color))
                info = bmp.GetInfo()
                bits = bmp.GetBitmapBits(True)
                bw = int(info.get("bmWidth", 0))
                bh = int(info.get("bmHeight", 0))
                bpp = int(info.get("bmBitsPixel", 0))
                stride = int(max(0, bw * 4))
                if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                    qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                    qimg = qimg.scaled(
                        int(size),
                        int(size),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                    canvas.fill(0)
                    painter = QPainter(canvas)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    dx = int((int(size) - int(qimg.width())) // 2)
                    dy = int((int(size) - int(qimg.height())) // 2)
                    painter.drawImage(int(dx), int(dy), qimg)
                    painter.end()
                    image = canvas
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass
            try:
                if hbm_color:
                    win32gui.DeleteObject(int(hbm_color))
            except Exception:
                pass
            try:
                if hbm_mask:
                    win32gui.DeleteObject(int(hbm_mask))
            except Exception:
                pass

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        if len(cls._desktop_icon_image_cache) > 480:
            try:
                cls._desktop_icon_image_cache.pop(next(iter(cls._desktop_icon_image_cache)))
            except Exception:
                pass
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_sys_index(cls, image_index, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            idx = int(image_index)
        except Exception:
            idx = -1
        cache_key = ("sysidx", int(idx), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_sys_index(int(idx), int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        if len(cls._desktop_icon_pixmap_cache) > 480:
            try:
                cls._desktop_icon_pixmap_cache.pop(next(iter(cls._desktop_icon_pixmap_cache)))
            except Exception:
                pass
        return QPixmap(pix)

    @classmethod
    def _image_from_hicon(cls, hicon, icon_px):
        size = max(12, min(128, int(icon_px)))
        hicon = cls._as_win_handle(hicon)
        if not hicon:
            return QImage()
        hbm_color = 0
        hbm_mask = 0
        win32ui_mod = _get_win32ui()
        try:
            icon_info = win32gui.GetIconInfo(int(hicon))
            if isinstance(icon_info, tuple) and len(icon_info) >= 5:
                hbm_mask = cls._as_win_handle(icon_info[3])
                hbm_color = cls._as_win_handle(icon_info[4])
            if hbm_color and win32ui_mod is not None:
                bmp = win32ui_mod.CreateBitmapFromHandle(int(hbm_color))
                info = bmp.GetInfo()
                bits = bmp.GetBitmapBits(True)
                bw = int(info.get("bmWidth", 0))
                bh = int(info.get("bmHeight", 0))
                bpp = int(info.get("bmBitsPixel", 0))
                stride = int(max(0, bw * 4))
                if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                    qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                    qimg = qimg.scaled(
                        int(size),
                        int(size),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                    canvas.fill(0)
                    painter = QPainter(canvas)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    dx = int((int(size) - int(qimg.width())) // 2)
                    dy = int((int(size) - int(qimg.height())) // 2)
                    painter.drawImage(int(dx), int(dy), qimg)
                    painter.end()
                    return canvas
        except Exception:
            pass
        finally:
            try:
                if hbm_color:
                    win32gui.DeleteObject(int(hbm_color))
            except Exception:
                pass
            try:
                if hbm_mask:
                    win32gui.DeleteObject(int(hbm_mask))
            except Exception:
                pass
        return QImage()

    @staticmethod
    def _guid_from_text(text):
        s = str(text or "").strip().strip("{}")
        parts = s.split("-")
        if len(parts) != 5:
            return None

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        raw = parts[3] + parts[4]
        if len(raw) != 16:
            return None
        try:
            d4 = (ctypes.c_ubyte * 8)(*([int(raw[i:i + 2], 16) for i in range(0, 16, 2)]))
            return GUID(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), d4)
        except Exception:
            return None

    @classmethod
    def _shell_item_image_for_path(cls, path, icon_px, thumbnail_first=True):
        size = max(12, min(256, int(icon_px)))
        path = str(path or "").strip()
        if not path:
            return QImage()
        cache_key = ("shellitem", str(os.path.normcase(path)), int(size), int(bool(thumbnail_first)))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        image = QImage()
        hbitmap = 0
        item_ptr = ctypes.c_void_p()
        win32ui_mod = _get_win32ui()
        try:
            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32
            iid = cls._guid_from_text("{BCC18B79-BA16-442F-80C4-8A59C30C463B}")  # IShellItemImageFactory
            if iid is None:
                cls._desktop_icon_image_cache[cache_key] = QImage()
                return QImage()

            shell32.SHCreateItemFromParsingName.argtypes = [
                wintypes.LPCWSTR,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            shell32.SHCreateItemFromParsingName.restype = ctypes.c_long
            coinit = int(ole32.CoInitialize(None))
            try:
                hr = int(
                    shell32.SHCreateItemFromParsingName(
                        ctypes.c_wchar_p(path),
                        None,
                        ctypes.byref(iid),
                        ctypes.byref(item_ptr),
                    )
                )
                if hr != 0 or not item_ptr.value:
                    cls._desktop_icon_image_cache[cache_key] = QImage()
                    return QImage()

                class SIZE(ctypes.Structure):
                    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

                siigbf_resizetofit = 0x00
                siigbf_biggersizeok = 0x01
                siigbf_icononly = 0x04
                siigbf_thumbnailonly = 0x08
                # COM vtable: IUnknown(3) + GetImage(1)
                vtbl = ctypes.cast(item_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                fn_type = ctypes.WINFUNCTYPE(
                    ctypes.c_long,
                    ctypes.c_void_p,
                    SIZE,
                    ctypes.c_uint,
                    ctypes.POINTER(ctypes.c_void_p),
                )
                get_image = fn_type(vtbl[3])

                flags = int(siigbf_resizetofit | siigbf_biggersizeok)
                if thumbnail_first:
                    flags |= int(siigbf_thumbnailonly)
                else:
                    flags |= int(siigbf_icononly)

                hbmp = ctypes.c_void_p()
                hr_img = int(get_image(item_ptr, SIZE(int(size), int(size)), int(flags), ctypes.byref(hbmp)))
                if hr_img != 0 or not hbmp.value:
                    hbmp = ctypes.c_void_p()
                    flags_fallback = int(siigbf_resizetofit | siigbf_biggersizeok | siigbf_icononly)
                    hr_img = int(get_image(item_ptr, SIZE(int(size), int(size)), int(flags_fallback), ctypes.byref(hbmp)))
                if hr_img == 0 and hbmp.value:
                    hbitmap = cls._as_win_handle(hbmp.value)
                    if hbitmap and win32ui_mod is not None:
                        bmp = win32ui_mod.CreateBitmapFromHandle(int(hbitmap))
                        info = bmp.GetInfo()
                        bits = bmp.GetBitmapBits(True)
                        bw = int(info.get("bmWidth", 0))
                        bh = int(info.get("bmHeight", 0))
                        bpp = int(info.get("bmBitsPixel", 0))
                        stride = int(max(0, bw * 4))
                        if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                            qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                            image = qimg.scaled(
                                int(size),
                                int(size),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
            finally:
                if coinit in (0, 1):  # S_OK or S_FALSE
                    try:
                        ole32.CoUninitialize()
                    except Exception:
                        pass
        except Exception:
            image = QImage()
        finally:
            try:
                if hbitmap:
                    win32gui.DeleteObject(int(hbitmap))
            except Exception:
                pass
            try:
                if item_ptr and item_ptr.value:
                    vtbl = ctypes.cast(item_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    rel_t = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
                    release = rel_t(vtbl[2])
                    release(item_ptr)
            except Exception:
                pass

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        return QImage(image)

    @classmethod
    def _icon_image_for_path(cls, path, icon_px):
        size = max(12, min(128, int(icon_px)))
        path = str(path or "").strip()
        if not path:
            return QImage()
        cache_key = ("path", str(os.path.normcase(path)), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        image = cls._shell_item_image_for_path(path, int(size), thumbnail_first=True)
        if not image.isNull():
            cls._desktop_icon_image_cache[cache_key] = QImage(image)
            return QImage(image)

        image = QImage()
        hicon = 0
        try:
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_uint),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80),
                ]

            shell32 = ctypes.windll.shell32
            shell32.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.POINTER(SHFILEINFOW),
                ctypes.c_uint,
                ctypes.c_uint,
            ]
            shell32.SHGetFileInfoW.restype = ctypes.c_void_p
            shfi = SHFILEINFOW()
            shgfi_icon = int(0x000000100)
            shgfi_large = int(0x000000000)
            ok_raw = shell32.SHGetFileInfoW(
                ctypes.c_wchar_p(path),
                0,
                ctypes.byref(shfi),
                ctypes.sizeof(shfi),
                int(shgfi_icon | shgfi_large),
            )
            ok = cls._as_win_handle(ok_raw)
            if ok and shfi.hIcon:
                hicon = cls._as_win_handle(shfi.hIcon)
                image = cls._image_from_hicon(int(hicon), int(size))
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass

        if image.isNull():
            try:
                provider = QFileIconProvider()
                icon = provider.icon(QFileInfo(path))
                if not icon.isNull():
                    pm = icon.pixmap(int(size), int(size))
                    if not pm.isNull():
                        image = pm.toImage().scaled(
                            int(size),
                            int(size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
            except Exception:
                image = QImage()

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_path(cls, path, icon_px):
        size = max(12, min(128, int(icon_px)))
        path = str(path or "").strip()
        if not path:
            return QPixmap()
        cache_key = ("path", str(os.path.normcase(path)), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_path(path, int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        return QPixmap(pix)

    @classmethod
    def _icon_image_for_stock_id(cls, stock_id, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            sid = int(stock_id)
        except Exception:
            sid = 0
        cache_key = ("stock", int(sid), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        image = QImage()
        hicon = 0
        try:
            class SHSTOCKICONINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hIcon", ctypes.c_void_p),
                    ("iSysImageIndex", ctypes.c_int),
                    ("iIcon", ctypes.c_int),
                    ("szPath", ctypes.c_wchar * 260),
                ]

            shell32 = ctypes.windll.shell32
            sii = SHSTOCKICONINFO()
            sii.cbSize = int(ctypes.sizeof(SHSTOCKICONINFO))
            shgsi_icon = int(0x000000100)
            shgsi_large = int(0x000000000)
            hr = int(
                shell32.SHGetStockIconInfo(
                    int(sid),
                    int(shgsi_icon | shgsi_large),
                    ctypes.byref(sii),
                )
            )
            if hr == 0 and sii.hIcon:
                hicon = cls._as_win_handle(sii.hIcon)
                image = cls._image_from_hicon(int(hicon), int(size))
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass

        if image.isNull():
            try:
                std = QStyle.StandardPixmap.SP_FileIcon
                if sid in (3, 4):
                    std = QStyle.StandardPixmap.SP_DirIcon
                elif sid in (31, 32):
                    std = QStyle.StandardPixmap.SP_TrashIcon
                icon = QApplication.style().standardIcon(std)
                if not icon.isNull():
                    pm = icon.pixmap(int(size), int(size))
                    if not pm.isNull():
                        image = pm.toImage().scaled(
                            int(size),
                            int(size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
            except Exception:
                image = QImage()

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_stock_id(cls, stock_id, icon_px):
        size = max(12, min(128, int(icon_px)))
        try:
            sid = int(stock_id)
        except Exception:
            sid = 0
        cache_key = ("stock", int(sid), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_stock_id(int(sid), int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        return QPixmap(pix)

    @classmethod
    def _icon_image_for_item(cls, caption, icon_px):
        size = max(12, min(128, int(icon_px)))
        icon_key, path, stock_recycle = cls._desktop_icon_identity(caption)
        cache_key = (str(icon_key), int(size))
        cached = cls._desktop_icon_image_cache.get(cache_key)
        if isinstance(cached, QImage):
            return QImage(cached)

        if not path and not stock_recycle:
            img = QImage()
            cls._desktop_icon_image_cache[cache_key] = QImage(img)
            return QImage(img)

        image = QImage()
        hicon = 0
        hbm_color = 0
        hbm_mask = 0
        win32ui_mod = _get_win32ui()
        try:
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_uint),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80),
                ]

            class SHSTOCKICONINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hIcon", ctypes.c_void_p),
                    ("iSysImageIndex", ctypes.c_int),
                    ("iIcon", ctypes.c_int),
                    ("szPath", ctypes.c_wchar * 260),
                ]

            def _as_handle(v):
                try:
                    return int(ctypes.c_void_p(int(v)).value or 0)
                except Exception:
                    return 0

            shell32 = ctypes.windll.shell32
            shell32.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.POINTER(SHFILEINFOW),
                ctypes.c_uint,
                ctypes.c_uint,
            ]
            shell32.SHGetFileInfoW.restype = ctypes.c_void_p
            if path and os.path.exists(path):
                shfi = SHFILEINFOW()
                shgfi_icon = int(0x000000100)
                shgfi_large = int(0x000000000)
                ok_raw = shell32.SHGetFileInfoW(
                    ctypes.c_wchar_p(path),
                    0,
                    ctypes.byref(shfi),
                    ctypes.sizeof(shfi),
                    shgfi_icon | shgfi_large,
                )
                ok = cls._as_win_handle(ok_raw)
                if ok and shfi.hIcon:
                    hicon = _as_handle(shfi.hIcon)
            elif stock_recycle:
                sii = SHSTOCKICONINFO()
                sii.cbSize = int(ctypes.sizeof(SHSTOCKICONINFO))
                siid_recycler = 31
                shgsi_icon = int(0x000000100)
                shgsi_large = int(0x000000000)
                hr = int(
                    shell32.SHGetStockIconInfo(
                        int(siid_recycler),
                        int(shgsi_icon | shgsi_large),
                        ctypes.byref(sii),
                    )
                )
                if hr == 0 and sii.hIcon:
                    hicon = _as_handle(sii.hIcon)

            if hicon:
                icon_info = win32gui.GetIconInfo(int(hicon))
                if isinstance(icon_info, tuple) and len(icon_info) >= 5:
                    hbm_mask = _as_handle(icon_info[3])
                    hbm_color = _as_handle(icon_info[4])

            if hbm_color and win32ui_mod is not None:
                bmp = win32ui_mod.CreateBitmapFromHandle(int(hbm_color))
                info = bmp.GetInfo()
                bits = bmp.GetBitmapBits(True)
                bw = int(info.get("bmWidth", 0))
                bh = int(info.get("bmHeight", 0))
                bpp = int(info.get("bmBitsPixel", 0))
                stride = int(max(0, bw * 4))
                if bw > 0 and bh > 0 and bpp >= 32 and stride > 0 and len(bits) >= stride * bh:
                    qimg = QImage(bits, bw, bh, stride, QImage.Format.Format_ARGB32).copy()
                    qimg = qimg.scaled(
                        int(size),
                        int(size),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                    canvas.fill(0)
                    painter = QPainter(canvas)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    dx = int((int(size) - int(qimg.width())) // 2)
                    dy = int((int(size) - int(qimg.height())) // 2)
                    painter.drawImage(int(dx), int(dy), qimg)
                    painter.end()
                    image = canvas
        except Exception:
            image = QImage()
        finally:
            try:
                if hicon:
                    win32gui.DestroyIcon(int(hicon))
            except Exception:
                pass
            try:
                if hbm_color:
                    win32gui.DeleteObject(int(hbm_color))
            except Exception:
                pass
            try:
                if hbm_mask:
                    win32gui.DeleteObject(int(hbm_mask))
            except Exception:
                pass

        if image.isNull():
            try:
                provider = QFileIconProvider()
                icon = QIcon()
                if path and os.path.exists(path):
                    icon = provider.icon(QFileInfo(path))
                elif stock_recycle:
                    icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
                else:
                    icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
                if not icon.isNull():
                    pm = icon.pixmap(int(size), int(size))
                    if not pm.isNull():
                        img = pm.toImage().scaled(
                            int(size),
                            int(size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        canvas = QImage(int(size), int(size), QImage.Format.Format_ARGB32)
                        canvas.fill(0)
                        painter = QPainter(canvas)
                        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                        dx = int((int(size) - int(img.width())) // 2)
                        dy = int((int(size) - int(img.height())) // 2)
                        painter.drawImage(int(dx), int(dy), img)
                        painter.end()
                        image = canvas
            except Exception:
                image = QImage()

        cls._desktop_icon_image_cache[cache_key] = QImage(image)
        if len(cls._desktop_icon_image_cache) > 320:
            try:
                cls._desktop_icon_image_cache.pop(next(iter(cls._desktop_icon_image_cache)))
            except Exception:
                pass
        return QImage(image)

    @classmethod
    def _icon_pixmap_for_item(cls, caption, icon_px):
        size = max(12, min(128, int(icon_px)))
        icon_key, _path, _stock_recycle = cls._desktop_icon_identity(caption)
        cache_key = (str(icon_key), int(size))
        cached = cls._desktop_icon_pixmap_cache.get(cache_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            return QPixmap(cached)
        image = cls._icon_image_for_item(caption, int(size))
        if image.isNull():
            return QPixmap()
        pix = QPixmap.fromImage(image)
        cls._desktop_icon_pixmap_cache[cache_key] = QPixmap(pix)
        if len(cls._desktop_icon_pixmap_cache) > 320:
            try:
                cls._desktop_icon_pixmap_cache.pop(next(iter(cls._desktop_icon_pixmap_cache)))
            except Exception:
                pass
        return QPixmap(pix)

    @staticmethod
    def _alpha_region_from_image(image, alpha_threshold=22):
        if image is None or image.isNull():
            return QRegion()
        img = image.convertToFormat(QImage.Format.Format_ARGB32)
        w = int(img.width())
        h = int(img.height())
        if w <= 0 or h <= 0:
            return QRegion()
        try:
            stride = int(img.bytesPerLine())
            total = int(img.sizeInBytes())
            ptr = img.bits()
            ptr.setsize(total)
            raw = ptr.asstring(total)
        except Exception:
            return QRegion()

        region = QRegion()
        threshold = int(max(0, min(255, int(alpha_threshold))))
        for y in range(h):
            row = int(y * stride)
            x = 0
            while x < w:
                while x < w and raw[row + (x * 4) + 3] <= threshold:
                    x += 1
                if x >= w:
                    break
                start = x
                x += 1
                while x < w and raw[row + (x * 4) + 3] > threshold:
                    x += 1
                length = int(x - start)
                if length > 0:
                    region = region.united(QRegion(QRect(int(start), int(y), int(length), 1)))
        return region

    @classmethod
    def _icon_alpha_region_for_item(cls, caption, icon_px):
        size = max(12, min(128, int(icon_px)))
        icon_key, _path, _stock_recycle = cls._desktop_icon_identity(caption)
        cache_key = (icon_key, int(size))
        cached = cls._desktop_icon_alpha_cache.get(cache_key)
        if isinstance(cached, QRegion):
            return QRegion(cached)

        image = cls._icon_image_for_item(caption, int(size))
        if image.isNull():
            region = QRegion()
        else:
            region = cls._alpha_region_from_image(image, alpha_threshold=20)

        cls._desktop_icon_alpha_cache[cache_key] = QRegion(region)
        if len(cls._desktop_icon_alpha_cache) > 320:
            try:
                cls._desktop_icon_alpha_cache.pop(next(iter(cls._desktop_icon_alpha_cache)))
            except Exception:
                pass
        return QRegion(region)

    @classmethod
    def _desktop_icon_title_font(cls):
        now = float(time.monotonic())
        cached = getattr(cls, "_desktop_icon_title_font_cache", None)
        cache_ts = float(getattr(cls, "_desktop_icon_title_font_cache_ts", 0.0) or 0.0)
        if isinstance(cached, QFont) and (now - cache_ts) <= 8.0:
            return QFont(cached)
        font = DesktopIconCloneOverlay._resolve_icon_title_font()
        if not isinstance(font, QFont):
            font = QFont("Segoe UI", 9)
        cls._desktop_icon_title_font_cache = QFont(font)
        cls._desktop_icon_title_font_cache_ts = now
        return QFont(font)

    @classmethod
    def _label_alpha_region(cls, text, size):
        if not isinstance(size, QSize):
            return QRegion()
        w = max(0, int(size.width()))
        h = max(0, int(size.height()))
        label = str(text or "").strip()
        if not label or w <= 0 or h <= 0:
            return QRegion()
        font = cls._desktop_icon_title_font()
        font_key = (
            str(font.family() or ""),
            int(font.pixelSize()),
            float(font.pointSizeF()),
            int(font.weight()),
            bool(font.italic()),
        )
        cache_key = (label, int(w), int(h), font_key)
        cached = cls._desktop_text_alpha_cache.get(cache_key)
        if isinstance(cached, QRegion):
            return QRegion(cached)

        pad_x = 6
        pad_y = 2
        cw = int(max(1, w + (pad_x * 2)))
        ch = int(max(1, h + (pad_y * 2)))
        img = QImage(cw, ch, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)
        flags = int(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
            | Qt.TextFlag.TextDontClip
        )
        draw_rect = QRect(int(pad_x - 4), int(pad_y), int(w + 8), int(h + 2))
        shadow_rect = QRect(draw_rect).translated(1, 1)
        # Include icon-label shadow pixels so only visibly rendered text gets punched.
        painter.setPen(QColor(0, 0, 0, 190))
        painter.drawText(shadow_rect, flags, label)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(draw_rect, flags, label)
        painter.end()

        region = cls._alpha_region_from_image(img, alpha_threshold=20)
        if not region.isEmpty():
            clip_rect = QRect(int(pad_x), int(pad_y), int(w), int(h))
            region = region.intersected(QRegion(clip_rect)).translated(-int(pad_x), -int(pad_y))
        cls._desktop_text_alpha_cache[cache_key] = QRegion(region)
        if len(cls._desktop_text_alpha_cache) > 1024:
            try:
                cls._desktop_text_alpha_cache.pop(next(iter(cls._desktop_text_alpha_cache)))
            except Exception:
                pass
        return QRegion(region)

    def _desktop_icon_clone_items_local(self, force=False):
        if not self._should_clone_desktop_icons():
            return []
        top_left = self._global_top_left()
        wx = int(top_left.x())
        wy = int(top_left.y())
        ww = int(self.width())
        wh = int(self.height())
        if ww <= 0 or wh <= 0:
            return []
        widget_screen_rect = QRect(wx, wy, ww, wh)
        rects_screen = self.__class__._desktop_icon_rects_screen(force=bool(force))
        edit_local_rect = self._desktop_icon_edit_rect_local(force=bool(force))
        edit_screen_rect = QRect()
        if isinstance(edit_local_rect, QRect) and int(edit_local_rect.width()) > 0 and int(edit_local_rect.height()) > 0:
            edit_screen_rect = QRect(edit_local_rect).translated(int(wx), int(wy))
        local_items = []
        for entry in rects_screen:
            if not isinstance(entry, dict):
                continue
            icon_rect = entry.get("icon")
            label_rect = entry.get("label")
            select_rect = entry.get("select")
            editing_this_item = False
            if isinstance(edit_screen_rect, QRect) and int(edit_screen_rect.width()) > 0 and int(edit_screen_rect.height()) > 0:
                probe = QRect()
                if isinstance(icon_rect, QRect):
                    probe = QRect(icon_rect)
                if isinstance(label_rect, QRect):
                    probe = QRect(label_rect) if probe.isNull() else probe.united(QRect(label_rect))
                if isinstance(select_rect, QRect):
                    probe = QRect(select_rect) if probe.isNull() else probe.united(QRect(select_rect))
                if not probe.isNull() and probe.intersects(edit_screen_rect):
                    editing_this_item = True
            caption = str(entry.get("text", "") or "")
            shell_path = str(entry.get("shell_path", "") or "")
            shell_is_folder = bool(entry.get("shell_is_folder", False))
            shell_is_virtual = bool(entry.get("shell_is_virtual", False))
            selected = bool(entry.get("selected", False))
            focused = bool(entry.get("focused", False))
            try:
                image_index = int(entry.get("image_index", -1))
            except Exception:
                image_index = -1
            local_icon = QRect()
            local_label = QRect()
            local_select = QRect()
            local_icon_visible = QRect()
            local_label_visible = QRect()
            if isinstance(icon_rect, QRect):
                icon_hit = icon_rect.intersected(widget_screen_rect)
                if int(icon_hit.width()) > 0 and int(icon_hit.height()) > 0:
                    local_icon_visible = icon_hit.translated(-wx, -wy)
                    local_icon = QRect(icon_rect).translated(-wx, -wy)
            if isinstance(label_rect, QRect):
                label_hit = label_rect.intersected(widget_screen_rect)
                if int(label_hit.width()) > 0 and int(label_hit.height()) > 0:
                    local_label_visible = label_hit.translated(-wx, -wy)
                    local_label = QRect(label_rect).translated(-wx, -wy)
            if isinstance(select_rect, QRect):
                select_hit = select_rect.intersected(widget_screen_rect)
                if int(select_hit.width()) > 0 and int(select_hit.height()) > 0:
                    local_select = select_hit.translated(-wx, -wy)
            if bool(editing_this_item):
                local_select = QRect()
            if int(local_select.width()) <= 0 or int(local_select.height()) <= 0:
                if (bool(selected) or bool(focused)) and not bool(editing_this_item):
                    merged = QRect()
                    if int(local_icon_visible.width()) > 0 and int(local_icon_visible.height()) > 0:
                        merged = QRect(local_icon_visible)
                    if int(local_label_visible.width()) > 0 and int(local_label_visible.height()) > 0:
                        merged = QRect(local_label_visible) if merged.isNull() else merged.united(QRect(local_label_visible))
                    if not merged.isNull() and int(merged.width()) > 0 and int(merged.height()) > 0:
                        local_select = merged.adjusted(-4, -2, 4, 2)
            if (
                (int(local_icon_visible.width()) <= 0 or int(local_icon_visible.height()) <= 0)
                and (int(local_label_visible.width()) <= 0 or int(local_label_visible.height()) <= 0)
            ):
                continue
            icon_side = 0
            if int(local_icon.width()) > 0 and int(local_icon.height()) > 0:
                icon_side = max(12, min(int(local_icon.width()), int(local_icon.height())))
            icon_pixmap = QPixmap()
            if shell_path and os.path.exists(shell_path):
                if shell_is_folder:
                    icon_pixmap = self.__class__._icon_pixmap_for_stock_id(3, int(icon_side or 48))
                else:
                    icon_pixmap = self.__class__._icon_pixmap_for_path(shell_path, int(icon_side or 48))
            elif shell_is_virtual and self.__class__._is_recycle_caption(caption):
                icon_pixmap = self.__class__._icon_pixmap_for_stock_id(31, int(icon_side or 48))
            elif image_index >= 0:
                icon_pixmap = self.__class__._icon_pixmap_for_sys_index(int(image_index), int(icon_side or 48))
            if icon_pixmap.isNull():
                icon_pixmap = self.__class__._icon_pixmap_for_item(caption, int(icon_side or 48))
            if int(local_icon.width()) > 0 and int(local_icon.height()) > 0 and not icon_pixmap.isNull():
                if int(icon_pixmap.width()) != int(icon_side) or int(icon_pixmap.height()) != int(icon_side):
                    icon_pixmap = icon_pixmap.scaled(
                        int(icon_side),
                        int(icon_side),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
            display_text = "" if bool(editing_this_item) else str(caption or "")
            local_items.append(
                {
                    "icon_rect": local_icon,
                    "icon_pixmap": icon_pixmap,
                    "label_rect": local_label,
                    "text": display_text,
                    "select_rect": local_select,
                    "selected": bool(selected) and not bool(editing_this_item),
                    "focused": bool(focused) and not bool(editing_this_item),
                }
            )
        return local_items

    def _desktop_icon_hole_rects_local(self, force=False):
        if not self._should_punch_desktop_icons():
            return []
        top_left = self._global_top_left()
        wx = int(top_left.x())
        wy = int(top_left.y())
        ww = int(self.width())
        wh = int(self.height())
        if ww <= 0 or wh <= 0:
            return []
        widget_screen_rect = QRect(wx, wy, ww, wh)
        widget_local_region = QRegion(QRect(0, 0, int(ww), int(wh)))
        rects_screen = self.__class__._desktop_icon_rects_screen(force=bool(force))
        local_items = []
        for entry in rects_screen:
            if not isinstance(entry, dict):
                continue
            icon_rect = entry.get("icon")
            label_rect = entry.get("label")
            caption = str(entry.get("text", "") or "").strip()
            shell_path = str(entry.get("shell_path", "") or "")
            shell_is_folder = bool(entry.get("shell_is_folder", False))
            shell_is_virtual = bool(entry.get("shell_is_virtual", False))
            try:
                image_index = int(entry.get("image_index", -1))
            except Exception:
                image_index = -1
            icon_region = QRegion()
            text_region = QRegion()

            if isinstance(icon_rect, QRect):
                icon_hit = icon_rect.intersected(widget_screen_rect)
                if int(icon_hit.width()) > 0 and int(icon_hit.height()) > 0:
                    icon_local_full = QRect(icon_rect).translated(-wx, -wy)
                    side = max(12, min(int(icon_local_full.width()), int(icon_local_full.height())))
                    alpha_region = QRegion()
                    if shell_path and os.path.exists(shell_path):
                        if shell_is_folder:
                            image = self.__class__._icon_image_for_stock_id(3, int(side))
                        else:
                            image = self.__class__._icon_image_for_path(shell_path, int(side))
                        if not image.isNull():
                            alpha_region = self.__class__._alpha_region_from_image(image, alpha_threshold=20)
                    elif shell_is_virtual and self.__class__._is_recycle_caption(caption):
                        image = self.__class__._icon_image_for_stock_id(31, int(side))
                        if not image.isNull():
                            alpha_region = self.__class__._alpha_region_from_image(image, alpha_threshold=20)
                    elif image_index >= 0:
                        image = self.__class__._icon_image_for_sys_index(int(image_index), int(side))
                        if not image.isNull():
                            alpha_region = self.__class__._alpha_region_from_image(image, alpha_threshold=20)
                    if alpha_region.isEmpty():
                        alpha_region = self.__class__._icon_alpha_region_for_item(caption, int(side))
                    if not alpha_region.isEmpty():
                        px = int(icon_local_full.x() + ((int(icon_local_full.width()) - int(side)) // 2))
                        py = int(icon_local_full.y() + ((int(icon_local_full.height()) - int(side)) // 2))
                        icon_region = alpha_region.translated(int(px), int(py)).intersected(widget_local_region)
                    if icon_region.isEmpty():
                        fallback_box = QRect(icon_rect).translated(-wx, -wy)
                        fb_side = max(10, min(int(fallback_box.width()), int(fallback_box.height())) - 16)
                        fx = int(fallback_box.x() + ((int(fallback_box.width()) - int(fb_side)) // 2))
                        fy = int(fallback_box.y() + ((int(fallback_box.height()) - int(fb_side)) // 2))
                        fallback = QRect(int(fx), int(fy), int(fb_side), int(fb_side))
                        if int(fallback.width()) > 0 and int(fallback.height()) > 0:
                            path = QPainterPath()
                            rr = max(3.0, min(float(fallback.width()), float(fallback.height())) * 0.16)
                            path.addRoundedRect(QRectF(fallback), rr, rr)
                            icon_region = QRegion(path.toFillPolygon().toPolygon()).intersected(widget_local_region)

            if isinstance(label_rect, QRect):
                label_hit = label_rect.intersected(widget_screen_rect)
                if int(label_hit.width()) > 0 and int(label_hit.height()) > 0:
                    label_local = QRect(label_rect).translated(-wx, -wy)
                    glyph_region = self.__class__._label_alpha_region(caption, label_local.size())
                    if not glyph_region.isEmpty():
                        text_region = glyph_region.translated(
                            int(label_local.x()),
                            int(label_local.y()),
                        ).intersected(widget_local_region)

            if not icon_region.isEmpty() or not text_region.isEmpty():
                local_items.append({"icon_region": icon_region, "label_region": text_region})
        return local_items

    def eventFilter(self, watched, event):
        # App-level key handling for widget-local shortcuts.
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            key = event.key() if hasattr(event, "key") else None
            if key == Qt.Key.Key_Shift and (self._is_cursor_over_widget() or self.is_resizing):
                self._refresh_resize_ui()
            elif (
                event.type() == QEvent.Type.KeyPress
                and key in (
                    Qt.Key.Key_M, Qt.Key.Key_O, Qt.Key.Key_P, Qt.Key.Key_C, Qt.Key.Key_G,
                    Qt.Key.Key_H, Qt.Key.Key_R, Qt.Key.Key_L
                )
                and self._is_topmost_widget_under_cursor()
            ):
                modifiers = event.modifiers() if hasattr(event, "modifiers") else Qt.KeyboardModifier.NoModifier
                ctrl_mod = Qt.KeyboardModifier.ControlModifier
                blocked_mods = ctrl_mod | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier
                is_auto_repeat = event.isAutoRepeat() if hasattr(event, "isAutoRepeat") else False
                if key == Qt.Key.Key_G:
                    only_ctrl = (
                        bool(modifiers & ctrl_mod)
                        and not bool(modifiers & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier))
                    )
                    only_shift = (
                        bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
                        and not bool(modifiers & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier | ctrl_mod))
                    )
                    no_mod = modifiers == Qt.KeyboardModifier.NoModifier
                    if is_auto_repeat:
                        return True
                    if only_ctrl and self._consume_shortcut_once(key, 1):
                        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "clear_temp_group"):
                            self.manager.clear_temp_group()
                        return True
                    if only_shift and self._consume_shortcut_once(key, 2):
                        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "start_marquee_selection"):
                            self.manager.start_marquee_selection(QCursor.pos())
                        return True
                    if no_mod and self._consume_shortcut_once(key, 0):
                        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "toggle_temp_group_member"):
                            self.manager.toggle_temp_group_member(self.profile_id)
                        return True
                    return False
                if (modifiers & blocked_mods) == Qt.KeyboardModifier.NoModifier and not is_auto_repeat:
                    if self._consume_shortcut_once(key, 0):
                        if key == Qt.Key.Key_M:
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "set_temp_group_mute"):
                                self.manager.set_temp_group_mute(self.profile_id, not bool(self.is_muted))
                            else:
                                self.toggle_mute_shortcut()
                        elif key == Qt.Key.Key_O:
                            self.open_settings()
                        elif key == Qt.Key.Key_C:
                            self.open_master_controller()
                        elif key == Qt.Key.Key_P:
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "stop_widget"):
                                QTimer.singleShot(0, lambda pid=self.profile_id: self.manager.stop_widget(pid))
                        elif key == Qt.Key.Key_R:
                            curr_corner = self.coerce_corner_mode(getattr(self, "corner_mode", self.CORNER_ROUNDED))
                            next_corner = (int(curr_corner) + 1) % 3
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "set_temp_group_corner_mode"):
                                self.manager.set_temp_group_corner_mode(self.profile_id, next_corner)
                            else:
                                self.toggle_corner_mode_shortcut()
                        elif key == Qt.Key.Key_L:
                            new_lock = not bool(self.is_locked)
                            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "set_temp_group_lock"):
                                self.manager.set_temp_group_lock(self.profile_id, new_lock)
                            else:
                                if hasattr(self, "cancel_active_interaction"):
                                    self.cancel_active_interaction()
                                self.apply_window_settings(self.layer_mode, new_lock)
                                self.save_all_settings()
                                if hasattr(self, "show_lock_hud"):
                                    self.show_lock_hud(new_lock)
                        return True
            return False

        if not self._is_event_for_this_widget(watched):
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            self.mousePressEvent(event)
            return True
        elif event.type() == QEvent.Type.MouseMove:
            self.mouseMoveEvent(event)
            return True
        elif event.type() == QEvent.Type.MouseButtonRelease:
            self.mouseReleaseEvent(event)
            return True
        elif event.type() == QEvent.Type.Wheel:
            self.wheelEvent(event)
            return True
        elif event.type() == QEvent.Type.ContextMenu:
            self.contextMenuEvent(event)
            return True
        elif event.type() == QEvent.Type.DragEnter:
            self.dragEnterEvent(event)
            return True
        elif event.type() == QEvent.Type.DragMove:
            self.dragMoveEvent(event)
            return True
        elif event.type() == QEvent.Type.Drop:
            self.dropEvent(event)
            return True
        elif event.type() == QEvent.Type.DragLeave:
            self.dragLeaveEvent(event)
            return True
        elif event.type() in (
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.HoverEnter,
            QEvent.Type.HoverLeave,
            QEvent.Type.HoverMove,
        ):
            QTimer.singleShot(0, self._refresh_resize_ui)
            return False
        return super().eventFilter(watched, event)

    def _is_event_for_this_widget(self, watched):
        if watched is self:
            return True
        if isinstance(watched, QWidget):
            return self.isAncestorOf(watched)
        return False

    @staticmethod
    def _extract_first_local_drop_path(event):
        mime = event.mimeData() if event else None
        if not mime or not mime.hasUrls():
            return ""
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if path:
                return os.path.normpath(path)
        return ""

    @staticmethod
    def _supported_media_extensions():
        return tuple(sorted(set(DesktopWidget._image_extensions() + DesktopWidget._video_extensions())))

    @staticmethod
    def _scan_media_paths_for_folder(folder_path):
        folder = str(folder_path or "").strip()
        if not folder or not os.path.isdir(folder):
            return []
        media_ext = tuple(DesktopWidget._supported_media_extensions())
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return []
        paths = []
        for name in names:
            p = os.path.join(folder, str(name))
            if os.path.isfile(p) and str(name).lower().endswith(media_ext):
                paths.append(os.path.normpath(p))
        return paths

    def _apply_drop_target(self, path):
        if not path:
            return False
        if os.path.isdir(path):
            folder_path = os.path.normpath(path)
            media_paths = self._scan_media_paths_for_folder(folder_path)
            if not media_paths:
                QMessageBox.information(
                    self,
                    "미디어 없음",
                    "드롭한 폴더에 지원되는 미디어 파일(이미지, GIF, 동영상)이 없습니다.",
                )
                return False

            choice_dialog = FolderLayoutChoiceDialog(self, folder_path)
            if choice_dialog.exec() != QDialog.DialogCode.Accepted:
                return False

            if choice_dialog.choice == "spread":
                spread_dialog = FolderSpreadDialog(self, folder_path, media_paths, self.size())
                if spread_dialog.exec() != QDialog.DialogCode.Accepted:
                    return False
                if hasattr(self, "manager") and self.manager and hasattr(self.manager, "create_spread_widgets"):
                    return bool(self.manager.create_spread_widgets(
                        self.profile_id,
                        dict(spread_dialog.result_data or {}),
                        origin_widget=self,
                    ))
                return False

            if choice_dialog.choice == "slide":
                slide_dialog = FolderSlideDialog(self, folder_path, media_paths)
                if slide_dialog.exec() != QDialog.DialogCode.Accepted:
                    return False
                chosen_paths = list(slide_dialog.result_paths or [])
                self.folder_path = folder_path
                if len(chosen_paths) == len(media_paths):
                    self.folder_item_paths = []
                else:
                    self.folder_item_paths = chosen_paths
                self._set_watched_folder(folder_path)
                self.update_playlist()
                self.current_idx = -1
                self.next_media()
                self.save_all_settings()
                return True

            self.folder_path = folder_path
            self.folder_item_paths = []
            self._set_watched_folder(folder_path)
            self.update_playlist()
            self.current_idx = -1
            self.next_media()
            self.save_all_settings()
            return True
        if os.path.isfile(path):
            if self._normalize_exec_path(path) != self._normalize_exec_path(getattr(self, "exec_path", "")):
                self._clear_bound_exec_window()
                self._clear_manual_focus_binding(persist=False, clear_bound=False)
            self.exec_path = path
            self.save_all_settings()
            return True
        return False

    @staticmethod
    def _normalize_exec_path(path):
        raw = str(path or "").strip()
        if not raw:
            return ""
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(raw)))
        except Exception:
            return os.path.normcase(raw)

    @staticmethod
    def _resolve_exec_launch_target(path):
        raw = str(path or "").strip()
        if not raw:
            return ""
        if not raw.lower().endswith(".lnk"):
            return raw
        win32com_client = _get_win32com_client()
        if win32com_client is None:
            return raw
        try:
            shell = win32com_client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(raw)
            target = str(getattr(shortcut, "Targetpath", "") or "").strip()
            if target:
                return target
        except Exception:
            pass
        return raw

    @staticmethod
    def _window_thread_and_pid(hwnd):
        try:
            user32 = ctypes.windll.user32
            pid = wintypes.DWORD(0)
            tid = int(user32.GetWindowThreadProcessId(int(hwnd), ctypes.byref(pid)))
            return int(tid), int(pid.value)
        except Exception:
            return 0, 0

    @staticmethod
    def _query_process_image_path(pid):
        try:
            pid_int = int(pid)
        except Exception:
            return ""
        if pid_int <= 0:
            return ""

        process_query_limited_information = 0x1000
        kernel32 = ctypes.windll.kernel32
        try:
            handle = int(kernel32.OpenProcess(int(process_query_limited_information), False, int(pid_int)) or 0)
        except Exception:
            handle = 0
        if not handle:
            return ""

        try:
            query_full = getattr(kernel32, "QueryFullProcessImageNameW", None)
            if query_full is None:
                return ""
            try:
                query_full.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
                query_full.restype = wintypes.BOOL
            except Exception:
                pass
            buf_size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(int(buf_size.value))
            ok = bool(query_full(wintypes.HANDLE(int(handle)), 0, buf, ctypes.byref(buf_size)))
            if ok:
                return str(buf.value or "")
        except Exception:
            return ""
        finally:
            try:
                kernel32.CloseHandle(wintypes.HANDLE(int(handle)))
            except Exception:
                pass
        return ""

    @staticmethod
    def _is_focusable_top_window(hwnd):
        try:
            hwnd_int = int(hwnd or 0)
            if hwnd_int <= 0:
                return False
            if not win32gui.IsWindow(hwnd_int):
                return False
            if not win32gui.IsWindowVisible(hwnd_int):
                return False
            if int(win32gui.GetParent(hwnd_int) or 0) != 0:
                return False
            owner_hwnd = int(win32gui.GetWindow(hwnd_int, win32con.GW_OWNER) or 0)
            ex_style = int(win32gui.GetWindowLong(hwnd_int, win32con.GWL_EXSTYLE) or 0)
            is_appwindow = bool(ex_style & int(win32con.WS_EX_APPWINDOW))
            if owner_hwnd != 0 and not is_appwindow:
                return False
            if (ex_style & int(win32con.WS_EX_TOOLWINDOW)) and not is_appwindow:
                return False
            return True
        except Exception:
            return False

    def _enumerate_focusable_windows(self):
        windows = []

        def _enum_window(hwnd, _lparam):
            try:
                if self._is_focusable_top_window(hwnd):
                    windows.append(int(hwnd))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(_enum_window, None)
        except Exception:
            pass
        return windows

    @staticmethod
    def _snapshot_process_ids():
        pids = set()
        try:
            kernel32 = ctypes.windll.kernel32
        except Exception:
            return pids

        th32cs_snprocess = 0x00000002
        max_path = 260
        invalid_handle_value = -1

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * max_path),
            ]

        try:
            kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
            kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
            kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
            kernel32.Process32FirstW.restype = wintypes.BOOL
            kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
            kernel32.Process32NextW.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
        except Exception:
            pass

        snap = None
        try:
            snap = kernel32.CreateToolhelp32Snapshot(int(th32cs_snprocess), 0)
            if snap is None or int(snap) == int(invalid_handle_value):
                return pids
            entry = PROCESSENTRY32W()
            entry.dwSize = int(ctypes.sizeof(PROCESSENTRY32W))
            ok = bool(kernel32.Process32FirstW(snap, ctypes.byref(entry)))
            while ok:
                try:
                    pid = int(entry.th32ProcessID)
                    if pid > 0:
                        pids.add(int(pid))
                except Exception:
                    pass
                ok = bool(kernel32.Process32NextW(snap, ctypes.byref(entry)))
        except Exception:
            pass
        finally:
            if snap not in (None, 0, int(invalid_handle_value)):
                try:
                    kernel32.CloseHandle(wintypes.HANDLE(int(snap)))
                except Exception:
                    pass
        return pids

    @staticmethod
    def _snapshot_process_name_map():
        name_map = {}
        try:
            kernel32 = ctypes.windll.kernel32
        except Exception:
            return name_map

        th32cs_snprocess = 0x00000002
        max_path = 260
        invalid_handle_value = -1

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * max_path),
            ]

        try:
            kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
            kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
            kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
            kernel32.Process32FirstW.restype = wintypes.BOOL
            kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
            kernel32.Process32NextW.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
        except Exception:
            pass

        snap = None
        try:
            snap = kernel32.CreateToolhelp32Snapshot(int(th32cs_snprocess), 0)
            if snap is None or int(snap) == int(invalid_handle_value):
                return name_map
            entry = PROCESSENTRY32W()
            entry.dwSize = int(ctypes.sizeof(PROCESSENTRY32W))
            ok = bool(kernel32.Process32FirstW(snap, ctypes.byref(entry)))
            while ok:
                try:
                    pid = int(entry.th32ProcessID)
                    name = str(entry.szExeFile or "").strip().lower()
                    if pid > 0 and name:
                        name_map[int(pid)] = str(name)
                except Exception:
                    pass
                ok = bool(kernel32.Process32NextW(snap, ctypes.byref(entry)))
        except Exception:
            pass
        finally:
            if snap not in (None, 0, int(invalid_handle_value)):
                try:
                    kernel32.CloseHandle(wintypes.HANDLE(int(snap)))
                except Exception:
                    pass
        return name_map

    @staticmethod
    def _format_exec_manual_focus_summary(enabled, proc_path="", proc_name="", title_hint="", class_name=""):
        if not bool(enabled):
            return "자동 (실행파일 기준)"
        target = ""
        path_norm = str(proc_path or "").strip()
        if path_norm:
            target = str(os.path.basename(path_norm) or "").strip()
        if not target:
            target = str(proc_name or "").strip()
        if not target:
            target = "미지정"
        details = []
        class_txt = str(class_name or "").strip()
        if class_txt:
            details.append(class_txt)
        title_txt = str(title_hint or "").strip()
        if title_txt:
            if len(title_txt) > 34:
                title_txt = f"{title_txt[:31]}..."
            details.append(title_txt)
        if details:
            return f"수동: {target} ({' / '.join(details)})"
        return f"수동: {target}"

    def get_exec_manual_focus_summary(self):
        return self._format_exec_manual_focus_summary(
            bool(getattr(self, "_exec_manual_focus_enabled", False)),
            getattr(self, "_exec_manual_focus_proc_path", ""),
            getattr(self, "_exec_manual_focus_proc_name", ""),
            getattr(self, "_exec_manual_focus_title", ""),
            getattr(self, "_exec_manual_focus_class", ""),
        )

    @staticmethod
    def _normalize_window_text_for_match(text):
        return " ".join(str(text or "").strip().lower().split())

    def _build_exec_manual_focus_signature_from_hwnd(self, hwnd):
        hwnd_int = int(hwnd or 0)
        if hwnd_int <= 0:
            return {}
        if not self._is_focusable_top_window(hwnd_int):
            return {}
        _tid, pid = self._window_thread_and_pid(hwnd_int)
        if pid <= 0 or int(pid) == int(os.getpid()):
            return {}

        proc_path = self._normalize_exec_path(self._query_process_image_path(pid))
        proc_name = str(os.path.basename(proc_path) or "").strip().lower()
        if not proc_name:
            try:
                proc_name = str(self._snapshot_process_name_map().get(int(pid), "") or "").strip().lower()
            except Exception:
                proc_name = ""

        try:
            class_name = str(win32gui.GetClassName(hwnd_int) or "").strip()
        except Exception:
            class_name = ""
        try:
            title_hint = str(win32gui.GetWindowText(hwnd_int) or "").strip()
        except Exception:
            title_hint = ""

        if not proc_path and not proc_name and not class_name:
            return {}

        return {
            "enabled": True,
            "proc_path": str(proc_path or ""),
            "proc_name": str(proc_name or ""),
            "title_hint": str(title_hint or ""),
            "class_name": str(class_name or ""),
        }

    def _apply_exec_manual_focus_signature(self, sig, persist=False):
        data = sig if isinstance(sig, dict) else {}
        proc_path = self._normalize_exec_path(data.get("proc_path", ""))
        proc_name = str(data.get("proc_name", "") or "").strip().lower()
        title_hint = str(data.get("title_hint", "") or "").strip()
        class_name = str(data.get("class_name", "") or "").strip()
        enabled = bool(data.get("enabled", False))
        if not (proc_path or proc_name or (class_name and title_hint)):
            enabled = False
            proc_path = ""
            proc_name = ""
            title_hint = ""
            class_name = ""
        self._exec_manual_focus_enabled = bool(enabled)
        self._exec_manual_focus_proc_path = str(proc_path or "")
        self._exec_manual_focus_proc_name = str(proc_name or "")
        self._exec_manual_focus_title = str(title_hint or "")
        self._exec_manual_focus_class = str(class_name or "")
        if bool(persist):
            self.save_all_settings()
        return bool(self._exec_manual_focus_enabled)

    def _set_manual_focus_binding_from_hwnd(self, hwnd, persist=True):
        sig = self._build_exec_manual_focus_signature_from_hwnd(hwnd)
        if not sig:
            return False
        if not self._apply_exec_manual_focus_signature(sig, persist=False):
            return False
        self._bind_exec_window(int(hwnd))
        if bool(persist):
            self.save_all_settings()
        return True

    def _clear_manual_focus_binding(self, persist=True, clear_bound=False):
        if bool(clear_bound):
            self._clear_bound_exec_window()
        self._exec_manual_focus_enabled = False
        self._exec_manual_focus_proc_path = ""
        self._exec_manual_focus_proc_name = ""
        self._exec_manual_focus_title = ""
        self._exec_manual_focus_class = ""
        if bool(persist):
            self.save_all_settings()

    def _capture_bindable_foreground_hwnd(self):
        try:
            hwnd = int(win32gui.GetForegroundWindow() or 0)
        except Exception:
            return 0
        if hwnd <= 0:
            return 0
        if not self._is_focusable_top_window(hwnd):
            return 0
        _tid, pid = self._window_thread_and_pid(hwnd)
        if pid <= 0 or int(pid) == int(os.getpid()):
            return 0
        return int(hwnd)

    def _find_running_window_for_manual_binding(self, only_unclaimed=False):
        if not bool(getattr(self, "_exec_manual_focus_enabled", False)):
            return 0

        target_path = self._normalize_exec_path(getattr(self, "_exec_manual_focus_proc_path", ""))
        target_name = str(getattr(self, "_exec_manual_focus_proc_name", "") or "").strip().lower()
        target_title = self._normalize_window_text_for_match(getattr(self, "_exec_manual_focus_title", ""))
        target_class = str(getattr(self, "_exec_manual_focus_class", "") or "").strip().lower()
        if not (target_path or target_name or (target_class and target_title)):
            return 0

        current_pid = int(os.getpid())
        pid_name_map = self._snapshot_process_name_map()
        try:
            foreground_hwnd = int(win32gui.GetForegroundWindow() or 0)
        except Exception:
            foreground_hwnd = 0

        candidates = []
        for hwnd_int in self._enumerate_focusable_windows():
            try:
                _tid, pid = self._window_thread_and_pid(hwnd_int)
                if pid <= 0 or pid == current_pid:
                    continue
                owner = self._exec_window_owner_for(hwnd_int)
                if bool(only_unclaimed) and owner and owner != str(self.profile_id):
                    continue

                proc_path = self._query_process_image_path(pid)
                proc_norm = self._normalize_exec_path(proc_path)
                proc_name = str(os.path.basename(proc_norm) or "").strip().lower()
                if not proc_name:
                    proc_name = str(pid_name_map.get(int(pid), "") or "").strip().lower()

                try:
                    class_name = str(win32gui.GetClassName(hwnd_int) or "").strip().lower()
                except Exception:
                    class_name = ""
                try:
                    title = self._normalize_window_text_for_match(win32gui.GetWindowText(hwnd_int))
                except Exception:
                    title = ""

                path_match = bool(target_path and proc_norm and proc_norm == target_path)
                name_match = bool(target_name and proc_name == target_name)
                class_match = bool(target_class and class_name == target_class)
                title_match = bool(target_title and title and (target_title in title or title in target_title))
                primary_match = bool(path_match or name_match)
                secondary_match = bool(class_match and (title_match or not target_title))
                if not primary_match and not secondary_match:
                    continue

                ex_style = int(win32gui.GetWindowLong(hwnd_int, win32con.GWL_EXSTYLE) or 0)
                score = 0
                if owner == str(self.profile_id):
                    score += 220
                elif not owner:
                    score += 110
                if path_match:
                    score += 260
                elif name_match:
                    score += 170
                if class_match:
                    score += 34
                if title_match:
                    score += 24
                if hwnd_int == foreground_hwnd:
                    score += 100
                if not bool(win32gui.IsIconic(hwnd_int)):
                    score += 20
                if ex_style & int(win32con.WS_EX_APPWINDOW):
                    score += 3
                if str(win32gui.GetWindowText(hwnd_int) or "").strip():
                    score += 5
                candidates.append((int(score), int(hwnd_int)))
            except Exception:
                continue

        if not candidates:
            return 0
        candidates.sort(key=lambda x: (int(x[0]), int(x[1])), reverse=True)
        return int(candidates[0][1])

    def _exec_window_owner_for(self, hwnd):
        if not (hasattr(self, "manager") and self.manager and hasattr(self.manager, "get_exec_window_owner")):
            return ""
        try:
            return str(self.manager.get_exec_window_owner(int(hwnd)) or "")
        except Exception:
            return ""

    def _claim_exec_window(self, hwnd):
        if not (hasattr(self, "manager") and self.manager and hasattr(self.manager, "claim_exec_window")):
            return True
        try:
            return bool(self.manager.claim_exec_window(self.profile_id, int(hwnd)))
        except Exception:
            return False

    def _release_exec_window_claim(self, hwnd=None):
        if not (hasattr(self, "manager") and self.manager and hasattr(self.manager, "release_exec_window_claim")):
            return
        try:
            if hwnd is None:
                self.manager.release_exec_window_claim(profile_id=self.profile_id)
            else:
                self.manager.release_exec_window_claim(profile_id=self.profile_id, hwnd=int(hwnd))
        except Exception:
            pass

    @staticmethod
    def _is_launcher_like_process(proc_name):
        name = str(proc_name or "").strip().lower()
        if not name:
            return False
        hard_block = {
            "update.exe",
            "updater.exe",
            "launcher.exe",
            "launchpad.exe",
            "start_protected_game.exe",
            "steam.exe",
            "epicgameslauncher.exe",
            "battle.net.exe",
            "riotclientservices.exe",
        }
        if name in hard_block:
            return True
        return ("launcher" in name) or ("updater" in name) or ("update" in name) or ("patcher" in name) or ("bootstrap" in name)

    def _bind_exec_window(self, hwnd):
        hwnd_int = int(hwnd or 0)
        if hwnd_int <= 0:
            return False
        if not self._is_focusable_top_window(hwnd_int):
            return False
        if not self._claim_exec_window(hwnd_int):
            return False
        old_hwnd = int(getattr(self, "_exec_bound_hwnd", 0) or 0)
        if old_hwnd > 0 and old_hwnd != hwnd_int:
            self._release_exec_window_claim(old_hwnd)
        self._exec_bound_hwnd = int(hwnd_int)
        _tid, pid = self._window_thread_and_pid(hwnd_int)
        self._exec_bound_pid = int(pid)
        return True

    def _clear_bound_exec_window(self):
        self._stop_exec_launch_learning()
        old_hwnd = int(getattr(self, "_exec_bound_hwnd", 0) or 0)
        self._exec_bound_hwnd = 0
        self._exec_bound_pid = 0
        if old_hwnd > 0:
            self._release_exec_window_claim(old_hwnd)

    def _focus_bound_exec_window(self):
        hwnd = int(getattr(self, "_exec_bound_hwnd", 0) or 0)
        if hwnd <= 0:
            return False
        if not self._is_focusable_top_window(hwnd):
            self._clear_bound_exec_window()
            return False
        owner = self._exec_window_owner_for(hwnd)
        if owner and owner != str(self.profile_id):
            self._clear_bound_exec_window()
            return False
        if not self._bind_exec_window(hwnd):
            return False
        return bool(self._focus_window_hwnd(hwnd))

    def _find_running_window_for_exec(self, exec_path, only_unclaimed=False):
        launch_target = self._resolve_exec_launch_target(exec_path)
        target_norm = self._normalize_exec_path(launch_target)
        target_name = str(os.path.basename(target_norm or launch_target) or "").strip().lower()
        if not target_norm and not target_name:
            return 0

        current_pid = int(os.getpid())
        pid_name_map = self._snapshot_process_name_map()
        try:
            foreground_hwnd = int(win32gui.GetForegroundWindow() or 0)
        except Exception:
            foreground_hwnd = 0

        candidates = []

        for hwnd_int in self._enumerate_focusable_windows():
            try:
                _tid, pid = self._window_thread_and_pid(hwnd_int)
                if pid <= 0 or pid == current_pid:
                    continue
                owner = self._exec_window_owner_for(hwnd_int)
                if bool(only_unclaimed) and owner and owner != str(self.profile_id):
                    continue
                proc_path = self._query_process_image_path(pid)
                proc_norm = self._normalize_exec_path(proc_path)
                proc_name = str(os.path.basename(proc_norm) or "").strip().lower()
                if not proc_name:
                    proc_name = str(pid_name_map.get(int(pid), "") or "").strip().lower()
                matched = bool(target_norm and proc_norm and proc_norm == target_norm)
                if not matched and target_name:
                    matched = str(proc_name) == target_name
                if not matched:
                    continue

                ex_style = int(win32gui.GetWindowLong(hwnd_int, win32con.GWL_EXSTYLE) or 0)
                score = 0
                if owner == str(self.profile_id):
                    score += 220
                elif not owner:
                    score += 110
                if hwnd_int == foreground_hwnd:
                    score += 100
                if not bool(win32gui.IsIconic(hwnd_int)):
                    score += 20
                if str(win32gui.GetWindowText(hwnd_int) or "").strip():
                    score += 5
                if ex_style & int(win32con.WS_EX_APPWINDOW):
                    score += 2
                candidates.append((int(score), int(hwnd_int)))
            except Exception:
                continue

        if not candidates:
            return 0
        candidates.sort(key=lambda x: (int(x[0]), int(x[1])), reverse=True)
        return int(candidates[0][1])

    def _collect_exec_learning_candidates(self, exec_path, baseline_pids, baseline_hwnds):
        launch_target = self._resolve_exec_launch_target(exec_path)
        target_norm = self._normalize_exec_path(launch_target)
        target_name = str(os.path.basename(target_norm or launch_target) or "").strip().lower()
        current_pid = int(os.getpid())
        pid_name_map = self._snapshot_process_name_map()
        try:
            foreground_hwnd = int(win32gui.GetForegroundWindow() or 0)
        except Exception:
            foreground_hwnd = 0

        current_pids = self._snapshot_process_ids()
        new_pids = set([int(pid) for pid in current_pids if int(pid) not in set(baseline_pids or set())])
        base_hwnds = set([int(h) for h in (baseline_hwnds or set())])
        out = []

        for hwnd_int in self._enumerate_focusable_windows():
            try:
                _tid, pid = self._window_thread_and_pid(hwnd_int)
                if pid <= 0 or pid == current_pid:
                    continue
                owner = self._exec_window_owner_for(hwnd_int)
                if owner and owner != str(self.profile_id):
                    continue

                proc_path = self._query_process_image_path(pid)
                proc_norm = self._normalize_exec_path(proc_path)
                proc_name = str(os.path.basename(proc_norm) or "").strip().lower()
                if not proc_name:
                    proc_name = str(pid_name_map.get(int(pid), "") or "").strip().lower()
                is_match_path = bool(target_norm and proc_norm and proc_norm == target_norm)
                is_match_name = bool(target_name and proc_name == target_name)
                is_new_pid = int(pid) in new_pids
                is_new_hwnd = int(hwnd_int) not in base_hwnds

                if not (is_match_path or is_match_name or is_new_pid or is_new_hwnd):
                    continue

                launcher_like = self._is_launcher_like_process(proc_name)
                ex_style = int(win32gui.GetWindowLong(hwnd_int, win32con.GWL_EXSTYLE) or 0)
                score = 0
                if is_match_path:
                    score += 220
                elif is_match_name:
                    score += 160
                if is_new_pid:
                    score += 120
                if is_new_hwnd:
                    score += 45
                if hwnd_int == foreground_hwnd:
                    score += 90
                if not bool(win32gui.IsIconic(hwnd_int)):
                    score += 20
                if str(win32gui.GetWindowText(hwnd_int) or "").strip():
                    score += 18
                if ex_style & int(win32con.WS_EX_APPWINDOW):
                    score += 2
                if launcher_like:
                    score -= 100
                out.append({
                    "hwnd": int(hwnd_int),
                    "score": int(score),
                    "launcher_like": bool(launcher_like),
                })
            except Exception:
                continue

        out.sort(key=lambda item: (int(item.get("score", 0)), int(item.get("hwnd", 0))), reverse=True)
        return out

    def _start_exec_launch_learning(self, exec_path, baseline_pids, baseline_hwnds):
        self._stop_exec_launch_learning()
        self._exec_launch_learning = {
            "exec_path": str(exec_path or ""),
            "baseline_pids": set([int(pid) for pid in (baseline_pids or set())]),
            "baseline_hwnds": set([int(hwnd) for hwnd in (baseline_hwnds or set())]),
            "deadline": float(time.monotonic()) + 26.0,
            "best_hwnd": 0,
            "best_score": -10**9,
            "best_launcher_like": True,
        }
        if hasattr(self, "_exec_launch_learn_timer"):
            self._exec_launch_learn_timer.start()
        QTimer.singleShot(180, self._on_exec_launch_learn_tick)

    def _stop_exec_launch_learning(self):
        if hasattr(self, "_exec_launch_learn_timer") and self._exec_launch_learn_timer.isActive():
            self._exec_launch_learn_timer.stop()
        self._exec_launch_learning = None

    def _on_exec_launch_learn_tick(self):
        state = getattr(self, "_exec_launch_learning", None)
        if not isinstance(state, dict):
            self._stop_exec_launch_learning()
            return

        exec_path = str(state.get("exec_path", "") or "")
        if not exec_path:
            self._stop_exec_launch_learning()
            return

        candidates = self._collect_exec_learning_candidates(
            exec_path,
            baseline_pids=state.get("baseline_pids", set()),
            baseline_hwnds=state.get("baseline_hwnds", set()),
        )
        if candidates:
            best = candidates[0]
            best_hwnd = int(best.get("hwnd", 0) or 0)
            best_score = int(best.get("score", -10**9) or -10**9)
            best_launcher_like = bool(best.get("launcher_like", True))
            if best_hwnd > 0:
                prev_score = int(state.get("best_score", -10**9))
                prev_launcher = bool(state.get("best_launcher_like", True))
                replace = False
                if best_launcher_like != prev_launcher:
                    replace = (not best_launcher_like)  # Non-launcher outranks launcher.
                elif best_score > prev_score:
                    replace = True
                if replace or int(state.get("best_hwnd", 0) or 0) <= 0:
                    state["best_hwnd"] = int(best_hwnd)
                    state["best_score"] = int(best_score)
                    state["best_launcher_like"] = bool(best_launcher_like)
                if not best_launcher_like and best_score >= 120:
                    if self._bind_exec_window(best_hwnd):
                        self._stop_exec_launch_learning()
                        return

        if float(time.monotonic()) >= float(state.get("deadline", 0.0)):
            fallback_hwnd = int(state.get("best_hwnd", 0) or 0)
            if fallback_hwnd > 0:
                self._bind_exec_window(fallback_hwnd)
            self._stop_exec_launch_learning()


    def _focus_window_hwnd(self, hwnd):
        hwnd_int = int(hwnd or 0)
        if hwnd_int <= 0:
            return False
        try:
            if not win32gui.IsWindow(hwnd_int):
                return False
        except Exception:
            return False

        try:
            if bool(win32gui.IsIconic(hwnd_int)):
                win32gui.ShowWindow(hwnd_int, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd_int, win32con.SW_SHOW)
        except Exception:
            pass
        # Taskbar-like raise: temporary topmost toggle to pull the target above overlays/fullscreen surfaces.
        try:
            z_flags = int(win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
            win32gui.SetWindowPos(hwnd_int, int(win32con.HWND_TOPMOST), 0, 0, 0, 0, z_flags)
            win32gui.SetWindowPos(hwnd_int, int(win32con.HWND_NOTOPMOST), 0, 0, 0, 0, z_flags)
        except Exception:
            pass
        try:
            win32gui.BringWindowToTop(hwnd_int)
        except Exception:
            pass
        try:
            win32gui.SetForegroundWindow(hwnd_int)
            try:
                if int(win32gui.GetForegroundWindow() or 0) == int(hwnd_int):
                    return True
            except Exception:
                pass
        except Exception:
            pass

        # Foreground lock fallback.
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            current_tid = int(kernel32.GetCurrentThreadId())
            fg_hwnd = int(user32.GetForegroundWindow() or 0)
            fg_tid, _ = self._window_thread_and_pid(fg_hwnd)
            target_tid, _ = self._window_thread_and_pid(hwnd_int)
            attached_pairs = []
            if fg_tid and fg_tid != current_tid:
                if bool(user32.AttachThreadInput(int(fg_tid), int(current_tid), True)):
                    attached_pairs.append((int(fg_tid), int(current_tid)))
            if target_tid and target_tid != current_tid:
                if bool(user32.AttachThreadInput(int(target_tid), int(current_tid), True)):
                    attached_pairs.append((int(target_tid), int(current_tid)))
            try:
                try:
                    user32.ShowWindow(int(hwnd_int), int(win32con.SW_RESTORE))
                except Exception:
                    pass
                user32.BringWindowToTop(int(hwnd_int))
                user32.SetForegroundWindow(int(hwnd_int))
                user32.SetFocus(int(hwnd_int))
                user32.SetActiveWindow(int(hwnd_int))
                try:
                    switch_to_this = getattr(user32, "SwitchToThisWindow", None)
                    if switch_to_this is not None:
                        switch_to_this.argtypes = [wintypes.HWND, wintypes.BOOL]
                        switch_to_this.restype = None
                        switch_to_this(wintypes.HWND(int(hwnd_int)), True)
                except Exception:
                    pass
            finally:
                for a_tid, b_tid in reversed(attached_pairs):
                    try:
                        user32.AttachThreadInput(int(a_tid), int(b_tid), False)
                    except Exception:
                        pass
            try:
                # Alt key trick can relax foreground restrictions in some game/launcher combinations.
                user32.keybd_event(int(win32con.VK_MENU), 0, 0, 0)
                user32.keybd_event(int(win32con.VK_MENU), 0, int(win32con.KEYEVENTF_KEYUP), 0)
                user32.SetForegroundWindow(int(hwnd_int))
            except Exception:
                pass
            try:
                z_flags = int(win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                win32gui.SetWindowPos(hwnd_int, int(win32con.HWND_TOPMOST), 0, 0, 0, 0, z_flags)
                win32gui.SetWindowPos(hwnd_int, int(win32con.HWND_NOTOPMOST), 0, 0, 0, 0, z_flags)
            except Exception:
                pass
            try:
                return int(win32gui.GetForegroundWindow() or 0) == int(hwnd_int)
            except Exception:
                try:
                    return bool(win32gui.IsWindowVisible(hwnd_int)) and not bool(win32gui.IsIconic(hwnd_int))
                except Exception:
                    return True
        except Exception:
            return False

    def _launch_or_focus_exec(self, exec_path):
        path = str(exec_path or "").strip()
        if self._focus_bound_exec_window():
            return True

        hwnd = self._find_running_window_for_manual_binding(only_unclaimed=True)
        if int(hwnd) > 0 and self._bind_exec_window(hwnd):
            self._stop_exec_launch_learning()
            return bool(self._focus_window_hwnd(hwnd))

        hwnd = self._find_running_window_for_manual_binding(only_unclaimed=False)
        if int(hwnd) > 0:
            owner = self._exec_window_owner_for(hwnd)
            if owner in ("", str(self.profile_id)):
                if self._bind_exec_window(hwnd):
                    self._stop_exec_launch_learning()
                    return bool(self._focus_window_hwnd(hwnd))

        if not path:
            return False

        hwnd = self._find_running_window_for_exec(path, only_unclaimed=True)
        if int(hwnd) > 0 and self._bind_exec_window(hwnd):
            self._stop_exec_launch_learning()
            return bool(self._focus_window_hwnd(hwnd))

        hwnd = self._find_running_window_for_exec(path, only_unclaimed=False)
        if int(hwnd) > 0:
            owner = self._exec_window_owner_for(hwnd)
            if owner in ("", str(self.profile_id)):
                if self._bind_exec_window(hwnd):
                    self._stop_exec_launch_learning()
                    return bool(self._focus_window_hwnd(hwnd))

        pre_pids = self._snapshot_process_ids()
        pre_hwnds = set(self._enumerate_focusable_windows())
        try:
            os.startfile(path)
            self._start_exec_launch_learning(path, pre_pids, pre_hwnds)
            return True
        except Exception as e:
            print(f"[exec-open-failed] profile={self.profile_id} path={path} error={e}")
            return False

    def _is_shift_down(self):
        return bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)

    def _consume_shortcut_once(self, key, modifier_bucket=0):
        now_ms = QDateTime.currentMSecsSinceEpoch()
        token = f"{int(key)}:{int(modifier_bucket)}"
        last_ms = int(self._shortcut_last_ms.get(token, 0))
        if (now_ms - last_ms) <= 120:
            return False
        self._shortcut_last_ms[token] = now_ms
        return True

    def _is_topmost_widget_under_cursor(self):
        pos = QCursor.pos()
        top_widget = QApplication.widgetAt(pos)
        while top_widget is not None:
            if top_widget is self:
                return True
            if isinstance(top_widget, DesktopWidget):
                return top_widget is self
            top_widget = top_widget.parentWidget()

        # Fallback for native/transparent edge cases.
        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "_widget_under_global_pos"):
            return self.manager._widget_under_global_pos(pos) is self
        return self.geometry().contains(pos)

    def _place_group_badge(self):
        if not hasattr(self, "group_badge"):
            return
        self.group_badge.adjustSize()
        margin = 10
        x = margin
        y = margin
        self.group_badge.move(x, y)

    def _refresh_group_badge(self):
        is_grouped = False
        if hasattr(self, "manager") and self.manager and hasattr(self.manager, "is_temp_group_member"):
            is_grouped = bool(self.manager.is_temp_group_member(self.profile_id))
        if is_grouped:
            self._place_group_badge()
            self.group_badge.show()
            self.group_badge.raise_()
        else:
            self.group_badge.hide()

    def _set_audio_output_attached(self, attach):
        if attach:
            self._audio_output_attached = True
            # Audio routing refresh should not interrupt an in-flight video crossfade.
            self._set_video_active_slot(int(getattr(self, "_video_active_slot", 0)), update_visual=False)
        else:
            for p in self._video_players():
                try:
                    p.setAudioOutput(None)
                except Exception:
                    pass
            self._audio_output_attached = False

    def _apply_mute_state(self, force_refresh=False):
        if self.is_muted:
            current_volume = float(self.audio_output.volume())
            if current_volume > 0.001:
                self._last_unmuted_volume = current_volume
            if not self._audio_output_attached:
                self._set_audio_output_attached(True)
            self.audio_output.setMuted(True)
            self.audio_output.setVolume(0.0)
            return

        if force_refresh:
            self._set_audio_output_attached(True)
        elif not self._audio_output_attached:
            self._set_audio_output_attached(True)
        restore_volume = float(getattr(self, "_last_unmuted_volume", 1.0))
        if restore_volume <= 0.001:
            restore_volume = 1.0
        restore_volume = max(0.0, min(1.0, restore_volume))
        self.audio_output.setVolume(restore_volume)
        self.audio_output.setMuted(False)
        if force_refresh and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            pos = self.media_player.position()
            self.media_player.play()
            if pos >= 0:
                self.media_player.setPosition(pos)

    def set_mute_shortcut_state(self, muted, log=False):
        self.is_muted = bool(muted)
        self._apply_mute_state(force_refresh=True)
        self.save_all_settings()
        # keep `log` arg for compatibility with existing call sites.
        _ = bool(log)

    def toggle_mute_shortcut(self):
        self.set_mute_shortcut_state(not bool(self.is_muted), log=True)

    def set_gpu_guard_shortcut_state(self, enabled, log=False, show_hud=False):
        pass

    def toggle_gpu_guard_shortcut(self):
        pass

    def set_corner_mode_shortcut_state(self, mode, log=False):
        mode_int = self.coerce_corner_mode(mode)
        self.corner_mode = mode_int
        self.apply_mask_and_style()
        self.save_all_settings()
        _ = bool(log)

    def toggle_corner_mode_shortcut(self):
        curr = self.coerce_corner_mode(getattr(self, "corner_mode", self.CORNER_ROUNDED))
        self.set_corner_mode_shortcut_state((int(curr) + 1) % 3, log=True)

    def set_performance_paused(self, paused, reason="", force=False):
        paused = bool(paused)
        if paused == self._performance_paused and not force:
            return

        self._performance_paused = paused
        if paused:
            self._perf_paused_video = False
            self._perf_paused_gif = False
            self._perf_gif_timer_was_active = False

            if self.stack.currentIndex() == 2:
                for player in self._video_players():
                    try:
                        if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                            player.pause()
                            self._perf_paused_video = True
                    except Exception:
                        continue
                self._cancel_video_crossfade()
                self._cancel_video_dual_pending(clear_source=True)
            elif self.stack.currentIndex() == 1 and self.movie is not None:
                if self.movie.state() == QMovie.MovieState.Running:
                    self.movie.setPaused(True)
                    self._perf_paused_gif = True
                if self.timer.isActive():
                    self.timer.stop()
                    self._perf_gif_timer_was_active = True

            return

        if self.stack.currentIndex() == 2:
            try:
                if self._perf_paused_video or self.media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
                    self.media_player.play()
            except Exception:
                pass
        elif self.stack.currentIndex() == 1 and self.movie is not None:
            try:
                self.movie.setPaused(False)
                if self.movie.state() != QMovie.MovieState.Running:
                    self.movie.start()
            except Exception:
                pass
        if (self._perf_gif_timer_was_active or not self.timer.isActive()) and self.stack.currentIndex() == 1 and self.movie is not None:
            if not self.timer.isActive():
                self.timer.start(self.interval_ms)

        self._perf_paused_video = False
        self._perf_paused_gif = False
        self._perf_gif_timer_was_active = False

    def _is_cursor_over_widget(self):
        if not self.isVisible():
            return False
        local = self.mapFromGlobal(QCursor.pos())
        return self.rect().contains(local)

    def _corner_rects(self):
        s = self.resize_overlay.handle_size
        m = self.resize_overlay.handle_margin
        w = max(0, self.width() - s - m)
        h = max(0, self.height() - s - m)
        return {
            "tl": QRect(m, m, s, s),
            "tr": QRect(w, m, s, s),
            "bl": QRect(m, h, s, s),
            "br": QRect(w, h, s, s),
        }

    def _corner_hit_test(self, local_pos):
        if local_pos is None:
            return None
        if not self.rect().contains(local_pos):
            return None

        for corner, rect in self._corner_rects().items():
            hit_box = rect.adjusted(-4, -4, 4, 4)
            if hit_box.contains(local_pos):
                return corner
        return None

    def _set_resize_cursor(self, corner):
        if corner in ("tl", "br"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif corner in ("tr", "bl"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def _refresh_resize_ui(self):
        self._cursor_inside = self._is_cursor_over_widget()
        show_handles = (
            (self._cursor_inside and self._is_shift_down() and not getattr(self, "is_locked", False))
            or self.is_resizing
        )

        if show_handles:
            self.resize_overlay.setGeometry(self.rect())
            self.resize_overlay.show()
            self.resize_overlay.raise_()
            if not self.is_resizing:
                local = self.mapFromGlobal(QCursor.pos())
                corner = self._corner_hit_test(local)
                self._set_resize_cursor(corner)
        else:
            self.resize_overlay.hide()
            if not self.is_resizing:
                self.unsetCursor()

    def _refresh_size_hud(self):
        text = f"{self.width()} x {self.height()}"
        self.size_hud.setText(text)
        fm = QFontMetrics(self.size_hud.font())
        hud_w = max(80, fm.horizontalAdvance(text) + 26)
        hud_h = max(24, fm.height() + 12)
        self.size_hud.resize(hud_w, hud_h)
        hud_x = max(0, (self.width() - hud_w) // 2)
        self.size_hud.move(hud_x, self._size_hud_top_padding)
        self.size_hud.raise_()

    def _show_size_hud(self):
        self._refresh_size_hud()
        self.size_hud.show()

    def _hide_size_hud(self):
        self.size_hud.hide()

    def _refresh_action_hud(self):
        if not hasattr(self, "action_hud"):
            return
        text = self.action_hud.text()
        if not text:
            return
        fm = QFontMetrics(self.action_hud.font())
        hud_w = max(92, fm.horizontalAdvance(text) + 24)
        hud_h = max(22, fm.height() + 10)
        self.action_hud.resize(hud_w, hud_h)
        hud_x = max(0, (self.width() - hud_w) // 2)
        self.action_hud.move(hud_x, self._size_hud_top_padding)
        self.action_hud.raise_()

    def _show_action_hud(self, text, timeout_ms=1200):
        if not hasattr(self, "action_hud"):
            return
        self.action_hud.setText(str(text))
        self._refresh_action_hud()
        self.action_hud.show()
        self.action_hud.raise_()
        if hasattr(self, "action_hud_timer"):
            self.action_hud_timer.start(max(400, int(timeout_ms)))

    def show_lock_hud(self, lock_enabled):
        self._show_action_hud(f"마우스 잠금 {'ON' if lock_enabled else 'OFF'}", timeout_ms=1300)

    def show_gpu_guard_hud(self, guard_enabled):
        self._show_action_hud(f"성능 보호 {'ON' if guard_enabled else 'OFF'}", timeout_ms=1300)

    def _set_drag_topmost(self, enabled):
        enabled = bool(enabled)
        active = bool(getattr(self, "_drag_topmost_active", False))
        if enabled == active:
            return

        self._drag_topmost_active = enabled
        if enabled:
            restore_layer = int(getattr(self, "layer_mode", self.LAYER_NORMAL))
            restore_lock = bool(getattr(self, "is_locked", False))
            self._drag_restore_layer = int(restore_layer)
            self._drag_restore_lock = bool(restore_lock)
            self.apply_window_settings(
                int(self.LAYER_TOPMOST),
                bool(restore_lock),
                cancel_interaction=False,
            )
            # Keep configured state logical value unchanged while dragging.
            self.layer_mode = int(restore_layer)
            self.is_locked = bool(restore_lock)
            return

        if not self.isVisible():
            self._drag_restore_layer = None
            self._drag_restore_lock = None
            return
        restore_layer = int(getattr(self, "_drag_restore_layer", getattr(self, "layer_mode", self.LAYER_NORMAL)))
        restore_lock = bool(getattr(self, "_drag_restore_lock", getattr(self, "is_locked", False)))
        self._drag_restore_layer = None
        self._drag_restore_lock = None
        self.apply_window_settings(
            int(restore_layer),
            bool(restore_lock),
            cancel_interaction=False,
        )

    def cancel_active_interaction(self):
        """Force-clear dragging/resizing transient states (used by lock toggle)."""
        self.start_pos = None
        self.is_moving = False
        self.is_resizing = False
        self.resize_corner = None
        self.resize_start_pos = None
        self._set_drag_topmost(False)
        self._reset_axis_snap()
        self._hide_size_hud()
        self.unsetCursor()
        self._refresh_resize_ui()

    def _apply_corner_resize(self, global_pos):
        if not self.is_resizing or not self.resize_corner:
            return

        prev_geo = QRect(self.geometry())
        delta = global_pos - self.resize_start_pos
        start = QRect(self.resize_start_geo)
        min_w = max(50, self.minimumWidth())
        min_h = max(50, self.minimumHeight())

        keep_ratio = bool(getattr(self, "keep_aspect_ratio", True))
        aspect_ratio = max(0.01, float(start.width()) / max(1, float(start.height())))

        if not keep_ratio:
            x = start.x()
            y = start.y()
            w = start.width()
            h = start.height()
            if self.resize_corner == "tl":
                x = start.x() + delta.x()
                y = start.y() + delta.y()
                w = start.width() - delta.x()
                h = start.height() - delta.y()
            elif self.resize_corner == "tr":
                y = start.y() + delta.y()
                w = start.width() + delta.x()
                h = start.height() - delta.y()
            elif self.resize_corner == "bl":
                x = start.x() + delta.x()
                w = start.width() - delta.x()
                h = start.height() + delta.y()
            elif self.resize_corner == "br":
                w = start.width() + delta.x()
                h = start.height() + delta.y()

            if w < min_w:
                if self.resize_corner in ("tl", "bl"):
                    x = start.x() + (start.width() - min_w)
                w = min_w
            if h < min_h:
                if self.resize_corner in ("tl", "tr"):
                    y = start.y() + (start.height() - min_h)
                h = min_h
        else:
            if self.resize_corner == "br":
                target_w = max(min_w, start.width() + delta.x())
                target_h = max(min_h, int(round(target_w / aspect_ratio)))
                w = target_w
                h = target_h
                x = start.x()
                y = start.y()
            elif self.resize_corner == "bl":
                target_w = max(min_w, start.width() - delta.x())
                target_h = max(min_h, int(round(target_w / aspect_ratio)))
                w = target_w
                h = target_h
                x = start.right() - w
                y = start.y()
            elif self.resize_corner == "tr":
                target_w = max(min_w, start.width() + delta.x())
                target_h = max(min_h, int(round(target_w / aspect_ratio)))
                w = target_w
                h = target_h
                x = start.x()
                y = start.bottom() - h
            elif self.resize_corner == "tl":
                target_w = max(min_w, start.width() - delta.x())
                target_h = max(min_h, int(round(target_w / aspect_ratio)))
                w = target_w
                h = target_h
                x = start.right() - w
                y = start.bottom() - h

        self.setGeometry(QRect(int(x), int(y), int(w), int(h)))
        new_geo = QRect(self.geometry())
        left_step = int(new_geo.x() - prev_geo.x())
        top_step = int(new_geo.y() - prev_geo.y())
        right_step = int((new_geo.x() + new_geo.width()) - (prev_geo.x() + prev_geo.width()))
        bottom_step = int((new_geo.y() + new_geo.height()) - (prev_geo.y() + prev_geo.height()))
        if left_step or top_step or right_step or bottom_step:
            if hasattr(self, "manager") and self.manager and hasattr(self.manager, "resize_temp_group_by_edges"):
                self.manager.resize_temp_group_by_edges(
                    self.profile_id,
                    left_step,
                    top_step,
                    right_step,
                    bottom_step,
                )

    def _reset_axis_snap(self):
        self._snap_lock_x = None
        self._snap_lock_y = None
        self._snap_origin_pointer_x = None
        self._snap_origin_pointer_y = None

    def _other_widgets(self):
        if not hasattr(self, "manager") or not self.manager:
            return []
        widgets = getattr(self.manager, "widgets", {})
        if not isinstance(widgets, dict):
            return []
        return [w for w in widgets.values() if w is not self and isinstance(w, QWidget) and w.isVisible()]

    def _find_axis_snap_target(self, axis, raw_value):
        best_target = None
        best_dist = 999999
        screen_snap_threshold = 10
        other_snap_threshold = getattr(self, "_axis_snap_threshold", 4)
        own_span = self.width() if axis == "x" else self.height()

        # 1. 모니터 화면 테두리 경계 (작업표시줄 제외 가용 영역) 약한 자석
        screen = QApplication.screenAt(self.geometry().center())
        if not screen:
            screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            if axis == "x":
                screen_candidates = (
                    geo.left(),                 # 화면 좌측 가장자리
                    geo.right() + 1 - own_span, # 화면 우측 가장자리
                )
            else:
                screen_candidates = (
                    geo.top(),                  # 화면 상단 가장자리
                    geo.bottom() + 1 - own_span,# 화면 하단 가장자리 (작업표시줄 바로 위)
                )
            for target in screen_candidates:
                dist = abs(raw_value - target)
                if dist <= screen_snap_threshold and dist < best_dist:
                    best_target = target
                    best_dist = dist

        # 2. 다른 위젯들과의 스냅
        for w in self._other_widgets():
            other_lead = w.x() if axis == "x" else w.y()
            other_trail = (w.x() + w.width()) if axis == "x" else (w.y() + w.height())

            candidates = (
                other_lead,                    # left-left / top-top
                other_trail,                   # left-right / top-bottom
                other_lead - own_span,         # right-left / bottom-top
                other_trail - own_span,        # right-right / bottom-bottom
            )
            for target in candidates:
                dist = abs(raw_value - target)
                if dist <= other_snap_threshold and dist < best_dist:
                    best_target = target
                    best_dist = dist
        return best_target

    def _apply_axis_snap(self, axis, raw_value, pointer_value):
        if axis == "x":
            lock = self._snap_lock_x
            origin = self._snap_origin_pointer_x
        else:
            lock = self._snap_lock_y
            origin = self._snap_origin_pointer_y

        if lock is not None and origin is not None:
            if abs(pointer_value - origin) > self._axis_snap_release:
                if axis == "x":
                    self._snap_lock_x = None
                    self._snap_origin_pointer_x = None
                else:
                    self._snap_lock_y = None
                    self._snap_origin_pointer_y = None
            else:
                return lock

        target = self._find_axis_snap_target(axis, raw_value)
        if target is not None:
            if axis == "x":
                self._snap_lock_x = target
                self._snap_origin_pointer_x = pointer_value
            else:
                self._snap_lock_y = target
                self._snap_origin_pointer_y = pointer_value
            return target

        return raw_value

    def _as_path_set(self, value):
        if isinstance(value, list):
            return {str(v) for v in value if str(v)}
        if value in (None, ""):
            return set()
        return {str(value)}

    @staticmethod
    def _as_path_list(value):
        if isinstance(value, (list, tuple)):
            return [os.path.normpath(str(v)) for v in value if str(v)]
        if value in (None, ""):
            return []
        return [os.path.normpath(str(value))]

    def _save_quarantined_media(self):
        self.settings.setValue("quarantined_media", sorted(self.quarantined_media))

    def _current_screen(self):
        screen = self.screen()
        if not screen:
            screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        return screen

    def _find_screen_by_name(self, name):
        if not name:
            return None
        for screen in QGuiApplication.screens():
            if screen.name() == name:
                return screen
        return None

    def _save_position_metadata(self):
        screen = self._current_screen()
        if not screen:
            return

        ag = screen.availableGeometry()
        max_x = max(1, ag.width() - self.width())
        max_y = max(1, ag.height() - self.height())
        gpos = self._global_top_left()
        rel_x = (gpos.x() - ag.x()) / max_x
        rel_y = (gpos.y() - ag.y()) / max_y
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))

        self.settings.setValue("screen_name", screen.name())
        self.settings.setValue("screen_rel_x", rel_x)
        self.settings.setValue("screen_rel_y", rel_y)
        self.settings.setValue("screen_dpr", float(screen.devicePixelRatio()))
        self.settings.setValue("screen_dpi", float(screen.logicalDotsPerInch()))

    def _restore_position_with_screen_fallback(self, saved_pos):
        if saved_pos:
            self._move_exact(saved_pos)
            if self.is_visible_on_any_screen():
                return

        saved_screen_name = self.settings.value("screen_name", "")
        rel_x = float(self.settings.value("screen_rel_x", 0.0))
        rel_y = float(self.settings.value("screen_rel_y", 0.0))
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))

        target_screen = self._find_screen_by_name(saved_screen_name) or QGuiApplication.primaryScreen()
        if not target_screen:
            return

        ag = target_screen.availableGeometry()
        max_x = max(0, ag.width() - self.width())
        max_y = max(0, ag.height() - self.height())
        x = ag.x() + int(round(max_x * rel_x))
        y = ag.y() + int(round(max_y * rel_y))
        self._move_exact((x, y))

    def _record_media_failure(self, path, reason):
        if not path:
            return

        count = self.media_fail_counts.get(path, 0) + 1
        self.media_fail_counts[path] = count
        print(f"[media-skip] {os.path.basename(path)} ({reason}) count={count}")

        if count >= self.max_media_failures:
            self.quarantined_media.add(path)
            self._save_quarantined_media()
            print(f"[media-quarantine] {os.path.basename(path)}")

    def _schedule_next_media(self):
        if self._failure_scheduled:
            return
        self._failure_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_next_media)

    def _run_scheduled_next_media(self):
        self._failure_scheduled = False
        self.next_media()

    def _skip_current_media(self, reason):
        path = self.current_media_path
        if path:
            self._record_media_failure(path, reason)

        if path in self.playlist and path in self.quarantined_media:
            idx = self.playlist.index(path)
            self.playlist.pop(idx)
            if idx <= self.current_idx:
                self.current_idx -= 1

        if not self.playlist:
            self.current_media_path = None
            self.stack.setCurrentIndex(0)
            return

        self._schedule_next_media()

    def load_settings(self):
        self.folder_path = str(self.settings.value("folder_path", "") or "")
        self.folder_item_paths = self._as_path_list(self.settings.value("folder_item_paths", []))
        self.exec_path = self.settings.value("exec_path", "")
        self._exec_manual_focus_enabled = _as_bool(
            self.settings.value("exec_manual_focus_enabled", False),
            False,
        )
        self._exec_manual_focus_proc_path = self._normalize_exec_path(
            self.settings.value("exec_manual_focus_proc_path", "")
        )
        self._exec_manual_focus_proc_name = str(
            self.settings.value("exec_manual_focus_proc_name", "") or ""
        ).strip().lower()
        self._exec_manual_focus_title = str(
            self.settings.value("exec_manual_focus_title", "") or ""
        ).strip()
        self._exec_manual_focus_class = str(
            self.settings.value("exec_manual_focus_class", "") or ""
        ).strip()
        if not (
            self._exec_manual_focus_proc_path
            or self._exec_manual_focus_proc_name
            or (
                self._exec_manual_focus_class
                and self._exec_manual_focus_title
            )
        ):
            self._exec_manual_focus_enabled = False
        self.interval_ms = int(self.settings.value("interval", 5)) * 1000
        self.is_muted = _as_bool(self.settings.value("is_muted", True), True)
        self.current_opacity_pct = int(self.settings.value("opacity_pct", 100))
        self.setWindowOpacity(self.current_opacity_pct / 100.0)
        self.bg_color_mode = int(self.settings.value("bg_color_mode", 1))
        self.corner_mode = self.coerce_corner_mode(
            self.settings.value("corner_mode", self.CORNER_ROUNDED)
        )
        self.media_fit_mode = max(0, min(int(self.settings.value("media_fit_mode", 0)), 1))
        self.video_transition_mode = self.coerce_video_transition_mode(
            self.settings.value("video_transition_mode", self.VIDEO_TRANSITION_SINGLE)
        )
        self.video_decode_mode = self.coerce_video_decode_mode(
            self.settings.value("video_decode_mode", self.VIDEO_DECODE_ORIGINAL)
        )
        self._video_swap_fade_duration_ms = self.coerce_video_dual_fade_ms(
            self.settings.value("video_dual_fade_ms", self.VIDEO_DUAL_FADE_DEFAULT_MS)
        )
        if self.settings.contains("layer_mode"):
            layer_schema_ver = int(self.settings.value("layer_schema_version", 0))
            raw_layer_mode = int(self.settings.value("layer_mode", self.LAYER_NORMAL))
            self.layer_mode = self.coerce_layer_mode(raw_layer_mode, layer_schema_ver)
            if layer_schema_ver < int(self.LAYER_SCHEMA_VERSION):
                self.settings.setValue("layer_mode", int(self.layer_mode))
                self.settings.setValue("layer_schema_version", int(self.LAYER_SCHEMA_VERSION))
                self.settings.sync()
        else:
            self.layer_mode = int(self.LAYER_NORMAL)
            self.settings.setValue("layer_mode", int(self.layer_mode))
            self.settings.setValue("layer_schema_version", int(self.LAYER_SCHEMA_VERSION))
            self.settings.sync()
        self.is_locked = _as_bool(self.settings.value("is_locked", False), False)
        self.gpu_guard_enabled = _as_bool(self.settings.value("gpu_guard_enabled", False), False)
        self.quarantined_media = self._as_path_set(self.settings.value("quarantined_media", []))
        self.growth_anchor = str(self.settings.value("growth_anchor", "top-left") or "top-left")
        w = int(self.settings.value("w", 200))
        h = int(self.settings.value("h", 200))
        self.resize(w, h)
        saved_pos = self.settings.value("pos")
        saved_size = self.settings.value("size")
        if saved_size:
            self.resize(saved_size)
        self._restore_position_with_screen_fallback(saved_pos)
        if not self.is_visible_on_any_screen():
            geo = self.settings.value("geometry")
            if geo:
                self.restoreGeometry(geo)
        if not self.is_visible_on_any_screen():
            self._move_exact((100, 100))
        self._set_watched_folder(self.folder_path)
        self._apply_mute_state()
        self._update_video_aspect_mode()
        self.apply_window_settings(self.layer_mode, self.is_locked)
        if saved_size:
            self.resize(saved_size)
        self._restore_position_with_screen_fallback(saved_pos)

    def _is_media_fill_mode(self):
        return int(getattr(self, "media_fit_mode", 0)) == 1

    @staticmethod
    def _safe_target_size(widget, fallback_size):
        fw = 0
        fh = 0
        if isinstance(fallback_size, QSize):
            fw = max(0, int(fallback_size.width()))
            fh = max(0, int(fallback_size.height()))

        if isinstance(widget, QWidget):
            s = widget.size()
            sw = int(s.width()) if isinstance(s, QSize) else 0
            sh = int(s.height()) if isinstance(s, QSize) else 0
            if sw > 0 and sh > 0:
                if widget.isVisible():
                    return QSize(int(sw), int(sh))
                # Hidden startup state: trust child size only when it is close to fallback.
                if fw <= 0 or fh <= 0:
                    return QSize(int(sw), int(sh))
                min_w = max(24, int(round(fw * 0.90)))
                min_h = max(24, int(round(fh * 0.90)))
                max_w = max(min_w, int(round(fw * 1.10)))
                max_h = max(min_h, int(round(fh * 1.10)))
                if min_w <= sw <= max_w and min_h <= sh <= max_h:
                    return QSize(int(sw), int(sh))
        if fw > 0 and fh > 0:
            return QSize(int(fw), int(fh))
        return QSize(1, 1)

    @staticmethod
    def _scaled_size_for_source(source_size, target_size, fill):
        if not isinstance(source_size, QSize) or not isinstance(target_size, QSize):
            return QSize(1, 1)
        sw = max(1, int(source_size.width()))
        sh = max(1, int(source_size.height()))
        tw = max(1, int(target_size.width()))
        th = max(1, int(target_size.height()))
        if bool(fill):
            scale = max(float(tw) / float(sw), float(th) / float(sh))
        else:
            scale = min(float(tw) / float(sw), float(th) / float(sh))
        nw = max(1, int(round(float(sw) * float(scale))))
        nh = max(1, int(round(float(sh) * float(scale))))
        return QSize(int(nw), int(nh))

    @staticmethod
    def _debug_media_name(path):
        try:
            return str(os.path.basename(str(path or "")) or "")
        except Exception:
            return str(path or "")

    def _video_dbg(self, event_name, **fields):
        if not bool(getattr(self, "_video_debug_enabled", False)):
            return
        try:
            ts = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
        except Exception:
            ts = ""
        parts = []
        for key, value in fields.items():
            if value is None:
                continue
            try:
                txt = str(value)
            except Exception:
                continue
            txt = txt.replace("\r", " ").replace("\n", " ").strip()
            if not txt:
                continue
            parts.append(f"{key}={txt}")
        suffix = f" {' '.join(parts)}" if parts else ""
        print(f"[video-dbg] t={ts} profile={self.profile_id} event={event_name}{suffix}")

    @staticmethod
    def _resolve_video_proxy_dir():
        base = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
        if not base:
            base = os.path.expanduser("~")
        return os.path.join(base, "MyHomeApp", "video_proxy_cache")

    @staticmethod
    def _runtime_binary_dirs():
        return runtime_binary_dirs(include_cwd=False, include_bin_subdir=True)

    @classmethod
    def _find_runtime_binary(cls, name):
        return find_runtime_binary(
            name,
            include_cwd=False,
            include_bin_subdir=True,
        )

    def _resolve_ffmpeg_path(self):
        cached = getattr(self, "_video_proxy_ffmpeg_path", None)
        if cached is not None:
            return str(cached or "")
        env_override = str(os.environ.get("MYWIDGET_FFMPEG", "") or "").strip()
        path = ""
        if env_override:
            try:
                if os.path.isfile(env_override):
                    path = env_override
            except Exception:
                path = ""
        if not path:
            path = str(self._find_runtime_binary("ffmpeg") or "")
        if not path:
            path = str(shutil.which("ffmpeg") or "")
        self._video_proxy_ffmpeg_path = path
        return path

    def _resolve_ffprobe_path(self):
        cached = getattr(self, "_video_proxy_ffprobe_path", None)
        if cached is not None:
            return str(cached or "")
        env_override = str(os.environ.get("MYWIDGET_FFPROBE", "") or "").strip()
        path = ""
        if env_override:
            try:
                if os.path.isfile(env_override):
                    path = env_override
            except Exception:
                path = ""
        if not path:
            path = str(self._find_runtime_binary("ffprobe") or "")
        if not path:
            path = str(shutil.which("ffprobe") or "")
        if not path:
            ffmpeg_path = self._resolve_ffmpeg_path()
            if ffmpeg_path:
                path = str(find_ffprobe_beside_ffmpeg(ffmpeg_path) or "")
        self._video_proxy_ffprobe_path = path
        return path

    def _video_source_signature(self, path):
        src = self._normalize_exec_path(path)
        if not src:
            return ""
        try:
            st = os.stat(path)
            return f"{src}|{int(st.st_size)}|{int(st.st_mtime_ns)}"
        except Exception:
            return src

    def _probe_video_height(self, path):
        signature = self._video_source_signature(path)
        if not signature:
            return 0
        cache = getattr(self, "_video_proxy_source_height_cache", {})
        cached = int(cache.get(signature, 0) or 0)
        if cached > 0:
            return int(cached)
        ffprobe = self._resolve_ffprobe_path()
        if not ffprobe:
            return 0
        h = int(probe_video_height(ffprobe, path, timeout_sec=3.0) or 0)
        if h > 0:
            cache[signature] = int(h)
            self._video_proxy_source_height_cache = cache
            return int(h)
        return 0

    def _video_decode_target_height_for_current_widget(self):
        mode = int(getattr(self, "video_decode_mode", self.VIDEO_DECODE_ORIGINAL))
        if mode == int(self.VIDEO_DECODE_ORIGINAL):
            return 0
        if mode == int(self.VIDEO_DECODE_1080P):
            return 1080
        if mode == int(self.VIDEO_DECODE_720P):
            return 720
        target = self._safe_target_size(getattr(self, "video_widget", None), self.size())
        h = max(1, int(target.height()))
        if h <= 540:
            return 540
        if h <= 720:
            return 720
        return 1080

    def _video_proxy_output_path(self, source_path, target_height):
        signature = self._video_source_signature(source_path)
        if not signature:
            return ""
        token = hashlib.sha1(f"{signature}|{int(target_height)}".encode("utf-8", "ignore")).hexdigest()[:24]
        name = f"{token}_{int(target_height)}p.mp4"
        return os.path.join(str(getattr(self, "_video_proxy_dir", "") or ""), name)

    def _video_proxy_key(self, source_path, target_height):
        sig = self._video_source_signature(source_path)
        if not sig:
            return ""
        return f"{sig}|{int(target_height)}"

    def _ensure_video_proxy_file(self, source_path, target_height, allow_build=True):
        return self._video_proxy_service.ensure_video_proxy_file(
            source_path,
            target_height,
            allow_build=bool(allow_build),
        )

    def _enqueue_video_proxy_build(self, source_path, target_height):
        return bool(
            self._video_proxy_service.enqueue_video_proxy_build(
                source_path,
                target_height,
            )
        )

    def _video_proxy_build_worker(self):
        self._video_proxy_service.video_proxy_build_worker()

    def _resolve_video_playback_path(self, source_path, allow_build=True):
        src = str(source_path or "")
        if not src or not self._is_video_path(src):
            return src
        target_height = int(self._video_decode_target_height_for_current_widget())
        if target_height <= 0:
            return src
        source_height = int(self._probe_video_height(src))
        if source_height > 0 and source_height <= int(target_height):
            return src
        proxy_path = self._ensure_video_proxy_file(src, target_height, allow_build=bool(allow_build))
        if proxy_path:
            self._video_dbg(
                "proxy_use",
                source=self._debug_media_name(src),
                playback=self._debug_media_name(proxy_path),
                target=f"{int(target_height)}p",
            )
            return proxy_path
        if not bool(allow_build):
            self._enqueue_video_proxy_build(src, target_height)
        return src

    def _video_players(self):
        out = []
        primary = getattr(self, "_video_primary_player", None)
        if isinstance(primary, QMediaPlayer):
            out.append(primary)
        secondary = getattr(self, "_video_secondary_player", None)
        if isinstance(secondary, QMediaPlayer) and secondary is not primary:
            out.append(secondary)
        return out

    def _video_player_slot(self, player):
        if player is None:
            return -1
        if player is getattr(self, "_video_primary_player", None):
            return 0
        if player is getattr(self, "_video_secondary_player", None):
            return 1
        return -1

    def _video_player_for_slot(self, slot):
        if int(slot) == 0:
            return getattr(self, "_video_primary_player", None)
        if int(slot) == 1:
            return getattr(self, "_video_secondary_player", None)
        return None

    def _video_item_for_slot(self, slot):
        if int(slot) == 0:
            return getattr(self, "video_item", None)
        if int(slot) == 1:
            return getattr(self, "video_item_dual", None)
        return None

    def _set_video_active_slot(self, slot, update_visual=True):
        slot_int = int(slot)
        player = self._video_player_for_slot(slot_int)
        if not isinstance(player, QMediaPlayer):
            return
        prev_slot = int(getattr(self, "_video_active_slot", -1))
        self._video_active_slot = int(slot_int)
        self.media_player = player
        if prev_slot != int(slot_int):
            self._video_dbg(
                "active_slot_change",
                prev_slot=prev_slot,
                new_slot=int(slot_int),
                current=self._debug_media_name(getattr(self, "current_media_path", "")),
            )
        audio_attached = bool(getattr(self, "_audio_output_attached", True))
        for p in self._video_players():
            try:
                if p is self.media_player and audio_attached:
                    p.setAudioOutput(self.audio_output)
                else:
                    p.setAudioOutput(None)
            except Exception:
                pass
        if bool(getattr(self, "_video_graphics_mode", False)) and bool(update_visual):
            self._cancel_video_crossfade()
            for idx in (0, 1):
                item = self._video_item_for_slot(idx)
                if item is None:
                    continue
                try:
                    if int(idx) == int(slot_int):
                        item.setOpacity(1.0)
                        item.setZValue(2.0)
                    else:
                        item.setOpacity(0.0)
                        item.setZValue(1.0)
                except Exception:
                    pass

    def _cancel_video_crossfade(self):
        group = getattr(self, "_video_crossfade_group", None)
        if group is None:
            return
        try:
            group.stop()
        except Exception:
            pass
        try:
            group.deleteLater()
        except Exception:
            pass
        self._video_crossfade_group = None

    def _cleanup_video_player_if_inactive(self, player):
        if not isinstance(player, QMediaPlayer):
            return
        if player is self.media_player:
            return
        pending_slot = int(getattr(self, "_video_dual_pending_slot", -1))
        if pending_slot >= 0:
            pending_player = self._video_player_for_slot(pending_slot)
            if player is pending_player:
                return
        try:
            if player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                player.stop()
        except Exception:
            pass
        try:
            player.setSource(QUrl())
        except Exception:
            pass

    def _start_video_crossfade(self, from_slot, to_slot):
        if not bool(getattr(self, "_video_graphics_mode", False)):
            return False
        from_item = self._video_item_for_slot(from_slot)
        to_item = self._video_item_for_slot(to_slot)
        if from_item is None or to_item is None or from_item is to_item:
            return False
        duration_ms = max(0, int(getattr(self, "_video_swap_fade_duration_ms", 0)))
        if duration_ms <= 0:
            return False
        self._cancel_video_crossfade()
        try:
            from_item.setOpacity(1.0)
            from_item.setZValue(2.0)
            to_item.setOpacity(0.0)
            to_item.setZValue(3.0)
        except Exception:
            return False
        anim_out = QPropertyAnimation(from_item, b"opacity", self)
        anim_out.setDuration(int(duration_ms))
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)
        anim_out.setEasingCurve(QEasingCurve.Type.Linear)
        anim_in = QPropertyAnimation(to_item, b"opacity", self)
        anim_in.setDuration(int(duration_ms))
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)
        anim_in.setEasingCurve(QEasingCurve.Type.Linear)
        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_out)
        group.addAnimation(anim_in)
        self._video_crossfade_group = group
        self._video_dbg(
            "crossfade_start",
            from_slot=int(from_slot),
            to_slot=int(to_slot),
            ms=int(duration_ms),
            media=self._debug_media_name(getattr(self, "current_media_path", "")),
        )

        def _on_finish():
            try:
                from_item.setOpacity(0.0)
                from_item.setZValue(1.0)
                to_item.setOpacity(1.0)
                to_item.setZValue(2.0)
            except Exception:
                pass
            self._video_dbg(
                "crossfade_finish",
                from_slot=int(from_slot),
                to_slot=int(to_slot),
                ms=int(duration_ms),
                media=self._debug_media_name(getattr(self, "current_media_path", "")),
            )
            self._cancel_video_crossfade()

        group.finished.connect(_on_finish)
        try:
            group.start()
            return True
        except Exception:
            self._cancel_video_crossfade()
            return False

    def _is_dual_video_transition_enabled(self):
        if int(getattr(self, "video_transition_mode", self.VIDEO_TRANSITION_SINGLE)) != int(self.VIDEO_TRANSITION_DUAL):
            return False
        if not bool(getattr(self, "_video_graphics_mode", False)):
            return False
        if not isinstance(getattr(self, "_video_secondary_player", None), QMediaPlayer):
            return False
        if getattr(self, "video_item_dual", None) is None:
            return False
        return True

    def _video_count_in_playlist(self):
        count = 0
        for path in list(getattr(self, "playlist", []) or []):
            if self._is_video_path(path):
                count += 1
        return int(count)

    def _next_playlist_entry(self):
        plist = list(getattr(self, "playlist", []) or [])
        if not plist:
            return -1, ""
        idx = int(getattr(self, "current_idx", -1))
        if idx < -1:
            idx = -1
        if idx >= len(plist):
            idx = len(plist) - 1
        next_idx = (int(idx) + 1) % len(plist)
        return int(next_idx), str(plist[next_idx])

    def _dual_preload_lookahead_ms(self, duration_ms):
        try:
            d = int(duration_ms)
        except Exception:
            d = 0
        if d <= 0:
            return 1400
        return int(max(900, min(2600, int(round(float(d) * 0.10)))))

    def _is_dual_video_transition_candidate(self, next_video_path):
        if not self._is_dual_video_transition_enabled():
            return False
        if not self._is_video_path(next_video_path):
            return False
        if int(self.stack.currentIndex()) != 2:
            return False
        if bool(getattr(self, "_performance_paused", False)):
            return False
        if self._video_count_in_playlist() < 2:
            return False
        current_path = str(getattr(self, "current_media_path", "") or "")
        if not current_path or not self._is_video_path(current_path):
            return False
        if self._normalize_exec_path(current_path) == self._normalize_exec_path(next_video_path):
            return False
        return True

    def _set_player_loop_count(self, player, loops):
        if not isinstance(player, QMediaPlayer):
            return False
        setter = getattr(player, "setLoops", None)
        if not callable(setter):
            return False
        try:
            setter(int(loops))
            return True
        except Exception:
            return False

    def _get_player_loop_count(self, player):
        if not isinstance(player, QMediaPlayer):
            return 1
        getter = getattr(player, "loops", None)
        if callable(getter):
            try:
                return int(getter())
            except Exception:
                pass
        return 1

    def _cancel_video_dual_pending(self, clear_source=False):
        if hasattr(self, "_video_dual_preload_timer") and self._video_dual_preload_timer.isActive():
            self._video_dual_preload_timer.stop()
        if hasattr(self, "_video_dual_end_wait_timer") and self._video_dual_end_wait_timer.isActive():
            self._video_dual_end_wait_timer.stop()
        pending_slot = int(getattr(self, "_video_dual_pending_slot", -1))
        pending_path = str(getattr(self, "_video_dual_pending_path", "") or "")
        self._video_dual_pending_slot = -1
        self._video_dual_pending_path = ""
        self._video_dual_pending_ready = False
        self._video_dual_pending_frame_ready = False
        self._video_dual_pending_frozen = False
        self._video_dual_waiting_for_swap = False
        self._video_dual_pending_seq = 0
        self._video_dual_pending_started_mono = 0.0
        if pending_slot < 0:
            return
        pending_player = self._video_player_for_slot(pending_slot)
        if not isinstance(pending_player, QMediaPlayer):
            return
        if bool(clear_source):
            try:
                if pending_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                    pending_player.stop()
            except Exception:
                pass
            try:
                pending_player.setSource(QUrl())
            except Exception:
                pass
        if pending_path:
            try:
                pending_player.setAudioOutput(None)
            except Exception:
                pass

    def _play_video_path_on_active_player(self, path):
        self._video_dual_preload_triggered_for_path = ""
        playback_path = self._resolve_video_playback_path(path, allow_build=False)
        self._video_dbg(
            "play_active",
            slot=int(getattr(self, "_video_active_slot", 0)),
            media=self._debug_media_name(path),
            playback=self._debug_media_name(playback_path),
        )
        self.stack.setCurrentIndex(2)
        self._update_video_aspect_mode()
        self._sync_video_loop_policy_for_path(path)
        self.media_player.setSource(self._to_media_qurl(playback_path))
        self._apply_mute_state()
        if bool(getattr(self, "_deferred_playback_active", False)):
            self._deferred_playback_pending = True
            self._refresh_icon_overlay_for_current_media()
            return
        self.media_player.play()
        self._refresh_icon_overlay_for_current_media()
        if self._performance_paused:
            self.set_performance_paused(True, reason="guard_active", force=True)

    def _try_start_dual_video_preload(self, next_video_path):
        if not self._is_dual_video_transition_candidate(next_video_path):
            return False
        inactive_slot = 1 - int(getattr(self, "_video_active_slot", 0))
        preload_player = self._video_player_for_slot(inactive_slot)
        if not isinstance(preload_player, QMediaPlayer):
            return False
        self._cancel_video_dual_pending(clear_source=True)
        try:
            if preload_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                preload_player.stop()
        except Exception:
            pass
        self._set_player_loop_count(preload_player, 1)
        try:
            preload_player.setAudioOutput(None)
        except Exception:
            pass
        try:
            preload_path = self._resolve_video_playback_path(str(next_video_path), allow_build=False)
            preload_player.setSource(self._to_media_qurl(str(preload_path)))
            preload_player.play()
        except Exception:
            return False
        self._video_dual_pending_slot = int(inactive_slot)
        self._video_dual_pending_path = str(next_video_path)
        self._video_dual_pending_ready = False
        self._video_dual_pending_frame_ready = False
        self._video_dual_pending_frozen = False
        self._video_dual_waiting_for_swap = False
        self._video_transition_seq = int(getattr(self, "_video_transition_seq", 0)) + 1
        self._video_dual_pending_seq = int(self._video_transition_seq)
        self._video_dual_pending_started_mono = float(time.monotonic())
        self._video_dbg(
            "preload_start",
            seq=int(self._video_dual_pending_seq),
            active_slot=int(getattr(self, "_video_active_slot", 0)),
            pending_slot=int(inactive_slot),
            from_media=self._debug_media_name(getattr(self, "current_media_path", "")),
            to_media=self._debug_media_name(next_video_path),
        )
        if hasattr(self, "_video_dual_preload_timer"):
            self._video_dual_preload_timer.start()
        return True

    def _is_dual_pending_swap_ready(self):
        if int(getattr(self, "_video_dual_pending_slot", -1)) < 0:
            return False
        if not bool(getattr(self, "_video_dual_pending_ready", False)):
            return False
        if bool(getattr(self, "_video_graphics_mode", False)):
            return bool(getattr(self, "_video_dual_pending_frame_ready", False))
        return True

    def _swap_to_dual_pending(self):
        pending_slot = int(getattr(self, "_video_dual_pending_slot", -1))
        if pending_slot < 0:
            return False
        pending_player = self._video_player_for_slot(pending_slot)
        if not isinstance(pending_player, QMediaPlayer):
            return False
        old_slot = int(getattr(self, "_video_active_slot", 0))
        old_player = self._video_player_for_slot(old_slot)
        seq = int(getattr(self, "_video_dual_pending_seq", 0))
        started = float(getattr(self, "_video_dual_pending_started_mono", 0.0))
        age_ms = int(round((float(time.monotonic()) - started) * 1000.0)) if started > 0.0 else -1
        self._cancel_video_dual_pending(clear_source=False)
        self._set_video_active_slot(pending_slot, update_visual=False)
        self._video_dual_preload_triggered_for_path = ""
        crossfade_started = self._start_video_crossfade(old_slot, pending_slot)
        if not crossfade_started:
            self._set_video_active_slot(pending_slot, update_visual=True)
        self._video_dbg(
            "swap",
            seq=seq,
            old_slot=int(old_slot),
            new_slot=int(pending_slot),
            wait_ms=int(age_ms),
            fade=bool(crossfade_started),
            media=self._debug_media_name(getattr(self, "current_media_path", "")),
        )
        self._apply_mute_state(force_refresh=True)
        try:
            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.media_player.play()
        except Exception:
            pass
        if isinstance(old_player, QMediaPlayer) and old_player is not self.media_player:
            if crossfade_started:
                delay_ms = max(1, int(getattr(self, "_video_swap_fade_duration_ms", 90)) + 30)
                QTimer.singleShot(
                    int(delay_ms),
                    lambda p=old_player: self._cleanup_video_player_if_inactive(p),
                )
            else:
                self._cleanup_video_player_if_inactive(old_player)
        return True

    def _fallback_from_dual_pending(self, reason=""):
        path = str(getattr(self, "_video_dual_pending_path", "") or "")
        seq = int(getattr(self, "_video_dual_pending_seq", 0))
        started = float(getattr(self, "_video_dual_pending_started_mono", 0.0))
        age_ms = int(round((float(time.monotonic()) - started) * 1000.0)) if started > 0.0 else -1
        if hasattr(self, "_video_dual_end_wait_timer") and self._video_dual_end_wait_timer.isActive():
            self._video_dual_end_wait_timer.stop()
        self._video_dual_waiting_for_swap = False
        self._video_dbg(
            "fallback",
            seq=seq,
            reason=reason,
            age_ms=int(age_ms),
            pending_ready=bool(getattr(self, "_video_dual_pending_ready", False)),
            frame_ready=bool(getattr(self, "_video_dual_pending_frame_ready", False)),
            pending_frozen=bool(getattr(self, "_video_dual_pending_frozen", False)),
            pending_media=self._debug_media_name(path),
        )
        self._cancel_video_dual_pending(clear_source=True)
        if not path:
            return
        if reason:
            print(f"[video-dual-fallback] profile={self.profile_id} reason={reason}")
        self._play_video_path_on_active_player(path)

    def _on_video_dual_preload_timeout(self):
        if int(getattr(self, "_video_dual_pending_slot", -1)) < 0:
            return
        # If pending media is already prepared, ignore this watchdog timeout.
        # EndOfMedia (or end-wait) will perform the actual swap.
        if bool(getattr(self, "_video_dual_pending_ready", False)) or bool(getattr(self, "_video_dual_pending_frame_ready", False)):
            self._video_dbg(
                "preload_timeout_ignored",
                seq=int(getattr(self, "_video_dual_pending_seq", 0)),
                pending_ready=bool(getattr(self, "_video_dual_pending_ready", False)),
                frame_ready=bool(getattr(self, "_video_dual_pending_frame_ready", False)),
                pending_media=self._debug_media_name(getattr(self, "_video_dual_pending_path", "")),
            )
            return
        self._video_dbg(
            "preload_timeout",
            seq=int(getattr(self, "_video_dual_pending_seq", 0)),
            pending_media=self._debug_media_name(getattr(self, "_video_dual_pending_path", "")),
        )
        self._fallback_from_dual_pending(reason="preload_timeout")

    def _on_video_dual_end_wait_timeout(self):
        if not bool(getattr(self, "_video_dual_waiting_for_swap", False)):
            return
        self._video_dbg(
            "end_wait_timeout",
            seq=int(getattr(self, "_video_dual_pending_seq", 0)),
            pending_ready=bool(getattr(self, "_video_dual_pending_ready", False)),
            frame_ready=bool(getattr(self, "_video_dual_pending_frame_ready", False)),
            pending_media=self._debug_media_name(getattr(self, "_video_dual_pending_path", "")),
        )
        self._video_dual_waiting_for_swap = False
        if int(getattr(self, "_video_dual_pending_slot", -1)) < 0:
            return
        if self._is_dual_pending_swap_ready():
            if self._swap_to_dual_pending():
                return
        self._fallback_from_dual_pending(reason="end_wait_timeout")

    def _stop_all_video_players(self, clear_source=True):
        self._cancel_video_crossfade()
        self._cancel_video_dual_pending(clear_source=bool(clear_source))
        for player in self._video_players():
            try:
                if player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                    player.stop()
            except Exception:
                pass
            self._set_player_loop_count(player, 1)
            if bool(clear_source):
                try:
                    player.setSource(QUrl())
                except Exception:
                    pass
        self._set_video_active_slot(int(getattr(self, "_video_active_slot", 0)))

    def _sync_video_viewport_update_mode(self):
        if not bool(getattr(self, "_video_graphics_mode", False)):
            return
        view = getattr(self, "video_widget", None)
        if not isinstance(view, QGraphicsView):
            return
        target_mode = QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        try:
            manager = getattr(self, "manager", None)
            widgets = getattr(manager, "widgets", {}) if manager is not None else {}
            visible_count = 0
            if isinstance(widgets, dict):
                for widget in widgets.values():
                    if isinstance(widget, DesktopWidget) and widget.isVisible():
                        visible_count += 1
                        if visible_count >= 2:
                            break
            if visible_count >= 2:
                target_mode = QGraphicsView.ViewportUpdateMode.SmartViewportUpdate
        except Exception:
            target_mode = QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        try:
            if view.viewportUpdateMode() != target_mode:
                view.setViewportUpdateMode(target_mode)
        except Exception:
            pass

    def _resize_video_surface(self):
        if not bool(getattr(self, "_video_graphics_mode", False)):
            return
        if not isinstance(getattr(self, "video_widget", None), QGraphicsView):
            return
        if getattr(self, "video_scene", None) is None or getattr(self, "video_item", None) is None:
            return
        try:
            target = self._safe_target_size(getattr(self, "video_widget", None), self.size())
            w = max(1, int(target.width()))
            h = max(1, int(target.height()))
            self.video_scene.setSceneRect(QRectF(0.0, 0.0, float(w), float(h)))
            self.video_item.setPos(QPointF(0.0, 0.0))
            self.video_item.setSize(QSizeF(float(w), float(h)))
            if getattr(self, "video_item_dual", None) is not None:
                self.video_item_dual.setPos(QPointF(0.0, 0.0))
                self.video_item_dual.setSize(QSizeF(float(w), float(h)))
        except Exception:
            pass

    def _update_video_aspect_mode(self):
        if not hasattr(self, "video_widget"):
            return
        mode = Qt.AspectRatioMode.KeepAspectRatio
        if self._is_media_fill_mode():
            mode = getattr(
                Qt.AspectRatioMode,
                "KeepAspectRatioByExpanding",
                Qt.AspectRatioMode.KeepAspectRatio,
            )
        if bool(getattr(self, "_video_graphics_mode", False)) and getattr(self, "video_item", None) is not None:
            try:
                self.video_item.setAspectRatioMode(mode)
            except Exception:
                pass
            if getattr(self, "video_item_dual", None) is not None:
                try:
                    self.video_item_dual.setAspectRatioMode(mode)
                except Exception:
                    pass
            self._resize_video_surface()
            return
        try:
            self.video_widget.setAspectRatioMode(mode)
        except Exception:
            pass

    def _update_movie_scaled_size(self):
        if not self.movie:
            return
        self._update_movie_scaled_size_for(self.movie)

    def _update_movie_scaled_size_for(self, movie_obj):
        if movie_obj is None:
            return
        target = self._safe_target_size(getattr(self, "img_label", None), self.size())
        src = QSize()
        orig_size = getattr(movie_obj, "_original_size", None)
        if isinstance(orig_size, QSize) and orig_size.isValid() and orig_size.width() > 0 and orig_size.height() > 0:
            src = orig_size
        else:
            file_name = movie_obj.fileName()
            if file_name and os.path.isfile(file_name):
                try:
                    reader = QImageReader(file_name)
                    r_size = reader.size()
                    if r_size.isValid() and r_size.width() > 0 and r_size.height() > 0:
                        src = r_size
                        movie_obj._original_size = r_size
                except Exception:
                    pass
        if int(src.width()) <= 0 or int(src.height()) <= 0:
            try:
                fr = movie_obj.frameRect()
                if isinstance(fr, QRect) and fr.isValid() and fr.width() > 0 and fr.height() > 0:
                    src = fr.size()
            except Exception:
                src = QSize()
        if int(src.width()) <= 0 or int(src.height()) <= 0:
            try:
                pm = movie_obj.currentPixmap()
                if isinstance(pm, QPixmap) and not pm.isNull():
                    src = pm.size()
            except Exception:
                src = QSize()
        if int(src.width()) <= 0 or int(src.height()) <= 0:
            src = QSize(int(target.width()), int(target.height()))
        scaled = self._scaled_size_for_source(src, target, fill=self._is_media_fill_mode())

        old_scaled = movie_obj.scaledSize()
        needs_reload = False
        if old_scaled != scaled:
            needs_reload = True
        elif movie_obj.currentPixmap() and not movie_obj.currentPixmap().isNull() and movie_obj.currentPixmap().size() != scaled:
            needs_reload = True

        if needs_reload:
            file_name = movie_obj.fileName()
            if movie_obj.cacheMode() == QMovie.CacheMode.CacheAll and file_name and os.path.isfile(file_name):
                cur_frame = max(0, int(movie_obj.currentFrameNumber()))
                is_running = (movie_obj.state() == QMovie.MovieState.Running)
                try:
                    movie_obj.stop()
                    movie_obj.setFileName(file_name)
                    movie_obj.setScaledSize(scaled)
                    if is_running:
                        movie_obj.start()
                        movie_obj.jumpToFrame(cur_frame)
                except Exception:
                    try:
                        movie_obj.setScaledSize(scaled)
                    except Exception:
                        pass
            else:
                try:
                    movie_obj.setScaledSize(scaled)
                except Exception:
                    pass

    def _estimate_gif_duration_ms(self, movie_obj):
        if movie_obj is None:
            return 0
        try:
            frame_count = int(movie_obj.frameCount())
        except Exception:
            frame_count = 0
        if frame_count <= 0:
            return 0
        try:
            frame_delay = int(movie_obj.nextFrameDelay())
        except Exception:
            frame_delay = 0
        if frame_delay <= 0:
            return 0
        # Cheap estimate only: avoid frame-by-frame seeking that can stall startup.
        return int(max(0, min(600000, int(frame_count) * int(frame_delay))))

    @staticmethod
    def _gif_cache_limit_bytes():
        raw = str(os.environ.get("MYCANVAS_GIF_CACHEALL_MAX_MB", "24") or "").strip()
        try:
            mb = float(raw)
        except Exception:
            mb = 24.0
        if mb <= 0:
            return 0
        return int(max(0.0, float(mb)) * 1024.0 * 1024.0)

    def _configure_gif_movie_cache(self, movie_obj, source_path):
        if movie_obj is None:
            return
        cache_mode = QMovie.CacheMode.CacheNone
        limit_bytes = int(self._gif_cache_limit_bytes())
        if limit_bytes > 0:
            try:
                file_size = int(os.path.getsize(str(source_path or "")))
            except Exception:
                file_size = -1
            if 0 <= int(file_size) <= int(limit_bytes):
                cache_mode = QMovie.CacheMode.CacheAll
        try:
            movie_obj.setCacheMode(cache_mode)
        except Exception:
            pass

    def _is_single_media_mode_active(self):
        if len(self.playlist) != 1:
            return False
        if not self.playlist:
            return False
        only_path = self._normalize_exec_path(self.playlist[0])
        current_path = self._normalize_exec_path(getattr(self, "current_media_path", ""))
        return bool(only_path and current_path and only_path == current_path)

    def _sync_current_media_cycle_policy(self):
        if not self._is_dual_video_transition_enabled():
            self._cancel_video_dual_pending(clear_source=True)
        if self.stack.currentIndex() == 2:
            current_path = str(getattr(self, "current_media_path", "") or "")
            if current_path:
                self._sync_video_loop_policy_for_path(current_path)
            return
        if self.stack.currentIndex() != 1:
            return
        # Static image branch.
        if self.movie is None:
            if self.current_static_pixmap is None or self.current_static_pixmap.isNull():
                return
            if self._is_single_media_mode_active():
                if self.timer.isActive():
                    self.timer.stop()
            else:
                if not self.timer.isActive():
                    self.timer.start(max(1, int(self.interval_ms)))
            return
        # GIF branch.
        if self._is_single_media_mode_active() and self.timer.isActive():
            self.timer.stop()
        if not bool(getattr(self, "_gif_loop_watch_active", False)):
            self._start_active_gif_loop_watch()

    def _restart_current_video_loop(self):
        if self.stack.currentIndex() != 2:
            return False
        if not self._is_single_media_mode_active():
            return False
        if self._is_native_video_infinite_loop_active():
            try:
                self.media_player.play()
                self._apply_mute_state()
                return True
            except Exception:
                pass
        try:
            self.media_player.setPosition(0)
        except Exception:
            pass
        try:
            self.media_player.play()
            self._apply_mute_state()
            return True
        except Exception:
            return False

    def _set_media_player_loops(self, loops, player=None):
        target = player if isinstance(player, QMediaPlayer) else self.media_player
        return bool(self._set_player_loop_count(target, loops))

    def _get_media_player_loops(self, player=None):
        target = player if isinstance(player, QMediaPlayer) else self.media_player
        return int(self._get_player_loop_count(target))

    def _is_native_video_infinite_loop_active(self):
        return int(self._get_media_player_loops()) < 0

    def _sync_video_loop_policy_for_path(self, path):
        if not self._is_video_path(path):
            self._set_media_player_loops(1)
            return
        if len(self.playlist) == 1:
            # Prefer player-native infinite loop for smoother single-video playback.
            self._set_media_player_loops(-1)
        else:
            self._set_media_player_loops(1)

    def _restart_current_gif_loop(self):
        if self.movie is None or self.stack.currentIndex() != 1:
            return False
        try:
            self.movie.jumpToFrame(0)
        except Exception:
            pass
        try:
            self.movie.start()
            if self.movie.state() != QMovie.MovieState.Running:
                self.movie.start()
        except Exception:
            return False
        self._start_active_gif_loop_watch()
        return True

    def _clear_active_gif_loop_watch(self):
        if hasattr(self, "_gif_loop_fallback_timer") and self._gif_loop_fallback_timer.isActive():
            self._gif_loop_fallback_timer.stop()
        self._gif_loop_watch_active = False
        self._gif_loop_last_frame = -1
        self._gif_loop_min_deadline = 0.0
        self._gif_wait_for_finished_only = False
        if self.movie is None:
            return
        try:
            self.movie.frameChanged.disconnect(self._on_active_gif_frame_changed)
        except Exception:
            pass
        try:
            self.movie.finished.disconnect(self._on_active_gif_finished)
        except Exception:
            pass

    def _start_active_gif_loop_watch(self):
        if self.movie is None:
            self._clear_active_gif_loop_watch()
            return
        self._clear_active_gif_loop_watch()
        self._gif_loop_watch_active = True
        try:
            loop_count = int(self.movie.loopCount())
        except Exception:
            loop_count = -1
        # Finite-loop GIFs should advance only when playback actually finishes.
        self._gif_wait_for_finished_only = (loop_count != -1)
        try:
            self._gif_loop_last_frame = int(self.movie.currentFrameNumber())
        except Exception:
            self._gif_loop_last_frame = -1
        self._gif_loop_min_deadline = float(time.monotonic()) + (max(1, int(self.interval_ms)) / 1000.0)
        try:
            if not self._gif_wait_for_finished_only:
                self.movie.frameChanged.connect(self._on_active_gif_frame_changed)
        except Exception:
            pass
        try:
            self.movie.finished.connect(self._on_active_gif_finished)
        except Exception:
            pass
        # Safety fallback: prevent getting stuck forever if frame signals stop unexpectedly.
        try:
            # Use a generous watchdog so long GIFs are not cut early.
            fallback_ms = max(300000, int(self.interval_ms) * 12)
        except Exception:
            fallback_ms = 300000
        if hasattr(self, "_gif_loop_fallback_timer"):
            self._gif_loop_fallback_timer.start(int(fallback_ms))

    def _on_active_gif_frame_changed(self, frame_number):
        if not bool(getattr(self, "_gif_loop_watch_active", False)):
            return
        if bool(getattr(self, "_gif_wait_for_finished_only", False)):
            return
        if self.movie is None or self.stack.currentIndex() != 1:
            self._clear_active_gif_loop_watch()
            return
        sender_obj = self.sender()
        if sender_obj is not self.movie:
            return
        try:
            frame_idx = int(frame_number)
        except Exception:
            frame_idx = -1
        last = int(getattr(self, "_gif_loop_last_frame", -1))
        if last > 0 and frame_idx == 0:
            now = float(time.monotonic())
            if now >= float(getattr(self, "_gif_loop_min_deadline", 0.0)):
                if self._is_single_media_mode_active():
                    self._gif_loop_min_deadline = float(now) + (max(1, int(self.interval_ms)) / 1000.0)
                else:
                    self._clear_active_gif_loop_watch()
                    self._schedule_next_media()
                return
        self._gif_loop_last_frame = int(frame_idx)

    def _on_active_gif_finished(self):
        if self.movie is None or self.stack.currentIndex() != 1:
            return
        sender_obj = self.sender()
        if sender_obj is not self.movie:
            return
        if self._is_single_media_mode_active():
            self._clear_active_gif_loop_watch()
            if self._restart_current_gif_loop():
                return
            self._schedule_next_media()
            return
        if self.timer.isActive():
            self.timer.stop()
        now = float(time.monotonic())
        deadline = float(getattr(self, "_gif_loop_min_deadline", 0.0))
        self._clear_active_gif_loop_watch()
        if now >= deadline:
            self._schedule_next_media()
            return
        remain_ms = max(1, int(round((deadline - now) * 1000.0)))
        active_movie = self.movie
        QTimer.singleShot(
            int(remain_ms),
            lambda m=active_movie: (
                self._schedule_next_media()
                if (self.movie is m and self.stack.currentIndex() == 1)
                else None
            ),
        )

    def _on_gif_loop_fallback_timeout(self):
        if not bool(getattr(self, "_gif_loop_watch_active", False)):
            return
        if bool(getattr(self, "_performance_paused", False)):
            if hasattr(self, "_gif_loop_fallback_timer"):
                self._gif_loop_fallback_timer.start(max(5000, int(self.interval_ms)))
            return
        if self._is_single_media_mode_active():
            self._clear_active_gif_loop_watch()
            if self._restart_current_gif_loop():
                return
        self._clear_active_gif_loop_watch()
        self._schedule_next_media()

    def _apply_media_scale_mode(self):
        self._update_video_aspect_mode()
        if self.movie:
            self._update_movie_scaled_size()
            return
        if self.current_static_pixmap and not self.current_static_pixmap.isNull():
            self._update_static_pixmap_size()

    def _cancel_pending_gif_swap(self):
        if hasattr(self, "_gif_swap_timeout") and self._gif_swap_timeout.isActive():
            self._gif_swap_timeout.stop()
        pending = getattr(self, "_gif_swap_pending_movie", None)
        self._gif_swap_pending_movie = None
        self._gif_swap_pending_path = ""
        self._gif_swap_pending_duration_ms = 0
        if pending is None:
            return
        try:
            pending.frameChanged.disconnect(self._on_gif_swap_frame_changed)
        except Exception:
            pass
        try:
            pending.stop()
        except Exception:
            pass
        try:
            pending.deleteLater()
        except Exception:
            pass

    def _schedule_gif_swap(self, path):
        self._cancel_pending_gif_swap()
        movie = QMovie(path)
        if not movie.isValid():
            try:
                movie.deleteLater()
            except Exception:
                pass
            return False
        self._configure_gif_movie_cache(movie, path)
        self._gif_swap_pending_movie = movie
        self._gif_swap_pending_path = str(path)
        self._gif_swap_pending_duration_ms = 0
        movie.frameChanged.connect(self._on_gif_swap_frame_changed)
        movie.start()
        try:
            first_ready = bool(movie.jumpToFrame(0))
        except Exception:
            first_ready = False
        if first_ready:
            try:
                movie.setPaused(True)
            except Exception:
                pass
            self._update_movie_scaled_size_for(movie)
            self._gif_swap_pending_duration_ms = int(self._estimate_gif_duration_ms(movie))
            QTimer.singleShot(0, self._complete_gif_swap)
            return True
        if hasattr(self, "_gif_swap_timeout"):
            self._gif_swap_timeout.start()
        return True

    def _start_gif_direct(self, path):
        movie = QMovie(path)
        if not movie.isValid():
            try:
                movie.deleteLater()
            except Exception:
                pass
            return False
        self._configure_gif_movie_cache(movie, path)
        self.movie = movie
        self.stack.setCurrentIndex(1)
        self.img_label.setUpdatesEnabled(False)
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setMovie(self.movie)
        try:
            self.movie.jumpToFrame(0)
        except Exception:
            pass
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setUpdatesEnabled(True)
        if bool(getattr(self, "_deferred_playback_active", False)):
            self._deferred_playback_pending = True
            return True
        self.movie.start()
        if self.movie.state() != QMovie.MovieState.Running:
            self.movie.start()
        gif_total_duration = int(self._estimate_gif_duration_ms(self.movie))
        try:
            loop_count = int(self.movie.loopCount())
        except Exception:
            loop_count = -1
        if loop_count == 1:
            wait_time = max(self.interval_ms, gif_total_duration) if gif_total_duration > 0 else self.interval_ms
            self.timer.start(wait_time)
            self._clear_active_gif_loop_watch()
        else:
            self._start_active_gif_loop_watch()
        if self._performance_paused:
            self.set_performance_paused(True, reason="guard_active", force=True)
        return True

    def _resume_deferred_playback(self):
        self._deferred_playback_active = False
        if not bool(getattr(self, "_deferred_playback_pending", False)):
            return
        self._deferred_playback_pending = False
        if self.stack.currentIndex() == 1 and self.movie is not None:
            try:
                self.movie.start()
                if self.movie.state() != QMovie.MovieState.Running:
                    self.movie.start()
                gif_total_duration = int(self._estimate_gif_duration_ms(self.movie))
                try:
                    loop_count = int(self.movie.loopCount())
                except Exception:
                    loop_count = -1
                if loop_count == 1:
                    wait_time = max(self.interval_ms, gif_total_duration) if gif_total_duration > 0 else self.interval_ms
                    self.timer.start(wait_time)
                    self._clear_active_gif_loop_watch()
                else:
                    self._start_active_gif_loop_watch()
            except Exception:
                pass
        elif self.stack.currentIndex() == 2 and self.media_player is not None:
            try:
                self.media_player.play()
            except Exception:
                pass

    def _complete_gif_swap(self):
        pending = getattr(self, "_gif_swap_pending_movie", None)
        if pending is None:
            return False
        if hasattr(self, "_gif_swap_timeout") and self._gif_swap_timeout.isActive():
            self._gif_swap_timeout.stop()
        try:
            pending.frameChanged.disconnect(self._on_gif_swap_frame_changed)
        except Exception:
            pass
        self._gif_swap_pending_movie = None
        self._gif_swap_pending_path = ""
        pending_duration = int(getattr(self, "_gif_swap_pending_duration_ms", 0) or 0)
        self._gif_swap_pending_duration_ms = 0
        self.movie = pending
        self.stack.setCurrentIndex(1)
        self.img_label.setUpdatesEnabled(False)
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setMovie(self.movie)
        try:
            self.movie.jumpToFrame(0)
        except Exception:
            pass
        self._update_movie_scaled_size_for(self.movie)
        self.img_label.setUpdatesEnabled(True)
        try:
            self.movie.setPaused(False)
        except Exception:
            pass
        if self.movie.state() != QMovie.MovieState.Running:
            self.movie.start()
        gif_total_duration = int(pending_duration)
        if gif_total_duration <= 0:
            gif_total_duration = int(self._estimate_gif_duration_ms(self.movie))
        try:
            loop_count = int(self.movie.loopCount())
        except Exception:
            loop_count = -1
        if loop_count == 1:
            wait_time = max(self.interval_ms, gif_total_duration) if gif_total_duration > 0 else self.interval_ms
            self.timer.start(wait_time)
            self._clear_active_gif_loop_watch()
        else:
            self._start_active_gif_loop_watch()
        self._refresh_icon_overlay_for_current_media()
        if self._performance_paused:
            self.set_performance_paused(True, reason="guard_active", force=True)
        return True

    def _on_gif_swap_frame_changed(self, frame_number):
        if int(frame_number) < 0:
            return
        pending = getattr(self, "_gif_swap_pending_movie", None)
        if pending is None:
            return
        sender_obj = self.sender()
        if sender_obj is not pending:
            return
        try:
            pending.setPaused(True)
        except Exception:
            pass
        self._update_movie_scaled_size_for(pending)
        self._gif_swap_pending_duration_ms = int(self._estimate_gif_duration_ms(pending))
        self._complete_gif_swap()

    def _on_gif_swap_timeout(self):
        pending = getattr(self, "_gif_swap_pending_movie", None)
        if pending is None:
            return
        fallback_path = str(getattr(self, "_gif_swap_pending_path", "") or "")
        if int(pending.currentFrameNumber()) >= 0:
            self._complete_gif_swap()
            return
        self._cancel_pending_gif_swap()
        if fallback_path and str(getattr(self, "current_media_path", "")) == fallback_path:
            if self._start_gif_direct(fallback_path):
                self._refresh_icon_overlay_for_current_media()
                return
        self._skip_current_media("gif_preload_timeout")

    def prepare_media_before_show(self):
        """Prime first media frame while hidden so opening doesn't pop from small->large."""
        if bool(getattr(self, "_initial_media_prepared", False)):
            self._apply_media_scale_mode()
            return
        pending = bool(getattr(self, "_initial_media_pending", False))
        if not pending:
            self._apply_media_scale_mode()
            self._initial_media_prepared = True
            return

        self._initial_media_pending = False
        if not self.playlist:
            self.update_playlist()
        if not self.playlist:
            self._initial_media_prepared = True
            return
        if not self.current_media_path:
            self.current_idx = -1
            self.next_media()
        else:
            self._apply_media_scale_mode()
        self._initial_media_prepared = True

    def is_visible_on_any_screen(self):
        for screen in QGuiApplication.screens():
            if screen.geometry().intersects(self.geometry()):
                return True
        return False

    def _move_exact(self, target):
        if isinstance(target, QPoint):
            x, y = target.x(), target.y()
        else:
            x, y = target

        try:
            hwnd = int(self.winId())
            win32gui.SetWindowPos(
                hwnd,
                0,
                int(x),
                int(y),
                0,
                0,
                win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            )
            # Keep Qt geometry in sync with native move result.
            self.move(int(x), int(y))
        except Exception:
            self.move(int(x), int(y))

    def _global_top_left(self):
        try:
            gp = self.mapToGlobal(QPoint(0, 0))
            if isinstance(gp, QPoint):
                return QPoint(int(gp.x()), int(gp.y()))
        except Exception:
            pass
        try:
            hwnd = int(self.winId())
            left, top, _right, _bottom = win32gui.GetWindowRect(hwnd)
            return QPoint(int(left), int(top))
        except Exception:
            return QPoint(int(self.x()), int(self.y()))

    def apply_mask_and_style(self):
        corner_mode = self.coerce_corner_mode(getattr(self, "corner_mode", self.CORNER_ROUNDED))
        self.corner_mode = int(corner_mode)
        if int(corner_mode) == int(self.CORNER_SQUARE):
            radius = 0
        elif int(corner_mode) == int(self.CORNER_ROUND):
            radius = max(1, min(int(self.width()), int(self.height())) // 2)
        else:
            radius = 20

        bg_options = ["transparent", "black", "white"]
        bg_idx = max(0, min(int(self.bg_color_mode), len(bg_options) - 1))
        bg = bg_options[bg_idx]

        container_style = f"QWidget#mainContainer {{ background-color: {bg}; border-radius: {radius}px; }}"
        if container_style != getattr(self, "_container_style_cache_key", None):
            self.container.setStyleSheet(container_style)
            self._container_style_cache_key = container_style
        if hasattr(self, "placeholder"):
            placeholder_style = f"background: #222; border-radius: {radius}px;"
            if placeholder_style != getattr(self, "_placeholder_style_cache_key", None):
                self.placeholder.setStyleSheet(placeholder_style)
                self._placeholder_style_cache_key = placeholder_style

        self._sync_desktop_icon_mask_timer()
        clone_icons = self._should_clone_desktop_icons()
        if clone_icons:
            self._refresh_desktop_icon_clone_overlay(force=False)
        else:
            self._set_clone_overlay_items([])

        if hasattr(self, "desktop_icon_clone_overlay") and self.desktop_icon_clone_overlay.isVisible():
            self.desktop_icon_clone_overlay.raise_()
        if hasattr(self, 'selection_overlay'):
            self.selection_overlay.raise_()
        if hasattr(self, 'resize_overlay'):
            self.resize_overlay.raise_()
        if hasattr(self, 'size_hud') and self.size_hud.isVisible():
            self.size_hud.raise_()
        if hasattr(self, 'action_hud') and self.action_hud.isVisible():
            self.action_hud.raise_()
        if hasattr(self, "group_badge") and self.group_badge.isVisible():
            self.group_badge.raise_()

        punch_icons = self._should_punch_desktop_icons()
        mask_region = None
        if radius > 0:
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), radius, radius)
            mask_region = QRegion(path.toFillPolygon().toPolygon())
        elif punch_icons:
            mask_region = QRegion(self.rect())

        if punch_icons and mask_region is not None:
            local_holes = self._desktop_icon_hole_rects_local(force=False)
            for hole in local_holes:
                if not isinstance(hole, dict):
                    continue
                label_region = hole.get("label_region")
                if isinstance(label_region, QRegion) and not label_region.isEmpty():
                    mask_region = mask_region.subtracted(label_region)
                icon_region = hole.get("icon_region")
                if isinstance(icon_region, QRegion) and not icon_region.isEmpty():
                    mask_region = mask_region.subtracted(icon_region)

        # In clone mode, keep only the active rename editor area native.
        edit_local_rect = self._desktop_icon_edit_rect_local(force=False)
        if isinstance(edit_local_rect, QRect) and int(edit_local_rect.width()) > 0 and int(edit_local_rect.height()) > 0:
            if mask_region is None:
                mask_region = QRegion(self.rect())
            edit_hole = QRegion(edit_local_rect.adjusted(-2, -1, 2, 1))
            if not edit_hole.isEmpty():
                mask_region = mask_region.subtracted(edit_hole)

        if mask_region is not None:
            self.setMask(mask_region)
        else:
            self.clearMask()

    def update_playlist(self):
        _update_playlist_impl(self)

    def _set_watched_folder(self, folder_path):
        _set_watched_folder_impl(self, folder_path)

    def _on_folder_changed_signal(self, _path):
        _on_folder_changed_signal_impl(self, _path)

    def _refresh_playlist_from_folder_change(self):
        _refresh_playlist_from_folder_change_impl(self)

    def open_settings(self):
        if hasattr(self, "manager") and self.manager:
            if hasattr(self.manager, "is_temp_group_member") and self.manager.is_temp_group_member(self.profile_id):
                if len(getattr(self.manager, "_temp_group_ids", set())) >= 2:
                    if hasattr(self.manager, "open_bulk_settings"):
                        self.manager.open_bulk_settings()
                        return

        old_folder = self.folder_path
        old_exec = str(self.exec_path or "")

        sdata = _build_settings_dialog_data_impl(self)
        dialog = SettingsDialog(self, sdata, widget_name=str(sdata.get("name", "")))

        if dialog.exec():
            spread_data = getattr(dialog, "pending_spread_config", None)
            if spread_data and hasattr(self, "manager") and self.manager and hasattr(self.manager, "create_spread_widgets"):
                if self.manager.create_spread_widgets(self.profile_id, dict(spread_data), origin_widget=self):
                    return
            _apply_settings_dialog_result_impl(self, dialog, old_folder, old_exec)
        else:
            self.setWindowOpacity(self.current_opacity_pct / 100.0)

    def apply_window_settings(self, layer, lock, cancel_interaction=True):
        # Prevent stale drag/resize state from leaking across lock toggles.
        if bool(cancel_interaction) and hasattr(self, "cancel_active_interaction"):
            self.cancel_active_interaction()
        layer = self.coerce_layer_mode(layer, self.LAYER_SCHEMA_VERSION)
        self.layer_mode = layer
        self.is_locked = lock
        was_visible = self.isVisible()
        current_pos = self._global_top_left()
        current_size = self.size()

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if int(layer) == int(self.LAYER_BACK):
            flags |= Qt.WindowType.WindowStaysOnBottomHint
        elif int(layer) == int(self.LAYER_TOPMOST):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if lock:
            flags |= Qt.WindowType.WindowTransparentForInput

        hwnd = int(self.winId()) if was_visible else 0
        layer_changed = (getattr(self, "_last_applied_layer_mode", None) != int(layer))
        self._last_applied_layer_mode = int(layer)

        if hwnd and not layer_changed and win32gui.IsWindow(hwnd):
            try:
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if lock:
                    ex_style |= win32con.WS_EX_TRANSPARENT
                else:
                    ex_style &= ~win32con.WS_EX_TRANSPARENT
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
                win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED)
                self.overrideWindowFlags(flags)
            except Exception:
                self.setWindowFlags(flags)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                if was_visible:
                    self.show()
                self.resize(current_size)
                self._move_exact(current_pos)
        else:
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            if was_visible:
                self.show()
            self.resize(current_size)
            self._move_exact(current_pos)
        self.setWindowOpacity(float(self.current_opacity_pct) / 100.0)
        self.apply_mask_and_style()
        self._schedule_desktop_icon_overlay_bootstrap(retries=3, delay_ms=60)
        self._refresh_resize_ui()
        self._refresh_group_badge()

    def show_selection(self, state):
            if state:
                self.selection_overlay.setGeometry(self.rect())
                self.selection_overlay.show()
                self.selection_overlay.raise_()
                if hasattr(self, "resize_overlay") and self.resize_overlay.isVisible():
                    self.resize_overlay.raise_()
            else:
                self.selection_overlay.hide()

    def _schedule_settings_sync(self, delay_ms=None):
        _schedule_settings_sync_impl(self, delay_ms=delay_ms)

    def _flush_settings_sync(self):
        _flush_settings_sync_impl(self)

    def save_all_settings(self, sync=None):
        _save_all_settings_impl(self, sync=sync)

    def preview_opacity(self, val_pct):
        self.setWindowOpacity(val_pct / 100.0)

    def next_media(self, prefer_preload=True):
        _next_media_impl(self, prefer_preload=prefer_preload)

    def _update_static_pixmap_size(self):
        _update_static_pixmap_size_impl(self)

    def check_video_status(self, s, player=None):
        _check_video_status_impl(self, s, player=player)

    def _on_video_error(self, error, error_string, player=None):
        _on_video_error_impl(self, error, error_string, player=player)

    def _on_video_position_changed(self, position_ms, player=None):
        _on_video_position_changed_impl(self, position_ms, player=player)

    def _on_video_frame_changed(self, frame, slot=-1):
        _on_video_frame_changed_impl(self, frame, slot=slot)


    def mousePressEvent(self, e):
        _mouse_press_event_impl(self, e)

    def mouseMoveEvent(self, e):
        _mouse_move_event_impl(self, e)

    def mouseReleaseEvent(self, e):
        _mouse_release_event_impl(self, e)

    def wheelEvent(self, e):
        _wheel_event_impl(self, e)

    def dragEnterEvent(self, event):
        _drag_enter_event_impl(self, event)

    def dragMoveEvent(self, event):
        _drag_move_event_impl(self, event)

    def dragLeaveEvent(self, event):
        _drag_leave_event_impl(self, event)

    def dropEvent(self, event):
        _drop_event_impl(self, event)

    def contextMenuEvent(self, e):
        _context_menu_event_impl(self, e)

    def fit_to_screen(self, include_taskbar=False):
        _fit_to_screen_impl(self, include_taskbar=include_taskbar)

    def snap_fill_available_space(self):
        _snap_fill_available_space_impl(self)

    def open_master_controller(self):
        _open_master_controller_impl(self)

    def showEvent(self, e):
        _prepare_first_show_impl(self)
        super().showEvent(e)
        _handle_post_show_impl(self)

    def resizeEvent(self, e):
        _handle_resize_impl(self)
        super().resizeEvent(e)

    def moveEvent(self, e):
        _handle_move_impl(self)
        super().moveEvent(e)

    def closeEvent(self, event):
        _prepare_close_impl(self)
        super().closeEvent(event)


_bind_settings_dialog_desktop_widget(DesktopWidget)


class MasterController(QMainWindow):
    @staticmethod
    def _frozen_executable_path():
        return _mc_frozen_executable_path_impl()

    @staticmethod
    def _windows_startup_folder_path():
        return _mc_windows_startup_folder_path_impl()

    @staticmethod
    def _startup_shortcut_icon_path(exe_path):
        return _mc_startup_shortcut_icon_path_impl(exe_path)

    @staticmethod
    def _startup_shortcut_pref_key():
        return _mc_startup_shortcut_pref_key_impl()

    def _startup_shortcut_path(self, exe_path=""):
        return _mc_startup_shortcut_path_impl(self, exe_path=exe_path)

    def _startup_shortcut_enabled(self):
        return _mc_startup_shortcut_enabled_impl(self)

    @staticmethod
    def _fast_startup_enabled():
        return _mc_fast_startup_enabled_impl()

    @staticmethod
    def _minimal_validation_enabled():
        return _mc_minimal_validation_enabled_impl()

    @staticmethod
    def _fast_set_switch_enabled():
        return _mc_fast_set_switch_enabled_impl()

    @classmethod
    def _resolve_app_icon(cls):
        return _mc_resolve_app_icon_impl(cls)

    def _ensure_windows_startup_shortcut(self, force=False):
        _mc_ensure_windows_startup_shortcut_impl(self, force=force)

    def _remove_windows_startup_shortcut(self):
        _mc_remove_windows_startup_shortcut_impl(self)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyWidgetBox v6.0 - 위젯 컨트롤러")
        self._fast_startup_mode = bool(self._fast_startup_enabled())
        self.app_icon = self._resolve_app_icon()
        from mywidgetbox_core import apply_windows_dark_title_bar, render_vector_icon
        if self.app_icon and not self.app_icon.isNull():
            self.setWindowIcon(self.app_icon)
        else:
            self.setWindowIcon(render_vector_icon("widget", "#528bf8", 32))
        self.setObjectName("masterWindow")
        self.setMinimumSize(560, 520)
        QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(self))
        self.master_settings = QSettings("MyHomeApp", "MasterV3")
        w_saved = int(self.master_settings.value("window_width", 620))
        if w_saved < 560:
            w_saved = 620
        h_saved = int(self.master_settings.value("window_height", 680))
        self.resize(max(560, min(3000, w_saved)), max(520, min(3000, h_saved)))
        try:
            master_sync_ms = int(os.environ.get("MYCANVAS_MASTER_SYNC_MS", "650") or "650")
        except Exception:
            master_sync_ms = 650
        self._master_settings_sync_delay_ms = max(120, min(3000, int(master_sync_ms)))
        self._master_settings_sync_timer = QTimer(self)
        self._master_settings_sync_timer.setSingleShot(True)
        self._master_settings_sync_timer.timeout.connect(self._flush_master_settings_sync)
        self.widgets = {}
        self._desktop_widget_cls = DesktopWidget
        self._temp_group_ids = set()
        self._exec_window_claims = {}
        self.profile_rows = {}
        self._profile_row_items = {}
        self._add_widget_row_item = None
        self._add_widget_row_widget = None
        self._profiles_loaded_set_id = ""
        self._startup_queue = []
        self._startup_queue_active = False
        self._startup_queue_mode = "default"
        self._bulk_set_switch_active = False
        self._startup_queue_timer = QTimer(self)
        self._startup_queue_timer.setSingleShot(True)
        self._startup_queue_timer.timeout.connect(self._run_next_startup_item)


        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        tray_menu = QMenu()
        tray_menu.addAction("관리자 열기", self.show_master_window); tray_menu.addSeparator(); tray_menu.addAction("전체 종료", self.quit_app)
        self.tray_icon.setContextMenu(tray_menu); self.tray_icon.show()

        chk_icon_url = self._ensure_checkbox_check_icon()
        self.setStyleSheet("""
            QMainWindow#masterWindow {
                background-color: #121c2b;
            }
            QWidget#masterRoot {
                background-color: #121c2b;
            }
            QFrame#titleBar {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QLabel#titleLabel {
                color: #f5f7ff;
                font-size: 17px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            QLabel#subtitleLabel {
                color: #9cb5d8;
                font-size: 11px;
            }
            QLabel#groupHeaderLabel {
                color: #92bbf8;
                font-size: 12px;
                font-weight: 700;
                padding: 6px 2px 2px 2px;
            }
            QLabel#gpuCfgLabel {
                color: #d6e2f7;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#gpuCfgValue {
                color: #edf3ff;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#gpuCfgHint {
                color: #b8c9e6;
                font-size: 10px;
            }
            QCheckBox#startupToggle,
            QCheckBox#fullscreenPauseToggle {
                color: #e4ecfb;
                font-size: 11px;
                font-weight: 600;
                spacing: 6px;
                min-height: 22px;
            }
            QCheckBox#startupToggle:hover,
            QCheckBox#fullscreenPauseToggle:hover {
                color: #ffffff;
            }
            QToolButton#gpuCfgBtn {
                min-width: 50px;
                min-height: 28px;
                color: #eef3ff;
                background-color: #1e314d;
                border: 1px solid #3b5a88;
                border-radius: 8px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QToolButton#gpuCfgBtn:hover {
                background-color: #2b456e;
                border-color: #527eb8;
            }
            QToolButton#gpuCfgBtn:checked {
                background-color: #3b609c;
                border-color: #689af0;
            }
            QPushButton#addSetHeaderBtn, QPushButton#guideHeaderBtn {
                min-height: 28px;
                border-radius: 8px;
                color: #eef3ff;
                background-color: #223756;
                border: 1px solid #436696;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton#addSetHeaderBtn:hover, QPushButton#guideHeaderBtn:hover {
                background-color: #304e7a;
                border-color: #5d87bf;
            }
            QFrame#gpuCfgPopup {
                background-color: #1a2940;
                border: 1px solid #3d5c8a;
                border-radius: 10px;
            }
            QScrollArea#accordionScroll {
                background: transparent;
                border: none;
            }
            QWidget#accordionContainer {
                background: transparent;
            }
            QFrame#setGroupCard {
                background-color: #162438;
                border: 1.5px solid #283d5a;
                border-radius: 12px;
            }
            QFrame#setGroupCard[applied="true"] {
                background-color: #17273e;
                border: 1.5px solid #3b68d4;
            }
            QFrame#setGroupHeader {
                background-color: #1c2e47;
                border: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
                min-height: 44px;
            }
            QFrame#setGroupHeader[expanded="true"] {
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border-bottom: 1px solid #283d5a;
            }
            QLabel#setGroupTitle {
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#setCountBadge {
                color: #7ea3d4;
                background-color: #101c2e;
                border: 1px solid #253954;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#setAppliedBadge {
                color: #10b981;
                background-color: rgba(16, 185, 129, 0.15);
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#setApplyBtn {
                min-height: 26px;
                border-radius: 6px;
                color: #ffffff;
                background-color: #3b68d4;
                border: 1px solid #5a85ea;
                font-size: 11px;
                font-weight: 700;
                padding: 0 10px;
            }
            QPushButton#setApplyBtn:hover {
                background-color: #4a77e8;
            }
            QFrame#setGroupBody {
                background-color: #131f30;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
                padding: 6px 8px 10px 8px;
            }
            QWidget#treeChildRow {
                background-color: #18273d;
                border: 1px solid #233752;
                border-radius: 8px;
                min-height: 40px;
            }
            QWidget#treeChildRow:hover {
                background-color: #213550;
                border-color: #385680;
            }
            QWidget#treeChildRow[running="true"] {
                background-color: #1a313d;
                border-color: #225a4a;
            }
            QPushButton#addTreeWidgetBtn {
                min-height: 28px;
                border-radius: 8px;
                color: #8da8cb;
                background-color: rgba(24, 39, 61, 0.4);
                border: 1px dashed #334d70;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 18px;
                text-align: center;
            }
            QPushButton#addTreeWidgetBtn:hover {
                background-color: #213550;
                border-color: #528bf8;
                color: #ffffff;
            }
            QSlider#gpuCfgSlider::groove:horizontal {
                height: 6px;
                border-radius: 3px;
                background: #395378;
            }
            QSlider#gpuCfgSlider::handle:horizontal {
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
                border: none;
                background: #7ea8f0;
            }
            QListWidget#profileList {
                background-color: rgba(24, 38, 60, 220);
                border: 1px solid #45618a;
                border-radius: 14px;
                padding: 6px 8px;
                outline: none;
            }
            QListWidget#profileList::item {
                border: none;
                padding: 0px;
            }
            QListWidget#profileList::item:selected {
                background-color: transparent;
            }
            QWidget#profileRow {
                background-color: transparent;
                border: none;
            }
            QWidget#addWidgetRow {
                background-color: transparent;
                border: none;
            }
            QWidget#profileRow[hovered="true"] {
                background-color: rgba(138, 173, 233, 40);
            }
            QWidget#profileRow[selected="true"] {
                background-color: rgba(150, 192, 255, 56);
            }
            QWidget#profileRow[running="true"][selected="true"] {
                background-color: rgba(119, 205, 178, 56);
            }
            QLabel#profileName {
                color: #edf2ff;
                font-size: 13px;
                font-weight: 600;
                padding: 0;
            }
            QLabel#statusDot {
                min-width: 3px;
                max-width: 3px;
                min-height: 16px;
                max-height: 16px;
                border-radius: 1px;
                background-color: #55667e;
                padding: 0px;
                margin: 0px;
            }
            QLabel#statusDot[running="true"] {
                background-color: #58c796;
            }
            QPushButton#primaryBtn,
            QPushButton#secondaryBtn,
            QPushButton#dangerBtn {
                min-height: 40px;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton#primaryBtn {
                color: #edf2ff;
                background-color: #406bdc;
                border: 1px solid #5f84e5;
            }
            QPushButton#primaryBtn:hover {
                background-color: #4a74e2;
            }
            QPushButton#primaryBtn:pressed {
                background-color: #365fc6;
            }
            QPushButton#secondaryBtn {
                color: #e5edf8;
                background-color: #283a54;
                border: 1px solid #3f5678;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #33486a;
            }
            QPushButton#secondaryBtn:pressed {
                background-color: #263a56;
            }
            QPushButton#secondaryBtn[pendingApply="true"] {
                color: #10251d;
                background-color: #58c796;
                border: 1px solid #7ad8af;
            }
            QPushButton#secondaryBtn[pendingApply="true"]:hover {
                background-color: #68d3a3;
            }
            QPushButton#secondaryBtn[pendingApply="true"]:pressed {
                background-color: #4cb487;
            }
            QPushButton#dangerBtn {
                color: #ffe8ec;
                background-color: #8f3741;
                border: 1px solid #b55460;
            }
            QPushButton#dangerBtn:hover {
                background-color: #a3434e;
            }
            QPushButton#dangerBtn:pressed {
                background-color: #7f2f39;
            }
            QPushButton[kind="rowAction"] {
                min-width: 28px;
                min-height: 28px;
                max-width: 28px;
                max-height: 28px;
                border-radius: 7px;
                padding: 0px;
                margin: 0px;
                text-align: center;
                color: #dbe4f6;
                background-color: transparent;
                border: none;
            }
            QPushButton[kind="rowAction"]:hover {
                background-color: #375074;
            }
            QPushButton[kind="rowAction"]:pressed {
                background-color: #21314b;
            }
            QPushButton#runBtn {
                border: none;
                color: #dbfff3;
            }
            QPushButton#runBtn:hover {
                background-color: #2b7d68;
            }
            QPushButton#stopBtn {
                border: none;
                color: #ffe9ef;
            }
            QPushButton#stopBtn:hover {
                background-color: #755b67;
            }
            QPushButton#deleteBtn {
                border: none;
                color: #ffe4e9;
            }
            QPushButton#deleteBtn:hover {
                background-color: #7b4a54;
            }
            QPushButton#setBtn {
                border: none;
                color: #e3edff;
            }
            QPushButton#setBtn:hover {
                background-color: #45638f;
            }
            QPushButton[kind="rowAction"]:disabled {
                background-color: #1b2639;
                border: none;
                color: #6f7f99;
            }
            QPushButton#bulkRunBtn,
            QPushButton#bulkStopBtn,
            QPushButton#bulkActionBtn,
            QPushButton#bulkDeleteBtn {
                min-height: 25px;
                padding: 0 4px;
                font-size: 11px;
                font-weight: 600;
                border-radius: 6px;
                color: #e5edf8;
                background-color: #283a54;
                border: 1px solid #486187;
            }
            QPushButton#bulkRunBtn:hover {
                background-color: #2b7d68;
                border-color: #4bd8b3;
                color: #dbfff3;
            }
            QPushButton#bulkStopBtn:hover {
                background-color: #6e505e;
                border-color: #a8738a;
                color: #ffe9ef;
            }
            QPushButton#bulkActionBtn:hover {
                background-color: #3b5780;
                border-color: #6287be;
                color: #ffffff;
            }
            QPushButton#bulkDeleteBtn:hover {
                background-color: #8c3642;
                border-color: #b54f5c;
                color: #ffe4e9;
            }
            QPushButton#bulkRunBtn:disabled,
            QPushButton#bulkStopBtn:disabled,
            QPushButton#bulkActionBtn:disabled,
            QPushButton#bulkDeleteBtn:disabled {
                color: #556478;
                background-color: #1e2a3c;
                border-color: #2a374a;
            }
            QCheckBox#selectAllCheck,
            QCheckBox#profileCheck {
                spacing: 0px;
                padding: 0px;
                margin: 0px;
            }
            QCheckBox#selectAllCheck::indicator,
            QCheckBox#profileCheck::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #4a668e;
                background-color: #172437;
            }
            QCheckBox#selectAllCheck::indicator:hover,
            QCheckBox#profileCheck::indicator:hover {
                border-color: #6a8ec2;
                background-color: #20334d;
            }
            QCheckBox#selectAllCheck::indicator:checked,
            QCheckBox#profileCheck::indicator:checked {
                background-color: #4a74e2;
                border-color: #7fa0f0;
                image: url(""" + chk_icon_url + """);
            }
            QCheckBox#selectAllCheck::indicator:disabled,
            QCheckBox#profileCheck::indicator:disabled {
                border-color: #35455c;
                background-color: #182230;
            }
        """)

        central = QWidget()
        central.setObjectName("masterRoot")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_bar = QFrame()
        title_bar.setObjectName("titleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(4, 2, 4, 4)
        title_bar_layout.setSpacing(8)

        from mywidgetbox_core import render_vector_icon

        title_bar_layout.addStretch(1)

        self.guide_btn = QPushButton("설명서")
        self.guide_btn.setObjectName("guideHeaderBtn")
        self.guide_btn.setIcon(render_vector_icon("help", "#eef3ff", 12))
        self.guide_btn.setIconSize(QSize(12, 12))
        self.guide_btn.setToolTip("MyWidgetBox 사용 설명서 열기")
        self.guide_btn.clicked.connect(self.open_guide_dialog)

        self.add_set_header_btn = QPushButton("새로운 세트")
        self.add_set_header_btn.setObjectName("addSetHeaderBtn")
        self.add_set_header_btn.setIcon(render_vector_icon("plus", "#eef3ff", 12))
        self.add_set_header_btn.setIconSize(QSize(12, 12))
        self.add_set_header_btn.setToolTip("새로운 위젯 세트 생성")
        self.add_set_header_btn.clicked.connect(self._on_add_set_clicked)

        self.gpu_cfg_toggle = QToolButton()
        self.gpu_cfg_toggle.setObjectName("gpuCfgBtn")
        self.gpu_cfg_toggle.setCheckable(True)
        self.gpu_cfg_toggle.setChecked(False)
        self.gpu_cfg_toggle.setText("GPU")
        self.gpu_cfg_toggle.setToolTip("GPU 부하 모니터링 및 자동 정지 설정")
        self.gpu_cfg_toggle.toggled.connect(self._toggle_gpu_cfg_panel)

        title_bar_layout.addWidget(self.guide_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        title_bar_layout.addWidget(self.add_set_header_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        title_bar_layout.addWidget(self.gpu_cfg_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(title_bar)

        self.gpu_cfg_panel = QFrame(self)
        self.gpu_cfg_panel.setObjectName("gpuCfgPopup")
        self.gpu_cfg_panel.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.gpu_cfg_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        gpu_cfg_panel_layout = QVBoxLayout(self.gpu_cfg_panel)
        gpu_cfg_panel_layout.setContentsMargins(10, 8, 10, 10)
        gpu_cfg_panel_layout.setSpacing(6)

        self.gpu_guard_enable_cb = QCheckBox("GPU 과부하 시 미디어 자동 일시정지")
        self.gpu_guard_enable_cb.setObjectName("gpuGuardMasterToggle")
        self.gpu_guard_enable_cb.setToolTip(
            "PC의 GPU 사용률이 설정치를 초과하면 모든 위젯의 미디어 재생을 일시정지하여 게임 및 작업 성능을 확보합니다."
        )
        gpu_cfg_panel_layout.addWidget(self.gpu_guard_enable_cb)

        gpu_pause_row = QHBoxLayout()
        gpu_pause_row.setContentsMargins(0, 0, 0, 0)
        gpu_pause_row.setSpacing(6)
        gpu_pause_lbl = QLabel("GPU 일시정지")
        gpu_pause_lbl.setObjectName("gpuCfgLabel")
        self.gpu_pause_value_lbl = QLabel("90%")
        self.gpu_pause_value_lbl.setObjectName("gpuCfgValue")
        gpu_pause_row.addWidget(gpu_pause_lbl)
        gpu_pause_row.addStretch()
        gpu_pause_row.addWidget(self.gpu_pause_value_lbl)
        gpu_cfg_panel_layout.addLayout(gpu_pause_row)

        self.gpu_pause_slider = QSlider(Qt.Orientation.Horizontal)
        self.gpu_pause_slider.setObjectName("gpuCfgSlider")
        self.gpu_pause_slider.setRange(1, 100)
        self.gpu_pause_slider.setSingleStep(1)
        self.gpu_pause_slider.wheelEvent = lambda event: event.ignore()
        gpu_cfg_panel_layout.addWidget(self.gpu_pause_slider)

        gpu_resume_row = QHBoxLayout()
        gpu_resume_row.setContentsMargins(0, 0, 0, 0)
        gpu_resume_row.setSpacing(6)
        gpu_resume_lbl = QLabel("GPU 재개")
        gpu_resume_lbl.setObjectName("gpuCfgLabel")
        self.gpu_resume_value_lbl = QLabel("70%")
        self.gpu_resume_value_lbl.setObjectName("gpuCfgValue")
        gpu_resume_row.addWidget(gpu_resume_lbl)
        gpu_resume_row.addStretch()
        gpu_resume_row.addWidget(self.gpu_resume_value_lbl)
        gpu_cfg_panel_layout.addLayout(gpu_resume_row)

        self.gpu_resume_slider = QSlider(Qt.Orientation.Horizontal)
        self.gpu_resume_slider.setObjectName("gpuCfgSlider")
        self.gpu_resume_slider.setRange(0, 99)
        self.gpu_resume_slider.setSingleStep(1)
        self.gpu_resume_slider.wheelEvent = lambda event: event.ignore()
        gpu_cfg_panel_layout.addWidget(self.gpu_resume_slider)

        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.Shape.HLine)
        sep_line.setStyleSheet("background-color: #283a54; min-height: 1px; max-height: 1px; border: none; margin: 4px 0;")
        gpu_cfg_panel_layout.addWidget(sep_line)

        self.startup_shortcut_cb = QCheckBox("시작프로그램 등록")
        self.startup_shortcut_cb.setObjectName("startupToggle")
        gpu_cfg_panel_layout.addWidget(self.startup_shortcut_cb)

        self.startup_shortcut_hint_lbl = QLabel("")
        self.startup_shortcut_hint_lbl.setObjectName("gpuCfgHint")
        self.startup_shortcut_hint_lbl.setWordWrap(True)
        gpu_cfg_panel_layout.addWidget(self.startup_shortcut_hint_lbl)

        self.pause_on_fullscreen_cb = QCheckBox("다른 앱 전체화면 시 미디어 일시정지")
        self.pause_on_fullscreen_cb.setObjectName("fullscreenPauseToggle")
        self.pause_on_fullscreen_cb.setToolTip(
            "게임이나 전체화면 동영상/앱 실행 중일 때 바탕화면 위젯의 GIF 및 영상 재생을 자동으로 일시정지합니다."
        )
        gpu_cfg_panel_layout.addWidget(self.pause_on_fullscreen_cb)

        self.fullscreen_pause_hint_lbl = QLabel("전체화면 게임/영상 실행 시 GIF·영상 정지 (창 복귀 시 자동 재개)")
        self.fullscreen_pause_hint_lbl.setObjectName("gpuCfgHint")
        self.fullscreen_pause_hint_lbl.setWordWrap(True)
        gpu_cfg_panel_layout.addWidget(self.fullscreen_pause_hint_lbl)
        self.gpu_cfg_panel.installEventFilter(self)

        # Accordion Tree Scroll Area
        self.accordion_scroll = QScrollArea()
        self.accordion_scroll.setObjectName("accordionScroll")
        self.accordion_scroll.setWidgetResizable(True)
        self.accordion_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.accordion_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.accordion_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.accordion_container = QWidget()
        self.accordion_container.setObjectName("accordionContainer")
        self.accordion_layout = QVBoxLayout(self.accordion_container)
        self.accordion_layout.setContentsMargins(0, 4, 0, 4)
        self.accordion_layout.setSpacing(8)
        self.accordion_scroll.setWidget(self.accordion_container)
        layout.addWidget(self.accordion_scroll, 1)

        # Fallback profile list (for compatibility)
        self.list_widget = ProfileListWidget()
        self.list_widget.setVisible(False)

        self._set_expanded_states = {}
        self.profile_rows = {}
        self._set_toolbars = {}

        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        self.exit_btn = QPushButton("프로그램 종료")
        self.exit_btn.setObjectName("dangerBtn")
        self.exit_btn.setIcon(render_vector_icon("close", "#fca5a5", 13))
        self.exit_btn.setIconSize(QSize(13, 13))
        self.exit_btn.clicked.connect(self.quit_app)
        btn_box.addWidget(self.exit_btn, 1)
        layout.addLayout(btn_box)

        self._set_order = []
        self._set_defs = {}
        self._current_set_id = ""
        self._applied_set_id = ""
        self._load_set_state()
        self._migrate_profile_run_flags()
        self._refresh_set_ui()
        self.load_profiles(force_rebuild=True)
        QTimer.singleShot(0, self.restore_last_session)
        app = QApplication.instance()
        if app:
            app.focusChanged.connect(self.handle_focus_change)
            app.installEventFilter(self)
        self._alt_click_pressed_prev = False
        self._alt_click_poll_timer = QTimer(self)
        self._alt_click_poll_timer.setInterval(30)
        self._alt_click_poll_timer.timeout.connect(self._poll_alt_click_toggle_lock)
        self._alt_click_poll_timer.start()
        self._gpu_sampler = GpuUsageSampler()
        self._gpu_guard_paused = False
        self._gpu_last_usage = 0.0
        self._gpu_high_streak = 0
        self._gpu_low_streak = 0
        self._gpu_below_high_streak = 0
        self._gpu_guard_high_pct = 90.0
        self._gpu_guard_low_pct = 70.0
        self._gpu_guard_high_hold = 2
        self._gpu_guard_low_hold = 3
        self._hovered_profile_pid = None
        self._apply_gpu_guard_thresholds(
            self.master_settings.value("gpu_guard_high_pct", 90),
            self.master_settings.value("gpu_guard_low_pct", 70),
            persist=False,
        )
        self._sync_gpu_threshold_inputs()
        self._gpu_guard_enabled = _as_bool(self.master_settings.value("gpu_guard_enabled", True), True)
        self.gpu_guard_enable_cb.setChecked(self._gpu_guard_enabled)
        self.gpu_pause_slider.setEnabled(self._gpu_guard_enabled)
        self.gpu_resume_slider.setEnabled(self._gpu_guard_enabled)
        self.gpu_guard_enable_cb.toggled.connect(self._on_gpu_guard_enable_toggled)
        self.gpu_pause_slider.valueChanged.connect(self._on_gpu_threshold_inputs_changed)
        self.gpu_resume_slider.valueChanged.connect(self._on_gpu_threshold_inputs_changed)
        self.startup_shortcut_cb.toggled.connect(self._on_startup_shortcut_toggled)
        self._sync_startup_shortcut_toggle()
        self._pause_on_fullscreen = _as_bool(self.master_settings.value("pause_on_fullscreen", True), True)
        self._fullscreen_paused = False
        self.pause_on_fullscreen_cb.setChecked(self._pause_on_fullscreen)
        self.pause_on_fullscreen_cb.toggled.connect(self._on_pause_on_fullscreen_toggled)
        self._gpu_guard_timer = QTimer(self)
        self._gpu_guard_timer.setInterval(1000)
        self._gpu_guard_timer.timeout.connect(self._poll_gpu_guard)
        self._gpu_guard_timer.start()
        QTimer.singleShot(0, self._apply_title_bar_theme)
        if self.startup_shortcut_cb.isChecked():
            QTimer.singleShot(1800, lambda: self._ensure_windows_startup_shortcut(force=True))
        
    @staticmethod
    def _as_list(value):
        return _mset_as_list_impl(value)

    @staticmethod
    def _normalize_ids(values):
        return _mset_normalize_ids_impl(values)

    def _set_key(self, set_id, field):
        return _mset_set_key_impl(self, set_id, field)

    def _all_profile_ids(self):
        return _mset_all_profile_ids_impl(self)

    def _next_profile_id(self, existing_ids=None):
        return _mset_next_profile_id_impl(self, existing_ids=existing_ids)

    def _next_set_id(self):
        return _mset_next_set_id_impl(self)

    def _default_set_name(self):
        return _mset_default_set_name_impl(self)

    def _profile_run_enabled(self, pid):
        return _mset_profile_run_enabled_impl(self, pid)

    def _set_profile_run_enabled(self, pid, enabled):
        _mset_set_profile_run_enabled_impl(self, pid, enabled)

    def _clone_profile_settings(self, src_pid, dst_pid):
        _mset_clone_profile_settings_impl(self, src_pid, dst_pid)

    def _set_current_set_id(self, set_id, persist=True):
        _mset_set_current_set_id_impl(self, set_id, persist=persist)

    def selected_set_id(self):
        return _mset_selected_set_id_impl(self)

    def get_set_items(self):
        return _mset_get_set_items_impl(self)

    def _clear_set_list_sidebar(self):
        if not hasattr(self, "set_list_layout"):
            return
        while self.set_list_layout.count():
            item = self.set_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_name_width(self):
        base = self._set_sidebar_collapsed_width if self._set_list_collapsed else self._set_sidebar_expanded_width
        return max(40, int(base) - 46)

    def _elide_set_text(self, text):
        width = self._set_name_width()
        metrics = QFontMetrics(self.font())
        return metrics.elidedText(str(text), Qt.TextElideMode.ElideRight, width)

    def _set_sidebar_collapsed(self, collapsed, persist=True):
        collapsed = bool(collapsed)
        if self._set_list_collapsed == collapsed:
            if persist:
                self.master_settings.setValue("set_list_collapsed", bool(collapsed))
                self.master_settings.sync()
            return
        self._set_list_collapsed = collapsed
        if persist:
            self.master_settings.setValue("set_list_collapsed", bool(collapsed))
            self.master_settings.sync()
        self._refresh_set_ui()

    def _clear_accordion_layout(self):
        if not hasattr(self, "accordion_layout"):
            return
        while self.accordion_layout.count():
            item = self.accordion_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _toggle_set_expanded(self, sid):
        sid = str(sid)
        curr = self._set_expanded_states.get(sid, True)
        self._set_expanded_states[sid] = not curr
        self.load_profiles(force_rebuild=True)

    def _on_apply_set_clicked(self, sid):
        sid = str(sid)
        self._set_current_set_id(sid, persist=True)
        self.run_all()

    def _rebuild_set_sidebar(self):
        self.load_profiles(force_rebuild=True)

    def _refresh_set_ui(self):
        self.load_profiles(force_rebuild=True)
        self._refresh_apply_button_state()

    def _refresh_apply_button_state(self):
        pass

    def _on_set_selected(self, sid):
        sid = str(sid)
        if sid not in self._set_defs:
            return
        current_sid = self.selected_set_id()
        if not self._set_list_collapsed and sid == current_sid:
            self._set_sidebar_collapsed(True, persist=True)
            self.load_profiles(force_rebuild=True)
            return
        if self._set_list_collapsed:
            self._set_sidebar_collapsed(False, persist=True)
        self._set_current_set_id(sid, persist=True)
        self.clear_all_highlights()
        self.load_profiles(force_rebuild=True)

    def _on_set_name_double_clicked(self, sid):
        sid = str(sid)
        if sid not in self._set_defs:
            return
        current_name = str(self._set_defs.get(sid, {}).get("name", f"세트{sid}"))
        new_name, ok = self._prompt_text_dialog("세트 이름 변경", "세트 이름:", current_name)
        if not ok or not new_name:
            return
        self.rename_set(sid, new_name)

    def _on_add_set_clicked(self):
        default_name = self._default_set_name()
        name, ok = self._prompt_text_dialog("새 세트", "새 세트 이름:", default_name)
        if not ok or not name:
            return
        sid = self.create_empty_set(name)
        if sid:
            self._set_expanded_states[str(sid)] = True
            self._set_current_set_id(str(sid), persist=True)
            self.load_profiles(force_rebuild=True)

    def open_set_manager(self, set_id=None):
        self._load_set_state()
        sid = str(set_id) if set_id not in (None, "") else self.selected_set_id()
        dialog = SetManagerDialog(self, target_sid=sid)
        dialog.exec()
        self._refresh_set_ui()
        self.load_profiles()

    def open_guide_dialog(self):
        from guide_dialog import GuideDialog
        dlg = GuideDialog(self)
        dlg.exec()

    def _load_set_state(self):
        _mset_load_set_state_impl(self)

    def _migrate_profile_run_flags(self):
        _mset_migrate_profile_run_flags_impl(self)

    def _current_set_profiles(self):
        return _mset_current_set_profiles_impl(self)

    def _set_current_profiles(self, profile_ids):
        _mset_set_current_profiles_impl(self, profile_ids)

    def _remove_profile_from_sets(self, profile_id):
        _mset_remove_profile_from_sets_impl(self, profile_id)

    def _cleanup_orphan_profiles(self):
        return _mset_cleanup_orphan_profiles_impl(self)

    def _profile_startup_media_kind(self, pid):
        spid = str(pid)
        settings = QSettings("MyHomeApp", f"Profile_{spid}")
        fip = settings.value("folder_item_paths")
        path = ""
        if fip:
            path = fip[0] if isinstance(fip, list) else str(fip)
        if not path:
            path = str(settings.value("image_path", "") or "")
        if not path:
            folder_path = str(settings.value("folder_path", "") or "").strip()
            if folder_path and os.path.isdir(folder_path):
                try:
                    media_ext = DesktopWidget._supported_media_extensions()
                    for name in sorted(os.listdir(folder_path)):
                        low = str(name).lower()
                        if low.endswith(media_ext):
                            path = os.path.join(folder_path, str(name))
                            break
                except Exception:
                    pass
        if path:
            target = str(path).strip().lower()
            if DesktopWidget._is_video_path(target):
                return "video"
            if DesktopWidget._is_gif_path(target):
                return "gif"
            if DesktopWidget._is_image_path(target):
                return "image"
        return "other"

    def _start_deferred_playbacks(self):
        deferred = [
            w for w in self.widgets.values()
            if isinstance(w, DesktopWidget) and bool(getattr(w, "_deferred_playback_pending", False))
        ]
        if not deferred:
            return
        for w in deferred:
            try:
                w._resume_deferred_playback()
            except Exception:
                pass

    def _bootstrap_all_desktop_icon_overlays(self):
        for w in self.widgets.values():
            if isinstance(w, DesktopWidget) and (w._should_clone_desktop_icons() or w._should_punch_desktop_icons()):
                try:
                    w._schedule_desktop_icon_overlay_bootstrap(retries=2, delay_ms=60)
                except Exception:
                    pass

    @staticmethod
    def _startup_delay_for_kind(kind, mode="default"):
        return _mqueue_startup_delay_for_kind_impl(kind, mode=mode)

    def _cancel_startup_queue(self):
        _mqueue_cancel_startup_queue_impl(self)

    def _build_profile_startup_queue(self, profile_ids):
        return _mqueue_build_profile_startup_queue_impl(self, profile_ids)

    def _build_set_startup_queue(self, set_id):
        return _mqueue_build_set_startup_queue_impl(self, set_id)

    def _begin_startup_queue(self, entries, mode="default"):
        _mqueue_begin_startup_queue_impl(self, entries, mode=mode)

    def _run_next_startup_item(self):
        _mqueue_run_next_startup_item_impl(self)

    def _sync_all_widget_video_viewports(self):
        _mwr_sync_all_widget_video_viewports_impl(self)

    def _start_widget_instance(self, pid, name, startup_kind=""):
        return _mwr_start_widget_instance_impl(self, pid, name, startup_kind=startup_kind)

    def _stop_widgets_bulk(self, target_ids):
        return _mwr_stop_widgets_bulk_impl(self, target_ids)

    def _stop_all_widgets_bulk(self):
        return _mwr_stop_all_widgets_bulk_impl(self)

    def is_temp_group_member(self, pid):
        return _mtg_is_temp_group_member_impl(self, pid)

    def _sync_temp_group_badges(self):
        _mtg_sync_temp_group_badges_impl(self)
        self._sync_temp_group_list_checkboxes()

    def _sync_temp_group_list_checkboxes(self):
        for spid, row in list(getattr(self, "profile_rows", {}).items()):
            if isinstance(row, ProfileRowWidget) and hasattr(row, "_checkbox") and row._checkbox:
                should_check = (str(spid) in self._temp_group_ids)
                if row._checkbox.isChecked() != should_check:
                    row._checkbox.blockSignals(True)
                    row._checkbox.setChecked(should_check)
                    row._checkbox.blockSignals(False)
        self._sync_bulk_action_ui()

    def _refresh_temp_group_ui(self):
        self._sync_temp_group_badges()
        self._sync_temp_group_list_checkboxes()

    def toggle_temp_group_member(self, pid):
        return _mtg_toggle_temp_group_member_impl(self, pid)

    def clear_temp_group(self, silent=False):
        return _mtg_clear_temp_group_impl(self, silent=silent)

    def start_marquee_selection(self, global_start_pos):
        if not hasattr(self, "_marquee_overlay") or self._marquee_overlay is None:
            self._marquee_overlay = MarqueeSelectionOverlay(self)
        self._marquee_overlay.start_selection(global_start_pos)

    def finish_marquee_selection(self, selection_rect):
        if not selection_rect or (selection_rect.width() < 5 and selection_rect.height() < 5):
            return
        matched_pids = []
        for pid, w in self.widgets.items():
            if not isinstance(w, QWidget) or not w.isVisible():
                continue
            if w.geometry().intersects(selection_rect):
                matched_pids.append(str(pid))
        modifiers = QApplication.keyboardModifiers()
        is_add = bool(modifiers & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier))
        if not matched_pids:
            if not is_add and self._temp_group_ids:
                self.clear_temp_group()
            return
        if not is_add:
            self._temp_group_ids.clear()
        for pid in matched_pids:
            self._temp_group_ids.add(str(pid))
        self._sync_temp_group_badges()
        for pid in matched_pids:
            w = self.widgets.get(str(pid))
            if w and hasattr(w, "_show_action_hud"):
                w._show_action_hud(f"임시 그룹 ({len(self._temp_group_ids)}개)")

    def _temp_group_shortcut_targets(self, source_pid):
        return _mtg_temp_group_shortcut_targets_impl(self, source_pid)

    def _temp_group_move_targets(self, source_pid):
        return _mtg_temp_group_move_targets_impl(self, source_pid)

    def move_temp_group_by_delta(self, source_pid, dx, dy):
        _mtg_move_temp_group_by_delta_impl(self, source_pid, dx, dy)

    def resize_temp_group_by_edges(self, source_pid, left_step, top_step, right_step, bottom_step):
        _mtg_resize_temp_group_by_edges_impl(self, source_pid, left_step, top_step, right_step, bottom_step)

    def save_temp_group_positions(self, source_pid):
        _mtg_save_temp_group_positions_impl(self, source_pid)

    def _cleanup_exec_window_claims(self):
        _mclaim_cleanup_exec_window_claims_impl(self)

    def get_exec_window_owner(self, hwnd):
        return _mclaim_get_exec_window_owner_impl(self, hwnd)

    def claim_exec_window(self, profile_id, hwnd):
        return _mclaim_claim_exec_window_impl(self, profile_id, hwnd)

    def release_exec_window_claim(self, profile_id=None, hwnd=None):
        _mclaim_release_exec_window_claim_impl(self, profile_id=profile_id, hwnd=hwnd)

    def set_temp_group_mute(self, source_pid, muted):
        _mtg_set_temp_group_mute_impl(self, source_pid, muted)

    def set_temp_group_gpu_guard(self, source_pid, enabled):
        _mtg_set_temp_group_gpu_guard_impl(self, source_pid, enabled)

    def set_temp_group_corner_mode(self, source_pid, mode):
        _mtg_set_temp_group_corner_mode_impl(self, source_pid, mode)

    def adjust_temp_group_opacity(self, source_pid, delta_pct):
        _mtg_adjust_temp_group_opacity_impl(self, source_pid, delta_pct)

    def adjust_temp_group_layer(self, source_pid, step):
        _mtg_adjust_temp_group_layer_impl(self, source_pid, step)

    def set_temp_group_lock(self, source_pid, lock):
        return _mtg_set_temp_group_lock_impl(self, source_pid, lock)

    def apply_set(self, set_id):
        _mset_apply_set_impl(self, set_id)

    def create_empty_set(self, name):
        return _mset_create_empty_set_impl(self, name)

    def copy_set(self, source_set_id, new_name):
        return _mset_copy_set_impl(self, source_set_id, new_name)

    def copy_profiles_from_set(self, source_set_id, target_set_id):
        return _mset_copy_profiles_from_set_impl(self, source_set_id, target_set_id)

    def rename_set(self, set_id, new_name):
        return _mset_rename_set_impl(self, set_id, new_name)

    def delete_set(self, set_id, parent=None):
        return _mset_delete_set_impl(self, set_id, parent=parent)

    def _on_profile_order_changed(self, ordered_ids):
        _mset_on_profile_order_changed_impl(self, ordered_ids)


    def _toggle_gpu_cfg_panel(self, expanded=None):
        if expanded is None:
            expanded = self.gpu_cfg_toggle.isChecked()
        expanded = bool(expanded)
        if expanded:
            self._place_gpu_cfg_panel()
            self.gpu_cfg_panel.show()
            self.gpu_cfg_panel.raise_()
            self.gpu_cfg_panel.activateWindow()
        else:
            self.gpu_cfg_panel.hide()

    def _place_gpu_cfg_panel(self):
        self.gpu_cfg_panel.adjustSize()
        hint = self.gpu_cfg_panel.sizeHint()
        popup_w = max(280, hint.width())
        popup_h = hint.height()

        anchor_global = self.gpu_cfg_toggle.mapToGlobal(QPoint(0, self.gpu_cfg_toggle.height() + 6))
        x = anchor_global.x() - (popup_w - self.gpu_cfg_toggle.width())
        y = anchor_global.y()

        screen = QGuiApplication.screenAt(anchor_global) or self.screen() or QGuiApplication.primaryScreen()
        if screen:
            ag = screen.availableGeometry()
            x = max(ag.left() + 8, min(x, ag.right() - popup_w - 8))
            y = max(ag.top() + 8, min(y, ag.bottom() - popup_h - 8))

        self.gpu_cfg_panel.setGeometry(x, y, popup_w, popup_h)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            if self._is_master_internal_object(obj):
                QTimer.singleShot(0, self._activate_from_internal_click)
        if obj is getattr(self, "gpu_cfg_panel", None):
            if event.type() == QEvent.Type.Hide and self.gpu_cfg_toggle.isChecked():
                prev = self.gpu_cfg_toggle.blockSignals(True)
                self.gpu_cfg_toggle.setChecked(False)
                self.gpu_cfg_toggle.blockSignals(prev)
        list_widget = getattr(self, "list_widget", None)
        viewport = list_widget.viewport() if list_widget is not None else None
        if obj is viewport:
            if event.type() == QEvent.Type.Leave:
                self._set_hovered_profile_row(None)
        return super().eventFilter(obj, event)

    def _is_master_internal_object(self, obj):
        if obj is self:
            return True
        if not isinstance(obj, QWidget):
            return False
        if obj is getattr(self, "gpu_cfg_panel", None):
            return True
        if self.isAncestorOf(obj):
            return True
        top = obj.window()
        return top is self or top is getattr(self, "gpu_cfg_panel", None)

    def _activate_from_internal_click(self):
        if not self.isVisible():
            return
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _sync_startup_shortcut_toggle(self):
        _mc_sync_startup_shortcut_toggle_impl(self)

    def _set_startup_shortcut_enabled(self, enabled, persist=True):
        _mc_set_startup_shortcut_enabled_impl(self, enabled, persist=persist)

    def _on_startup_shortcut_toggled(self, checked):
        _mc_on_startup_shortcut_toggled_impl(self, checked)

    def _apply_gpu_guard_thresholds(self, high_pct, low_pct, persist=True):
        _mc_apply_gpu_guard_thresholds_impl(self, high_pct, low_pct, persist=persist)

    def _sync_gpu_threshold_inputs(self):
        _mc_sync_gpu_threshold_inputs_impl(self)

    def _on_gpu_threshold_inputs_changed(self):
        _mc_on_gpu_threshold_inputs_changed_impl(self)

    @staticmethod
    def _action_icon_pixmap(kind, color_hex, size=16):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color_hex), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind == "run":
            painter.drawPolygon(
                QPolygonF([
                    QPointF(5.0, 3.5),
                    QPointF(12.5, 8.0),
                    QPointF(5.0, 12.5),
                ])
            )
        elif kind == "stop":
            painter.drawRect(QRectF(4.0, 4.0, 8.0, 8.0))
        elif kind == "settings":
            center = QPointF(8.0, 8.0)
            outer_r = 3.6
            inner_r = 1.9
            for i in range(8):
                angle = math.radians(i * 45.0)
                x1 = center.x() + math.cos(angle) * 4.8
                y1 = center.y() + math.sin(angle) * 4.8
                x2 = center.x() + math.cos(angle) * 6.6
                y2 = center.y() + math.sin(angle) * 6.6
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            painter.drawEllipse(center, outer_r, outer_r)
            painter.drawEllipse(center, inner_r, inner_r)
        elif kind == "delete":
            painter.drawLine(QPointF(4.0, 4.0), QPointF(12.0, 12.0))
            painter.drawLine(QPointF(12.0, 4.0), QPointF(4.0, 12.0))
        elif kind == "copy":
            painter.drawRect(QRectF(3.5, 5.5, 6.5, 6.5))
            painter.drawPolyline([
                QPointF(6.0, 3.5),
                QPointF(12.5, 3.5),
                QPointF(12.5, 10.0),
                QPointF(10.0, 10.0),
            ])

        painter.end()
        return pixmap

    @classmethod
    def _build_action_icon(cls, kind, color_hex):
        icon = QIcon()
        icon.addPixmap(cls._action_icon_pixmap(kind, color_hex), QIcon.Mode.Normal)
        icon.addPixmap(cls._action_icon_pixmap(kind, color_hex), QIcon.Mode.Active)
        disabled_color = QColor(color_hex).darker(170).name()
        icon.addPixmap(cls._action_icon_pixmap(kind, disabled_color), QIcon.Mode.Disabled)
        return icon

    @classmethod
    def _ensure_checkbox_check_icon(cls):
        cache_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "MyWidgetBox", "cache")
        try:
            os.makedirs(cache_dir, exist_ok=True)
            icon_path = os.path.join(cache_dir, "checkbox_check.png")
            pix = QPixmap(14, 14)
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#ffffff"), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(QPoint(3, 7), QPoint(6, 10))
            painter.drawLine(QPoint(6, 10), QPoint(11, 4))
            painter.end()
            pix.save(icon_path, "PNG")
            return icon_path.replace("\\", "/")
        except Exception:
            return ""

    def _set_profile_row_selected(self, pid, selected):
        row = self.profile_rows.get(str(pid))
        if row is None:
            return
        if isinstance(row, ProfileRowWidget):
            row.set_selected(selected)
            return
        row.setProperty("selected", "true" if selected else "false")
        style = row.style()
        if style:
            style.unpolish(row)
            style.polish(row)
        row.update()

    def _apply_title_bar_theme(self):
        self._apply_window_title_bar_theme(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "master_settings") and self.master_settings:
            self.master_settings.setValue("window_width", int(self.width()))
            self.master_settings.setValue("window_height", int(self.height()))

    @staticmethod
    def _apply_window_title_bar_theme(window):
        try:
            import ctypes
            hwnd = int(window.winId())
            dwmapi = ctypes.windll.dwmapi
            value = ctypes.c_int(1)
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(20),
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
            # Keep title bar color aligned with controller palette.
            # COLORREF is 0x00BBGGRR.
            caption_color = ctypes.c_uint(0x00795035)  # #355079
            text_color = ctypes.c_uint(0x00FFF7F5)     # #f5f7ff
            # DWMWA_CAPTION_COLOR = 35, DWMWA_TEXT_COLOR = 36 (Win11+)
            dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(35),
                ctypes.byref(caption_color),
                ctypes.sizeof(caption_color)
            )
            dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(36),
                ctypes.byref(text_color),
                ctypes.sizeof(text_color)
            )
        except Exception:
            pass

    @staticmethod
    def _themed_input_dialog_style():
        return """
            QDialog {
                background-color: #162233;
            }
            QLabel {
                color: #e6eefc;
                font-size: 12px;
                font-weight: 600;
            }
            QLineEdit {
                min-height: 32px;
                color: #ffffff;
                background-color: #121c2b;
                border: 1px solid #283a54;
                border-radius: 8px;
                padding: 2px 10px;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border: 1.5px solid #528bf8;
                background-color: #17283f;
            }
            QComboBox {
                min-height: 32px;
                color: #eaf1fc;
                background-color: #24364f;
                border: 1px solid #3d5578;
                border-radius: 8px;
                padding: 2px 28px 2px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QComboBox:hover {
                background-color: #2d4361;
            }
            QComboBox:focus {
                border: 1.5px solid #528bf8;
            }
            QComboBox QAbstractItemView {
                background-color: #21324a;
                color: #eef4ff;
                border: 1px solid #3d587d;
                border-radius: 6px;
                selection-background-color: #3f5e8e;
                selection-color: #ffffff;
                outline: 0;
                font-size: 12px;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 8px;
                padding: 0 14px;
                color: #e8efff;
                background-color: #2b3e5b;
                border: 1px solid #48648c;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #385075;
                border-color: #5d7fae;
                color: #ffffff;
            }
        """

    def _prompt_text_dialog(self, title, label, default_text=""):
        from mywidgetbox_core import ask_dark_input
        return ask_dark_input(self, title, label, default_text=default_text)

    def _prompt_choice_dialog(self, title, label, choices):
        from mywidgetbox_core import apply_windows_dark_title_bar, render_vector_icon
        dialog = QInputDialog(self)
        dialog.setWindowTitle(str(title))
        dialog.setWindowIcon(render_vector_icon("widget", "#528bf8", 32))
        dialog.setMinimumSize(360, 220)
        dialog.resize(360, 220)
        dialog.setLabelText(str(label))
        dialog.setComboBoxEditable(False)
        dialog.setComboBoxItems([str(v) for v in choices])
        dialog.setTextValue(str(choices[0]) if choices else "")
        dialog.setOkButtonText("확인")
        dialog.setCancelButtonText("취소")
        dialog.setStyleSheet(self._themed_input_dialog_style())
        QTimer.singleShot(0, lambda d=dialog: apply_windows_dark_title_bar(d))
        if dialog.exec():
            return dialog.textValue(), True
        return "", False

    def _add_profile_group_header(self, text):
        item = QListWidgetItem(self.list_widget)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(1, 28))
        lbl = QLabel(text)
        lbl.setObjectName("groupHeaderLabel")
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, lbl)

    def _add_widget_add_row(self):
        item = QListWidgetItem(self.list_widget)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(1, 34))

        row = QWidget()
        row.setObjectName("addWidgetRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        is_applied = self._is_current_set_applied()

        btn = QPushButton("＋", row)
        btn.setObjectName("addWidgetBtn")
        btn.clicked.connect(self.add_profile)
        btn.setEnabled(is_applied)

        lbl = QLabel("위젯 추가" if is_applied else "위젯 추가 (세트 적용 필요)", row)
        lbl.setObjectName("addWidgetLabel")
        if not is_applied:
            lbl.setStyleSheet("color: #7b8ea8;")
            btn.setToolTip("현재 적용된 세트에서만 위젯을 추가할 수 있습니다 (하단의 '세트 적용' 필요)")
            lbl.setToolTip("현재 적용된 세트에서만 위젯을 추가할 수 있습니다 (하단의 '세트 적용' 필요)")
        else:
            btn.setToolTip("새로운 위젯 추가")

        row_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)
        self._add_widget_row_item = item
        self._add_widget_row_widget = row
        return item, row

    def _add_profile_row(self, pid, name, is_running, insert_index=None):
        spid = str(pid)
        item = QListWidgetItem(self.list_widget)
        item.setData(Qt.ItemDataRole.UserRole, spid)

        row = ProfileRowWidget()
        row.setObjectName("profileRow")
        row.setProperty("running", "true" if is_running else "false")
        row.setProperty("hovered", "false")
        row.setProperty("selected", "false")
        row.setMinimumHeight(46)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 4, 4)
        row_layout.setSpacing(6)

        status_dot = QLabel()
        status_dot.setObjectName("statusDot")
        status_dot.setFixedSize(3, 16)
        status_dot.setProperty("running", "true" if is_running else "false")

        lbl = QLabel()
        lbl.setObjectName("profileName")
        lbl.setMinimumHeight(20)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        btn_run = QPushButton("실행")
        btn_stop = QPushButton("중지")
        btn_set = QPushButton("설정")
        btn_del = QPushButton("삭제")
        btn_run.setObjectName("runBtn")
        btn_stop.setObjectName("stopBtn")
        btn_set.setObjectName("setBtn")
        btn_del.setObjectName("deleteBtn")

        btns = [btn_run, btn_stop, btn_set, btn_del]
        for btn in btns:
            btn.setProperty("kind", "rowAction")
            btn.setText("")
            btn.setFixedSize(28, 28)
            btn.setIconSize(QSize(14, 14))
            btn.setVisible(False)

        btn_run.setIcon(render_vector_icon("run", "#58c796", 14))
        btn_run.setToolTip("위젯 실행")
        btn_stop.setIcon(render_vector_icon("stop", "#f87171", 14))
        btn_stop.setToolTip("위젯 정지")
        btn_set.setIcon(render_vector_icon("settings", "#93c5fd", 14))
        btn_set.setToolTip("위젯 상세 설정")
        btn_del.setIcon(render_vector_icon("trash", "#f87171", 14))
        btn_del.setToolTip("위젯 삭제")
        btn_run.setEnabled(not is_running)
        btn_stop.setEnabled(is_running)

        btn_run.clicked.connect(
            lambda _, p=spid: self.run_widget(
                p,
                str(QSettings("MyHomeApp", f"Profile_{p}").value("name", "New 세팅")),
            )
        )
        btn_stop.clicked.connect(lambda _, p=spid: self.stop_widget(p))
        btn_set.clicked.connect(lambda _, p=spid: self.open_widget_settings(p))
        btn_del.clicked.connect(lambda _, p=spid: self.delete_profile(p))

        checkbox = QCheckBox(row)
        checkbox.setObjectName("profileCheck")
        checkbox.setFixedSize(16, 16)
        checkbox.setChecked(spid in self._temp_group_ids)
        checkbox.toggled.connect(lambda checked, p=spid: self._on_row_checkbox_changed(p, checked))

        action_wrap = QWidget()
        action_wrap_layout = QHBoxLayout(action_wrap)
        action_wrap_layout.setContentsMargins(0, 0, 0, 0)
        action_wrap_layout.setSpacing(4)
        for btn in btns:
            action_wrap_layout.addWidget(btn)
        action_wrap.setFixedWidth(4 * 28 + 3 * action_wrap_layout.spacing())

        row_layout.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(lbl, 1, Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(action_wrap, 0, Qt.AlignmentFlag.AlignVCenter)
        row.set_action_buttons(btns)
        row._checkbox = checkbox
        row._name_label = lbl
        row._status_dot = status_dot
        row._btn_run = btn_run
        row._btn_stop = btn_stop
        row._btn_set = btn_set
        row._btn_del = btn_del
        row._action_wrap = action_wrap
        row._pid = spid
        row._full_name = str(name)

        item.setSizeHint(QSize(1, 46))
        if insert_index in (None, ""):
            self.list_widget.addItem(item)
        else:
            try:
                safe_index = max(0, min(int(insert_index), self.list_widget.count()))
            except Exception:
                safe_index = self.list_widget.count()
            self.list_widget.insertItem(safe_index, item)
        self.list_widget.setItemWidget(item, row)
        self.profile_rows[spid] = row
        self._profile_row_items[spid] = item
        self._refresh_profile_row(spid, str(name), bool(is_running))
        self._sync_bulk_action_ui()
        return row

    def _profile_list_order(self):
        ordered = []
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item is None:
                continue
            raw_pid = item.data(Qt.ItemDataRole.UserRole)
            if raw_pid in (None, ""):
                continue
            ordered.append(str(raw_pid))
        return ordered

    def _elide_profile_row_name(self, row, name):
        label = getattr(row, "_name_label", None)
        if label is None:
            return str(name)
        layout = row.layout() if isinstance(row, QWidget) else None
        if layout is None:
            return str(name)
        action_wrap = getattr(row, "_action_wrap", None)
        margin_width = int(layout.contentsMargins().left()) + int(layout.contentsMargins().right())
        status_width = 10 + 18 + int(layout.spacing()) * 2
        action_width = (int(action_wrap.width()) if isinstance(action_wrap, QWidget) else 0) + int(layout.spacing())
        viewport_w = int(self.list_widget.viewport().width())
        if viewport_w <= 0:
            viewport_w = max(260, int(self.width()) - 48)
        name_max_width = max(60, int(viewport_w) - int(margin_width) - int(status_width) - int(action_width) - 12)
        return QFontMetrics(label.font()).elidedText(
            str(name), Qt.TextElideMode.ElideRight, int(name_max_width)
        )

    def _refresh_profile_row(self, pid, name, is_running):
        spid = str(pid)
        row = self.profile_rows.get(spid)
        if not isinstance(row, ProfileRowWidget):
            return False
        label = getattr(row, "_name_label", None)
        status_dot = getattr(row, "_status_dot", None)
        btn_run = getattr(row, "_btn_run", None)
        btn_stop = getattr(row, "_btn_stop", None)
        btn_set = getattr(row, "_btn_set", None)
        btn_del = getattr(row, "_btn_del", None)
        cb = getattr(row, "_checkbox", None)
        if not isinstance(label, QLabel) or not isinstance(status_dot, QLabel):
            return False
        if not isinstance(btn_run, QPushButton) or not isinstance(btn_stop, QPushButton):
            return False

        full_name = str(name)
        row._full_name = full_name
        label.setToolTip(full_name)
        label.setText(self._elide_profile_row_name(row, full_name))

        if isinstance(cb, QCheckBox):
            cb.blockSignals(True)
            cb.setChecked(spid in self._temp_group_ids)
            cb.blockSignals(False)

        running_prop = "true" if bool(is_running) else "false"
        row_changed = False
        if str(row.property("running") or "") != running_prop:
            row.setProperty("running", running_prop)
            row_changed = True
        if str(status_dot.property("running") or "") != running_prop:
            status_dot.setProperty("running", running_prop)
            dot_style = status_dot.style()
            if dot_style:
                dot_style.unpolish(status_dot)
                dot_style.polish(status_dot)
            status_dot.update()

        is_applied = self._is_current_set_applied()

        if not is_applied:
            btn_run.setEnabled(False)
            btn_stop.setEnabled(False)
            if isinstance(btn_set, QPushButton):
                btn_set.setEnabled(False)
            if isinstance(btn_del, QPushButton):
                btn_del.setEnabled(False)
            if isinstance(cb, QCheckBox):
                cb.setEnabled(False)
        else:
            btn_run.setEnabled(not bool(is_running))
            btn_stop.setEnabled(bool(is_running))
            if isinstance(btn_set, QPushButton):
                btn_set.setEnabled(True)
            if isinstance(btn_del, QPushButton):
                btn_del.setEnabled(True)
            if isinstance(cb, QCheckBox):
                cb.setEnabled(True)

        if row_changed:
            row._refresh_style()
        return True

    def _can_incremental_profile_refresh(self, profile_ids):
        desired = [str(pid) for pid in profile_ids]
        if self._add_widget_row_item is None:
            return False
        if self.list_widget.count() != len(desired) + 1:
            return False
        top_item = self.list_widget.item(0)
        if top_item is not self._add_widget_row_item:
            return False
        if self._profile_list_order() != desired:
            return False
        for pid in desired:
            row = self.profile_rows.get(pid)
            item = self._profile_row_items.get(pid)
            if row is None or item is None:
                return False
            if self.list_widget.itemWidget(item) is not row:
                return False
        return True

    def _rebuild_profile_rows(self, profile_ids):
        self.list_widget.clear()
        self.profile_rows = {}
        self._profile_row_items = {}
        self._add_widget_row_item = None
        self._add_widget_row_widget = None
        self._add_widget_add_row()
        for pid in profile_ids:
            name = QSettings("MyHomeApp", f"Profile_{pid}").value("name", "New 세팅")
            self._add_profile_row(pid, str(name), pid in self.widgets)
        self._set_hovered_profile_row(None)

    def load_profiles(self, force_rebuild=False):
        self._clear_accordion_layout()
        self.profile_rows = {}
        self._set_toolbars.clear()
        from mywidgetbox_core import render_vector_icon

        applied_sid = str(getattr(self, "_applied_set_id", "") or "")
        selected_sid = str(self.selected_set_id() or "")

        # 시작 시 현재 적용 중인 세트만 펼치고 나머지는 접음
        if not self._set_expanded_states:
            self._set_expanded_states = {str(sid): (str(sid) == applied_sid) for sid in self._set_order}

        for s_idx, sid in enumerate(self._set_order):
            sid_str = str(sid)
            data = self._set_defs.get(sid_str, {})
            name = str(data.get("name", f"세트{sid_str}"))
            pids = [str(p) for p in self._as_list(data.get("profiles", []))]
            is_applied = (sid_str == applied_sid)
            is_expanded = self._set_expanded_states.get(sid_str, False)

            # 부모 세트 카드
            set_card = QFrame()
            set_card.setObjectName("setGroupCard")
            set_card.setProperty("applied", "true" if is_applied else "false")
            card_layout = QVBoxLayout(set_card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            # 세트 헤더
            header = QFrame(set_card)
            header.setObjectName("setGroupHeader")
            header.setProperty("expanded", "true" if is_expanded else "false")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(10, 8, 10, 8)
            header_layout.setSpacing(6)

            # 접기/펼치기 버튼
            toggle_btn = QPushButton(header)
            toggle_btn.setProperty("kind", "rowAction")
            toggle_btn.setFixedSize(24, 24)
            toggle_btn.setIconSize(QSize(12, 12))
            toggle_btn.setIcon(render_vector_icon("chevron_down" if is_expanded else "chevron_right", "#9cb5d8", 12))
            toggle_btn.setToolTip("세트 접기 / 펼치기")
            toggle_btn.clicked.connect(lambda _, s=sid_str: self._toggle_set_expanded(s))

            # 세트 폴더 아이콘
            folder_icon_lbl = QLabel(header)
            folder_icon_lbl.setPixmap(render_vector_icon("folder", "#528bf8" if is_applied else "#8da8cb", 16).pixmap(16, 16))

            # 세트 이름 (긴 이름 자동 말줄임표 ... 적용)
            title_lbl = ElidedLabel(name, header)
            title_lbl.setObjectName("setGroupTitle")
            title_lbl.setToolTip(f"세트: {name} (더블클릭하여 이름 변경)")

            # 세트 헤더 더블클릭 시 세트 이름 즉시 변경
            header.mouseDoubleClickEvent = lambda e, s=sid_str: self.rename_set(s) if e.button() == Qt.MouseButton.LeftButton else None

            # 위젯 개수 뱃지
            count_badge = QLabel(f"{len(pids)}개", header)
            count_badge.setObjectName("setCountBadge")

            header_layout.addWidget(toggle_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            header_layout.addWidget(folder_icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
            header_layout.addWidget(title_lbl, 1, Qt.AlignmentFlag.AlignVCenter)
            header_layout.addWidget(count_badge, 0, Qt.AlignmentFlag.AlignVCenter)
            header_layout.addStretch(0)

            # 세트 액션 버튼
            if is_applied:
                applied_badge = QLabel("적용 중", header)
                applied_badge.setObjectName("setAppliedBadge")
                header_layout.addWidget(applied_badge, 0, Qt.AlignmentFlag.AlignVCenter)
            else:
                apply_btn = QPushButton("세트 적용", header)
                apply_btn.setObjectName("setApplyBtn")
                apply_btn.setToolTip(f"'{name}' 세트의 위젯들을 바탕화면에 적용합니다")
                apply_btn.clicked.connect(lambda _, s=sid_str: self._on_apply_set_clicked(s))
                header_layout.addWidget(apply_btn, 0, Qt.AlignmentFlag.AlignVCenter)

            # 세트 순서 이동 버튼 (▲ / ▼)
            btn_set_up = QPushButton(header)
            btn_set_up.setProperty("kind", "rowAction")
            btn_set_up.setFixedSize(26, 26)
            btn_set_up.setIconSize(QSize(12, 12))
            btn_set_up.setIcon(render_vector_icon("chevron_up", "#8da8cb", 12))
            btn_set_up.setToolTip("세트를 위로 이동")
            btn_set_up.setEnabled(s_idx > 0)
            btn_set_up.clicked.connect(lambda _, s=sid_str: self.move_set_up(s))
            header_layout.addWidget(btn_set_up, 0, Qt.AlignmentFlag.AlignVCenter)

            btn_set_down = QPushButton(header)
            btn_set_down.setProperty("kind", "rowAction")
            btn_set_down.setFixedSize(26, 26)
            btn_set_down.setIconSize(QSize(12, 12))
            btn_set_down.setIcon(render_vector_icon("chevron_down", "#8da8cb", 12))
            btn_set_down.setToolTip("세트를 아래로 이동")
            btn_set_down.setEnabled(s_idx < len(self._set_order) - 1)
            btn_set_down.clicked.connect(lambda _, s=sid_str: self.move_set_down(s))
            header_layout.addWidget(btn_set_down, 0, Qt.AlignmentFlag.AlignVCenter)

            menu_btn = QPushButton(header)
            menu_btn.setProperty("kind", "rowAction")
            menu_btn.setFixedSize(26, 26)
            menu_btn.setIconSize(QSize(13, 13))
            menu_btn.setIcon(render_vector_icon("settings", "#8da8cb", 13))
            menu_btn.setToolTip("세트 관리 (이름 변경, 복사, 삭제)")
            menu_btn.clicked.connect(lambda _, s=sid_str: self.open_set_manager(s))
            header_layout.addWidget(menu_btn, 0, Qt.AlignmentFlag.AlignVCenter)

            card_layout.addWidget(header)

            # 자식 위젯 영역
            if is_expanded:
                body = QFrame(set_card)
                body.setObjectName("setGroupBody")
                body_layout = QVBoxLayout(body)
                body_layout.setContentsMargins(10, 6, 10, 8)
                body_layout.setSpacing(4)

                # 세트 내 일괄 제어 툴바 (위젯이 있을 때)
                if pids:
                    toolbar_row = QHBoxLayout()
                    toolbar_row.setContentsMargins(4, 2, 4, 4)
                    toolbar_row.setSpacing(6)

                    select_all_cb = QCheckBox(body)
                    select_all_cb.setObjectName("selectAllCheck")
                    select_all_cb.setToolTip("이 세트의 모든 위젯 선택 / 해제")
                    def _toggle_set_selection(checked, set_pids=pids):
                        for p in set_pids:
                            sp = str(p)
                            row_w = self.profile_rows.get(sp)
                            if row_w and hasattr(row_w, "_checkbox") and row_w._checkbox:
                                row_w._checkbox.setChecked(bool(checked))
                    select_all_cb.toggled.connect(_toggle_set_selection)

                    toolbar_lbl = QLabel("전체 선택", body)
                    toolbar_lbl.setObjectName("groupHeaderLabel")

                    toolbar_row.addWidget(select_all_cb, 0, Qt.AlignmentFlag.AlignVCenter)
                    toolbar_row.addWidget(toolbar_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
                    toolbar_row.addStretch(1)

                    bulk_run = QPushButton("실행", body)
                    bulk_run.setObjectName("bulkRunBtn")
                    bulk_run.setIcon(render_vector_icon("run", "#58c796", 12))
                    bulk_run.setIconSize(QSize(12, 12))
                    bulk_run.setToolTip("선택한 정지 위젯 일괄 실행")
                    bulk_run.clicked.connect(self.bulk_run_profiles)

                    bulk_stop = QPushButton("정지", body)
                    bulk_stop.setObjectName("bulkStopBtn")
                    bulk_stop.setIcon(render_vector_icon("stop", "#cddbf0", 12))
                    bulk_stop.setIconSize(QSize(12, 12))
                    bulk_stop.setToolTip("선택한 실행 위젯 일괄 정지")
                    bulk_stop.clicked.connect(self.bulk_stop_profiles)

                    bulk_set = QPushButton("설정", body)
                    bulk_set.setObjectName("bulkActionBtn")
                    bulk_set.setIcon(render_vector_icon("settings", "#cddbf0", 12))
                    bulk_set.setIconSize(QSize(12, 12))
                    bulk_set.setToolTip("선택한 위젯 일괄 설정")
                    bulk_set.clicked.connect(self.open_bulk_settings)

                    bulk_del = QPushButton("삭제", body)
                    bulk_del.setObjectName("bulkDeleteBtn")
                    bulk_del.setIcon(render_vector_icon("trash", "#f87171", 12))
                    bulk_del.setIconSize(QSize(12, 12))
                    bulk_del.setToolTip("선택한 위젯 일괄 삭제")
                    bulk_del.clicked.connect(self.delete_checked_profiles)

                    toolbar_row.addWidget(bulk_run)
                    toolbar_row.addWidget(bulk_stop)
                    toolbar_row.addWidget(bulk_set)
                    toolbar_row.addWidget(bulk_del)

                    self._set_toolbars[sid_str] = {
                        'select_all': select_all_cb,
                        'run': bulk_run,
                        'stop': bulk_stop,
                        'set': bulk_set,
                        'del': bulk_del,
                        'pids': pids
                    }

                    body_layout.addLayout(toolbar_row)

                for idx, pid in enumerate(pids):
                    spid = str(pid)
                    p_cfg = QSettings("MyHomeApp", f"Profile_{spid}")
                    p_name = str(p_cfg.value("name", f"위젯 {spid}"))
                    is_running = bool(spid in self.widgets or (int(spid) in self.widgets if spid.isdigit() else False))

                    media_mode = str(p_cfg.value("media_mode", "file") or "file").lower()
                    img_path = str(p_cfg.value("image_path", "") or "")
                    ext = os.path.splitext(img_path)[1].lower()
                    if media_mode == "slide":
                        badge_text = "SLIDE"
                    elif ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"):
                        badge_text = "VID"
                    elif ext == ".gif":
                        badge_text = "GIF"
                    else:
                        badge_text = "IMG"

                    row = ProfileRowWidget(body)
                    row.setObjectName("treeChildRow")
                    row.setProperty("running", "true" if is_running else "false")
                    row._pid = spid
                    row_layout = QHBoxLayout(row)
                    row_layout.setContentsMargins(6, 4, 8, 4)
                    row_layout.setSpacing(6)

                    # 들여쓰기 트리 브랜치 선
                    branch = TreeBranchLine(is_last=False, parent=row)

                    # 임시 그룹 연동 체크박스
                    cb = QCheckBox(row)
                    cb.setObjectName("profileCheck")
                    cb.setChecked(spid in self._temp_group_ids)
                    cb.toggled.connect(lambda checked, p=spid: self._on_row_checkbox_changed(p, checked))

                    status_dot = QLabel(row)
                    status_dot.setObjectName("statusDot")
                    status_dot.setFixedSize(4, 18)
                    status_dot.setProperty("running", "true" if is_running else "false")

                    # 위젯 이름 (긴 파일명 자동 말줄임표 ... 적용)
                    name_lbl = ElidedLabel(p_name, row)
                    name_lbl.setObjectName("profileName")
                    name_lbl.setToolTip(p_name)

                    badge_lbl = QLabel(badge_text, row)
                    badge_lbl.setObjectName("mediaBadge")
                    badge_lbl.setStyleSheet("""
                        QLabel#mediaBadge {
                            color: #7da5dc;
                            background-color: #101c2e;
                            border: 1px solid #233752;
                            border-radius: 4px;
                            padding: 1px 5px;
                            font-size: 10px;
                            font-weight: 700;
                        }
                    """)

                    btn_up = QPushButton(row)
                    btn_down = QPushButton(row)
                    btn_run = QPushButton(row)
                    btn_stop = QPushButton(row)
                    btn_set = QPushButton(row)
                    btn_del = QPushButton(row)

                    for b in (btn_up, btn_down, btn_run, btn_stop, btn_set, btn_del):
                        b.setProperty("kind", "rowAction")
                        b.setFixedSize(24, 24)
                        b.setIconSize(QSize(12, 12))

                    btn_up.setIcon(render_vector_icon("chevron_up", "#9cb5d8", 12))
                    btn_up.setToolTip("위로 이동 (로딩 순서 올림)")
                    btn_down.setIcon(render_vector_icon("chevron_down", "#9cb5d8", 12))
                    btn_down.setToolTip("아래로 이동 (로딩 순서 내림)")

                    btn_up.setEnabled(idx > 0)
                    btn_down.setEnabled(idx < len(pids) - 1)

                    btn_up.clicked.connect(lambda _, p=spid, s=sid_str: self.move_profile_up(p, s))
                    btn_down.clicked.connect(lambda _, p=spid, s=sid_str: self.move_profile_down(p, s))

                    btn_run.setIcon(render_vector_icon("run", "#58c796", 12))
                    btn_run.setToolTip("위젯 실행")
                    btn_stop.setIcon(render_vector_icon("stop", "#f87171", 12))
                    btn_stop.setToolTip("위젯 정지")
                    btn_set.setIcon(render_vector_icon("settings", "#93c5fd", 12))
                    btn_set.setToolTip("위젯 상세 설정")
                    btn_del.setIcon(render_vector_icon("trash", "#f87171", 12))
                    btn_del.setToolTip("위젯 삭제")

                    btn_run.setEnabled(not is_running)
                    btn_stop.setEnabled(is_running)

                    btn_run.clicked.connect(lambda _, p=spid, n=p_name: self.run_widget(p, n))
                    btn_stop.clicked.connect(lambda _, p=spid: self.stop_widget(p))
                    btn_set.clicked.connect(lambda _, p=spid: self.open_widget_settings(p))
                    btn_del.clicked.connect(lambda _, p=spid: self.delete_profile(p))

                    row_layout.addWidget(branch, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(cb, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(name_lbl, 1, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(btn_up, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(btn_down, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(btn_run, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(btn_stop, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(btn_set, 0, Qt.AlignmentFlag.AlignVCenter)
                    row_layout.addWidget(btn_del, 0, Qt.AlignmentFlag.AlignVCenter)

                    row._checkbox = cb
                    row.clicked.connect(lambda p: self.highlight_widget(p))
                    row.doubleClicked.connect(lambda p: self.rename_profile(p))

                    body_layout.addWidget(row)
                    self.profile_rows[spid] = row

                # 이 세트에 위젯 추가 행
                add_row = QWidget(body)
                add_row_layout = QHBoxLayout(add_row)
                add_row_layout.setContentsMargins(6, 8, 8, 4)
                add_row_layout.setSpacing(6)

                add_btn = QPushButton("새로운 위젯 추가", add_row)
                add_btn.setObjectName("addTreeWidgetBtn")
                add_btn.setIcon(render_vector_icon("plus", "#8da8cb", 12))
                add_btn.setIconSize(QSize(12, 12))
                add_btn.clicked.connect(lambda _, s=sid_str: self.add_profile(target_set_id=s))

                add_row_layout.addStretch(1)
                add_row_layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignCenter)
                add_row_layout.addStretch(1)
                body_layout.addWidget(add_row)

                card_layout.addWidget(body)

            self.accordion_layout.addWidget(set_card)

        self.accordion_layout.addStretch(1)
        self._sync_bulk_action_ui()

    def _on_row_checkbox_changed(self, pid, checked):
        spid = str(pid)
        if checked:
            self._temp_group_ids.add(spid)
        else:
            self._temp_group_ids.discard(spid)
        self._sync_temp_group_badges()
        self._sync_bulk_action_ui()

    def _on_select_all_toggled(self, checked):
        for spid, row in self.profile_rows.items():
            if isinstance(row, ProfileRowWidget) and hasattr(row, "_checkbox") and row._checkbox:
                row._checkbox.blockSignals(True)
                row._checkbox.setChecked(bool(checked))
                row._checkbox.blockSignals(False)
                if checked:
                    self._temp_group_ids.add(str(spid))
                else:
                    self._temp_group_ids.discard(str(spid))
        self._sync_temp_group_badges()
        self._sync_bulk_action_ui()

    def _checked_profile_ids(self):
        return [str(pid) for pid in self._temp_group_ids if str(pid) in self.profile_rows]

    def _set_of_profile(self, pid):
        spid = str(pid)
        for sid, sdata in self._set_defs.items():
            if spid in [str(p) for p in self._as_list(sdata.get("profiles", []))]:
                return str(sid)
        return str(self.selected_set_id() or "")

    def _is_current_set_applied(self):
        return True

    def _check_set_applied_for_action(self, action_name="조작"):
        return True

    def _sync_bulk_action_ui(self):
        for sid, tb in getattr(self, "_set_toolbars", {}).items():
            set_pids = [str(p) for p in tb.get("pids", [])]
            checked_pids = [p for p in set_pids if p in self._temp_group_ids]
            any_checked = (len(checked_pids) > 0)

            # 1개라도 정지되어 있는 위젯이 체크되어 있으면 실행 활성화
            any_stopped = any((p not in self.widgets and (int(p) not in self.widgets if p.isdigit() else True)) for p in checked_pids)
            # 1개라도 실행 중인 위젯이 체크되어 있으면 정지 활성화
            any_running = any((p in self.widgets or (int(p) in self.widgets if p.isdigit() else False)) for p in checked_pids)

            run_btn = tb.get("run")
            if run_btn is not None:
                run_btn.setEnabled(bool(any_checked and any_stopped))

            stop_btn = tb.get("stop")
            if stop_btn is not None:
                stop_btn.setEnabled(bool(any_checked and any_running))

            set_btn = tb.get("set")
            if set_btn is not None:
                set_btn.setEnabled(bool(any_checked))

            del_btn = tb.get("del")
            if del_btn is not None:
                del_btn.setEnabled(bool(any_checked))

            sa_cb = tb.get("select_all")
            if sa_cb is not None:
                sa_cb.blockSignals(True)
                sa_cb.setChecked(bool(len(checked_pids) == len(set_pids) and len(set_pids) > 0))
                sa_cb.blockSignals(False)

    def bulk_run_profiles(self):
        if not self._check_set_applied_for_action("일괄 실행"):
            return
        checked_ids = self._checked_profile_ids()
        if not checked_ids:
            return
        for pid in checked_ids:
            spid = str(pid)
            if spid not in self.widgets:
                name = str(QSettings("MyHomeApp", f"Profile_{spid}").value("name", "New 세팅"))
                self.run_widget(spid, name, defer_reload=True)
        self.update_active_status()
        self.load_profiles()

    def move_profile_up(self, pid, sid=None):
        spid = str(pid)
        if not sid:
            sid = self._set_of_profile(spid)
        sid = str(sid)
        if sid not in self._set_defs:
            return

        pids = [str(p) for p in self._as_list(self._set_defs[sid].get("profiles", []))]
        if spid not in pids:
            return

        idx = pids.index(spid)
        if idx <= 0:
            return

        pids[idx], pids[idx - 1] = pids[idx - 1], pids[idx]
        self._set_defs[sid]["profiles"] = pids
        self.master_settings.setValue(self._set_key(sid, "profiles"), pids)
        self.master_settings.sync()
        self.load_profiles(force_rebuild=True)

    def move_profile_down(self, pid, sid=None):
        spid = str(pid)
        if not sid:
            sid = self._set_of_profile(spid)
        sid = str(sid)
        if sid not in self._set_defs:
            return

        pids = [str(p) for p in self._as_list(self._set_defs[sid].get("profiles", []))]
        if spid not in pids:
            return

        idx = pids.index(spid)
        if idx < 0 or idx >= len(pids) - 1:
            return

        pids[idx], pids[idx + 1] = pids[idx + 1], pids[idx]
        self._set_defs[sid]["profiles"] = pids
        self.master_settings.setValue(self._set_key(sid, "profiles"), pids)
        self.master_settings.sync()
        self.load_profiles(force_rebuild=True)

    def move_set_up(self, set_id):
        sid = str(set_id)
        if sid not in self._set_order:
            return
        idx = self._set_order.index(sid)
        if idx <= 0:
            return
        self._set_order[idx], self._set_order[idx - 1] = self._set_order[idx - 1], self._set_order[idx]
        self.master_settings.setValue("set_ids", list(self._set_order))
        if hasattr(self.master_settings, "sync"):
            self.master_settings.sync()
        self.load_profiles(force_rebuild=True)

    def move_set_down(self, set_id):
        sid = str(set_id)
        if sid not in self._set_order:
            return
        idx = self._set_order.index(sid)
        if idx < 0 or idx >= len(self._set_order) - 1:
            return
        self._set_order[idx], self._set_order[idx + 1] = self._set_order[idx + 1], self._set_order[idx]
        self.master_settings.setValue("set_ids", list(self._set_order))
        if hasattr(self.master_settings, "sync"):
            self.master_settings.sync()
        self.load_profiles(force_rebuild=True)

    def bulk_stop_profiles(self):
        if not self._check_set_applied_for_action("일괄 정지"):
            return
        checked_ids = self._checked_profile_ids()
        if not checked_ids:
            return
        for pid in checked_ids:
            spid = str(pid)
            if spid in self.widgets:
                self.stop_widget(spid)
        self.update_active_status()
        self.load_profiles()

    def open_bulk_settings(self):
        if not self._check_set_applied_for_action("일괄 설정"):
            return
        checked_ids = self._checked_profile_ids()
        if not checked_ids:
            return

        first_pid = checked_ids[0]
        first_running = first_pid in self.widgets
        s_obj = QSettings("MyHomeApp", f"Profile_{first_pid}")

        if first_running:
            w = self.widgets[first_pid]
            base_data = {
                'folder_path': w.folder_path,
                'folder_item_paths': list(getattr(w, 'folder_item_paths', []) or []),
                'exec_path': w.exec_path,
                'w': w.width(),
                'h': w.height(),
                'layer_mode': getattr(w, 'layer_mode', DesktopWidget.LAYER_NORMAL),
                'layer_schema_version': int(DesktopWidget.LAYER_SCHEMA_VERSION),
                'is_locked': getattr(w, 'is_locked', False),
                'opacity_pct': w.current_opacity_pct,
                'bg_color_mode': w.bg_color_mode,
                'corner_mode': DesktopWidget.coerce_corner_mode(getattr(w, 'corner_mode', DesktopWidget.CORNER_ROUNDED)),
                'media_fit_mode': int(getattr(w, 'media_fit_mode', 0)),
                'video_transition_mode': int(getattr(w, 'video_transition_mode', DesktopWidget.VIDEO_TRANSITION_SINGLE)),
                'video_decode_mode': int(getattr(w, 'video_decode_mode', DesktopWidget.VIDEO_DECODE_ORIGINAL)),
                'video_dual_fade_ms': int(getattr(w, '_video_swap_fade_duration_ms', DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS)),
                'interval': w.interval_ms // 1000,
                'is_muted': w.is_muted,
                'gpu_guard_enabled': getattr(w, 'gpu_guard_enabled', False),
            }
        else:
            base_data = {
                'folder_path': s_obj.value("folder_path", ""),
                'folder_item_paths': DesktopWidget._as_path_list(s_obj.value("folder_item_paths", [])),
                'exec_path': s_obj.value("exec_path", ""),
                'w': int(s_obj.value("w", 200)),
                'h': int(s_obj.value("h", 200)),
                'layer_mode': DesktopWidget.coerce_layer_mode(
                    int(s_obj.value("layer_mode", DesktopWidget.LAYER_NORMAL)),
                    int(s_obj.value("layer_schema_version", 0)),
                ),
                'layer_schema_version': int(DesktopWidget.LAYER_SCHEMA_VERSION),
                'is_locked': _as_bool(s_obj.value("is_locked", False), False),
                'opacity_pct': int(s_obj.value("opacity_pct", 100)),
                'bg_color_mode': int(s_obj.value("bg_color_mode", 1)),
                'corner_mode': DesktopWidget.coerce_corner_mode(
                    s_obj.value("corner_mode", DesktopWidget.CORNER_ROUNDED)
                ),
                'media_fit_mode': int(s_obj.value("media_fit_mode", 0)),
                'video_transition_mode': DesktopWidget.coerce_video_transition_mode(
                    s_obj.value("video_transition_mode", DesktopWidget.VIDEO_TRANSITION_SINGLE)
                ),
                'video_decode_mode': DesktopWidget.coerce_video_decode_mode(
                    s_obj.value("video_decode_mode", DesktopWidget.VIDEO_DECODE_ORIGINAL)
                ),
                'video_dual_fade_ms': DesktopWidget.coerce_video_dual_fade_ms(
                    s_obj.value("video_dual_fade_ms", DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS)
                ),
                'interval': int(s_obj.value("interval", 5)),
                'is_muted': _as_bool(s_obj.value("is_muted", True), True),
                'gpu_guard_enabled': _as_bool(s_obj.value("gpu_guard_enabled", False), False),
            }

        dialog = SettingsDialog(self, base_data, bulk_mode=True, target_count=len(checked_ids))
        if not dialog.exec():
            return

        new_w = dialog.width_input.value()
        new_h = dialog.height_input.value()
        new_interval = dialog.sec_input.value() * 1000
        new_opacity = dialog.opacity_slider.value()
        new_bg = dialog.bg_combo.currentIndex()
        new_corner = DesktopWidget.coerce_corner_mode(dialog.corner_combo.currentIndex())
        new_media_fit = dialog.media_mode_combo.currentIndex()
        new_video_transition = DesktopWidget.coerce_video_transition_mode(
            dialog.video_transition_combo.currentIndex()
        )
        new_video_decode_mode = DesktopWidget.coerce_video_decode_mode(
            dialog.video_decode_combo.currentIndex()
        )
        new_video_dual_fade_ms = DesktopWidget.coerce_video_dual_fade_ms(
            dialog.video_dual_fade_ms_spin.value()
        )
        new_layer = dialog.layer_combo.currentIndex()
        new_lock = dialog.lock_cb.isChecked()
        new_mute = dialog.mute_checkbox.isChecked()
        new_gpu_guard = dialog.gpu_guard_checkbox.isChecked()

        spread_relayout_cfg = dialog.get_spread_relayout_config() if hasattr(dialog, "get_spread_relayout_config") else None
        if spread_relayout_cfg:
            keep_indiv_size = True
        else:
            keep_indiv_size = bool(getattr(dialog, "keep_individual_size_cb", None) and dialog.keep_individual_size_cb.isChecked())
            if not keep_indiv_size:
                sizes = set()
                for pid in checked_ids:
                    spid = str(pid)
                    if spid in self.widgets:
                        sizes.add((self.widgets[spid].width(), self.widgets[spid].height()))
                    else:
                        prof_s = QSettings("MyHomeApp", f"Profile_{spid}")
                        sizes.add((int(prof_s.value("w", 200)), int(prof_s.value("h", 200))))
                if len(sizes) > 1:
                    from mywidgetbox_core import ask_dark_confirm
                    if not ask_dark_confirm(
                        self,
                        "위젯 크기 일괄 변경",
                        f"그룹 내 위젯들의 크기가 서로 다릅니다.\n모든 위젯의 크기를 [{new_w} x {new_h} px]로 일괄 변경하시겠습니까?\n('취소' 시 각 위젯의 기존 크기가 유지됩니다.)",
                        yes_text="일괄 변경",
                        no_text="기존 크기 유지",
                        is_danger=False,
                    ):
                        keep_indiv_size = True

        for pid in checked_ids:
            spid = str(pid)
            prof_s = QSettings("MyHomeApp", f"Profile_{spid}")
            if not keep_indiv_size:
                prof_s.setValue("w", new_w)
                prof_s.setValue("h", new_h)
            prof_s.setValue("opacity_pct", new_opacity)
            prof_s.setValue("bg_color_mode", new_bg)
            prof_s.setValue("corner_mode", int(new_corner))
            prof_s.setValue("media_fit_mode", int(new_media_fit))
            prof_s.setValue("video_transition_mode", int(new_video_transition))
            prof_s.setValue("video_decode_mode", int(new_video_decode_mode))
            prof_s.setValue("video_dual_fade_ms", int(new_video_dual_fade_ms))
            prof_s.setValue("layer_mode", new_layer)
            prof_s.setValue("layer_schema_version", int(DesktopWidget.LAYER_SCHEMA_VERSION))
            prof_s.setValue("is_locked", bool(new_lock))
            prof_s.setValue("interval", new_interval // 1000)
            prof_s.setValue("is_muted", bool(new_mute))
            prof_s.setValue("gpu_guard_enabled", bool(new_gpu_guard))
            prof_s.sync()

            if spid in self.widgets:
                w = self.widgets[spid]
                if not keep_indiv_size and (w.width() != new_w or w.height() != new_h):
                    w.resize(new_w, new_h)
                w.current_opacity_pct = new_opacity
                w.setWindowOpacity(new_opacity / 100.0)
                w.bg_color_mode = new_bg
                w.corner_mode = DesktopWidget.coerce_corner_mode(new_corner)
                w.media_fit_mode = int(new_media_fit)
                w.video_transition_mode = int(new_video_transition)
                w.video_decode_mode = int(new_video_decode_mode)
                w._video_swap_fade_duration_ms = int(new_video_dual_fade_ms)
                w.apply_mask_and_style()
                w._sync_current_media_cycle_policy()
                w.apply_window_settings(new_layer, new_lock)
                w.is_muted = new_mute
                w._apply_mute_state()
                w.gpu_guard_enabled = bool(new_gpu_guard)
                if not w.gpu_guard_enabled:
                    w.set_performance_paused(False, reason="guard_disabled")
                elif self._gpu_guard_paused:
                    w.set_performance_paused(True, reason=f"gpu {self._gpu_last_usage:.1f}%", force=True)
                w.interval_ms = new_interval
                if w.timer.isActive():
                    w.timer.setInterval(new_interval)
                if hasattr(w, "_apply_media_scale_mode"):
                    w._apply_media_scale_mode()

        if spread_relayout_cfg:
            group_media_paths = []
            for pid in checked_ids:
                spid = str(pid)
                m_path = ""
                if spid in self.widgets:
                    w_inst = self.widgets[spid]
                    if hasattr(w_inst, "get_current_media_path"):
                        m_path = w_inst.get_current_media_path()
                if not m_path:
                    p_s = QSettings("MyHomeApp", f"Profile_{spid}")
                    fpaths = DesktopWidget._as_path_list(p_s.value("folder_item_paths", []))
                    if fpaths:
                        m_path = fpaths[0]
                group_media_paths.append(m_path)

            from master_operations import calculate_spread_layout
            layout_positions = calculate_spread_layout(
                item_paths=group_media_paths,
                w=spread_relayout_cfg["w"],
                h=spread_relayout_cfg["h"],
                cols=spread_relayout_cfg["cols"],
                rows=int(spread_relayout_cfg.get("rows", max(1, (len(checked_ids) + spread_relayout_cfg["cols"] - 1) // max(1, spread_relayout_cfg["cols"])))),
                margin=spread_relayout_cfg["margin"],
                fit_strategy=spread_relayout_cfg["fit_strategy"],
                spread_direction=spread_relayout_cfg["direction"],
            )

            for idx, pid in enumerate(checked_ids):
                if idx < len(layout_positions) and layout_positions[idx]:
                    px, py, pw, ph = layout_positions[idx]
                    spid = str(pid)
                    prof_s = QSettings("MyHomeApp", f"Profile_{spid}")
                    prof_s.setValue("x", px)
                    prof_s.setValue("y", py)
                    prof_s.setValue("w", pw)
                    prof_s.setValue("h", ph)
                    relayout_fit_mode = 0 if spread_relayout_cfg.get("fit_strategy") == "fit_inside" else 1
                    prof_s.setValue("media_fit_mode", relayout_fit_mode)
                    prof_s.sync()

                    if spid in self.widgets:
                        w_inst = self.widgets[spid]
                        w_inst.media_fit_mode = relayout_fit_mode
                        w_inst.setGeometry(px, py, pw, ph)
                        w_inst.save_all_settings()
                        w_inst.apply_mask_and_style()
                        if hasattr(w_inst, "_apply_media_scale_mode"):
                            w_inst._apply_media_scale_mode()

        self.load_profiles()

    def delete_checked_profiles(self):
        if not self._check_set_applied_for_action("일괄 삭제"):
            return
        checked_ids = self._checked_profile_ids()
        if not checked_ids:
            return

        from mywidgetbox_core import ask_dark_confirm
        if not ask_dark_confirm(
            self,
            "위젯 일괄 삭제",
            f"선택한 {len(checked_ids)}개의 위젯을 완전히 삭제하시겠습니까?",
            yes_text="삭제",
            no_text="취소",
            is_danger=True,
        ):
            return

        sid = self.selected_set_id()
        p_ids = self._all_profile_ids()
        set_profiles = list(self._set_defs.get(sid, {}).get("profiles", [])) if sid in self._set_defs else []

        for pid in checked_ids:
            spid = str(pid)
            if spid in self._temp_group_ids:
                self._temp_group_ids.remove(spid)
            if spid in self.widgets:
                w = self.widgets[spid]
                w.close()
                w.deleteLater()
                del self.widgets[spid]
            prof_s = QSettings("MyHomeApp", f"Profile_{spid}")
            prof_s.clear()
            prof_s.sync()
            if spid in p_ids:
                p_ids.remove(spid)
            if spid in set_profiles:
                set_profiles.remove(spid)

        self.master_settings.setValue("profile_ids", p_ids)
        if sid in self._set_defs:
            self._set_defs[sid]["profiles"] = set_profiles
            self.master_settings.setValue(self._set_key(sid, "profiles"), set_profiles)
        self.master_settings.sync()

        self._sync_temp_group_badges()
        self.update_active_status()
        self.load_profiles(force_rebuild=True)

    def open_widget_settings(self, pid):
        if not self._check_set_applied_for_action("설정"):
            return
        pid = str(pid)

        if pid in self._temp_group_ids and len(self._temp_group_ids) >= 2:
            self.open_bulk_settings()
            return

        is_running = pid in self.widgets
        s_obj = QSettings("MyHomeApp", f"Profile_{pid}")
        widget_display_name = str(s_obj.value("name", f"위젯 {pid}"))
        stored_prev_exec = str(s_obj.value("exec_path", "") or "")

        if is_running:
            w = self.widgets[pid]
            current_data = {
                'folder_path': w.folder_path,
                'folder_item_paths': list(getattr(w, 'folder_item_paths', []) or []),
                'exec_path': w.exec_path,
                'focus_binding_summary': w.get_exec_manual_focus_summary() if hasattr(w, "get_exec_manual_focus_summary") else "자동 (실행파일 기준)",
                'focus_binding_host': w,
                'w': w.width(),
                'h': w.height(),
                'layer_mode': getattr(w, 'layer_mode', DesktopWidget.LAYER_NORMAL),
                'layer_schema_version': int(DesktopWidget.LAYER_SCHEMA_VERSION),
                'is_locked': getattr(w, 'is_locked', False),
                'opacity_pct': w.current_opacity_pct,
                'bg_color_mode': w.bg_color_mode,
                'corner_mode': DesktopWidget.coerce_corner_mode(getattr(w, 'corner_mode', DesktopWidget.CORNER_ROUNDED)),
                'media_fit_mode': int(getattr(w, 'media_fit_mode', 0)),
                'video_transition_mode': int(getattr(w, 'video_transition_mode', DesktopWidget.VIDEO_TRANSITION_SINGLE)),
                'video_decode_mode': int(getattr(w, 'video_decode_mode', DesktopWidget.VIDEO_DECODE_ORIGINAL)),
                'video_dual_fade_ms': int(getattr(w, '_video_swap_fade_duration_ms', DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS)),
                'interval': w.interval_ms // 1000,
                'is_muted': w.is_muted,
                'gpu_guard_enabled': getattr(w, 'gpu_guard_enabled', False),
                'keep_aspect_ratio': getattr(w, 'keep_aspect_ratio', True),
                'auto_fit_slide_media': getattr(w, 'auto_fit_slide_media', False),
            }
        else:

            current_data = {
                'folder_path': s_obj.value("folder_path", ""),
                'folder_item_paths': DesktopWidget._as_path_list(s_obj.value("folder_item_paths", [])),
                'exec_path': s_obj.value("exec_path", ""),
                'focus_binding_summary': DesktopWidget._format_exec_manual_focus_summary(
                    _as_bool(s_obj.value("exec_manual_focus_enabled", False), False),
                    s_obj.value("exec_manual_focus_proc_path", ""),
                    s_obj.value("exec_manual_focus_proc_name", ""),
                    s_obj.value("exec_manual_focus_title", ""),
                    s_obj.value("exec_manual_focus_class", ""),
                ),
                'focus_binding_host': None,
                'w': int(s_obj.value("w", 200)),
                'h': int(s_obj.value("h", 200)),
                'keep_aspect_ratio': _as_bool(s_obj.value("keep_aspect_ratio", True), True),
                'auto_fit_slide_media': _as_bool(s_obj.value("auto_fit_slide_media", False), False),
                'layer_mode': DesktopWidget.coerce_layer_mode(
                    int(s_obj.value("layer_mode", DesktopWidget.LAYER_NORMAL)),
                    int(s_obj.value("layer_schema_version", 0)),
                ),
                'layer_schema_version': int(DesktopWidget.LAYER_SCHEMA_VERSION),
                'is_locked': _as_bool(s_obj.value("is_locked", False), False),
                'opacity_pct': int(s_obj.value("opacity_pct", 100)),
                'bg_color_mode': int(s_obj.value("bg_color_mode", 1)),
                'corner_mode': DesktopWidget.coerce_corner_mode(
                    s_obj.value("corner_mode", DesktopWidget.CORNER_ROUNDED)
                ),
                'media_fit_mode': int(s_obj.value("media_fit_mode", 0)),
                'video_transition_mode': DesktopWidget.coerce_video_transition_mode(
                    s_obj.value("video_transition_mode", DesktopWidget.VIDEO_TRANSITION_SINGLE)
                ),
                'video_decode_mode': DesktopWidget.coerce_video_decode_mode(
                    s_obj.value("video_decode_mode", DesktopWidget.VIDEO_DECODE_ORIGINAL)
                ),
                'video_dual_fade_ms': DesktopWidget.coerce_video_dual_fade_ms(
                    s_obj.value("video_dual_fade_ms", DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS)
                ),
                'interval': int(s_obj.value("interval", 5)),
                'is_muted': _as_bool(s_obj.value("is_muted", True), True),
                'gpu_guard_enabled': _as_bool(s_obj.value("gpu_guard_enabled", False), False),
            }

        dialog = SettingsDialog(self, current_data, widget_name=widget_display_name)
        

        if is_running:
            dialog.opacity_slider.valueChanged.connect(self.widgets[pid].preview_opacity)

        if dialog.exec():
            spread_data = getattr(dialog, "pending_spread_config", None)
            if spread_data:
                self.create_spread_widgets(pid, dict(spread_data), origin_widget=self.widgets.get(pid))
                return

            new_folder = dialog.folder_path
            new_folder_item_paths = list(getattr(dialog, "folder_item_paths", []) or [])
            new_exec = dialog.exec_path
            new_w = dialog.width_input.value()
            new_h = dialog.height_input.value()
            new_interval = dialog.sec_input.value() * 1000
            new_opacity = dialog.opacity_slider.value()
            new_bg = dialog.bg_combo.currentIndex()
            new_corner = DesktopWidget.coerce_corner_mode(dialog.corner_combo.currentIndex())
            new_media_fit = dialog.media_mode_combo.currentIndex()
            new_video_transition = DesktopWidget.coerce_video_transition_mode(
                dialog.video_transition_combo.currentIndex()
            )
            new_video_decode_mode = DesktopWidget.coerce_video_decode_mode(
                dialog.video_decode_combo.currentIndex()
            )
            new_video_dual_fade_ms = DesktopWidget.coerce_video_dual_fade_ms(
                dialog.video_dual_fade_ms_spin.value()
            )
            new_layer = dialog.layer_combo.currentIndex()
            new_lock = dialog.lock_cb.isChecked()
            new_mute = dialog.mute_checkbox.isChecked()
            new_gpu_guard = dialog.gpu_guard_checkbox.isChecked()
            new_keep_aspect = bool(getattr(dialog, "keep_aspect_ratio_cb", None) and dialog.keep_aspect_ratio_cb.isChecked())
            new_slide_auto_aspect = bool(getattr(dialog, "slide_auto_aspect_cb", None) and dialog.slide_auto_aspect_cb.isChecked())

            s_obj.setValue("layer_mode", new_layer)
            s_obj.setValue("layer_schema_version", int(DesktopWidget.LAYER_SCHEMA_VERSION))
            s_obj.setValue("is_locked", bool(new_lock))
            s_obj.setValue("keep_aspect_ratio", bool(new_keep_aspect))
            s_obj.setValue("auto_fit_slide_media", bool(new_slide_auto_aspect))
            s_obj.setValue("folder_path", new_folder)
            s_obj.setValue("folder_item_paths", new_folder_item_paths)
            s_obj.setValue("exec_path", new_exec)
            if DesktopWidget._normalize_exec_path(stored_prev_exec) != DesktopWidget._normalize_exec_path(new_exec):
                s_obj.setValue("exec_manual_focus_enabled", False)
                s_obj.setValue("exec_manual_focus_proc_path", "")
                s_obj.setValue("exec_manual_focus_proc_name", "")
                s_obj.setValue("exec_manual_focus_title", "")
                s_obj.setValue("exec_manual_focus_class", "")
            s_obj.setValue("w", new_w); s_obj.setValue("h", new_h)
            s_obj.setValue("opacity_pct", new_opacity)
            s_obj.setValue("bg_color_mode", new_bg)
            s_obj.setValue("corner_mode", int(new_corner))
            s_obj.setValue("media_fit_mode", int(new_media_fit))
            s_obj.setValue("video_transition_mode", int(new_video_transition))
            s_obj.setValue("video_decode_mode", int(new_video_decode_mode))
            s_obj.setValue("video_dual_fade_ms", int(new_video_dual_fade_ms))
            s_obj.setValue("interval", new_interval // 1000)
            s_obj.setValue("is_muted", bool(new_mute))
            s_obj.setValue("gpu_guard_enabled", bool(new_gpu_guard))
            s_obj.sync()


            if is_running:
                w = self.widgets[pid]
                w.keep_aspect_ratio = bool(new_keep_aspect)
                w.auto_fit_slide_media = bool(new_slide_auto_aspect)
                w.base_slide_w = new_w
                w.base_slide_h = new_h

                if w.width() != new_w or w.height() != new_h:
                    w.resize(new_w, new_h)
                
                w.current_opacity_pct = new_opacity
                w.setWindowOpacity(new_opacity / 100.0)
                
                w.bg_color_mode = new_bg
                w.corner_mode = DesktopWidget.coerce_corner_mode(new_corner)
                w.media_fit_mode = int(new_media_fit)
                w.video_transition_mode = int(new_video_transition)
                w.video_decode_mode = int(new_video_decode_mode)
                w._video_swap_fade_duration_ms = int(new_video_dual_fade_ms)
                w.apply_mask_and_style()
                w._sync_current_media_cycle_policy()

                w.apply_window_settings(new_layer, new_lock)

                prev_exec = str(getattr(w, "exec_path", "") or "")
                w.exec_path = new_exec
                if hasattr(w, "_normalize_exec_path") and hasattr(w, "_clear_bound_exec_window"):
                    if w._normalize_exec_path(prev_exec) != w._normalize_exec_path(new_exec):
                        w._clear_bound_exec_window()
                        if hasattr(w, "_clear_manual_focus_binding"):
                            w._clear_manual_focus_binding(persist=False, clear_bound=False)
                w.is_muted = new_mute
                w._apply_mute_state()
                w.gpu_guard_enabled = bool(new_gpu_guard)
                if not w.gpu_guard_enabled:
                    w.set_performance_paused(False, reason="guard_disabled")
                elif self._gpu_guard_paused:
                    w.set_performance_paused(True, reason=f"gpu {self._gpu_last_usage:.1f}%", force=True)


                old_folder = str(w.folder_path or "")
                old_folder_items = list(getattr(w, "folder_item_paths", []) or [])
                source_changed = (old_folder != str(new_folder or "") or old_folder_items != new_folder_item_paths)
                if new_folder:
                    w.folder_path = new_folder
                    w.folder_item_paths = list(new_folder_item_paths)
                    w._set_watched_folder(new_folder)
                else:
                    w.folder_path = str(new_folder or "")
                    w.folder_item_paths = []
                    w._set_watched_folder(w.folder_path)
                w.interval_ms = new_interval

                if source_changed:

                    w.update_playlist()
                    w.current_idx = -1
                    w.next_media()
                else:
                    if hasattr(w, "_apply_media_scale_mode"):
                        w._apply_media_scale_mode()

                if w.timer.isActive():
                    w.timer.setInterval(new_interval)
                    



            self.load_profiles()
        else:
            if is_running:
                self.widgets[pid].setWindowOpacity(self.widgets[pid].current_opacity_pct / 100.0)

    def create_spread_widgets(self, origin_pid, spread_config, origin_widget=None):
        if not spread_config:
            return False

        sid = self.selected_set_id()
        if sid not in self._set_defs and self._set_order:
            sid = self._set_order[0]
        applied_sid = str(getattr(self, "_applied_set_id", "") or "")
        if applied_sid and sid and sid != applied_sid:
            self._set_current_set_id(sid, persist=True)
            self.apply_set(sid)
        folder_path = str(spread_config.get("folder_path", "") or "").strip()
        item_paths = list(spread_config.get("item_paths", []) or [])
        if not item_paths:
            return False

        w = max(50, int(spread_config.get("w", 200)))
        h = max(50, int(spread_config.get("h", 200)))
        rows = max(1, int(spread_config.get("rows", 1)))
        cols = max(1, int(spread_config.get("cols", 1)))
        margin = max(0, int(spread_config.get("margin", 10)))

        spid = str(origin_pid) if origin_pid not in (None, "") else ""
        target_widget = origin_widget or (self.widgets.get(spid) if spid else None)

        fit_strategy = spread_config.get("fit_strategy", "auto_aspect")

        if target_widget and target_widget.isVisible():
            start_x = target_widget.x()
            start_y = target_widget.y()
        else:
            start_x = None
            start_y = None

        sid = self.selected_set_id()
        if sid not in self._set_defs and self._set_order:
            sid = self._set_order[0]
        current_set_profiles = list(self._set_defs.get(sid, {}).get("profiles", [])) if sid in self._set_defs else []

        # 기존 세트의 위젯들은 안전하게 보존하며, spid가 세트에 없으면 포함
        if spid and spid not in current_set_profiles:
            current_set_profiles.append(spid)

        all_pids = self._all_profile_ids()
        created_count = 0

        spread_direction = str(spread_config.get("spread_direction", "top-left") or "top-left")
        bg_mode = int(spread_config.get("bg_color_mode", 0))
        corner_mode = int(spread_config.get("corner_mode", 0))

        from master_operations import calculate_spread_layout
        positions = calculate_spread_layout(
            item_paths=item_paths,
            w=w,
            h=h,
            cols=cols,
            rows=rows,
            margin=margin,
            fit_strategy=fit_strategy,
            spread_direction=spread_direction,
            start_x=start_x,
            start_y=start_y,
        )

        for idx, item_path in enumerate(item_paths):
            item_name = os.path.basename(item_path)
            pos_x, pos_y, item_w, item_h = positions[idx]
            media_fit_mode = 1 if fit_strategy in (
                "auto_aspect", "fullscreen_autofill", "grid_span", "crop_fill",
                "modular_tetris", "treemap_collage", "justified_rows", "justified_columns"
            ) else 0

            if idx == 0 and target_widget:
                target_widget.profile_name = item_name
                target_widget.folder_path = folder_path
                target_widget.folder_item_paths = [item_path]
                target_widget._set_watched_folder(folder_path)
                target_widget.bg_color_mode = bg_mode
                target_widget.corner_mode = corner_mode
                target_widget.media_fit_mode = media_fit_mode
                target_widget.growth_anchor = spread_direction
                target_widget.move(pos_x, pos_y)
                target_widget.resize(item_w, item_h)
                if hasattr(target_widget, "apply_mask_and_style"):
                    target_widget.apply_mask_and_style()
                target_widget.update_playlist()
                target_widget.current_idx = -1
                target_widget.next_media()
                target_widget.save_all_settings()
                QSettings("MyHomeApp", f"Profile_{target_widget.profile_id}").setValue("name", item_name)
                QSettings("MyHomeApp", f"Profile_{target_widget.profile_id}").setValue("corner_mode", corner_mode)
                created_count += 1
                continue

            new_id = self._next_profile_id(all_pids)
            all_pids.append(new_id)

            new_settings = QSettings("MyHomeApp", f"Profile_{new_id}")
            new_settings.setValue("name", item_name)
            new_settings.setValue("x", pos_x)
            new_settings.setValue("y", pos_y)
            new_settings.setValue("w", item_w)
            new_settings.setValue("h", item_h)
            new_settings.setValue("pos", QPoint(pos_x, pos_y))
            new_settings.setValue("size", QSize(item_w, item_h))
            new_settings.setValue("folder_path", folder_path)
            new_settings.setValue("folder_item_paths", [item_path])
            new_settings.setValue("bg_color_mode", bg_mode)
            new_settings.setValue("media_fit_mode", media_fit_mode)
            new_settings.setValue("layer_mode", int(DesktopWidget.LAYER_NORMAL))
            new_settings.setValue("layer_schema_version", int(DesktopWidget.LAYER_SCHEMA_VERSION))
            new_settings.setValue("corner_mode", corner_mode)
            new_settings.setValue("video_transition_mode", int(DesktopWidget.VIDEO_TRANSITION_SINGLE))
            new_settings.setValue("video_decode_mode", int(DesktopWidget.VIDEO_DECODE_ORIGINAL))
            new_settings.setValue("video_dual_fade_ms", int(DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS))
            new_settings.setValue("interval", 5)
            new_settings.setValue("is_muted", True)
            new_settings.setValue("gpu_guard_enabled", False)
            new_settings.setValue("run_enabled", True)
            new_settings.sync()

            if sid in self._set_defs:
                if new_id not in current_set_profiles:
                    current_set_profiles.append(new_id)

            self.run_widget(new_id, item_name, defer_reload=True)
            created_count += 1

        self.master_settings.setValue("profile_ids", all_pids)
        if sid in self._set_defs:
            self._set_defs[sid]["profiles"] = current_set_profiles
            self.master_settings.setValue(self._set_key(sid, "profiles"), current_set_profiles)
        self.master_settings.sync()

        self.update_active_status()
        self.load_profiles()
        return bool(created_count > 0)

    def _set_hovered_profile_row(self, pid):
        next_pid = str(pid) if pid not in (None, "") else None
        if getattr(self, "_hovered_profile_pid", None) == next_pid:
            return
        self._hovered_profile_pid = next_pid
        for row_pid, row in self.profile_rows.items():
            if isinstance(row, ProfileRowWidget):
                row.set_hovered(row_pid == next_pid)

    def _on_profile_item_entered(self, item):
        raw_pid = item.data(Qt.ItemDataRole.UserRole)
        self._set_hovered_profile_row(raw_pid)

    def highlight_widget(self, item):
        """리스트 아이템 클릭 시 해당 위젯만 강조"""
        raw_pid = item.data(Qt.ItemDataRole.UserRole)
        if raw_pid in (None, ""):
            self.clear_all_highlights()
            return
        target_pid = str(raw_pid)
        
        for pid, widget in self.widgets.items():
            if str(pid) == target_pid:
                widget.show_selection(True)
            else:
                widget.show_selection(False)

        for pid in self.profile_rows.keys():
            self._set_profile_row_selected(pid, pid == target_pid)

    def clear_all_highlights(self):
        """모든 위젯의 강조 레이어 제거"""
        for widget in self.widgets.values():
            widget.show_selection(False)
        for pid in self.profile_rows.keys():
            self._set_profile_row_selected(pid, False)
        self.list_widget.clearSelection()

    def handle_focus_change(self, old, new):
        """컨트롤러 외부나 리스트 외의 곳을 클릭하면 강조 해제"""

        if new is None:
            self.clear_all_highlights()

    def mousePressEvent(self, event):
        self.clear_all_highlights()
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "gpu_cfg_panel") and self.gpu_cfg_panel.isVisible():
            self._place_gpu_cfg_panel()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "gpu_cfg_panel") and self.gpu_cfg_panel.isVisible():
            self._place_gpu_cfg_panel()

    def _move_master_near_anchor(self, anchor_rect):
        if not isinstance(anchor_rect, QRect):
            return

        anchor = QRect(anchor_rect)
        screen = QGuiApplication.screenAt(anchor.center()) or self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return

        ag = screen.availableGeometry()
        gap = 12
        margin = 8
        w = max(100, int(self.width()))
        h = max(100, int(self.height()))

        # Prefer right side of settings dialog; fallback to left when out of bounds.
        x = int(anchor.right()) + gap
        y = int(anchor.top())
        if x + w > int(ag.right()) - margin:
            x = int(anchor.left()) - gap - w

        min_x = int(ag.left()) + margin
        max_x = int(ag.right()) - w - margin
        min_y = int(ag.top()) + margin
        max_y = int(ag.bottom()) - h - margin

        x = max(min_x, min(int(x), max_x))
        y = max(min_y, min(int(y), max_y))
        self.move(int(x), int(y))

    def show_master_window(self, anchor_rect=None, restart=False):
        """컨트롤러를 보이게 하고 필요 시 앵커 옆에 재배치한다."""
        if bool(restart) and self.isVisible():
            self.hide()
            try:
                QApplication.processEvents()
            except Exception:
                pass

        self.showNormal()
        if isinstance(anchor_rect, QRect):
            self._move_master_near_anchor(anchor_rect)
        self.show()
        self.raise_()
        self.activateWindow()

    def _widget_under_global_pos(self, global_pos):
        candidates = []
        for w in self.widgets.values():
            if not isinstance(w, QWidget) or not w.isVisible():
                continue
            if w.geometry().contains(global_pos):
                layer = int(getattr(w, "layer_mode", DesktopWidget.LAYER_NORMAL))
                candidates.append((layer, int(w.winId()), w))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]

    def _poll_alt_click_toggle_lock(self):
        try:
            alt_down = bool(win32api.GetAsyncKeyState(win32con.VK_MENU) & 0x8000)
            left_down = bool(win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
            chord_down = alt_down and left_down

            if chord_down and not self._alt_click_pressed_prev:
                cursor_x, cursor_y = win32api.GetCursorPos()
                target = self._widget_under_global_pos(QPoint(int(cursor_x), int(cursor_y)))
                if target is not None:
                    new_lock = not bool(getattr(target, "is_locked", False))
                    if hasattr(target, "cancel_active_interaction"):
                        target.cancel_active_interaction()
                    target.apply_window_settings(int(getattr(target, "layer_mode", DesktopWidget.LAYER_NORMAL)), new_lock)
                    target.save_all_settings()
                    if hasattr(target, "show_lock_hud"):
                        target.show_lock_hud(new_lock)
                    if hasattr(target, "_refresh_group_badge"):
                        target._refresh_group_badge()

            self._alt_click_pressed_prev = chord_down
        except Exception:
            # Keep polling robust even if key-state API fails transiently.
            self._alt_click_pressed_prev = False

    def _gpu_guard_targets(self):
        return [
            w for w in self.widgets.values()
            if isinstance(w, DesktopWidget)
        ]

    def _on_gpu_guard_enable_toggled(self, checked):
        self._gpu_guard_enabled = bool(checked)
        self.master_settings.setValue("gpu_guard_enabled", self._gpu_guard_enabled)
        self.gpu_pause_slider.setEnabled(self._gpu_guard_enabled)
        self.gpu_resume_slider.setEnabled(self._gpu_guard_enabled)
        if not self._gpu_guard_enabled and getattr(self, "_gpu_guard_paused", False):
            self._set_gpu_guard_paused(False, self._gpu_last_usage, reason="guard_disabled")

    def _set_gpu_guard_paused(self, paused, usage, reason="", force_targets=False):
        self._gpu_guard_paused = bool(paused)
        self._gpu_last_usage = float(usage)

        targets = set(self._gpu_guard_targets())
        for w in self.widgets.values():
            if not isinstance(w, DesktopWidget):
                continue
            if w in targets:
                w.set_performance_paused(
                    self._gpu_guard_paused,
                    reason=f"{reason} ({self._gpu_last_usage:.1f}%)" if reason else f"{self._gpu_last_usage:.1f}%",
                    force=bool(force_targets and self._gpu_guard_paused),
                )
            else:
                w.set_performance_paused(False, reason="guard_not_target")

    def _on_pause_on_fullscreen_toggled(self, checked):
        self._pause_on_fullscreen = bool(checked)
        self.master_settings.setValue("pause_on_fullscreen", self._pause_on_fullscreen)
        if not self._pause_on_fullscreen and getattr(self, "_fullscreen_paused", False):
            self._fullscreen_paused = False
            for w in self.widgets.values():
                if isinstance(w, DesktopWidget):
                    w.set_performance_paused(False, reason="fullscreen_disabled")

    def _is_other_app_fullscreen(self):
        try:
            import win32gui, win32api, win32con, win32process
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or hwnd == win32gui.GetDesktopWindow() or hwnd == win32gui.GetShellWindow():
                return False

            try:
                _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                if win_pid == os.getpid():
                    return False
            except Exception:
                pass

            own_hwnds = {int(self.winId())}
            for w in self.widgets.values():
                if w and w.isVisible():
                    try:
                        own_hwnds.add(int(w.winId()))
                    except Exception:
                        pass
            if int(hwnd) in own_hwnds:
                return False

            class_name = win32gui.GetClassName(hwnd)
            shell_classes = (
                "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                "SHELLDLL_DefView", "SysListView32", "DV2ControlHost",
                "Windows.UI.Core.CoreWindow",
            )
            if class_name in shell_classes:
                return False

            try:
                root = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
                if root and root != hwnd:
                    root_cls = win32gui.GetClassName(root)
                    if root_cls in shell_classes:
                        return False
            except Exception:
                pass

            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return False

            try:
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            except Exception:
                style = 0

            rect = win32gui.GetWindowRect(hwnd)
            w_left, w_top, w_right, w_bottom = rect

            monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            if not monitor:
                return False
            mon_info = win32api.GetMonitorInfo(monitor)
            m_left, m_top, m_right, m_bottom = mon_info["Monitor"]
            work_left, work_top, work_right, work_bottom = mon_info["Work"]

            # 1. 완전 전체화면 (게임, 유튜브 F11, 독점 전체화면: 모니터 영역 전체를 덮음)
            if w_left <= m_left and w_top <= m_top and w_right >= m_right and w_bottom >= m_bottom:
                return True

            # 2. 창 최대화 (작업 관리자, 웹브라우저, 창모드 게임 등 해당 모니터 작업 영역 전체를 채움)
            is_maximized = bool(style & win32con.WS_MAXIMIZE)
            covers_work_area = (
                w_left <= work_left + 16 and w_top <= work_top + 16 and
                w_right >= work_right - 16 and w_bottom >= work_bottom - 16
            )
            if is_maximized or covers_work_area:
                return True
        except Exception:
            pass
        return False

    def _poll_gpu_guard(self):
        # 0. 다른 앱 전체화면 일시정지 감지 및 처리
        if getattr(self, "_pause_on_fullscreen", True):
            is_fs = self._is_other_app_fullscreen()
            if is_fs:
                if not getattr(self, "_fullscreen_paused", False):
                    self._fullscreen_paused = True
                    for w in self.widgets.values():
                        if isinstance(w, DesktopWidget):
                            w.set_performance_paused(True, reason="전체화면 감지", force=True)
                return
            else:
                if getattr(self, "_fullscreen_paused", False):
                    self._fullscreen_paused = False
                    for w in self.widgets.values():
                        if isinstance(w, DesktopWidget):
                            w.set_performance_paused(False, reason="전체화면 해제")

        if not getattr(self, "_gpu_guard_enabled", True):
            if self._gpu_guard_paused:
                self._set_gpu_guard_paused(False, self._gpu_last_usage, reason="guard_disabled")
            return

        targets = self._gpu_guard_targets()
        if not targets:
            self._gpu_high_streak = 0
            self._gpu_low_streak = 0
            self._gpu_below_high_streak = 0
            if self._gpu_guard_paused:
                self._set_gpu_guard_paused(False, self._gpu_last_usage, reason="targets_empty")
            return

        usage = self._gpu_sampler.sample_pct()
        if usage is None:
            return
        self._gpu_last_usage = float(usage)

        if not self._gpu_guard_paused:
            if usage >= self._gpu_guard_high_pct:
                self._gpu_high_streak += 1
            else:
                self._gpu_high_streak = 0
            self._gpu_low_streak = 0
            self._gpu_below_high_streak = 0

            if self._gpu_high_streak >= self._gpu_guard_high_hold:
                self._gpu_high_streak = 0
                self._set_gpu_guard_paused(True, usage, reason="gpu_high", force_targets=True)
        else:
            # Keep newly enabled targets in paused state while guard is active.
            self._set_gpu_guard_paused(True, usage, reason="gpu_guard_active", force_targets=False)
            if usage <= self._gpu_guard_low_pct:
                self._gpu_low_streak += 1
            else:
                self._gpu_low_streak = 0
            if usage < self._gpu_guard_high_pct:
                self._gpu_below_high_streak += 1
            else:
                self._gpu_below_high_streak = 0
            self._gpu_high_streak = 0

            if self._gpu_low_streak >= self._gpu_guard_low_hold:
                self._gpu_low_streak = 0
                self._gpu_below_high_streak = 0
                self._set_gpu_guard_paused(False, usage, reason="gpu_recovered")
            elif self._gpu_below_high_streak >= max(6, self._gpu_guard_low_hold * 3):
                # Fallback: avoid "stuck paused" when low threshold is set too aggressively.
                self._gpu_low_streak = 0
                self._gpu_below_high_streak = 0
                self._set_gpu_guard_paused(False, usage, reason="gpu_recovered_soft")

    def add_profile(self, target_set_id=None):
        if target_set_id not in (None, False, ""):
            sid = str(target_set_id)
        else:
            sid = str(getattr(self, "_applied_set_id", "") or self.selected_set_id() or "")

        if sid not in self._set_defs and self._set_order:
            sid = self._set_order[0]

        p_ids = self._all_profile_ids()
        new_id = self._next_profile_id(p_ids)
        p_ids.append(new_id)

        new_settings = QSettings("MyHomeApp", f"Profile_{new_id}")
        new_settings.setValue("name", "New 세팅")
        new_settings.setValue("w", 200)
        new_settings.setValue("h", 200)
        new_settings.setValue("growth_anchor", "top-left")
        new_settings.setValue("layer_mode", int(DesktopWidget.LAYER_NORMAL))
        new_settings.setValue("layer_schema_version", int(DesktopWidget.LAYER_SCHEMA_VERSION))
        new_settings.setValue("corner_mode", 0)
        new_settings.setValue("media_fit_mode", 0)
        new_settings.setValue("video_transition_mode", int(DesktopWidget.VIDEO_TRANSITION_SINGLE))
        new_settings.setValue("video_decode_mode", int(DesktopWidget.VIDEO_DECODE_ORIGINAL))
        new_settings.setValue("video_dual_fade_ms", int(DesktopWidget.VIDEO_DUAL_FADE_DEFAULT_MS))
        new_settings.setValue("run_enabled", True)
        new_settings.sync()

        self.master_settings.setValue("profile_ids", p_ids)
        if sid in self._set_defs:
            profiles = list(self._set_defs[sid].get("profiles", []))
            profiles = [new_id] + [pid for pid in profiles if pid != new_id]
            self._set_defs[sid]["profiles"] = profiles
            self.master_settings.setValue(self._set_key(sid, "profiles"), profiles)
        self.master_settings.sync()

        applied_sid = str(getattr(self, "_applied_set_id", "") or "")
        if applied_sid != sid:
            self._set_current_set_id(sid, persist=True)
            self.apply_set(sid)
        else:
            self.run_widget(new_id, "New 세팅")

    def run_widget(self, pid, name, defer_reload=False):
        spid = str(pid)
        target_sid = self._set_of_profile(spid)
        applied_sid = str(getattr(self, "_applied_set_id", "") or "")
        if target_sid and target_sid != applied_sid:
            self._set_current_set_id(target_sid, persist=True)
            self.apply_set(target_sid)

        self._set_profile_run_enabled(spid, True)
        if spid not in self.widgets:
            display_name = name if name not in (None, "") else QSettings(
                "MyHomeApp", f"Profile_{spid}"
            ).value("name", "New 세팅")
            self._start_widget_instance(spid, str(display_name))
        if not defer_reload:
            self.update_active_status()
            self.load_profiles()

    def stop_widget(self, pid):
        spid = str(pid)
        self._set_profile_run_enabled(spid, False)
        if spid in self._temp_group_ids:
            self._temp_group_ids.remove(spid)
        if spid in self.widgets:
            widget = self.widgets[spid]
            widget.close()
            widget.deleteLater()
            del self.widgets[spid]
            self._sync_all_widget_video_viewports()
        self._sync_temp_group_badges()
        self.update_active_status()
        self.load_profiles()

    def restore_last_session(self):
        self._load_set_state()
        sid = self.selected_set_id()
        if not sid and self._set_order:
            sid = self._set_order[0]
        if sid:
            self.apply_set(sid)


        # Startup visibility policy:
        # - hide controller if at least one widget was restored
        # - show controller if no widget exists to run
        if self.widgets:
            self.hide()
        else:
            self.show()

    def run_all(self):
        sid = self.selected_set_id()
        if sid:
            self.apply_set(sid)

    def delete_profile(self, pid):
        if not self._check_set_applied_for_action("삭제"):
            return
        spid = str(pid)
        from mywidgetbox_core import ask_dark_confirm
        if not ask_dark_confirm(self, "위젯 삭제", "이 위젯을 완전히 삭제하시겠습니까?", yes_text="삭제", no_text="취소", is_danger=True):
            return
        if True:
            if spid in self._temp_group_ids:
                self._temp_group_ids.remove(spid)
            if spid in self.widgets:
                widget = self.widgets[spid]
                widget.close()
                widget.deleteLater()
                del self.widgets[spid]
            prof_settings = QSettings("MyHomeApp", f"Profile_{spid}")
            prof_settings.clear()
            prof_settings.sync()
            p_ids = self._all_profile_ids()
            if spid in p_ids:
                p_ids.remove(spid)
                self.master_settings.setValue("profile_ids", p_ids)
            self._remove_profile_from_sets(spid)
            self.master_settings.sync()
            self._sync_temp_group_badges()
            self.update_active_status()
            self.load_profiles()

    def closeEvent(self, event):
        if hasattr(self, "gpu_cfg_panel") and self.gpu_cfg_panel.isVisible():
            self.gpu_cfg_panel.hide()
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

    def quit_app(self):
        if hasattr(self, "_alt_click_poll_timer"):
            self._alt_click_poll_timer.stop()
        if hasattr(self, "_gpu_guard_timer"):
            self._gpu_guard_timer.stop()
        if hasattr(self, "_gpu_sampler"):
            self._gpu_sampler.close()
        self.clear_temp_group(silent=True)
        for w in list(self.widgets.values()):
            w.close()
        QTimer.singleShot(450, self._finalize_quit)

    def _finalize_quit(self):
        try:
            self._load_set_state()
            self._cleanup_orphan_profiles()
        except Exception as e:
            print(f"[orphan-cleanup] failed: {e}")
        self._flush_master_settings_sync()
        app = QApplication.instance()
        if app:
            app.quit()

    def rename_profile(self, item_or_pid):
        if hasattr(item_or_pid, "data"):
            pid = item_or_pid.data(Qt.ItemDataRole.UserRole)
        else:
            pid = str(item_or_pid)
        if pid in (None, ""):
            return
        current_name = QSettings("MyHomeApp", f"Profile_{pid}").value("name", "New 세팅")
        from mywidgetbox_core import ask_dark_input
        new_name, ok = ask_dark_input(
            self,
            title="위젯 이름 변경",
            prompt="위젯 이름을 입력하세요:",
            default_text=str(current_name),
            ok_text="저장",
            cancel_text="취소",
        )
        if ok and new_name:
            QSettings("MyHomeApp", f"Profile_{pid}").setValue("name", new_name)
            self.load_profiles()

    def rename_set(self, set_id, name=None):
        sid = str(set_id)
        if sid not in self._set_defs:
            return
        if name is not None:
            new_name = str(name).strip()
            if new_name:
                self._set_defs[sid]["name"] = new_name
                self.master_settings.setValue(self._set_key(sid, "name"), new_name)
                self.master_settings.sync()
                self.load_profiles()
            return
        current_name = self._set_defs[sid].get("name", f"세트{sid}")
        from mywidgetbox_core import ask_dark_input
        new_name, ok = ask_dark_input(
            self,
            title="세트 이름 변경",
            prompt="세트 이름을 입력하세요:",
            default_text=str(current_name),
            ok_text="저장",
            cancel_text="취소",
        )
        if ok and new_name:
            self._set_defs[sid]["name"] = new_name
            self.master_settings.setValue(self._set_key(sid, "name"), new_name)
            self.master_settings.sync()
            self.load_profiles()

    def _schedule_master_settings_sync(self, delay_ms=None):
        _mc_schedule_master_settings_sync_impl(self, delay_ms=delay_ms)

    def _flush_master_settings_sync(self):
        _mc_flush_master_settings_sync_impl(self)

    def update_active_status(self, sync=True):
        _mc_update_active_status_impl(self, sync=sync)


if __name__ == "__main__":

    sys.excepthook = lambda cls, exception, traceback: sys.__excepthook__(cls, exception, traceback)

    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_CompressHighFrequencyEvents, True)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    from mywidgetbox_ui_primitives import PreventInputWheelScrollFilter
    app._wheel_filter = PreventInputWheelScrollFilter(app)
    app.installEventFilter(app._wheel_filter)
    master = MasterController()
    # Avoid initial flash before restore_last_session decides visibility.
    master.hide()
        
    try:
        sys.exit(app.exec())
    except Exception as e:
        print("CRITICAL ERROR:", e)
        import traceback
        traceback.print_exc()
        input("엔터를 누르면 종료합니다...") # 에러 확인을 위해 잠시 멈춤
