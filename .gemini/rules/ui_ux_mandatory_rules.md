---
description: MyWidgetBox UI/UX Design System and Implementation Mandatory Rules
globs: ["**/*.py", "**/*.qss", "**/*.md"]
alwaysApply: true
---

# 🚨 MyWidgetBox Mandatory System Specifications & UI/UX Rules

You MUST ALWAYS read and strictly follow `c:/MyWidgetBox/PROJECT_SPEC_AND_DESIGN_SYSTEM.md` whenever inspecting, modifying, or creating any code, UI components, styling, or algorithms in MyWidgetBox.

## 10 Inviolable Invariants (절대 불변 10대 규칙):
1. **Never Break Checkbox Indicators**: Do NOT override `QCheckBox::indicator` CSS arbitrarily; doing so erases the native V-checkmark (✓). Only style text color, font-size, and spacing.
2. **Strict Design Tokens**: Follow the defined color palette (`#121c2b` Surface, `#162233` App, `#162438`/`#1d2c42` Card, `#528bf8`/`#3b68d4` Accent, `#8f3741` Danger). Never use raw default grey/white styles.
3. **Modal Dialog Parent Hierarchy**: Any `QMessageBox` or dialog popup MUST use `parent=self` or the active modal window to prevent hiding behind other modal dialogs.
4. **Hardware Key Detection**: Alt/Ctrl wheel gestures MUST double-check `win32api.GetAsyncKeyState` to guarantee physical key sensing on Windows/Korean keyboards.
5. **Dual Wheel Scroll Fallback**: Wheel delta MUST handle both `e.angleDelta().y() or e.angleDelta().x()` for horizontal-scrolling mouse drivers (Logitech, Razer, etc.).
6. **Minimum 1 Set Invariant**: At least 1 set must always remain in the system. Deleting the last remaining set is blocked in Set Manager ([⚙]).
7. **Individual Size Preservation**: In bulk settings, individual widget dimensions (W x H) MUST be preserved by default (`keep_individual_size_cb`). Never force-overwrite unless explicitly confirmed.
8. **Pause on Fullscreen Media Policy**: When other apps are fullscreen (games, video players, etc.), background GIF frame timers and video playback MUST be paused to conserve GPU/CPU and battery.
9. **Vector Icons Only**: Always use `render_vector_icon(name, color, size)` from `mywidgetbox_core.py`.
10. **Build & Integrity Verification**: Always run `python -m py_compile` and unit tests before running `cmd.exe /c build_release.cmd`. Verify clean compilation on every single change.
