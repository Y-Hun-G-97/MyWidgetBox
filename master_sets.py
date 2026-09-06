# Consolidated master set store and apply logic
import os

from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtWidgets import QMessageBox

from mywidgetbox_core import _as_bool


def _sync_master_settings(controller, immediate=False):
    if bool(immediate):
        flush = getattr(controller, "_flush_master_settings_sync", None)
        if callable(flush):
            flush()
            return
    schedule = getattr(controller, "_schedule_master_settings_sync", None)
    if callable(schedule):
        schedule()
        return
    try:
        controller.master_settings.sync()
    except Exception:
        pass


def as_list(value):
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if value in (None, ""):
        return []
    return [str(value)]


def normalize_ids(values):
    out = []
    seen = set()
    for value in values:
        sid = str(value)
        if not sid or sid in seen:
            continue
        out.append(sid)
        seen.add(sid)
    return out


def set_key(_controller, set_id, field):
    return f"sets/{set_id}/{field}"


def all_profile_ids(controller):
    return controller._normalize_ids(controller._as_list(controller.master_settings.value("profile_ids", [])))


def next_profile_id(controller, existing_ids=None):
    if existing_ids is None:
        existing_ids = controller._all_profile_ids()
    max_id = 0
    for pid in existing_ids:
        try:
            max_id = max(max_id, int(str(pid)))
        except Exception:
            continue
    return str(max_id + 1)


def next_set_id(controller):
    max_id = 0
    for sid in controller._set_order:
        try:
            max_id = max(max_id, int(str(sid)))
        except Exception:
            continue
    return str(max_id + 1)


def default_set_name(controller):
    used = {str(data.get("name", "")).strip() for data in controller._set_defs.values()}
    idx = 1
    while True:
        candidate = f"세트{idx}"
        if candidate not in used:
            return candidate
        idx += 1


def profile_run_enabled(_controller, pid):
    spid = str(pid)
    raw = QSettings("MyHomeApp", f"Profile_{spid}").value("run_enabled", None)
    if raw is None:
        return True
    return _as_bool(raw, True)


def set_profile_run_enabled(_controller, pid, enabled):
    spid = str(pid)
    settings = QSettings("MyHomeApp", f"Profile_{spid}")
    settings.setValue("run_enabled", bool(enabled))
    settings.sync()


def clone_profile_settings(_controller, src_pid, dst_pid):
    src = QSettings("MyHomeApp", f"Profile_{src_pid}")
    dst = QSettings("MyHomeApp", f"Profile_{dst_pid}")
    dst.clear()
    for key in src.allKeys():
        dst.setValue(key, src.value(key))
    if dst.value("run_enabled", None) is None:
        dst.setValue("run_enabled", True)
    dst.sync()


def set_current_set_id(controller, set_id, persist=True, refresh=True):
    sid = str(set_id)
    if sid not in controller._set_defs:
        sid = controller._set_order[0] if controller._set_order else ""
    controller._current_set_id = sid
    if persist and sid:
        controller.master_settings.setValue("current_set_id", sid)
        _sync_master_settings(controller)
    if refresh:
        controller._refresh_set_ui()


def selected_set_id(controller):
    return str(controller._current_set_id) if controller._current_set_id else ""


def get_set_items(controller):
    items = []
    for sid in controller._set_order:
        data = controller._set_defs.get(str(sid), {})
        items.append((str(sid), str(data.get("name", f"세트{sid}")), len(data.get("profiles", []))))
    return items


