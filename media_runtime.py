# Consolidated media/runtime helpers
import os
import sys


def runtime_binary_dirs(include_cwd=False, include_bin_subdir=True):
    dirs = []
    try:
        meipass = str(getattr(sys, "_MEIPASS", "") or "").strip()
        if meipass:
            dirs.append(meipass)
    except Exception:
        pass
    try:
        exe_path = str(getattr(sys, "executable", "") or "").strip()
        if exe_path:
            exe_dir = os.path.dirname(os.path.abspath(exe_path))
            if exe_dir:
                dirs.append(exe_dir)
    except Exception:
        pass
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir:
            dirs.append(script_dir)
    except Exception:
        pass
    if bool(include_cwd):
        try:
            cwd = os.getcwd()
            if cwd:
                dirs.append(cwd)
        except Exception:
            pass

    out = []
    seen = set()
    for raw in dirs:
        base = str(raw or "").strip()
        if not base:
            continue
        candidates = [base]
        if bool(include_bin_subdir):
            candidates.append(os.path.join(base, "bin"))
        for candidate in candidates:
            key = os.path.normcase(os.path.normpath(str(candidate)))
            if key in seen:
                continue
            seen.add(key)
            out.append(str(candidate))
    return out


def find_runtime_binary(name, include_cwd=False, include_bin_subdir=True):
    raw = str(name or "").strip()
    if not raw:
        return ""
    names = [raw]
    if os.name == "nt" and not raw.lower().endswith(".exe"):
        names.insert(0, f"{raw}.exe")
    for folder in runtime_binary_dirs(
        include_cwd=bool(include_cwd),
        include_bin_subdir=bool(include_bin_subdir),
    ):
        for fname in names:
            candidate = os.path.join(folder, fname)
            try:
                if os.path.isfile(candidate):
                    return candidate
            except Exception:
                continue
    return ""

import os
import subprocess


def find_ffprobe_beside_ffmpeg(ffmpeg_path):
    ffmpeg = str(ffmpeg_path or "").strip()
    if not ffmpeg:
        return ""
    probe_names = ["ffprobe.exe"] if os.name == "nt" else ["ffprobe"]
    for probe_name in probe_names:
        candidate = os.path.join(os.path.dirname(ffmpeg), probe_name)
        if os.path.exists(candidate):
            return candidate
    return ""


def probe_video_height(ffprobe_path, media_path, timeout_sec=3.0):
    ffprobe = str(ffprobe_path or "").strip()
    if not ffprobe:
        return 0
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=height",
        "-of",
        "csv=p=0",
        str(media_path),
    ]
    try:
        run_kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": float(timeout_sec),
            "check": False,
        }
        if os.name == "nt":
            flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if flags:
                run_kwargs["creationflags"] = int(flags)
        proc = subprocess.run(cmd, **run_kwargs)
        if int(proc.returncode) != 0:
            return 0
        out = str(proc.stdout or "").strip()
        if out.isdigit():
            return int(out)
    except Exception:
        return 0
    return 0

import os


def scan_media_paths(folder, media_extensions):
    media_ext = tuple(media_extensions or ())
    if not media_ext:
        return []
    try:
        files = os.listdir(folder)
    except OSError:
        return []
    entries = []
    for name in sorted(files):
        path = os.path.join(folder, str(name))
        low = str(name).lower()
        if low.endswith(media_ext):
            entries.append(path)
    return entries

import os
import subprocess
import threading


class VideoProxyService:
    def __init__(self, host):
        self._host = host

    def ensure_video_proxy_file(self, source_path, target_height, allow_build=True):
        host = self._host
        out_path = host._video_proxy_output_path(source_path, target_height)
        if not out_path:
            return ""
        try:
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return out_path
        except Exception:
            pass
        if not bool(allow_build):
            return ""
        key = host._video_proxy_key(source_path, target_height)
        if not key:
            return ""
        failed = getattr(host, "_video_proxy_failed_keys", set())
        if key in failed:
            return ""
        ffmpeg = host._resolve_ffmpeg_path()
        if not ffmpeg:
            failed.add(key)
            host._video_proxy_failed_keys = failed
            return ""
        out_dir = os.path.dirname(out_path)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            failed.add(key)
            host._video_proxy_failed_keys = failed
            return ""
        temp_out = out_path + ".tmp.mp4"
        try:
            if os.path.exists(temp_out):
                os.remove(temp_out)
        except Exception:
            pass
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-vf",
            f"scale=-2:{int(target_height)}:flags=lanczos",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(temp_out),
        ]
        ok = False
        try:
            run_kwargs = {
                "capture_output": True,
                "text": True,
                "timeout": 180.0,
                "check": False,
            }
            if os.name == "nt":
                flags = 0
                flags |= int(getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
                flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if flags:
                    run_kwargs["creationflags"] = int(flags)
            proc = subprocess.run(cmd, **run_kwargs)
            ok = int(proc.returncode) == 0
        except Exception:
            ok = False
        if ok:
            try:
                if os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
                    os.replace(temp_out, out_path)
                    host._video_dbg(
                        "proxy_built",
                        source=host._debug_media_name(source_path),
                        target=f"{int(target_height)}p",
                    )
                    return out_path
            except Exception:
                ok = False
        try:
            if os.path.exists(temp_out):
                os.remove(temp_out)
        except Exception:
            pass
        failed.add(key)
        host._video_proxy_failed_keys = failed
        host._video_dbg(
            "proxy_failed",
            source=host._debug_media_name(source_path),
            target=f"{int(target_height)}p",
        )
        return ""

    def enqueue_video_proxy_build(self, source_path, target_height):
        host = self._host
        src = str(source_path or "")
        h = int(target_height or 0)
        if not src or h <= 0:
            return False
        key = host._video_proxy_key(src, h)
        if not key:
            return False
        out_path = host._video_proxy_output_path(src, h)
        if out_path:
            try:
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    return False
            except Exception:
                pass
        failed = getattr(host, "_video_proxy_failed_keys", set())
        if key in failed:
            return False
        start_worker = False
        with host._video_proxy_build_lock:
            if key in host._video_proxy_building_keys:
                return False
            host._video_proxy_building_keys.add(key)
            host._video_proxy_build_queue.append((key, src, h))
            if not bool(getattr(host, "_video_proxy_build_worker_running", False)):
                host._video_proxy_build_worker_running = True
                start_worker = True
        host._video_dbg(
            "proxy_queue",
            source=host._debug_media_name(src),
            target=f"{int(h)}p",
        )
        if start_worker:
            t = threading.Thread(target=self.video_proxy_build_worker, daemon=True)
            t.start()
        return True

    def video_proxy_build_worker(self):
        host = self._host
        while True:
            with host._video_proxy_build_lock:
                if not host._video_proxy_build_queue:
                    host._video_proxy_build_worker_running = False
                    return
                key, src, h = host._video_proxy_build_queue.popleft()
            try:
                self.ensure_video_proxy_file(src, h, allow_build=True)
            except Exception:
                pass
            finally:
                with host._video_proxy_build_lock:
                    host._video_proxy_building_keys.discard(key)
