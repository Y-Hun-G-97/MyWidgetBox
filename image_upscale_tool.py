import os
import shutil
import subprocess
import sys


class ToolExecutionError(RuntimeError):
    pass


def _runtime_binary_dirs():
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
    try:
        cwd = os.getcwd()
        if cwd:
            dirs.append(cwd)
    except Exception:
        pass
    out = []
    seen = set()
    for raw in dirs:
        key = os.path.normcase(os.path.normpath(str(raw)))
        if key in seen:
            continue
        seen.add(key)
        out.append(str(raw))
    return out


def find_ffmpeg_binary():
    env_candidates = [
        str(os.environ.get("IMAGE_UPSCALE_FFMPEG", "") or "").strip(),
        str(os.environ.get("MYWIDGET_FFMPEG", "") or "").strip(),
    ]
    for path in env_candidates:
        if path and os.path.isfile(path):
            return path

    names = ["ffmpeg.exe", "ffmpeg"] if os.name == "nt" else ["ffmpeg"]
    for folder in _runtime_binary_dirs():
        for name in names:
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate):
                return candidate

    fallback = str(shutil.which("ffmpeg") or "").strip()
    if fallback and os.path.isfile(fallback):
        return fallback
    return ""


def _run_command(cmd):
    run_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name == "nt":
        flags = 0
        try:
            flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        try:
            flags |= int(getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
        except Exception:
            pass
        if flags:
            run_kwargs["creationflags"] = int(flags)
    proc = subprocess.run(cmd, **run_kwargs)
    if int(proc.returncode) != 0:
        msg = str(proc.stderr or proc.stdout or "").strip()
        if not msg:
            msg = f"ffmpeg failed (exit code: {proc.returncode})"
        raise ToolExecutionError(msg)
    return proc


def _require_input_image(path):
    src = str(path or "").strip()
    if not src:
        raise ToolExecutionError("Input image path is empty.")
    if not os.path.isfile(src):
        raise ToolExecutionError(f"Input file not found: {src}")
    return os.path.abspath(src)


def _require_output_path(path):
    out = str(path or "").strip()
    if not out:
        raise ToolExecutionError("Output path is empty.")
    abs_out = os.path.abspath(out)
    parent = os.path.dirname(abs_out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return abs_out


def _ensure_ffmpeg_path(ffmpeg_path):
    cand = str(ffmpeg_path or "").strip()
    if cand and os.path.isfile(cand):
        return cand
    found = find_ffmpeg_binary()
    if found:
        return found
    raise ToolExecutionError(
        "ffmpeg not found. Put ffmpeg.exe next to MyCanvas.exe or set PATH."
    )


def upscale_image_file(input_path, output_path, scale=2.0, sharpen=True, ffmpeg_path=""):
    src = _require_input_image(input_path)
    dst = _require_output_path(output_path)
    if os.path.normcase(os.path.normpath(src)) == os.path.normcase(os.path.normpath(dst)):
        raise ToolExecutionError("Input and output file are identical.")

    try:
        scale_val = float(scale)
    except Exception:
        scale_val = 2.0
    scale_val = max(1.1, min(8.0, scale_val))
    ffmpeg = _ensure_ffmpeg_path(ffmpeg_path)

    vf_parts = [f"scale=ceil(iw*{scale_val:.6f}):ceil(ih*{scale_val:.6f}):flags=lanczos"]
    if bool(sharpen):
        vf_parts.append("unsharp=5:5:0.8:3:3:0.4")
    vf = ",".join(vf_parts)

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        src,
        "-vf",
        vf,
        "-frames:v",
        "1",
        dst,
    ]
    _run_command(cmd)
    if not os.path.isfile(dst):
        raise ToolExecutionError("Upscaled output file was not created.")
    return {
        "output_path": dst,
        "ffmpeg_path": ffmpeg,
        "scale": scale_val,
    }