def load_set_state(controller):
    profile_ids = controller._all_profile_ids()
    raw_set_ids = controller._normalize_ids(controller._as_list(controller.master_settings.value("set_ids", [])))
    if bool(getattr(controller, "_fast_startup_mode", False)) and _as_bool(
        os.environ.get("MYCANVAS_MIN_VALIDATION", "1"),
        True,
    ):
        if not raw_set_ids:
            raw_set_ids = ["1"]
        profile_set = set(profile_ids)
        set_defs = {}
        for sid in raw_set_ids:
            name_raw = controller.master_settings.value(controller._set_key(sid, "name"), f"세트{sid}")
            name = str(name_raw).strip() or f"세트{sid}"
            raw_profiles = controller._normalize_ids(
                controller._as_list(controller.master_settings.value(controller._set_key(sid, "profiles"), []))
            )
            if profile_set:
                raw_profiles = [pid for pid in raw_profiles if pid in profile_set]
            set_defs[sid] = {"name": name, "profiles": raw_profiles}
        if not set_defs:
            set_defs = {"1": {"name": "세트1", "profiles": list(profile_ids)}}
            raw_set_ids = ["1"]
        current_sid = str(controller.master_settings.value("current_set_id", raw_set_ids[0]))
        if current_sid not in set_defs:
            current_sid = raw_set_ids[0]
        if not controller.master_settings.contains("applied_set_id"):
            applied_sid = current_sid
        else:
            raw_applied = controller.master_settings.value("applied_set_id", "")
            if raw_applied in (None, ""):
                applied_sid = ""
            else:
                applied_sid = str(raw_applied)
                if applied_sid not in set_defs:
                    applied_sid = ""
        controller._set_order = list(raw_set_ids)
        controller._set_defs = set_defs
        controller._current_set_id = current_sid
        controller._applied_set_id = applied_sid
        return
    changed = False

    if not raw_set_ids:
        raw_set_ids = ["1"]
        controller.master_settings.setValue("set_ids", raw_set_ids)
        controller.master_settings.setValue(controller._set_key("1", "name"), "세트1")
        controller.master_settings.setValue(controller._set_key("1", "profiles"), list(profile_ids))
        changed = True

    set_defs = {}
    assigned_profiles = set()
    for sid in raw_set_ids:
        name_raw = controller.master_settings.value(controller._set_key(sid, "name"), f"세트{sid}")
        name = str(name_raw).strip() or f"세트{sid}"
        raw_profiles = controller._normalize_ids(
            controller._as_list(controller.master_settings.value(controller._set_key(sid, "profiles"), []))
        )
        clean_profiles = []
        for pid in raw_profiles:
            if pid not in profile_ids:
                changed = True
                continue
            if pid in assigned_profiles:
                changed = True
                continue
            assigned_profiles.add(pid)
            clean_profiles.append(pid)
        if raw_profiles != clean_profiles:
            controller.master_settings.setValue(controller._set_key(sid, "profiles"), clean_profiles)
            changed = True
        if str(name_raw) != name:
            controller.master_settings.setValue(controller._set_key(sid, "name"), name)
            changed = True
        set_defs[sid] = {"name": name, "profiles": clean_profiles}

    if not set_defs:
        raw_set_ids = ["1"]
        set_defs = {"1": {"name": "세트1", "profiles": list(profile_ids)}}
        controller.master_settings.setValue("set_ids", raw_set_ids)
        controller.master_settings.setValue(controller._set_key("1", "name"), "세트1")
        controller.master_settings.setValue(controller._set_key("1", "profiles"), list(profile_ids))
        changed = True

    current_sid = str(controller.master_settings.value("current_set_id", raw_set_ids[0]))
    if current_sid not in set_defs:
        current_sid = raw_set_ids[0]
        controller.master_settings.setValue("current_set_id", current_sid)
        changed = True

    # Backward-compat: if profile_ids contains entries that are not referenced by
    # any set, attach them to the currently selected set so they remain operable.
    unassigned_profiles = [pid for pid in profile_ids if pid not in assigned_profiles]
    if unassigned_profiles:
        attach_sid = current_sid if current_sid in set_defs else (raw_set_ids[0] if raw_set_ids else "")
        if attach_sid:
            existing_profiles = list(set_defs.get(attach_sid, {}).get("profiles", []))
            merged_profiles = existing_profiles + [pid for pid in unassigned_profiles if pid not in existing_profiles]
            if merged_profiles != existing_profiles:
                set_defs.setdefault(attach_sid, {"name": f"세트{attach_sid}", "profiles": []})
                set_defs[attach_sid]["profiles"] = merged_profiles
                controller.master_settings.setValue(controller._set_key(attach_sid, "profiles"), merged_profiles)
                changed = True

    controller._set_order = list(raw_set_ids)
    controller._set_defs = set_defs
    controller._current_set_id = current_sid
    if not controller.master_settings.contains("applied_set_id"):
        applied_sid = current_sid
        controller.master_settings.setValue("applied_set_id", applied_sid)
        changed = True
    else:
        raw_applied = controller.master_settings.value("applied_set_id", "")
        if raw_applied in (None, ""):
            applied_sid = ""
        else:
            applied_sid = str(raw_applied)
            if applied_sid not in set_defs:
                applied_sid = ""
                controller.master_settings.setValue("applied_set_id", "")
                changed = True
    controller._applied_set_id = applied_sid
    if changed:
        _sync_master_settings(controller)


