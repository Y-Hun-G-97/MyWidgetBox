from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QPoint, QPointF, QSettings, Qt
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import MyWidgetBox as mw


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str


class DummyManager:
    def __init__(self):
        self.master_open_called = False

    def show_master_window(self):
        self.master_open_called = True


class FakeWheelEvent:
    def __init__(self, delta_y: int, modifiers: Qt.KeyboardModifier):
        self._delta_y = delta_y
        self._modifiers = modifiers

    def angleDelta(self):
        return QPoint(0, self._delta_y)

    def modifiers(self):
        return self._modifiers


class FakeMouseEvent:
    def __init__(self, button: Qt.MouseButton, local_pos: QPoint, global_pos: QPoint):
        self._button = button
        self._local = QPointF(local_pos)
        self._global = QPointF(global_pos)

    def button(self):
        return self._button

    def position(self):
        return QPointF(self._local)

    def globalPosition(self):
        return QPointF(self._global)


def log(msg: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def pump(app: QApplication, ms: int = 200):
    end = time.time() + (ms / 1000.0)
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def maybe_show(widget, app: QApplication, visible: bool, ms_visible: int = 600):
    widget.show()
    pump(app, ms_visible if visible else 120)


def get_base_path() -> Path:
    env = os.environ.get("TEST_BASE")
    if env:
        p = Path(env)
        if p.exists():
            return p

    return Path(r"C:\Users\ggrol\OneDrive\바탕 화면\명조")


def _name_match(name: str, suffix: str) -> bool:
    if suffix.lower() == "gif":
        return name.lower().endswith("gif")
    return name.endswith(suffix)


def pick_media_folder(base: Path, suffix: str, exts: tuple[str, ...], max_depth: int = 4) -> Path | None:
    if not base.exists():
        return None

    candidates: list[tuple[Path, int]] = []
    scanned = 0

    # Fast path: direct children first.
    for d in base.iterdir():
        if not d.is_dir() or not _name_match(d.name.strip(), suffix):
            continue
        files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in exts]
        if files:
            candidates.append((d, len(files)))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    # Slow path: depth-limited recursive scan.
    for root, dirs, _ in os.walk(base):
        root_path = Path(root)
        rel_parts = root_path.relative_to(base).parts
        if len(rel_parts) >= max_depth:
            dirs[:] = []

        for dname in dirs:
            d = root_path / dname
            scanned += 1
            if scanned % 200 == 0:
                log(f"folder scan in progress: suffix={suffix}, scanned={scanned}")

            if not _name_match(d.name.strip(), suffix):
                continue

            try:
                files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in exts]
            except PermissionError:
                continue

            if files:
                candidates.append((d, len(files)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


def seed_profile(profile_id: str, folder: Path | None = None):
    s = QSettings("MyHomeApp", f"Profile_{profile_id}")
    s.clear()
    s.setValue("name", f"TEST_{profile_id}")
    s.setValue("w", 220)
    s.setValue("h", 180)
    s.setValue("interval", 2)
    s.setValue("bg_color_mode", 1)
    s.setValue("opacity_pct", 100)
    s.setValue("is_muted", "true")
    if folder is not None:
        s.setValue("folder_path", str(folder))
    s.sync()


def clear_profile(profile_id: str):
    s = QSettings("MyHomeApp", f"Profile_{profile_id}")
    s.clear()
    s.sync()


def widget_with_profile(profile_id: str, manager=None):
    if manager is None:
        manager = DummyManager()
    w = mw.DesktopWidget(profile_id, f"TEST_{profile_id}", manager)
    return w, manager


def test_media_branch(
    kind: str,
    folder: Path,
    app: QApplication,
    *,
    visible: bool = False,
    video_cap_sec: int = 20,
) -> TestResult:
    profile_id = f"tc_media_{kind}_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, folder)

    w, _ = widget_with_profile(profile_id)
    try:
        w.folder_path = str(folder)
        w.update_playlist()
        w.current_idx = -1
        w.next_media()
        maybe_show(w, app, visible, 1200)

        if kind == "image":
            ok = w.stack.currentIndex() == 1 and w.current_static_pixmap is not None and w.timer.isActive()
            detail = (
                f"stack={w.stack.currentIndex()} pix={w.current_static_pixmap is not None} "
                f"timer={w.timer.isActive()} playlist={len(w.playlist)}"
            )
        elif kind == "gif":
            ok = w.stack.currentIndex() == 1 and w.movie is not None and w.timer.isActive()
            detail = (
                f"stack={w.stack.currentIndex()} movie={w.movie is not None} "
                f"timer={w.timer.isActive()} playlist={len(w.playlist)}"
            )
        else:
            src = w.media_player.source().toString()
            start_idx = w.current_idx
            elapsed = 0
            cap_ms = max(1, video_cap_sec) * 1000
            while elapsed < cap_ms and w.current_idx == start_idx:
                pump(app, 250)
                elapsed += 250

            forced_next = False
            if w.current_idx == start_idx and len(w.playlist) > 1:
                w.next_media()
                forced_next = True
                pump(app, 250)

            ok = w.stack.currentIndex() == 2 and bool(src)
            detail = (
                f"stack={w.stack.currentIndex()} source={bool(src)} state={w.media_player.playbackState().name} "
                f"playlist={len(w.playlist)} elapsed_ms={elapsed} forced_next={forced_next}"
            )

        return TestResult(f"media_{kind}", ok, detail)
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def test_resize_freedom(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    profile_id = f"tc_resize_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        w.folder_path = str(image_folder)
        w.update_playlist()
        w.current_idx = -1
        w.next_media()
        maybe_show(w, app, visible, 900)

        w.resize(420, 260)
        pump(app, 200)
        large = (w.width(), w.height())

        w.resize(50, 50)
        pump(app, 200)
        small = (w.width(), w.height())

        ok = (small[0] <= 60 and small[1] <= 60 and small[0] < large[0] and small[1] < large[1])
        detail = f"large={large} small={small}"
        return TestResult("resize_freedom", ok, detail)
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def test_ctrl_wheel_opacity_save(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    profile_id = f"tc_opacity_wheel_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        maybe_show(w, app, visible, 500)
        before = w.current_opacity_pct
        w.wheelEvent(FakeWheelEvent(-120, Qt.KeyboardModifier.ControlModifier))
        pump(app, 80)
        after = w.current_opacity_pct

        s = QSettings("MyHomeApp", f"Profile_{profile_id}")
        saved = int(s.value("opacity_pct", -1))
        ok = after == max(10, before - 5) and saved == after
        detail = f"before={before} after={after} saved={saved}"
        return TestResult("ctrl_wheel_opacity_save", ok, detail)
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def test_shift_corner_resize_save(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    profile_id = f"tc_shift_resize_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        maybe_show(w, app, visible, 700)
        w.resize(220, 180)
        w._move_exact((200, 180))
        pump(app, 120)
        before = (w.width(), w.height())

        original_shift = w._is_shift_down
        w._is_shift_down = lambda: True
        try:
            start_local = w._corner_rects()["br"].center()
            start_global = w.mapToGlobal(start_local)
            drag_local = QPoint(start_local.x() + 64, start_local.y() + 46)
            drag_global = w.mapToGlobal(drag_local)

            w.mousePressEvent(FakeMouseEvent(Qt.MouseButton.LeftButton, start_local, start_global))
            w.mouseMoveEvent(FakeMouseEvent(Qt.MouseButton.LeftButton, drag_local, drag_global))
            w.mouseReleaseEvent(FakeMouseEvent(Qt.MouseButton.LeftButton, drag_local, drag_global))
            pump(app, 180)
        finally:
            w._is_shift_down = original_shift

        after = (w.width(), w.height())
        s = QSettings("MyHomeApp", f"Profile_{profile_id}")
        saved_w = int(s.value("w", -1))
        saved_h = int(s.value("h", -1))
        saved_ok = (saved_w, saved_h) == after
        grew = after[0] > before[0] and after[1] > before[1]
        ok = grew and saved_ok
        detail = f"before={before} after={after} saved=({saved_w},{saved_h})"
        return TestResult("shift_corner_resize_save", ok, detail)
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def test_mute_persistence(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    profile_id = f"tc_mute_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        maybe_show(w, app, visible, 500)
        w.is_muted = False
        w.audio_output.setMuted(False)
        w.save_all_settings()
        w.close()
        w.deleteLater()

        w2, _ = widget_with_profile(profile_id)
        try:
            pump(app, 180)
            off_ok = (w2.is_muted is False and w2.audio_output.isMuted() is False)

            w2.is_muted = True
            w2.audio_output.setMuted(True)
            w2.save_all_settings()
            w2.close()
            w2.deleteLater()

            w3, _ = widget_with_profile(profile_id)
            try:
                pump(app, 180)
                on_ok = (w3.is_muted is True and w3.audio_output.isMuted() is True)
                ok = off_ok and on_ok
                detail = f"off_ok={off_ok} on_ok={on_ok}"
                return TestResult("mute_persistence", ok, detail)
            finally:
                w3.close()
                w3.deleteLater()
        finally:
            pass
    finally:
        clear_profile(profile_id)


def test_top_position_persistence(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    profile_id = f"tc_top_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        maybe_show(w, app, visible, 700)
        w._move_exact((120, 0))
        pump(app, 180)
        y_before = w.y()
        w.save_all_settings()
        w.close()
        w.deleteLater()

        w2, _ = widget_with_profile(profile_id)
        try:
            maybe_show(w2, app, visible, 700)
            y_after = w2.y()
            ok = abs(y_after - y_before) <= 4
            detail = f"y_before={y_before} y_after={y_after}"
            return TestResult("top_position_persistence", ok, detail)
        finally:
            w2.close()
            w2.deleteLater()
    finally:
        clear_profile(profile_id)


def test_playlist_clear_on_invalid(image_folder: Path, app: QApplication) -> TestResult:
    profile_id = f"tc_playlist_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        w.folder_path = str(image_folder)
        w.update_playlist()
        before = len(w.playlist)

        w.folder_path = str(image_folder / "__not_exists__")
        w.update_playlist()
        after = len(w.playlist)

        ok = before > 0 and after == 0
        detail = f"before={before} after={after}"
        return TestResult("playlist_clear_invalid_folder", ok, detail)
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def test_broken_media_skip_and_quarantine(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    source_images = [p for p in image_folder.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".ico", ".jfif", ".webp")]
    if not source_images:
        return TestResult("broken_media_skip_and_quarantine", False, "no source image in image folder")

    profile_id = f"tc_broken_skip_{int(time.time() * 1000) % 1000000}"
    work_dir = Path(tempfile.mkdtemp(prefix="widget_broken_media_"))
    try:
        bad_file = work_dir / "a_broken.png"
        bad_file.write_bytes(b"this_is_not_a_valid_image")
        valid_file = work_dir / f"b_valid{source_images[0].suffix.lower()}"
        shutil.copy2(source_images[0], valid_file)

        seed_profile(profile_id, work_dir)
        w, _ = widget_with_profile(profile_id)
        try:
            w.folder_path = str(work_dir)
            w._set_watched_folder(str(work_dir))
            w.update_playlist()
            w.current_idx = -1
            w.next_media()
            maybe_show(w, app, visible, 900)
            pump(app, 600)

            current = w.current_media_path
            quarantined = str(bad_file) in w.quarantined_media
            skipped = str(bad_file) not in w.playlist
            valid_shown = current is not None and os.path.basename(current).startswith("b_valid")
            ok = quarantined and skipped and valid_shown
            detail = f"quarantined={quarantined} skipped={skipped} valid_shown={valid_shown} current={current}"
            return TestResult("broken_media_skip_and_quarantine", ok, detail)
        finally:
            w.close()
            w.deleteLater()
    finally:
        clear_profile(profile_id)
        shutil.rmtree(work_dir, ignore_errors=True)


def test_position_restore_screen_fallback(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    profile_id = f"tc_pos_fallback_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        maybe_show(w, app, visible, 700)
        screen = w._current_screen()
        if not screen:
            return TestResult("position_restore_screen_fallback", False, "no screen")
        ag = screen.availableGeometry()
        target_x = ag.x() + max(0, ag.width() - w.width() - 12)
        target_y = ag.y() + max(0, ag.height() - w.height() - 12)
        w._move_exact((target_x, target_y))
        pump(app, 180)
        w.save_all_settings()
        w.close()
        w.deleteLater()

        s = QSettings("MyHomeApp", f"Profile_{profile_id}")
        s.setValue("pos", QPoint(-5000, -5000))
        s.sync()

        w2, _ = widget_with_profile(profile_id)
        try:
            maybe_show(w2, app, visible, 900)
            on_screen = w2.is_visible_on_any_screen()
            near = abs(w2.x() - target_x) <= 160 and abs(w2.y() - target_y) <= 160
            ok = on_screen and near
            detail = f"on_screen={on_screen} expected=({target_x},{target_y}) actual=({w2.x()},{w2.y()}) near={near}"
            return TestResult("position_restore_screen_fallback", ok, detail)
        finally:
            w2.close()
            w2.deleteLater()
    finally:
        clear_profile(profile_id)


def test_utf8_text_cleanup() -> TestResult:
    src = Path("MyWidgetBox.py")
    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return TestResult("utf8_text_cleanup", False, f"decode_error={e}")

    checks = {
        "no_escaped_widget_word": "\\\\uc704\\\\uc82f" not in text,
        "no_folder_emoji_button": "📂 폴더 선택" not in text,
        "no_run_emoji_button": "🚀 실행파일 선택" not in text,
        "no_setting_emoji_button": "⚙️" not in text,
    }
    ok = all(checks.values())
    detail = " ".join([f"{k}={v}" for k, v in checks.items()])
    return TestResult("utf8_text_cleanup", ok, detail)


def test_layer_lock_flags(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    profile_id = f"tc_flags_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    w, _ = widget_with_profile(profile_id)
    try:
        maybe_show(w, app, visible, 500)
        w.apply_window_settings(2, True)
        pump(app, 140)
        flags = w.windowFlags()
        top = bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        transparent = bool(flags & Qt.WindowType.WindowTransparentForInput)
        ok = w.layer_mode == 2 and w.is_locked is True and top and transparent
        detail = f"layer={w.layer_mode} lock={w.is_locked} top={top} transparent={transparent}"
        return TestResult("layer_lock_flags", ok, detail)
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def test_open_master_controller_action(image_folder: Path, app: QApplication) -> TestResult:
    profile_id = f"tc_master_action_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, image_folder)

    manager = DummyManager()
    w, _ = widget_with_profile(profile_id, manager)
    try:
        w.open_master_controller()
        ok = manager.master_open_called
        return TestResult("open_master_controller_action", ok, f"called={manager.master_open_called}")
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def test_folder_realtime_refresh(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    source_images = [p for p in image_folder.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".ico", ".jfif", ".webp")]
    if not source_images:
        return TestResult("folder_realtime_refresh", False, "no source image in image folder")

    profile_id = f"tc_live_folder_{int(time.time() * 1000) % 1000000}"
    work_dir = Path(tempfile.mkdtemp(prefix="widget_live_refresh_"))
    try:
        first_src = source_images[0]
        first_copy = work_dir / f"a{first_src.suffix.lower()}"
        shutil.copy2(first_src, first_copy)

        seed_profile(profile_id, work_dir)
        s = QSettings("MyHomeApp", f"Profile_{profile_id}")
        s.setValue("interval", 5)
        s.sync()

        w, _ = widget_with_profile(profile_id)
        try:
            w.folder_path = str(work_dir)
            w._set_watched_folder(str(work_dir))
            w.update_playlist()
            w.current_idx = -1
            w.next_media()
            maybe_show(w, app, visible, 900)

            initial_count = len(w.playlist)
            if initial_count != 1:
                return TestResult("folder_realtime_refresh", False, f"initial_count={initial_count}")

            second_copy = work_dir / f"b{first_src.suffix.lower()}"
            shutil.copy2(first_src, second_copy)
            pump(app, 1400)
            after_add = len(w.playlist)

            current_path = w.playlist[w.current_idx] if 0 <= w.current_idx < len(w.playlist) else None
            removed_ok = False
            switched_ok = False
            if current_path and os.path.exists(current_path):
                os.remove(current_path)
                pump(app, 1500)
                removed_ok = current_path not in w.playlist
                if 0 <= w.current_idx < len(w.playlist):
                    switched_path = w.playlist[w.current_idx]
                    switched_ok = os.path.exists(switched_path) and switched_path != current_path

            ok = after_add >= 2 and removed_ok and switched_ok
            detail = (
                f"initial={initial_count} after_add={after_add} removed_ok={removed_ok} "
                f"switched_ok={switched_ok} playlist_now={len(w.playlist)}"
            )
            return TestResult("folder_realtime_refresh", ok, detail)
        finally:
            w.close()
            w.deleteLater()
    finally:
        clear_profile(profile_id)
        shutil.rmtree(work_dir, ignore_errors=True)


def test_settings_migration_and_run_all(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    pid1 = f"tc_migrate_{int(time.time() * 1000) % 1000000}"
    pid2 = f"{pid1}_2"
    seed_profile(pid1, image_folder)
    seed_profile(pid2, image_folder)

    s1 = QSettings("MyHomeApp", f"Profile_{pid1}")
    s1.setValue("is_muted", "false")
    s1.setValue("is_locked", "true")
    s1.setValue("layer_mode", 2)
    s1.sync()

    backup = backup_master_settings()
    try:
        w, _ = widget_with_profile(pid1)
        try:
            maybe_show(w, app, visible, 500)
            parsed_ok = (w.is_muted is False and w.is_locked is True and w.layer_mode == 2)
            w.save_all_settings()
        finally:
            w.close()
            w.deleteLater()

        s1_reload = QSettings("MyHomeApp", f"Profile_{pid1}")
        muted_saved = s1_reload.value("is_muted")
        locked_saved = s1_reload.value("is_locked")
        bool_saved_ok = (mw._as_bool(muted_saved, True) is False) and (mw._as_bool(locked_saved, False) is True)

        master_s = QSettings("MyHomeApp", "MasterV3")
        master_s.setValue("profile_ids", [pid1, pid2])
        master_s.setValue("active_profiles", pid1)  # intentionally scalar
        master_s.sync()

        master = mw.MasterController()
        try:
            master.restore_last_session()
            pump(app, 500)
            restore_ok = pid1 in master.widgets

            master.run_all()
            pump(app, 500)
            run_all_ok = len(master.widgets) == 2

            active_raw = master_s.value("active_profiles")
            active_ok = isinstance(active_raw, list) and set(active_raw) == {pid1, pid2}
        finally:
            for p in list(master.widgets.keys()):
                master.stop_widget(p)
            master.tray_icon.hide()
            master.hide()
            master.deleteLater()

        ok = parsed_ok and bool_saved_ok and restore_ok and run_all_ok and active_ok
        detail = (
            f"parsed_ok={parsed_ok} bool_saved_ok={bool_saved_ok} restore_ok={restore_ok} "
            f"run_all_ok={run_all_ok} active_ok={active_ok}"
        )
        return TestResult("settings_migration_and_run_all", ok, detail)
    finally:
        restore_master_settings(backup)
        clear_profile(pid1)
        clear_profile(pid2)


def test_video_interactions(
    video_folder: Path,
    app: QApplication,
    *,
    visible: bool = False,
    video_cap_sec: int = 20,
) -> TestResult:
    profile_id = f"tc_video_interact_{int(time.time() * 1000) % 1000000}"
    seed_profile(profile_id, video_folder)

    settings = QSettings("MyHomeApp", f"Profile_{profile_id}")
    settings.setValue("exec_path", r"C:\Windows\System32\notepad.exe")
    settings.sync()

    w, _ = widget_with_profile(profile_id)
    try:
        w.folder_path = str(video_folder)
        w.update_playlist()
        if not w.playlist:
            return TestResult("video_interactions", False, "no video file in selected folder")

        w.current_idx = -1
        w.next_media()
        maybe_show(w, app, visible, 1200)

        if w.stack.currentIndex() != 2:
            return TestResult("video_interactions", False, f"video not active stack={w.stack.currentIndex()}")

        # Drag widget on video surface.
        before = w.pos()
        center = w.video_widget.rect().center()
        drag_to = QPoint(center.x() + 90, center.y() + 70)
        QTest.mousePress(w.video_widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
        QTest.mouseMove(w.video_widget, drag_to, delay=40)
        pump(app, 120)
        QTest.mouseRelease(w.video_widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, drag_to)
        pump(app, 180)
        after = w.pos()
        moved = abs(after.x() - before.x()) > 5 or abs(after.y() - before.y()) > 5

        # Left-click launch action with mocked startfile.
        with patch("MyWidgetBox.os.startfile") as mock_startfile:
            click_pos = w.video_widget.rect().center()
            QTest.mouseClick(w.video_widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, click_pos, delay=20)
            pump(app, 120)
            click_ok = mock_startfile.called

        # Right-click context menu action with Python fake menu to avoid native blocking.
        class _DummySignal:
            def connect(self, _fn):
                return None

        class _DummyAction:
            def __init__(self):
                self.triggered = _DummySignal()

        class _FakeMenu:
            exec_called = False

            def __init__(self, *_args, **_kwargs):
                pass

            def setStyleSheet(self, *_args, **_kwargs):
                return None

            def addAction(self, *_args, **_kwargs):
                return _DummyAction()

            def exec(self, *_args, **_kwargs):
                _FakeMenu.exec_called = True
                return None

        with patch.object(mw, "QMenu", _FakeMenu):
            right_pos = w.video_widget.rect().center()
            ctx_evt = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                right_pos,
                w.video_widget.mapToGlobal(right_pos),
            )
            QApplication.sendEvent(w.video_widget, ctx_evt)
            pump(app, 120)
            context_ok = _FakeMenu.exec_called

        # Do not wait full video; cap observation time then force next if needed.
        start_idx = w.current_idx
        elapsed = 0
        cap_ms = max(1, video_cap_sec) * 1000
        while elapsed < cap_ms and w.current_idx == start_idx:
            pump(app, 250)
            elapsed += 250

        forced_next = False
        advanced = True
        if len(w.playlist) > 1:
            if w.current_idx == start_idx:
                w.next_media()
                forced_next = True
                pump(app, 220)
            advanced = (w.current_idx != start_idx)

        ok = moved and click_ok and context_ok and advanced
        detail = (
            f"moved={moved} click_ok={click_ok} context_ok={context_ok} "
            f"elapsed_ms={elapsed} forced_next={forced_next} advanced={advanced}"
        )
        return TestResult("video_interactions", ok, detail)
    finally:
        w.close()
        w.deleteLater()
        clear_profile(profile_id)


def backup_master_settings() -> dict:
    m = QSettings("MyHomeApp", "MasterV3")
    return {k: m.value(k) for k in m.allKeys()}


def restore_master_settings(backup: dict):
    m = QSettings("MyHomeApp", "MasterV3")
    m.clear()
    for k, v in backup.items():
        m.setValue(k, v)
    m.sync()


def test_controller_visibility_no_active(app: QApplication, *, visible: bool = False) -> TestResult:
    m = QSettings("MyHomeApp", "MasterV3")
    m.setValue("profile_ids", [])
    m.setValue("active_profiles", [])
    m.sync()

    master = mw.MasterController()
    try:
        master.restore_last_session()
        pump(app, 700 if visible else 250)
        ok = master.isVisible() and len(master.widgets) == 0
        detail = f"visible={master.isVisible()} widgets={len(master.widgets)}"
        return TestResult("controller_visible_no_active", ok, detail)
    finally:
        master.tray_icon.hide()
        master.hide()
        master.deleteLater()


def test_controller_hidden_with_active(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    pid = f"tc_active_{int(time.time() * 1000) % 1000000}"
    seed_profile(pid, image_folder)

    m = QSettings("MyHomeApp", "MasterV3")
    m.setValue("profile_ids", [pid])
    m.setValue("active_profiles", [pid])
    m.sync()

    master = mw.MasterController()
    try:
        master.restore_last_session()
        pump(app, 900 if visible else 500)
        ok = (len(master.widgets) >= 1 and not master.isVisible())
        detail = f"visible={master.isVisible()} widgets={len(master.widgets)}"
        return TestResult("controller_hidden_with_active", ok, detail)
    finally:
        for p in list(master.widgets.keys()):
            master.stop_widget(p)
        master.tray_icon.hide()
        master.hide()
        master.deleteLater()
        clear_profile(pid)


def test_controller_visible_after_all_stopped(image_folder: Path, app: QApplication, *, visible: bool = False) -> TestResult:
    pid = f"tc_stopall_{int(time.time() * 1000) % 1000000}"
    seed_profile(pid, image_folder)

    m = QSettings("MyHomeApp", "MasterV3")
    m.setValue("profile_ids", [pid])
    m.setValue("active_profiles", [pid])
    m.sync()

    master1 = mw.MasterController()
    try:
        master1.restore_last_session()
        pump(app, 900 if visible else 500)
        had_widget = pid in master1.widgets
        if had_widget:
            master1.stop_widget(pid)
            pump(app, 250)

        active_after_stop = m.value("active_profiles", [])

        master2 = mw.MasterController()
        try:
            master2.restore_last_session()
            pump(app, 700 if visible else 300)
            ok = had_widget and (not active_after_stop) and master2.isVisible() and len(master2.widgets) == 0
            detail = (
                f"had_widget={had_widget} active_after_stop={active_after_stop} "
                f"visible_after_restart={master2.isVisible()} widgets_after_restart={len(master2.widgets)}"
            )
            return TestResult("controller_visible_after_all_stopped", ok, detail)
        finally:
            master2.tray_icon.hide()
            master2.hide()
            master2.deleteLater()
    finally:
        for p in list(master1.widgets.keys()):
            master1.stop_widget(p)
        master1.tray_icon.hide()
        master1.hide()
        master1.deleteLater()
        clear_profile(pid)


def run_all_tests(*, visible: bool = False, video_cap_sec: int = 20) -> list[TestResult]:
    app = QApplication.instance() or QApplication([])

    base = get_base_path()
    log(f"base path: {base}")
    image_folder = pick_media_folder(base, "이미지", (".png", ".jpg", ".jpeg", ".ico", ".jfif", ".webp"))
    gif_folder = pick_media_folder(base, "gif", (".gif",))
    video_folder = pick_media_folder(base, "영상", (".mp4", ".avi", ".mov"))
    log(f"picked image folder: {image_folder}")
    log(f"picked gif folder: {gif_folder}")
    log(f"picked video folder: {video_folder}")

    results: list[TestResult] = []
    master_backup = backup_master_settings()

    def run_case(label: str, fn):
        log(f"START {label}")
        t0 = time.time()
        try:
            result = fn()
        except Exception as e:
            result = TestResult(label, False, f"exception={type(e).__name__}: {e}")
        dt = time.time() - t0
        state = "PASS" if result.passed else "FAIL"
        log(f"END {label}: {state} ({dt:.2f}s) | {result.detail}")
        results.append(result)

    try:
        if image_folder:
            run_case(
                "media_image",
                lambda: test_media_branch("image", image_folder, app, visible=visible, video_cap_sec=video_cap_sec),
            )
            run_case("resize_freedom", lambda: test_resize_freedom(image_folder, app, visible=visible))
            run_case("ctrl_wheel_opacity_save", lambda: test_ctrl_wheel_opacity_save(image_folder, app, visible=visible))
            run_case("shift_corner_resize_save", lambda: test_shift_corner_resize_save(image_folder, app, visible=visible))
            run_case("mute_persistence", lambda: test_mute_persistence(image_folder, app, visible=visible))
            run_case(
                "top_position_persistence",
                lambda: test_top_position_persistence(image_folder, app, visible=visible),
            )
            run_case(
                "position_restore_screen_fallback",
                lambda: test_position_restore_screen_fallback(image_folder, app, visible=visible),
            )
            run_case("playlist_clear_invalid_folder", lambda: test_playlist_clear_on_invalid(image_folder, app))
            run_case(
                "broken_media_skip_and_quarantine",
                lambda: test_broken_media_skip_and_quarantine(image_folder, app, visible=visible),
            )
            run_case("folder_realtime_refresh", lambda: test_folder_realtime_refresh(image_folder, app, visible=visible))
            run_case(
                "settings_migration_and_run_all",
                lambda: test_settings_migration_and_run_all(image_folder, app, visible=visible),
            )
            run_case("utf8_text_cleanup", test_utf8_text_cleanup)
            run_case("layer_lock_flags", lambda: test_layer_lock_flags(image_folder, app, visible=visible))
            run_case("open_master_controller_action", lambda: test_open_master_controller_action(image_folder, app))
        else:
            results.append(TestResult("image_dependent_tests", False, f"image folder not found under {base}"))

        if gif_folder:
            run_case(
                "media_gif",
                lambda: test_media_branch("gif", gif_folder, app, visible=visible, video_cap_sec=video_cap_sec),
            )
        else:
            results.append(TestResult("media_gif", False, f"gif folder not found under {base}"))

        if video_folder:
            run_case(
                "media_video",
                lambda: test_media_branch("video", video_folder, app, visible=visible, video_cap_sec=video_cap_sec),
            )
            run_case(
                "video_interactions",
                lambda: test_video_interactions(video_folder, app, visible=visible, video_cap_sec=video_cap_sec),
            )
        else:
            results.append(TestResult("media_video", False, f"video folder not found under {base}"))

        run_case("controller_visible_no_active", lambda: test_controller_visibility_no_active(app, visible=visible))

        if image_folder:
            run_case(
                "controller_hidden_with_active",
                lambda: test_controller_hidden_with_active(image_folder, app, visible=visible),
            )
            run_case(
                "controller_visible_after_all_stopped",
                lambda: test_controller_visible_after_all_stopped(image_folder, app, visible=visible),
            )

    finally:
        restore_master_settings(master_backup)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--visible", action="store_true", help="show widgets/controller during tests")
    parser.add_argument(
        "--video-cap-sec",
        type=int,
        default=20,
        help="max seconds to observe a video before forcing next media",
    )
    args = parser.parse_args()

    results = run_all_tests(visible=args.visible, video_cap_sec=args.video_cap_sec)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print("FEATURE_TEST_RESULTS_START")
    for r in results:
        state = "PASS" if r.passed else "FAIL"
        print(f"[{state}] {r.name}: {r.detail}")
    print(f"SUMMARY: {passed}/{total} passed")
    print("FEATURE_TEST_RESULTS_END")
