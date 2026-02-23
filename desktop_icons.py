# Consolidated desktop icon components
import ctypes

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class DesktopIconCloneOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._items = []
        self._font = self._resolve_icon_title_font()
        self._flags = int(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
            | Qt.TextFlag.TextDontClip
        )

    @staticmethod
    def _resolve_icon_title_font():
        try:
            class LOGFONTW(ctypes.Structure):
                _fields_ = [
                    ("lfHeight", ctypes.c_long),
                    ("lfWidth", ctypes.c_long),
                    ("lfEscapement", ctypes.c_long),
                    ("lfOrientation", ctypes.c_long),
                    ("lfWeight", ctypes.c_long),
                    ("lfItalic", ctypes.c_ubyte),
                    ("lfUnderline", ctypes.c_ubyte),
                    ("lfStrikeOut", ctypes.c_ubyte),
                    ("lfCharSet", ctypes.c_ubyte),
                    ("lfOutPrecision", ctypes.c_ubyte),
                    ("lfClipPrecision", ctypes.c_ubyte),
                    ("lfQuality", ctypes.c_ubyte),
                    ("lfPitchAndFamily", ctypes.c_ubyte),
                    ("lfFaceName", ctypes.c_wchar * 32),
                ]

            spi_geticontitlelogfont = 0x001F
            lf = LOGFONTW()
            ok = ctypes.windll.user32.SystemParametersInfoW(
                int(spi_geticontitlelogfont),
                int(ctypes.sizeof(LOGFONTW)),
                ctypes.byref(lf),
                0,
            )
            if ok:
                face = str(lf.lfFaceName or "").strip() or "Segoe UI"
                font = QFont(face)
                h = int(abs(int(lf.lfHeight or 0)))
                if h > 0:
                    font.setPixelSize(h)
                weight = int(lf.lfWeight or 400)
                if weight >= 600:
                    font.setBold(True)
                font.setItalic(bool(lf.lfItalic))
                return font
        except Exception:
            pass
        return QFont("Segoe UI", 9)

    def set_items(self, items):
        self._items = list(items or [])
        self.update()

    def _elided_icon_label_text(self, text, label_rect, selected=False, focused=False):
        raw = str(text or "")
        if not raw:
            return ""
        # Explorer-like behavior: idle desktop labels are visually constrained and elided.
        if bool(selected) or bool(focused):
            return raw
        if not isinstance(label_rect, QRect):
            return raw
        max_width = max(10, int(label_rect.width()))
        max_height = max(10, int(label_rect.height()))
        fm = QFontMetrics(self._font)
        line_h = max(1, int(fm.lineSpacing()))
        max_lines = max(1, min(2, int(max_height // line_h)))
        src = raw.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        if max_lines <= 1:
            return str(fm.elidedText(src, Qt.TextElideMode.ElideRight, int(max_width)))
        if fm.horizontalAdvance(src) <= int(max_width):
            return src

        lines = []
        remaining = str(src)
        for i in range(int(max_lines)):
            if not remaining:
                break
            is_last = i == int(max_lines - 1)
            if is_last:
                lines.append(str(fm.elidedText(remaining, Qt.TextElideMode.ElideRight, int(max_width))))
                remaining = ""
                break
            if fm.horizontalAdvance(remaining) <= int(max_width):
                lines.append(str(remaining))
                remaining = ""
                break
            lo = 1
            hi = len(remaining)
            best = 1
            while lo <= hi:
                mid = (lo + hi) // 2
                chunk = remaining[:mid]
                if fm.horizontalAdvance(chunk) <= int(max_width):
                    best = int(mid)
                    lo = int(mid + 1)
                else:
                    hi = int(mid - 1)
            consume = max(1, int(best))
            # Prefer wrapping at whitespace so labels like "Google Chrome" break as
            # "Google" + "Chrome" instead of splitting inside a word.
            segment = str(remaining[:consume])
            space_pos = segment.rfind(" ")
            if space_pos > 0:
                consume = int(space_pos + 1)
                part = str(remaining[:space_pos]).rstrip()
            else:
                part = segment.rstrip()
            if not part:
                part = str(remaining[:max(1, consume)]).rstrip()
            lines.append(part if part else remaining[:1])
            remaining = str(remaining[max(1, consume):]).lstrip()

        if not lines:
            return str(fm.elidedText(src, Qt.TextElideMode.ElideRight, int(max_width)))
        return "\n".join([ln for ln in lines if ln])

    def paintEvent(self, event):
        if not self._items:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._font)
        for item in self._items:
            if not isinstance(item, dict):
                continue
            edit_rect = item.get("edit_rect")
            if isinstance(edit_rect, QRect):
                if int(edit_rect.width()) > 0 and int(edit_rect.height()) > 0:
                    painter.setPen(QPen(QColor(74, 130, 218, 230), 1))
                    painter.setBrush(QColor(255, 255, 255, 230))
                    painter.drawRoundedRect(QRectF(edit_rect), 2.0, 2.0)
                    txt = str(item.get("edit_text", "") or "")
                    if txt:
                        painter.setPen(QColor(18, 18, 18, 255))
                        painter.drawText(
                            QRect(
                                int(edit_rect.x()) + 4,
                                int(edit_rect.y()) + 1,
                                max(0, int(edit_rect.width()) - 6),
                                max(0, int(edit_rect.height()) - 2),
                            ),
                            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                            txt,
                        )
                continue

            selected = bool(item.get("selected", False))
            focused = bool(item.get("focused", False))
            select_rect = item.get("select_rect")
            if isinstance(select_rect, QRect) and int(select_rect.width()) > 0 and int(select_rect.height()) > 0:
                if selected:
                    painter.setPen(QPen(QColor(112, 170, 255, 230), 1))
                    painter.setBrush(QColor(64, 136, 255, 96))
                    painter.drawRoundedRect(QRectF(select_rect), 4.0, 4.0)
                elif focused:
                    painter.setPen(QPen(QColor(150, 192, 255, 170), 1, Qt.PenStyle.DotLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(QRectF(select_rect), 4.0, 4.0)

            icon_rect = item.get("icon_rect")
            icon_pm = item.get("icon_pixmap")
            if (
                isinstance(icon_rect, QRect)
                and isinstance(icon_pm, QPixmap)
                and not icon_pm.isNull()
                and int(icon_rect.width()) > 0
                and int(icon_rect.height()) > 0
            ):
                target = QRect(icon_rect)
                if int(target.width()) != int(icon_pm.width()) or int(target.height()) != int(icon_pm.height()):
                    target = QRect(
                        int(icon_rect.x() + ((int(icon_rect.width()) - int(icon_pm.width())) // 2)),
                        int(icon_rect.y() + ((int(icon_rect.height()) - int(icon_pm.height())) // 2)),
                        int(icon_pm.width()),
                        int(icon_pm.height()),
                    )
                painter.drawPixmap(target, icon_pm)

            label_rect = item.get("label_rect")
            text = str(item.get("text", "") or "")
            if isinstance(label_rect, QRect) and int(label_rect.width()) > 0 and int(label_rect.height()) > 0 and text:
                # Explorer label bounds are tight; expand slightly to avoid glyph clipping.
                draw_rect = QRect(label_rect).adjusted(-4, 0, 4, 2)
                display_text = self._elided_icon_label_text(
                    text,
                    draw_rect,
                    selected=bool(selected),
                    focused=bool(focused),
                )
                if not display_text:
                    continue
                shadow_rect = QRect(draw_rect).translated(1, 1)
                painter.setPen(QColor(0, 0, 0, 190))
                painter.drawText(shadow_rect, self._flags, display_text)
                painter.setPen(QColor(255, 255, 255, 255))
                painter.drawText(draw_rect, self._flags, display_text)

import os

from PyQt6.QtCore import QRect


def desktop_icon_render_signature_of_rects(rects):
    sig = []
    for entry in list(rects or []):
        if not isinstance(entry, dict):
            continue
        try:
            image_index = int(entry.get("image_index", -1))
        except Exception:
            image_index = -1
        icon_rect = entry.get("icon")
        if isinstance(icon_rect, QRect):
            rx = int(icon_rect.x())
            ry = int(icon_rect.y())
            rw = int(icon_rect.width())
            rh = int(icon_rect.height())
        else:
            rx = ry = rw = rh = 0
        shell_path = str(entry.get("shell_path", "") or "")
        path_mtime_ns = 0
        if shell_path:
            norm_path = str(os.path.normpath(shell_path))
            low = norm_path.lower()
            # Track file-icon resource changes without being noisy on folder content changes.
            if low.endswith((".lnk", ".url", ".exe", ".ico")):
                try:
                    path_mtime_ns = int(os.stat(norm_path).st_mtime_ns)
                except Exception:
                    path_mtime_ns = 0
        sig.append((int(image_index), int(rx), int(ry), int(rw), int(rh), int(path_mtime_ns)))
    return tuple(sig)


def is_recycle_caption(caption):
    key = str(caption or "").strip().lower()
    if not key:
        return False
    recycle_keys = {
        "recycle bin",
        "휴지통",
        "papelera de reciclaje",
        "corbeille",
        "cestino",
        "корзина",
        "kosz",
        "lixeira",
    }
    return bool(key in recycle_keys)

import ctypes
import os
from ctypes import wintypes

import win32gui
from PyQt6.QtCore import QRect


def query_desktop_icon_rects_screen(
    listview_hwnd,
    shell_items_by_name_func,
    shell_items_in_order_func,
):
    if not listview_hwnd:
        return [], {}
    lvm_first = 0x1000
    lvm_getitemcount = lvm_first + 4
    lvm_getitemrect = lvm_first + 14
    lvm_getitemtextw = lvm_first + 115
    lvm_getitemw = lvm_first + 75
    lvm_getitemstate = lvm_first + 44
    lvm_geteditcontrol = lvm_first + 24
    lvif_image = 0x00000002
    lvif_text = 0x00000001
    lvir_icon = 1
    lvir_label = 2
    lvir_selectbounds = 3
    lvis_selected = 0x0002
    lvis_focused = 0x0001
    try:
        count = int(win32gui.SendMessage(int(listview_hwnd), int(lvm_getitemcount), 0, 0) or 0)
    except Exception:
        count = 0
    if count <= 0:
        return [], {}

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class LVITEMW(ctypes.Structure):
        _fields_ = [
            ("mask", wintypes.UINT),
            ("iItem", ctypes.c_int),
            ("iSubItem", ctypes.c_int),
            ("state", wintypes.UINT),
            ("stateMask", wintypes.UINT),
            ("pszText", wintypes.LPWSTR),
            ("cchTextMax", ctypes.c_int),
            ("iImage", ctypes.c_int),
            ("lParam", wintypes.LPARAM),
            ("iIndent", ctypes.c_int),
            ("iGroupId", ctypes.c_int),
            ("cColumns", wintypes.UINT),
            ("puColumns", ctypes.POINTER(wintypes.UINT)),
            ("piColFmt", ctypes.POINTER(ctypes.c_int)),
            ("iGroup", ctypes.c_int),
        ]

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    try:
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.VirtualAllocEx.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            ctypes.c_size_t,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        kernel32.VirtualAllocEx.restype = wintypes.LPVOID
        kernel32.ReadProcessMemory.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.LPVOID,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        kernel32.ReadProcessMemory.restype = wintypes.BOOL
        kernel32.WriteProcessMemory.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.LPCVOID,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        kernel32.WriteProcessMemory.restype = wintypes.BOOL
        kernel32.VirtualFreeEx.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            ctypes.c_size_t,
            wintypes.DWORD,
        ]
        kernel32.VirtualFreeEx.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
    except Exception:
        pass

    pid = wintypes.DWORD(0)
    try:
        user32.GetWindowThreadProcessId(int(listview_hwnd), ctypes.byref(pid))
    except Exception:
        return [], {}
    if int(pid.value) <= 0:
        return [], {}

    process_access = int(0x0400 | 0x0010 | 0x0020 | 0x0008)  # QUERY | VM_READ | VM_WRITE | VM_OPERATION
    mem_commit_reserve = int(0x1000 | 0x2000)
    mem_release = int(0x8000)
    page_readwrite = int(0x04)
    proc = None
    remote_ptr = None
    layouts = []
    rect_size = int(ctypes.sizeof(RECT))
    lvitem_size = int(ctypes.sizeof(LVITEMW))
    text_cch = 280
    text_buf_size = int(text_cch * ctypes.sizeof(ctypes.c_wchar))
    align = 16
    rect_off = 0
    lvitem_off = int(((rect_size + (align - 1)) // align) * align)
    text_off = int(((lvitem_off + lvitem_size + (align - 1)) // align) * align)
    alloc_size = max(rect_size, int(text_off + text_buf_size))
    shell_items = shell_items_by_name_func(refresh=False)
    shell_items_order = shell_items_in_order_func(refresh=False)
    shell_name_seen = {}

    def _normalize_item_name(value):
        s = str(value or "").strip().lower()
        if not s:
            return ""
        return " ".join(s.split())

    def _names_similar(a, b):
        na = _normalize_item_name(a)
        nb = _normalize_item_name(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        sa = os.path.splitext(na)[0]
        sb = os.path.splitext(nb)[0]
        return bool(sa and sb and (sa == sb or sa == nb or sb == na))

    def _read_item_rect(item_index, rect_code, remote_rect):
        probe = RECT()
        probe.left = int(rect_code)
        probe.top = 0
        probe.right = 0
        probe.bottom = 0
        try:
            written = ctypes.c_size_t(0)
            ok_write = bool(
                kernel32.WriteProcessMemory(
                    proc,
                    ctypes.c_void_p(int(remote_rect)),
                    ctypes.byref(probe),
                    rect_size,
                    ctypes.byref(written),
                )
            )
        except Exception:
            ok_write = False
        if not ok_write:
            return None
        try:
            ok = int(
                win32gui.SendMessage(
                    int(listview_hwnd),
                    int(lvm_getitemrect),
                    int(item_index),
                    int(remote_rect),
                )
                or 0
            )
        except Exception:
            ok = 0
        if not ok:
            return None
        out = RECT()
        bytes_read = ctypes.c_size_t(0)
        try:
            copied = bool(
                kernel32.ReadProcessMemory(
                    proc,
                    ctypes.c_void_p(int(remote_rect)),
                    ctypes.byref(out),
                    rect_size,
                    ctypes.byref(bytes_read),
                )
            )
        except Exception:
            copied = False
        if not copied or int(bytes_read.value) < rect_size:
            return None
        return (int(out.left), int(out.top), int(out.right), int(out.bottom))

    def _read_item_image_index(item_index, remote_lvitem):
        item = LVITEMW()
        item.mask = int(lvif_image)
        item.iItem = int(item_index)
        item.iSubItem = 0
        item.iImage = -1
        try:
            written = ctypes.c_size_t(0)
            ok_write = bool(
                kernel32.WriteProcessMemory(
                    proc,
                    ctypes.c_void_p(int(remote_lvitem)),
                    ctypes.byref(item),
                    lvitem_size,
                    ctypes.byref(written),
                )
            )
        except Exception:
            ok_write = False
        if not ok_write:
            return -1
        try:
            ok = int(
                win32gui.SendMessage(
                    int(listview_hwnd),
                    int(lvm_getitemw),
                    0,
                    int(remote_lvitem),
                )
                or 0
            )
        except Exception:
            ok = 0
        if not ok:
            return -1
        out = LVITEMW()
        bytes_read = ctypes.c_size_t(0)
        try:
            copied = bool(
                kernel32.ReadProcessMemory(
                    proc,
                    ctypes.c_void_p(int(remote_lvitem)),
                    ctypes.byref(out),
                    lvitem_size,
                    ctypes.byref(bytes_read),
                )
            )
        except Exception:
            copied = False
        if not copied or int(bytes_read.value) < lvitem_size:
            return -1
        try:
            return int(out.iImage)
        except Exception:
            return -1

    def _read_item_text(item_index, remote_lvitem, remote_text):
        item = LVITEMW()
        item.mask = int(lvif_text)
        item.iItem = int(item_index)
        item.iSubItem = 0
        item.cchTextMax = int(text_cch)
        item.pszText = ctypes.cast(ctypes.c_void_p(int(remote_text)), wintypes.LPWSTR)
        try:
            written = ctypes.c_size_t(0)
            ok_write = bool(
                kernel32.WriteProcessMemory(
                    proc,
                    ctypes.c_void_p(int(remote_lvitem)),
                    ctypes.byref(item),
                    lvitem_size,
                    ctypes.byref(written),
                )
            )
        except Exception:
            ok_write = False
        if not ok_write:
            return ""
        try:
            win32gui.SendMessage(
                int(listview_hwnd),
                int(lvm_getitemtextw),
                int(item_index),
                int(remote_lvitem),
            )
        except Exception:
            return ""
        raw = ctypes.create_string_buffer(text_buf_size)
        bytes_read = ctypes.c_size_t(0)
        try:
            copied = bool(
                kernel32.ReadProcessMemory(
                    proc,
                    ctypes.c_void_p(int(remote_text)),
                    raw,
                    text_buf_size,
                    ctypes.byref(bytes_read),
                )
            )
        except Exception:
            copied = False
        if not copied:
            return ""
        try:
            text = raw.raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
        except Exception:
            text = ""
        return str(text or "").strip()

    def _read_item_state(item_index, mask):
        try:
            st = int(
                win32gui.SendMessage(
                    int(listview_hwnd),
                    int(lvm_getitemstate),
                    int(item_index),
                    int(mask),
                )
                or 0
            )
        except Exception:
            st = 0
        return int(st)

    def _client_rect_to_screen(rect_tuple):
        if not rect_tuple:
            return None
        left, top, right, bottom = rect_tuple
        try:
            sx1, sy1 = win32gui.ClientToScreen(int(listview_hwnd), (int(left), int(top)))
            sx2, sy2 = win32gui.ClientToScreen(int(listview_hwnd), (int(right), int(bottom)))
        except Exception:
            return None
        x1 = min(int(sx1), int(sx2))
        y1 = min(int(sy1), int(sy2))
        x2 = max(int(sx1), int(sx2))
        y2 = max(int(sy1), int(sy2))
        w = max(0, int(x2 - x1))
        h = max(0, int(y2 - y1))
        if w <= 0 or h <= 0:
            return None
        return QRect(int(x1), int(y1), int(w), int(h))

    edit_info = {}
    try:
        proc = kernel32.OpenProcess(process_access, False, int(pid.value))
        if not proc:
            return [], {}
        remote_ptr = kernel32.VirtualAllocEx(proc, None, alloc_size, mem_commit_reserve, page_readwrite)
        if not remote_ptr:
            return [], {}
        remote_base = int(remote_ptr)
        remote_rect = int(remote_base + rect_off)
        remote_lvitem = int(remote_base + lvitem_off)
        remote_text = int(remote_base + text_off)
        for idx in range(int(count)):
            icon_rect = _client_rect_to_screen(_read_item_rect(int(idx), int(lvir_icon), int(remote_rect)))
            label_rect = _client_rect_to_screen(_read_item_rect(int(idx), int(lvir_label), int(remote_rect)))
            select_rect = _client_rect_to_screen(_read_item_rect(int(idx), int(lvir_selectbounds), int(remote_rect)))
            image_index = _read_item_image_index(int(idx), int(remote_lvitem))
            label_text = _read_item_text(int(idx), int(remote_lvitem), int(remote_text))
            state_bits = _read_item_state(int(idx), int(lvis_selected | lvis_focused))
            if icon_rect is None and label_rect is None:
                continue
            key = str(label_text or "").strip().lower()
            shell_meta = {}
            seq_meta = {}
            if int(idx) < len(shell_items_order):
                try:
                    seq_meta = dict(shell_items_order[int(idx)] or {})
                except Exception:
                    seq_meta = {}
            if seq_meta:
                seq_name = str(seq_meta.get("name", "") or "")
                if _names_similar(label_text, seq_name):
                    shell_meta = dict(seq_meta)
            if key:
                pos = int(shell_name_seen.get(key, 0) or 0)
                shell_name_seen[key] = int(pos + 1)
                candidates = list(shell_items.get(key, []) or [])
                if not shell_meta and pos < len(candidates):
                    shell_meta = dict(candidates[pos] or {})
                elif not shell_items:
                    shell_items = shell_items_by_name_func(refresh=True)
                    shell_items_order = shell_items_in_order_func(refresh=True)
                    candidates = list(shell_items.get(key, []) or [])
                    if not shell_meta and pos < len(candidates):
                        shell_meta = dict(candidates[pos] or {})
            if not shell_meta and seq_meta:
                shell_meta = dict(seq_meta)
            shell_path = str(shell_meta.get("path", "") or "")
            shell_virtual = bool(shell_meta.get("is_virtual", False))
            shell_folder = bool(shell_meta.get("is_folder", False))
            display_text = str(shell_meta.get("name", "") or "").strip()
            if not display_text:
                display_text = str(label_text or "").strip()
            if select_rect is None:
                merged = None
                if isinstance(icon_rect, QRect) and isinstance(label_rect, QRect):
                    merged = QRect(icon_rect).united(QRect(label_rect))
                elif isinstance(icon_rect, QRect):
                    merged = QRect(icon_rect)
                elif isinstance(label_rect, QRect):
                    merged = QRect(label_rect)
                if isinstance(merged, QRect) and int(merged.width()) > 0 and int(merged.height()) > 0:
                    select_rect = merged.adjusted(-4, -2, 4, 2)
            if shell_path and not shell_virtual:
                try:
                    shell_folder = bool(os.path.isdir(shell_path))
                except Exception:
                    pass
            layouts.append(
                {
                    "icon": icon_rect,
                    "label": label_rect,
                    "text": display_text,
                    "image_index": int(image_index),
                    "shell_path": shell_path,
                    "shell_is_folder": bool(shell_folder),
                    "shell_is_virtual": bool(shell_virtual),
                    "selected": bool(int(state_bits) & int(lvis_selected)),
                    "focused": bool(int(state_bits) & int(lvis_focused)),
                    "select": select_rect,
                }
            )

        try:
            edit_hwnd = int(
                win32gui.SendMessage(
                    int(listview_hwnd),
                    int(lvm_geteditcontrol),
                    0,
                    0,
                )
                or 0
            )
        except Exception:
            edit_hwnd = 0
        if edit_hwnd:
            try:
                if win32gui.IsWindow(edit_hwnd) and win32gui.IsWindowVisible(edit_hwnd):
                    left, top, right, bottom = win32gui.GetWindowRect(int(edit_hwnd))
                    txt = str(win32gui.GetWindowText(int(edit_hwnd)) or "")
                    edit_info = {
                        "rect": QRect(
                            int(left),
                            int(top),
                            max(0, int(right - left)),
                            max(0, int(bottom - top)),
                        ),
                        "text": txt,
                        "hwnd": int(edit_hwnd),
                    }
            except Exception:
                edit_info = {}
    finally:
        try:
            if proc and remote_ptr:
                kernel32.VirtualFreeEx(proc, ctypes.c_void_p(int(remote_ptr)), 0, mem_release)
        except Exception:
            pass
        try:
            if proc:
                kernel32.CloseHandle(proc)
        except Exception:
            pass
    return layouts, dict(edit_info)

import ctypes
import os
from ctypes import wintypes

import win32gui


def resolve_desktop_listview_hwnd(cached_hwnd=0, refresh=False):
    cached = int(cached_hwnd or 0)
    if not bool(refresh) and cached:
        try:
            if win32gui.IsWindow(cached) and str(win32gui.GetClassName(cached)) == "SysListView32":
                return int(cached)
        except Exception:
            pass
    hwnd = 0
    defview = 0
    try:
        prog = int(win32gui.FindWindow("Progman", None) or 0)
    except Exception:
        prog = 0
    if prog:
        try:
            defview = int(win32gui.FindWindowEx(int(prog), 0, "SHELLDLL_DefView", None) or 0)
        except Exception:
            defview = 0
    if not defview:
        found = {"defview": 0}

        def _enum_top(window_hwnd, lparam):
            try:
                dv = int(win32gui.FindWindowEx(int(window_hwnd), 0, "SHELLDLL_DefView", None) or 0)
            except Exception:
                dv = 0
            if dv:
                lparam["defview"] = int(dv)
                return False
            return True

        try:
            win32gui.EnumWindows(_enum_top, found)
        except Exception:
            pass
        defview = int(found.get("defview") or 0)
    if defview:
        try:
            hwnd = int(win32gui.FindWindowEx(int(defview), 0, "SysListView32", None) or 0)
        except Exception:
            hwnd = 0
    try:
        if hwnd and win32gui.IsWindow(hwnd) and str(win32gui.GetClassName(hwnd)) == "SysListView32":
            return int(hwnd)
    except Exception:
        pass
    return 0


def build_desktop_caption_path_map():
    mapping = {}
    dirs = []
    try:
        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        def _guid(text):
            s = str(text or "").strip().strip("{}")
            parts = s.split("-")
            if len(parts) != 5:
                return None
            d4_hex = parts[3] + parts[4]
            if len(d4_hex) != 16:
                return None
            d4 = (ctypes.c_ubyte * 8)(*([int(d4_hex[i:i + 2], 16) for i in range(0, 16, 2)]))
            return GUID(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), d4)

        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long

        def _known_folder_path(guid_text):
            g = _guid(guid_text)
            if g is None:
                return ""
            out_ptr = ctypes.c_wchar_p()
            hr = int(shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out_ptr)))
            if hr != 0:
                return ""
            try:
                return str(out_ptr.value or "")
            finally:
                try:
                    ole32.CoTaskMemFree(out_ptr)
                except Exception:
                    pass

        desktop_dir = _known_folder_path("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
        public_desktop_dir = _known_folder_path("C4AA340D-F20F-4863-AFEF-F87EF2E6BA25")
        if desktop_dir:
            dirs.append(desktop_dir)
        if public_desktop_dir:
            dirs.append(public_desktop_dir)
    except Exception:
        pass
    try:
        dirs.append(os.path.join(os.path.expanduser("~"), "Desktop"))
    except Exception:
        pass
    try:
        pub = str(os.environ.get("PUBLIC", "") or "").strip()
        if pub:
            dirs.append(os.path.join(pub, "Desktop"))
    except Exception:
        pass

    seen_dirs = set()
    for base in dirs:
        d = os.path.normpath(str(base or ""))
        if not d or d in seen_dirs:
            continue
        seen_dirs.add(d)
        if not os.path.isdir(d):
            continue
        try:
            for entry in os.scandir(d):
                try:
                    name = str(entry.name or "")
                    path = str(entry.path or "")
                except Exception:
                    continue
                if not name or not path:
                    continue
                low_full = name.lower()
                stem = os.path.splitext(name)[0].lower()
                if low_full and low_full not in mapping:
                    mapping[low_full] = path
                if stem and stem not in mapping:
                    mapping[stem] = path
        except Exception:
            continue
    return dict(mapping)


def fetch_desktop_shell_items(win32com_client):
    if win32com_client is None:
        return {}, []
    out = {}
    ordered = []
    try:
        shell = win32com_client.Dispatch("Shell.Application")
        ns = shell.Namespace(0)
        if ns is not None:
            items = ns.Items()
            count = int(getattr(items, "Count", 0) or 0)
            for i in range(count):
                try:
                    it = items.Item(i)
                except Exception:
                    continue
                try:
                    name = str(getattr(it, "Name", "") or "").strip()
                except Exception:
                    name = ""
                if not name:
                    continue
                key = name.lower()
                try:
                    path = str(getattr(it, "Path", "") or "").strip()
                except Exception:
                    path = ""
                try:
                    is_folder = bool(getattr(it, "IsFolder", False))
                except Exception:
                    is_folder = False
                is_virtual = bool(path.startswith("::")) if path else True
                rec = {
                    "name": str(name),
                    "path": str(path),
                    "is_folder": bool(is_folder),
                    "is_virtual": bool(is_virtual),
                }
                ordered.append(rec)
                out.setdefault(key, []).append(rec)
    except Exception:
        out = {}
        ordered = []
    return dict(out), list(ordered)