def migrate_profile_run_flags(controller):
    if bool(getattr(controller, "_fast_startup_mode", False)) and _as_bool(
        os.environ.get("MYCANVAS_MIN_VALIDATION", "1"),
        True,
    ):
        return
    marker_key = "run_flag_migrated_v1"
    if _as_bool(controller.master_settings.value(marker_key, False), False):
        return
    profile_ids = controller._all_profile_ids()
    legacy_raw = controller.master_settings.value("active_profiles", None)
    has_legacy = legacy_raw is not None
    legacy_active = set(controller._as_list(legacy_raw)) if has_legacy else set()
    for pid in profile_ids:
        settings = QSettings("MyHomeApp", f"Profile_{pid}")
        if settings.value("run_enabled", None) is None:
            should_run = (pid in legacy_active) if has_legacy else True
            settings.setValue("run_enabled", bool(should_run))
    controller.master_settings.setValue(marker_key, True)
    _sync_master_settings(controller)


def current_set_profiles(controller):
    sid = controller.selected_set_id()
    data = controller._set_defs.get(sid, {})
    return list(data.get("profiles", []))


def set_current_profiles(controller, profile_ids):
    sid = controller.selected_set_id()
    if not sid or sid not in controller._set_defs:
        return
    clean_profiles = controller._normalize_ids(profile_ids)
    controller._set_defs[sid]["profiles"] = clean_profiles
    controller.master_settings.setValue(controller._set_key(sid, "profiles"), clean_profiles)
    _sync_master_settings(controller)


def remove_profile_from_sets(controller, profile_id):
    spid = str(profile_id)
    changed = False
    for sid in controller._set_order:
        data = controller._set_defs.get(sid, {})
        profiles = [pid for pid in data.get("profiles", []) if pid != spid]
        if profiles != data.get("profiles", []):
            data["profiles"] = profiles
            controller._set_defs[sid] = data
            controller.master_settings.setValue(controller._set_key(sid, "profiles"), profiles)
            changed = True
    if changed:
        _sync_master_settings(controller)


def cleanup_orphan_profiles(controller):
    referenced = set()
    for data in controller._set_defs.values():
        for pid in data.get("profiles", []):
            referenced.add(str(pid))

    profile_ids = controller._all_profile_ids()
    orphan_ids = [pid for pid in profile_ids if pid not in referenced]
    if not orphan_ids:
        return 0

    for pid in orphan_ids:
        profile_settings = QSettings("MyHomeApp", f"Profile_{pid}")
        profile_settings.clear()
        profile_settings.sync()

    kept_profile_ids = [pid for pid in profile_ids if pid in referenced]
    controller.master_settings.setValue("profile_ids", kept_profile_ids)
    active_ids = controller._as_list(controller.master_settings.value("active_profiles", []))
    controller.master_settings.setValue(
        "active_profiles",
        [pid for pid in active_ids if pid in referenced],
    )
    _sync_master_settings(controller)
    return len(orphan_ids)


def create_empty_set(controller, name):
    clean_name = str(name).strip()
    if not clean_name:
        return ""
    sid = controller._next_set_id()
    controller._set_order.append(sid)
    controller._set_defs[sid] = {"name": clean_name, "profiles": []}
    controller.master_settings.setValue("set_ids", list(controller._set_order))
    controller.master_settings.setValue(controller._set_key(sid, "name"), clean_name)
    controller.master_settings.setValue(controller._set_key(sid, "profiles"), [])
    _sync_master_settings(controller)
    return sid


def copy_set(controller, source_set_id, new_name):
    source_sid = str(source_set_id)
    if source_sid not in controller._set_defs:
        return ""
    clean_name = str(new_name).strip()
    if not clean_name:
        return ""

    profile_ids = controller._all_profile_ids()
    profile_id_set = set(profile_ids)
    next_profile_num = 0
    for pid in profile_ids:
        try:
            next_profile_num = max(next_profile_num, int(pid))
        except Exception:
            continue

    copied_profiles = []
    for src_pid in controller._set_defs[source_sid].get("profiles", []):
        next_profile_num += 1
        while str(next_profile_num) in profile_id_set:
            next_profile_num += 1
        new_pid = str(next_profile_num)
        controller._clone_profile_settings(src_pid, new_pid)
        profile_ids.append(new_pid)
        profile_id_set.add(new_pid)
        copied_profiles.append(new_pid)

    sid = controller._next_set_id()
    controller._set_order.append(sid)
    controller._set_defs[sid] = {"name": clean_name, "profiles": copied_profiles}
    controller.master_settings.setValue("profile_ids", profile_ids)
    controller.master_settings.setValue("set_ids", list(controller._set_order))
    controller.master_settings.setValue(controller._set_key(sid, "name"), clean_name)
    controller.master_settings.setValue(controller._set_key(sid, "profiles"), copied_profiles)
    _sync_master_settings(controller)
    return sid


def copy_profiles_from_set(controller, source_set_id, target_set_id):
    source_sid = str(source_set_id)
    target_sid = str(target_set_id)
    if source_sid not in controller._set_defs or target_sid not in controller._set_defs:
        return False
    if source_sid == target_sid:
        return False

    profile_ids = controller._all_profile_ids()
    profile_id_set = set(profile_ids)
    next_profile_num = 0
    for pid in profile_ids:
        try:
            next_profile_num = max(next_profile_num, int(pid))
        except Exception:
            continue

    copied_profiles = []
    for src_pid in controller._set_defs[source_sid].get("profiles", []):
        next_profile_num += 1
        while str(next_profile_num) in profile_id_set:
            next_profile_num += 1
        new_pid = str(next_profile_num)
        controller._clone_profile_settings(src_pid, new_pid)
        profile_ids.append(new_pid)
        profile_id_set.add(new_pid)
        copied_profiles.append(new_pid)

    if not copied_profiles:
        return False

    target_profiles = list(controller._set_defs[target_sid].get("profiles", []))
    target_profiles = copied_profiles + target_profiles
    controller._set_defs[target_sid]["profiles"] = target_profiles

    controller.master_settings.setValue("profile_ids", profile_ids)
    controller.master_settings.setValue(controller._set_key(target_sid, "profiles"), target_profiles)
    _sync_master_settings(controller)
    controller._refresh_set_ui()
    return True


def rename_set(controller, set_id, new_name):
    sid = str(set_id)
    if sid not in controller._set_defs:
        return False
    clean_name = str(new_name).strip()
    if not clean_name:
        return False
    controller._set_defs[sid]["name"] = clean_name
    controller.master_settings.setValue(controller._set_key(sid, "name"), clean_name)
    _sync_master_settings(controller)
    controller._refresh_set_ui()
    return True


def delete_set(controller, set_id, parent=None):
    sid = str(set_id)
    if sid not in controller._set_defs:
        return False
    from PyQt6.QtWidgets import QWidget
    parent_window = parent if isinstance(parent, QWidget) else (controller if isinstance(controller, QWidget) else None)
    if len(controller._set_order) <= 1:
        QMessageBox.information(parent_window, "세트 삭제", "최소 1개의 세트는 유지되어야 합니다.")
        return False

    set_name = str(controller._set_defs[sid].get("name", f"세트{sid}"))
    removed_profiles = [str(pid) for pid in controller._set_defs[sid].get("profiles", [])]
    remaining_set_ids = [str(x) for x in controller._set_order if str(x) != sid]
    if not remaining_set_ids:
        QMessageBox.information(parent_window, "세트 삭제", "최소 1개의 세트는 유지되어야 합니다.")
        return False
    absorb_target_sid = str(remaining_set_ids[0])
    absorb_target_name = str(controller._set_defs.get(absorb_target_sid, {}).get("name", f"세트{absorb_target_sid}"))

    delete_profiles = False
    if removed_profiles:
        choice_box = QMessageBox(parent_window)
        choice_box.setWindowModality(Qt.WindowModality.ApplicationModal)
        choice_box.setWindowTitle("세트 삭제")
        choice_box.setIcon(QMessageBox.Icon.Warning)
        choice_box.setText(f"'{set_name}' 세트를 삭제합니다.")
        choice_box.setInformativeText(
            f"포함된 프로필 {len(removed_profiles)}개 처리 방식을 선택하세요.\n"
            f"- 흡수: '{absorb_target_name}'(첫번째 세트)로 이동\n"
            f"- 삭제: 프로필도 함께 완전 삭제"
        )
        choice_box.setStyleSheet("""
            QMessageBox {
                background-color: #1e2d42;
            }
            QMessageBox QLabel {
                color: #e6eefc;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                min-height: 32px;
                min-width: 110px;
                border-radius: 8px;
                padding: 4px 14px;
                color: #e8efff;
                background-color: #35507a;
                border: 1px solid #5977a4;
                font-weight: 600;
                font-size: 12px;
            }
            QMessageBox QPushButton:hover {
                background-color: #446599;
            }
        """)
        absorb_btn = choice_box.addButton("첫번째 세트로 흡수", QMessageBox.ButtonRole.AcceptRole)
        purge_btn = choice_box.addButton("프로필도 함께 삭제", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = choice_box.addButton("취소", QMessageBox.ButtonRole.RejectRole)
        purge_btn.setStyleSheet("""
            QPushButton {
                background-color: #7a3945;
                border: 1px solid #9e4e5c;
                color: #ffe4e9;
            }
            QPushButton:hover {
                background-color: #8f4453;
            }
        """)
        choice_box.setDefaultButton(absorb_btn)
        from mywidgetbox_core import apply_windows_dark_title_bar
        QTimer.singleShot(0, lambda: apply_windows_dark_title_bar(choice_box))
        choice_box.exec()
        clicked = choice_box.clickedButton()
        if clicked is None or clicked is cancel_btn:
            return False
        delete_profiles = (clicked is purge_btn)
    else:
        from mywidgetbox_core import ask_dark_confirm
        if not ask_dark_confirm(
            parent_window,
            "세트 삭제",
            f"'{set_name}' 세트를 완전히 삭제하시겠습니까?",
            yes_text="삭제",
            no_text="취소",
            is_danger=True,
        ):
            return False

    if delete_profiles and removed_profiles:
        remove_ids = set([str(pid) for pid in removed_profiles])
        for pid in list(remove_ids):
            if pid in controller._temp_group_ids:
                controller._temp_group_ids.remove(pid)
            if pid in controller.widgets:
                widget = controller.widgets.get(pid)
                if widget is not None:
                    widget.close()
                    widget.deleteLater()
                controller.widgets.pop(pid, None)
            profile_settings = QSettings("MyHomeApp", f"Profile_{pid}")
            profile_settings.clear()
            profile_settings.sync()

        profile_ids = [pid for pid in controller._all_profile_ids() if str(pid) not in remove_ids]
        controller.master_settings.setValue("profile_ids", profile_ids)
        active_ids = controller._as_list(controller.master_settings.value("active_profiles", []))
        controller.master_settings.setValue(
            "active_profiles",
            [pid for pid in active_ids if str(pid) not in remove_ids],
        )
    elif removed_profiles:
        target_profiles = list(controller._set_defs.get(absorb_target_sid, {}).get("profiles", []))
        merged_profiles = target_profiles + [pid for pid in removed_profiles if pid not in target_profiles]
        if absorb_target_sid in controller._set_defs:
            controller._set_defs[absorb_target_sid]["profiles"] = merged_profiles
        controller.master_settings.setValue(controller._set_key(absorb_target_sid, "profiles"), merged_profiles)

    controller.master_settings.remove(f"sets/{sid}")
    controller._set_defs.pop(sid, None)
    controller._set_order = [x for x in controller._set_order if str(x) != sid]
    controller.master_settings.setValue("set_ids", list(controller._set_order))
    _sync_master_settings(controller)

    selected_sid = controller.selected_set_id()
    was_applied = (str(getattr(controller, "_applied_set_id", "")) == sid)

    if selected_sid == sid:
        fallback_sid = absorb_target_sid if absorb_target_sid in controller._set_defs else (controller._set_order[0] if controller._set_order else "")
        controller._set_current_set_id(fallback_sid, persist=True, refresh=False)

    if was_applied:
        # Request 2: 세트 삭제 시 첫번째 세트를 무조건 적용하는 게 아니라 세트가 적용되지 않은 상태 유지
        if hasattr(controller, "stop_applied_set"):
            controller.stop_applied_set(suppress_refresh=True)
        else:
            controller._cancel_startup_queue()
            controller._stop_all_widgets_bulk()
            controller._applied_set_id = ""
            controller.master_settings.setValue("applied_set_id", "")
            _sync_master_settings(controller, immediate=True)

    controller._sync_temp_group_badges()
    controller.update_active_status()
    controller.load_profiles(force_rebuild=True)
    return True


def on_profile_order_changed(controller, ordered_ids):
    sid = controller.selected_set_id()
    if not sid or sid not in controller._set_defs:
        return
    current = list(controller._set_defs[sid].get("profiles", []))
    if not current:
        return
    current_set = set(current)
    ordered = [pid for pid in controller._normalize_ids(ordered_ids) if pid in current_set]
    if len(ordered) != len(current):
        for pid in current:
            if pid not in ordered:
                ordered.append(pid)
    if ordered == current:
        return
    controller._set_defs[sid]["profiles"] = ordered
    controller.master_settings.setValue(controller._set_key(sid, "profiles"), ordered)
    _sync_master_settings(controller)
    controller.load_profiles()

def apply_set(controller, set_id):
    sid = str(set_id)
    if sid not in controller._set_defs:
        return

    controller._cancel_startup_queue()
    previous_applied_sid = str(getattr(controller, "_applied_set_id", "") or "")
    controller._set_current_set_id(sid, persist=False)
    controller.clear_all_highlights()
    controller.clear_temp_group(silent=True)
    target_profiles = [
        str(pid) for pid in controller._set_defs.get(sid, {}).get("profiles", []) if controller._profile_run_enabled(pid)
    ]
    current_running = {str(pid) for pid in controller.widgets.keys()}
    startup_entries = []

    use_fast_switch = bool(controller._fast_set_switch_enabled()) and sid != previous_applied_sid
    if use_fast_switch:
        target_set = set(target_profiles)
        keep_ids = current_running.intersection(target_set)
        stop_ids = current_running.difference(target_set)
        controller._stop_widgets_bulk(stop_ids)
        start_ids = [pid for pid in target_profiles if pid not in keep_ids]
        startup_entries = controller._build_profile_startup_queue(start_ids)
    else:
        controller._stop_all_widgets_bulk()
        startup_entries = controller._build_set_startup_queue(sid)

    controller._applied_set_id = sid
    controller.master_settings.setValue("current_set_id", sid)
    controller.master_settings.setValue("applied_set_id", sid)
    if not (bool(getattr(controller, "_fast_startup_mode", False)) and bool(controller._minimal_validation_enabled())):
        _sync_master_settings(controller)
    controller._refresh_set_ui()
    controller.load_profiles(force_rebuild=True)
    controller._begin_startup_queue(startup_entries, mode="set_switch")


def sort_profiles_by_screen_pos(controller, set_id):
    """
    세트 내 위젯들의 순서를 화면에 보이는 위치(좌상단 -> 우하단) 순서로 재정렬.
    세로(y) 좌표를 25px 단위로 구간화하여 같은 행의 위젯들은 왼쪽(x)부터 오른쪽 순으로 정렬.
    """
    sid = str(set_id)
    if sid not in controller._set_defs:
        return False
    profiles = list(controller._set_defs[sid].get("profiles", []))
    if len(profiles) <= 1:
        return False

    def get_pos(pid):
        spid = str(pid)
        w = controller.widgets.get(spid)
        if w is not None and hasattr(w, "x") and hasattr(w, "y"):
            return (w.y(), w.x())
        from PyQt6.QtCore import QSettings
        cfg = QSettings("MyHomeApp", f"Profile_{spid}")
        try:
            x = int(cfg.value("x", 100))
            y = int(cfg.value("y", 100))
        except Exception:
            x, y = 100, 100
        return (y, x)

    sorted_profiles = sorted(
        profiles,
        key=lambda pid: (round(get_pos(pid)[0] / 25), get_pos(pid)[1], get_pos(pid)[0], str(pid))
    )
    if sorted_profiles == profiles:
        return False

    controller._set_defs[sid]["profiles"] = sorted_profiles
    controller.master_settings.setValue(controller._set_key(sid, "profiles"), sorted_profiles)
    _sync_master_settings(controller)
    controller.load_profiles(force_rebuild=True)
    if hasattr(controller, "sync_set_z_order"):
        controller.sync_set_z_order(sid)
    return True


def clear_set_video_cache(controller, set_id):
    """
    지정한 세트에 속한 위젯들의 영상 프록시 캐시 파일을 찾아 삭제하고 (삭제 파일수, 삭제 용량바이트)를 반환.
    """
    import os, hashlib
    from PyQt6.QtCore import QSettings
    sid = str(set_id)
    if sid not in controller._set_defs:
        return 0, 0
    pids = list(controller._set_defs[sid].get("profiles", []))
    if not pids:
        return 0, 0

    base = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if not base:
        base = os.path.expanduser("~")
    cache_dir = os.path.join(base, "MyHomeApp", "video_proxy_cache")
    if not os.path.isdir(cache_dir):
        return 0, 0

    video_paths = set()
    for pid in pids:
        cfg = QSettings("MyHomeApp", f"Profile_{pid}")
        img_path = str(cfg.value("image_path", "") or "").strip()
        if img_path:
            video_paths.add(img_path)
        slide_items = cfg.value("slide_items", [])
        if isinstance(slide_items, list):
            for it in slide_items:
                if isinstance(it, dict) and "path" in it:
                    video_paths.add(str(it["path"]).strip())

    tokens = set()
    for vp in video_paths:
        if not vp:
            continue
        try:
            st = os.stat(vp)
            sig = f"{os.path.abspath(vp)}|{int(st.st_size)}|{int(st.st_mtime_ns)}"
        except Exception:
            sig = os.path.abspath(vp)
        for h in (360, 540, 720, 1080):
            tok = hashlib.sha1(f"{sig}|{h}".encode("utf-8", "ignore")).hexdigest()[:24]
            tokens.add(tok)

    removed_files = 0
    removed_bytes = 0
    for root, _dirs, files in os.walk(cache_dir):
        for fname in files:
            matches = any(fname.startswith(tok) for tok in tokens)
            if matches:
                fp = os.path.join(root, fname)
                try:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    removed_files += 1
                    removed_bytes += sz
                except Exception:
                    pass

    return removed_files, removed_bytes
