#!/usr/bin/env python3
"""
Path Tracer Pro — DearPyGui Edition
FTC autonomous path planning tool.
"""

import dearpygui.dearpygui as dpg
import json
import math
import os
import copy
import subprocess
from typing import List, Tuple, Optional

from environment import Environment, EnvironmentEditor

# ── Field configuration ─────────────────────────────────────────────
FIELD_WIDTH_IN = 144
FIELD_HEIGHT_IN = 144
BACKGROUND_IMAGE = "nope"
OUTPUT_FILE = "path.json"
FUNCTIONS_FILE = "functions.json"
PREFS_FILE = "preferences.json"

# ── View defaults ────────────────────────────────────────────────────
DEFAULT_SCALE = 5
MIN_SCALE = 1
MAX_SCALE = 15
INITIAL_WINDOW_W = 1280
INITIAL_WINDOW_H = 960
MENU_BAR_HEIGHT = 22

# ── Path settings ────────────────────────────────────────────────────
STEP_SIZE = 0.5
SNAP_ANGLES = [math.radians(a) for a in [0, 45, 90, 135, 180, 225, 270, 315]]

# ── Colors (RGBA 0-255) ─────────────────────────────────────────────
COL_BG = (30, 30, 30, 255)
COL_GRID = (50, 50, 50, 255)
COL_PATH = (255, 0, 0, 255)
COL_PATH_POINT = (255, 80, 80, 255)
COL_FUNC_WAIT = (0, 255, 0, 255)
COL_FUNC_MOVE = (0, 150, 255, 255)
COL_FUNC_ROT = (255, 255, 0, 255)
COL_START = (255, 255, 255, 255)
COL_START_INNER = (0, 255, 0, 255)
COL_HINT = (100, 255, 100, 255)

MAX_UNDO = 100


# ── Data classes ─────────────────────────────────────────────────────
class Function:
    def __init__(self, name: str, x: float, y: float, rotation: float = 0,
                 function_type: str = "wait_till", action: str = "function"):
        self.name = name
        self.x = x
        self.y = y
        self.rotation = rotation
        self.function_type = function_type
        self.action = action
        self.width = 12
        self.height = 12

    def to_dict(self):
        return {
            "name": self.name, "x": self.x, "y": self.y,
            "rotation": self.rotation, "type": self.function_type,
            "action": self.action,
        }

    def clone(self):
        return Function(self.name, self.x, self.y, self.rotation,
                        self.function_type, self.action)

    @staticmethod
    def from_dict(data):
        return Function(
            data["name"], data["x"], data["y"],
            data.get("rotation", 0),
            data.get("type", "wait_till"),
            data.get("action", "function"),
        )


# ── Main application ────────────────────────────────────────────────
class PathTracer:
    def __init__(self):
        # View state
        self.scale = DEFAULT_SCALE
        self.offset_x = 0.0
        self.offset_y = 0.0

        # Path state
        self.drawing = False
        self.last_point: Optional[Tuple[float, float]] = None
        self.path_points: List[Tuple[float, float]] = []

        # Start position
        self.start_pos: Optional[Tuple[float, float, float]] = None
        self.placing_start = False

        # Function state
        self.functions: List[Function] = []
        self.function_templates = ["intake", "outtake", "score", "park"]
        self.selected_function: Optional[str] = None
        self.selected_function_type = "wait_till"
        self.selected_action = "function"
        self.placing_function = False

        # Snap settings
        self.snap_enabled = False
        self.snap_inches = 24
        self.grid_offset = 0

        # Panning
        self.panning = False
        self.pan_start: Optional[Tuple[float, float]] = None
        self.pan_offset_start: Optional[Tuple[float, float]] = None

        # Background texture
        self.bg_texture_id = None

        # Status
        self.status_msg = "Ready — Press H for help"

        # View toggles
        self.show_grid = True
        self.show_path_points = True
        self.show_labels = True
        self.show_status_bar = True

        # Undo / Redo
        self.undo_stack: list = []
        self.redo_stack: list = []
        self._suppress_snapshot = False

        # Clipboard
        self.clipboard: Optional[dict] = None

        # Preferences
        self.prefs = {
            "step_size": STEP_SIZE,
            "default_scale": DEFAULT_SCALE,
            "snap_inches": 24,
            "grid_offset": 0,
            "path_thickness": 3,
            "point_radius": 4,
            "path_color": list(COL_PATH),
            "auto_save": False,
        }
        self._load_prefs()

        # Current open files
        self.current_path_file: Optional[str] = None
        self.current_functions_file: Optional[str] = None

        # Environment
        self.env_editor = EnvironmentEditor(
            on_save_callback=self._on_env_saved,
            on_close_callback=self._on_env_closed,
        )
        self.active_env: Optional[Environment] = None

    # ─────────────────────────────────────────────────────────────
    # Undo / Redo
    # ─────────────────────────────────────────────────────────────
    def _snapshot(self) -> dict:
        return {
            "path_points": list(self.path_points),
            "functions": [f.to_dict() for f in self.functions],
            "start_pos": self.start_pos,
            "function_templates": list(self.function_templates),
        }

    def _restore(self, snap: dict):
        self._suppress_snapshot = True
        self.path_points = list(snap["path_points"])
        self.functions = [Function.from_dict(d) for d in snap["functions"]]
        self.start_pos = snap["start_pos"]
        self.function_templates = list(snap["function_templates"])
        self._suppress_snapshot = False

    def push_undo(self):
        if self._suppress_snapshot:
            return
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.status_msg = "Nothing to undo"
            return
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        self.status_msg = "Undo"

    def redo(self):
        if not self.redo_stack:
            self.status_msg = "Nothing to redo"
            return
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        self.status_msg = "Redo"

    # ─────────────────────────────────────────────────────────────
    # Clipboard
    # ─────────────────────────────────────────────────────────────
    def copy_selection(self):
        if hasattr(self, "_ctx_func") and self._ctx_func in self.functions:
            self.clipboard = {"type": "function", "data": self._ctx_func.to_dict()}
            self.status_msg = f"Copied function '{self._ctx_func.name}'"
        elif self.path_points:
            self.clipboard = {"type": "path", "data": list(self.path_points)}
            self.status_msg = f"Copied path ({len(self.path_points)} pts)"
        else:
            self.status_msg = "Nothing to copy"

    def cut_selection(self):
        if hasattr(self, "_ctx_func") and self._ctx_func in self.functions:
            self.push_undo()
            self.clipboard = {"type": "function", "data": self._ctx_func.to_dict()}
            self.functions.remove(self._ctx_func)
            self.status_msg = f"Cut function '{self._ctx_func.name}'"
        elif self.path_points:
            self.push_undo()
            self.clipboard = {"type": "path", "data": list(self.path_points)}
            self.path_points.clear()
            self.status_msg = "Cut path"
        else:
            self.status_msg = "Nothing to cut"

    def paste_clipboard(self):
        if not self.clipboard:
            self.status_msg = "Clipboard empty"
            return
        self.push_undo()
        if self.clipboard["type"] == "function":
            f = Function.from_dict(self.clipboard["data"])
            f.x += 6
            f.y += 6
            self.functions.append(f)
            self.status_msg = f"Pasted function '{f.name}'"
        elif self.clipboard["type"] == "path":
            self.path_points = list(self.clipboard["data"])
            self.status_msg = f"Pasted path ({len(self.path_points)} pts)"

    # ─────────────────────────────────────────────────────────────
    # Preferences
    # ─────────────────────────────────────────────────────────────
    def _load_prefs(self):
        if os.path.exists(PREFS_FILE):
            try:
                with open(PREFS_FILE, "r") as f:
                    self.prefs.update(json.load(f))
            except Exception:
                pass
        self._apply_prefs()

    def _apply_prefs(self):
        global STEP_SIZE
        STEP_SIZE = self.prefs["step_size"]
        self.snap_inches = self.prefs["snap_inches"]
        self.grid_offset = self.prefs["grid_offset"]

    def _save_prefs(self):
        with open(PREFS_FILE, "w") as f:
            json.dump(self.prefs, f, indent=2)
        self._apply_prefs()
        self.status_msg = "Preferences saved"

    # ── Coordinate conversion ────────────────────────────────────
    def screen_to_field(self, sx, sy):
        return (sx - self.offset_x) / self.scale, (sy - self.offset_y) / self.scale

    def field_to_screen(self, fx, fy):
        return fx * self.scale + self.offset_x, fy * self.scale + self.offset_y

    def snap_coord(self, x, y):
        if not self.snap_enabled:
            return x, y
        xa, ya = x - self.grid_offset, y - self.grid_offset
        return (round(xa / self.snap_inches) * self.snap_inches + self.grid_offset,
                round(ya / self.snap_inches) * self.snap_inches + self.grid_offset)

    def get_function_at_pos(self, fx, fy):
        for func in self.functions:
            if abs(fx - func.x) < func.width / 2 and abs(fy - func.y) < func.height / 2:
                return func
        return None

    def is_click_on_start(self, fx, fy):
        if not self.start_pos:
            return False
        sx, sy, _ = self.start_pos
        return math.hypot(fx - sx, fy - sy) < 18

    # ── File I/O ─────────────────────────────────────────────────
    def new_path(self):
        self.push_undo()
        self.path_points.clear()
        self.functions.clear()
        self.start_pos = None
        self.last_point = None
        self.current_path_file = None
        self.current_functions_file = None
        self.status_msg = "New path created"

    def save_to(self, path_file, func_file):
        data = {"path": [{"x": x, "y": y} for x, y in self.path_points]}
        with open(path_file, "w") as f:
            json.dump(data, f, indent=2)
        fdata = {
            "functions": [fn.to_dict() for fn in self.functions],
            "templates": self.function_templates,
        }
        if self.start_pos:
            fdata["start_pos"] = {"x": self.start_pos[0], "y": self.start_pos[1],
                                  "rotation": self.start_pos[2]}
        with open(func_file, "w") as f:
            json.dump(fdata, f, indent=2)
        self.current_path_file = path_file
        self.current_functions_file = func_file
        self.status_msg = f"Saved → {os.path.basename(path_file)}"

    def save_all(self):
        self.save_to(self.current_path_file or OUTPUT_FILE,
                     self.current_functions_file or FUNCTIONS_FILE)

    def load_from(self, filepath):
        self.push_undo()
        directory = os.path.dirname(filepath) or "."
        base = os.path.basename(filepath)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                data = json.load(f)
            if "path" in data:
                self.path_points = [(p["x"], p["y"]) for p in data.get("path", [])]
                self.current_path_file = filepath
            if "functions" in data:
                self.functions = [Function.from_dict(fn) for fn in data.get("functions", [])]
                self.function_templates = data.get("templates", self.function_templates)
                if "start_pos" in data:
                    sp = data["start_pos"]
                    self.start_pos = (sp["x"], sp["y"], sp["rotation"])
                self.current_functions_file = filepath
        # Try companion file
        if "path" in base.lower():
            companion = os.path.join(directory, base.replace("path", "functions"))
        elif "functions" in base.lower():
            companion = os.path.join(directory, base.replace("functions", "path"))
        else:
            companion = None
        if companion and os.path.exists(companion) and companion != filepath:
            with open(companion, "r") as f:
                cdata = json.load(f)
            if "path" in cdata:
                self.path_points = [(p["x"], p["y"]) for p in cdata.get("path", [])]
                self.current_path_file = companion
            if "functions" in cdata:
                self.functions = [Function.from_dict(fn) for fn in cdata.get("functions", [])]
                self.function_templates = cdata.get("templates", self.function_templates)
                if "start_pos" in cdata:
                    sp = cdata["start_pos"]
                    self.start_pos = (sp["x"], sp["y"], sp["rotation"])
                self.current_functions_file = companion
        self.status_msg = f"Loaded {os.path.basename(filepath)}"

    def load_all(self):
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "r") as f:
                data = json.load(f)
                self.path_points = [(p["x"], p["y"]) for p in data.get("path", [])]
        if os.path.exists(FUNCTIONS_FILE):
            with open(FUNCTIONS_FILE, "r") as f:
                data = json.load(f)
                self.functions = [Function.from_dict(fn) for fn in data.get("functions", [])]
                self.function_templates = data.get("templates", self.function_templates)
                if "start_pos" in data:
                    sp = data["start_pos"]
                    self.start_pos = (sp["x"], sp["y"], sp["rotation"])
        self.current_path_file = OUTPUT_FILE
        self.current_functions_file = FUNCTIONS_FILE
        self.status_msg = f"Loaded {len(self.path_points)} pts, {len(self.functions)} funcs"

    # ── Background ───────────────────────────────────────────────
    def load_background(self):
        if os.path.exists(BACKGROUND_IMAGE):
            w, h, _, data = dpg.load_image(BACKGROUND_IMAGE)
            with dpg.texture_registry():
                self.bg_texture_id = dpg.add_static_texture(width=w, height=h, default_value=data)

    # ── Drawing helpers ──────────────────────────────────────────
    def _draw_arrow(self, dl, cx, cy, angle_deg, length, color, thickness=2):
        angle = math.radians(angle_deg)
        ex = cx + math.cos(angle) * length
        ey = cy + math.sin(angle) * length
        dpg.draw_line((cx, cy), (ex, ey), color=color, thickness=thickness, parent=dl)
        sz = 8
        la = angle + math.radians(150)
        ra = angle - math.radians(150)
        dpg.draw_triangle(
            (ex, ey),
            (ex + math.cos(la) * sz, ey + math.sin(la) * sz),
            (ex + math.cos(ra) * sz, ey + math.sin(ra) * sz),
            color=color, fill=color, parent=dl)

    # ── Main render ──────────────────────────────────────────────
    def render(self):
        dl = "canvas"
        dpg.delete_item(dl, children_only=True)

        if self.bg_texture_id:
            ox, oy = self.offset_x, self.offset_y
            fw = FIELD_WIDTH_IN * self.scale
            fh = FIELD_HEIGHT_IN * self.scale
            dpg.draw_image(self.bg_texture_id, (ox, oy), (ox + fw, oy + fh), parent=dl)

        if self.show_grid:
            self._draw_grid(dl)

        # Render active environment objects on main canvas
        if self.active_env and self.env_editor:
            self.env_editor.render_on_main(dl, self.field_to_screen)

        self._draw_path(dl)
        self._draw_start(dl)
        self._draw_functions(dl)
        self._draw_cursor(dl)

    def _draw_grid(self, dl):
        spacing = self.snap_inches * self.scale
        if spacing < 4:
            return
        off_px = self.grid_offset * self.scale
        fw = FIELD_WIDTH_IN * self.scale
        fh = FIELD_HEIGHT_IN * self.scale
        ox, oy = self.offset_x, self.offset_y
        x = ox + (off_px % spacing)
        while x <= ox + fw:
            dpg.draw_line((x, oy), (x, oy + fh), color=COL_GRID, thickness=1, parent=dl)
            x += spacing
        y = oy + (off_px % spacing)
        while y <= oy + fh:
            dpg.draw_line((ox, y), (ox + fw, y), color=COL_GRID, thickness=1, parent=dl)
            y += spacing

    def _draw_path(self, dl):
        pcol = tuple(self.prefs["path_color"])
        thick = self.prefs["path_thickness"]
        radius = self.prefs["point_radius"]
        if len(self.path_points) < 2:
            if len(self.path_points) == 1:
                sx, sy = self.field_to_screen(*self.path_points[0])
                dpg.draw_circle((sx, sy), radius, color=pcol, fill=pcol, parent=dl)
            return
        pts = [self.field_to_screen(x, y) for x, y in self.path_points]
        dpg.draw_polyline(pts, color=pcol, thickness=thick, parent=dl)
        if self.show_path_points:
            for sx, sy in pts:
                dpg.draw_circle((sx, sy), radius, color=COL_PATH_POINT, fill=COL_PATH_POINT, parent=dl)

    def _draw_start(self, dl):
        if not self.start_pos:
            return
        x, y, rot = self.start_pos
        sx, sy = self.field_to_screen(x, y)
        r = max(8, int(18 * self.scale))
        dpg.draw_circle((sx, sy), r, color=COL_START, thickness=3, parent=dl)
        dpg.draw_circle((sx, sy), max(3, r - 5), color=COL_START_INNER, thickness=2, parent=dl)
        self._draw_arrow(dl, sx, sy, rot, r + 10, COL_START, 3)
        if self.show_labels:
            dpg.draw_text((sx - 22, sy - r - 20), "START", color=COL_START, size=14, parent=dl)
            dpg.draw_text((sx - 12, sy + r + 5), f"{rot}°", color=(200, 200, 200, 255), size=12, parent=dl)

    def _draw_functions(self, dl):
        for func in self.functions:
            sx, sy = self.field_to_screen(func.x, func.y)
            w = max(int(func.width * self.scale), 8)
            h = max(int(func.height * self.scale), 8)
            color = (COL_FUNC_ROT if func.action == "rotate_only"
                     else COL_FUNC_WAIT if func.function_type == "wait_till"
                     else COL_FUNC_MOVE)
            if func.action == "rotate_only":
                dpg.draw_circle((sx, sy), w // 2, color=color, thickness=2, parent=dl)
            else:
                dpg.draw_rectangle((sx - w // 2, sy - h // 2), (sx + w // 2, sy + h // 2),
                                   color=color, thickness=2, parent=dl)
                if func.function_type != "wait_till":
                    dpg.draw_line((sx - w // 2, sy - h // 2), (sx + w // 2, sy + h // 2),
                                 color=color, thickness=1, parent=dl)
            a = math.radians(func.rotation)
            dpg.draw_line((sx, sy), (sx + math.cos(a) * w // 2, sy + math.sin(a) * h // 2),
                          color=color, thickness=2, parent=dl)
            if self.show_labels:
                lbl = (f"R:{func.rotation}°" if func.action == "rotate_only"
                       else f"{'W' if func.function_type == 'wait_till' else 'M'}:{func.name}")
                dpg.draw_text((sx - len(lbl) * 3.5, sy - h // 2 - 18), lbl, color=color, size=12, parent=dl)

    def _draw_cursor(self, dl):
        if not dpg.is_item_hovered("drawlist_window"):
            return
        mpos = dpg.get_mouse_pos(local=False)
        wpos = dpg.get_item_pos("canvas")
        mx, my = mpos[0] - wpos[0], mpos[1] - wpos[1]
        fx, fy = self.snap_coord(*self.screen_to_field(mx, my))
        sx, sy = self.field_to_screen(fx, fy)

        if self.placing_start:
            r = max(8, int(18 * self.scale))
            dpg.draw_circle((sx, sy), r, color=(255, 255, 255, 128), thickness=2, parent=dl)
            dpg.draw_line((sx, sy), (sx + r + 10, sy), color=(255, 255, 255, 128), thickness=2, parent=dl)
            dpg.draw_text((sx - 30, sy - r - 20), "START (0°)", color=(255, 255, 255, 180), size=12, parent=dl)
        elif self.placing_function:
            w = max(int(12 * self.scale), 8)
            if self.selected_action == "rotate_only":
                dpg.draw_circle((sx, sy), w // 2, color=COL_FUNC_ROT, thickness=2, parent=dl)
                dpg.draw_text((sx - 30, sy - w // 2 - 18), "Rotate Only", color=COL_FUNC_ROT, size=12, parent=dl)
            else:
                col = COL_FUNC_WAIT if self.selected_function_type == "wait_till" else COL_FUNC_MOVE
                dpg.draw_rectangle((sx - w // 2, sy - w // 2), (sx + w // 2, sy + w // 2),
                                   color=col, thickness=2, parent=dl)
                prefix = "Wait" if self.selected_function_type == "wait_till" else "Move"
                lbl = f"{prefix}: {self.selected_function}"
                dpg.draw_text((sx - len(lbl) * 3.5, sy - w // 2 - 18), lbl, color=col, size=12, parent=dl)
        elif self.start_pos and len(self.path_points) == 0 and not self.placing_function:
            ssx, ssy = self.field_to_screen(self.start_pos[0], self.start_pos[1])
            dpg.draw_line((ssx, ssy), (sx, sy), color=COL_HINT, thickness=1, parent=dl)
            dpg.draw_text((sx + 10, sy - 16), "Path starts from START", color=COL_HINT, size=12, parent=dl)

    # ── Mouse handling ───────────────────────────────────────────
    def _local_mouse(self):
        mpos = dpg.get_mouse_pos(local=False)
        wpos = dpg.get_item_pos("canvas")
        return mpos[0] - wpos[0], mpos[1] - wpos[1]

    def on_mouse_down(self, sender, app_data):
        button = app_data
        if not dpg.is_item_hovered("drawlist_window"):
            return
        mx, my = self._local_mouse()
        fx, fy = self.screen_to_field(mx, my)

        if button == 0:
            if self.placing_start:
                self.push_undo()
                sfx, sfy = self.snap_coord(fx, fy)
                self.start_pos = (sfx, sfy, 0)
                self.placing_start = False
                self.status_msg = f"Start placed at ({sfx:.1f}, {sfy:.1f}). Right-click to rotate."
                return
            if self.placing_function:
                self.push_undo()
                sfx, sfy = self.snap_coord(fx, fy)
                if self.selected_action == "rotate_only":
                    self.functions.append(Function("rotate", sfx, sfy, 0, "wait_till", "rotate_only"))
                    self.status_msg = f"Rotation point at ({sfx:.1f}, {sfy:.1f})"
                elif self.selected_function:
                    self.functions.append(Function(self.selected_function, sfx, sfy, 0,
                                                   self.selected_function_type, self.selected_action))
                    self.status_msg = f"Placed {self.selected_function} at ({sfx:.1f}, {sfy:.1f})"
                return
            if not self.start_pos:
                self.status_msg = "⚠ Place START position first (press P)"
                return
            self.push_undo()
            self.drawing = True
            sfx, sfy = self.snap_coord(fx, fy)
            clicked_func = self.get_function_at_pos(sfx, sfy)
            if clicked_func:
                sfx, sfy = clicked_func.x, clicked_func.y
            if len(self.path_points) == 0:
                sx2, sy2, _ = self.start_pos
                self.path_points.append((sx2, sy2))
                self.last_point = (sx2, sy2)
            self.last_point = (sfx, sfy)
            self.path_points.append(self.last_point)

        elif button == 1:
            if self.placing_function or self.placing_start:
                self.placing_function = False
                self.placing_start = False
                self.selected_function = None
                self.status_msg = "Placement cancelled"
                return
            if self.is_click_on_start(fx, fy):
                dpg.configure_item("ctx_start", show=True)
                return
            func = self.get_function_at_pos(fx, fy)
            if func:
                self._ctx_func = func
                if func.action == "function":
                    lbl = "Change to Run While Moving" if func.function_type == "wait_till" else "Change to Wait Till"
                    dpg.set_item_label("ctx_func_toggle_type", lbl)
                    dpg.configure_item("ctx_func_toggle_type", show=True)
                else:
                    dpg.configure_item("ctx_func_toggle_type", show=False)
                dpg.configure_item("ctx_func", show=True)
                return
            dpg.configure_item("ctx_general", show=True)

        elif button == 2:
            self.panning = True
            gpos = dpg.get_mouse_pos(local=False)
            self.pan_start = (gpos[0], gpos[1])
            self.pan_offset_start = (self.offset_x, self.offset_y)

    def on_mouse_release(self, sender, app_data):
        if app_data == 0:
            self.drawing = False
            self.last_point = None
        elif app_data == 2:
            self.panning = False
            self.pan_start = None

    def on_mouse_move(self, sender, app_data):
        if self.panning and self.pan_start:
            gpos = dpg.get_mouse_pos(local=False)
            self.offset_x = self.pan_offset_start[0] + gpos[0] - self.pan_start[0]
            self.offset_y = self.pan_offset_start[1] + gpos[1] - self.pan_start[1]

        if self.drawing and self.last_point and dpg.is_item_hovered("drawlist_window"):
            mx, my = self._local_mouse()
            fx, fy = self.screen_to_field(mx, my)
            nearby = self.get_function_at_pos(fx, fy)
            if nearby:
                fx, fy = nearby.x, nearby.y
            else:
                fx, fy = self.snap_coord(fx, fy)
            lx, ly = self.last_point
            dx, dy = fx - lx, fy - ly
            if abs(dx) > 0.05 or abs(dy) > 0.05:
                angle = math.atan2(dy, dx)
                best = min(SNAP_ANGLES, key=lambda a: abs(a - angle))
                step = self.prefs["step_size"]
                nx, ny = lx + math.cos(best) * step, ly + math.sin(best) * step
                check = self.get_function_at_pos(nx, ny)
                if check:
                    nx, ny = check.x, check.y
                else:
                    nx, ny = self.snap_coord(nx, ny)
                self.last_point = (nx, ny)
                self.path_points.append(self.last_point)

    def on_mouse_wheel(self, sender, app_data):
        if not dpg.is_item_hovered("drawlist_window"):
            return
        mx, my = self._local_mouse()
        fx, fy = self.screen_to_field(mx, my)
        old = self.scale
        self.scale = max(MIN_SCALE, min(MAX_SCALE, self.scale + (1 if app_data > 0 else -1)))
        if old != self.scale:
            nsx, nsy = self.field_to_screen(fx, fy)
            self.offset_x += mx - nsx
            self.offset_y += my - nsy

    # ── Keyboard ─────────────────────────────────────────────────
    def on_key_press(self, sender, app_data):
        key = app_data
        if key == dpg.mvKey_H:
            self._toggle("help_window")
        elif key == dpg.mvKey_P:
            self.placing_start = True
            self.placing_function = False
            self.status_msg = "Click on the field to place START position"
        elif key == dpg.mvKey_S:
            self.save_all()
        elif key == dpg.mvKey_L:
            self.load_all()
        elif key == dpg.mvKey_C:
            self.push_undo()
            self.path_points.clear()
            self.last_point = None
            self.status_msg = "Path cleared"
        elif key == dpg.mvKey_G:
            self.snap_enabled = not self.snap_enabled
            dpg.set_value("menu_toggle_snap", self.snap_enabled)
            self.status_msg = f"Snap: {'ON' if self.snap_enabled else 'OFF'}"
        elif key == dpg.mvKey_F:
            self._toggle("function_window")
        elif key == dpg.mvKey_Z:
            self.undo()
        elif key == dpg.mvKey_Y:
            self.redo()
        elif key == dpg.mvKey_Escape:
            if self.placing_function or self.placing_start:
                self.placing_function = False
                self.placing_start = False
                self.selected_function = None
                self.status_msg = "Placement cancelled"
            else:
                dpg.configure_item("help_window", show=False)
                dpg.configure_item("function_window", show=False)

    def _toggle(self, tag):
        dpg.configure_item(tag, show=not dpg.get_item_configuration(tag)["show"])

    # ── Context menu callbacks ───────────────────────────────────
    def ctx_start_delete(self):
        self.push_undo(); self.start_pos = None; self.status_msg = "Start removed"

    def ctx_start_rotate(self, delta):
        if self.start_pos:
            self.push_undo()
            x, y, r = self.start_pos
            self.start_pos = (x, y, (r + delta) % 360)
            self.status_msg = f"Start rotation: {self.start_pos[2]}°"

    def ctx_start_set_rot(self, deg):
        if self.start_pos:
            self.push_undo()
            self.start_pos = (self.start_pos[0], self.start_pos[1], deg)
            self.status_msg = f"Start rotation: {deg}°"

    def ctx_func_delete(self):
        if hasattr(self, "_ctx_func") and self._ctx_func in self.functions:
            self.push_undo(); self.functions.remove(self._ctx_func); self.status_msg = "Function deleted"

    def ctx_func_rotate(self, delta):
        if hasattr(self, "_ctx_func"):
            self.push_undo()
            self._ctx_func.rotation = (self._ctx_func.rotation + delta) % 360
            self.status_msg = f"Function rotation: {self._ctx_func.rotation}°"

    def ctx_func_toggle_type(self):
        if hasattr(self, "_ctx_func"):
            self.push_undo()
            f = self._ctx_func
            f.function_type = "run_while_moving" if f.function_type == "wait_till" else "wait_till"
            self.status_msg = f"Function type: {f.function_type}"

    # ── Function menu callbacks ──────────────────────────────────
    def func_menu_set_action(self, action):
        self.selected_action = action
        if action == "rotate_only":
            self.selected_function = None
            self.placing_function = True
            dpg.configure_item("function_window", show=False)
            self.status_msg = "Click to place rotation point"

    def func_menu_set_type(self, ftype):
        self.selected_function_type = ftype

    def func_menu_select(self, name):
        self.selected_function = name
        self.placing_function = True
        dpg.configure_item("function_window", show=False)
        self.status_msg = f"Click to place '{name}' ({self.selected_function_type})"

    def func_menu_add_template(self, sender=None, app_data=None, user_data=None):
        name = dpg.get_value("new_template_input").strip()
        if name and name not in self.function_templates:
            self.function_templates.append(name)
            self._rebuild_template_list()
            dpg.set_value("new_template_input", "")
            self.status_msg = f"Added template: {name}"

    def _rebuild_template_list(self):
        dpg.delete_item("template_list_group", children_only=True)
        for name in self.function_templates:
            dpg.add_button(label=name, parent="template_list_group",
                           callback=lambda s, a, u=name: self.func_menu_select(u), width=-1)

    # ── View actions ─────────────────────────────────────────────
    def zoom_in(self):
        self.scale = min(MAX_SCALE, self.scale + 1)

    def zoom_out(self):
        self.scale = max(MIN_SCALE, self.scale - 1)

    def zoom_reset(self):
        self.scale = DEFAULT_SCALE; self.offset_x = 0.0; self.offset_y = 0.0

    def zoom_fit(self):
        vw = dpg.get_viewport_client_width()
        vh = dpg.get_viewport_client_height() - MENU_BAR_HEIGHT
        self.scale = max(MIN_SCALE, min(MAX_SCALE, int(min(vw / FIELD_WIDTH_IN, vh / FIELD_HEIGHT_IN))))
        fw, fh = FIELD_WIDTH_IN * self.scale, FIELD_HEIGHT_IN * self.scale
        self.offset_x = (vw - fw) / 2
        self.offset_y = (vh - fh) / 2 + MENU_BAR_HEIGHT

    # ── File dialog callbacks ────────────────────────────────────
    def _on_open_file(self, sender, app_data):
        if app_data and "file_path_name" in app_data:
            self.load_from(app_data["file_path_name"])

    def _on_save_file(self, sender, app_data):
        if app_data and "file_path_name" in app_data:
            fpath = app_data["file_path_name"]
            d = os.path.dirname(fpath)
            b = os.path.basename(fpath)
            pf = fpath
            ff = os.path.join(d, b.replace("path", "functions")) if "path" in b.lower() else os.path.join(d, "functions.json")
            self.save_to(pf, ff)

    # ── Preferences dialog ───────────────────────────────────────
    def _prefs_open(self):
        dpg.set_value("pref_step_size", self.prefs["step_size"])
        dpg.set_value("pref_default_scale", self.prefs["default_scale"])
        dpg.set_value("pref_snap_inches", self.prefs["snap_inches"])
        dpg.set_value("pref_grid_offset", self.prefs["grid_offset"])
        dpg.set_value("pref_path_thickness", self.prefs["path_thickness"])
        dpg.set_value("pref_point_radius", self.prefs["point_radius"])
        pc = self.prefs["path_color"]
        dpg.set_value("pref_path_color", pc if len(pc) == 4 else pc + [255])
        dpg.set_value("pref_auto_save", self.prefs["auto_save"])
        dpg.configure_item("prefs_window", show=True)

    def _prefs_apply(self):
        self.prefs["step_size"] = dpg.get_value("pref_step_size")
        self.prefs["default_scale"] = dpg.get_value("pref_default_scale")
        self.prefs["snap_inches"] = dpg.get_value("pref_snap_inches")
        self.prefs["grid_offset"] = dpg.get_value("pref_grid_offset")
        self.prefs["path_thickness"] = dpg.get_value("pref_path_thickness")
        self.prefs["point_radius"] = dpg.get_value("pref_point_radius")
        self.prefs["path_color"] = [int(c) for c in dpg.get_value("pref_path_color")[:4]]
        self.prefs["auto_save"] = dpg.get_value("pref_auto_save")
        self._apply_prefs()
        self._save_prefs()
        dpg.configure_item("prefs_window", show=False)

    # ── Environment integration ─────────────────────────────────
    def _env_new(self):
        self.env_editor.open_new()
        self.active_env = self.env_editor.get_env()
        self._sync_env_to_field()
        self.status_msg = "New environment created"

    def _env_open(self):
        dpg.show_item("env_open_dialog")

    def _env_open_file_cb(self, sender, app_data):
        if app_data and "file_path_name" in app_data:
            self.env_editor.open_file(app_data["file_path_name"])
            self.active_env = self.env_editor.get_env()
            self._sync_env_to_field()
            self.status_msg = f"Environment loaded: {os.path.basename(app_data['file_path_name'])}"

    def _env_close(self):
        self.env_editor.close()
        self.active_env = None
        self.status_msg = "Environment closed"

    def _on_env_saved(self, env):
        self.active_env = env
        self._sync_env_to_field()
        self.status_msg = f"Environment saved"

    def _on_env_closed(self):
        self.active_env = None

    def _sync_env_to_field(self):
        """Sync environment metadata into path tracer globals."""
        if not self.active_env:
            return
        m = self.active_env.metadata
        # Update function templates from environment
        env_func_names = [vf.name for vf in self.active_env.valid_functions]
        for name in env_func_names:
            if name not in self.function_templates:
                self.function_templates.append(name)
        self._rebuild_template_list()

    def _run_convert(self):
        self.save_all()
        if os.path.exists("convert.py"):
            result = subprocess.run(["python3", "convert.py"], capture_output=True, text=True)
            self.status_msg = "Generated AutoData.java" if result.returncode == 0 else f"Error: {result.stderr.strip()[:80]}"
        else:
            self.status_msg = "convert.py not found in working directory"

    # ═════════════════════════════════════════════════════════════
    # BUILD
    # ═════════════════════════════════════════════════════════════
    def build(self):
        dpg.create_context()
        dpg.create_viewport(title="Path Tracer Pro — DearPyGui",
                            width=INITIAL_WINDOW_W, height=INITIAL_WINDOW_H)

        self.load_background()
        self.load_all()

        # ── File dialogs ──────────────────────────────────────
        with dpg.file_dialog(directory_selector=False, show=False,
                             callback=self._on_open_file, tag="open_file_dialog",
                             width=600, height=400):
            dpg.add_file_extension(".json", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

        with dpg.file_dialog(directory_selector=False, show=False,
                             callback=self._on_save_file, tag="save_file_dialog",
                             width=600, height=400, default_filename="path.json"):
            dpg.add_file_extension(".json", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

        with dpg.file_dialog(directory_selector=False, show=False,
                             callback=self._env_open_file_cb, tag="env_open_dialog",
                             width=600, height=400):
            dpg.add_file_extension(".frctenv", color=(0, 255, 100, 255))
            dpg.add_file_extension(".*")

        # ── Primary window ────────────────────────────────────
        with dpg.window(label="Field", tag="drawlist_window", no_title_bar=True,
                        no_move=True, no_resize=True, no_close=True,
                        no_scrollbar=True, no_scroll_with_mouse=True):

            # ══════════════════════════════════════════════════
            #  MENU BAR
            # ══════════════════════════════════════════════════
            with dpg.menu_bar(tag="main_menu_bar"):

                # ── File ──────────────────────────────────
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="New Path",
                                      callback=lambda: self.new_path())
                    dpg.add_menu_item(label="Open Path...",
                                      shortcut="L",
                                      callback=lambda: dpg.show_item("open_file_dialog"))
                    dpg.add_menu_item(label="Save",
                                      shortcut="S",
                                      callback=lambda: self.save_all())
                    dpg.add_menu_item(label="Save As...",
                                      callback=lambda: dpg.show_item("save_file_dialog"))
                    dpg.add_separator()
                    dpg.add_menu_item(label="New Environment",
                                      callback=lambda: self._env_new())
                    dpg.add_menu_item(label="Open Environment...",
                                      callback=lambda: self._env_open())
                    dpg.add_menu_item(label="Close Environment",
                                      callback=lambda: self._env_close())
                    dpg.add_separator()
                    dpg.add_menu_item(label="Preferences...",
                                      callback=lambda: self._prefs_open())
                    dpg.add_separator()
                    dpg.add_menu_item(label="Exit",
                                      callback=lambda: dpg.stop_dearpygui())

                # ── Edit ──────────────────────────────────
                with dpg.menu(label="Edit"):
                    dpg.add_menu_item(label="Undo",
                                      shortcut="Z",
                                      callback=lambda: self.undo())
                    dpg.add_menu_item(label="Redo",
                                      shortcut="Y",
                                      callback=lambda: self.redo())
                    dpg.add_separator()
                    dpg.add_menu_item(label="Copy",
                                      callback=lambda: self.copy_selection())
                    dpg.add_menu_item(label="Cut",
                                      callback=lambda: self.cut_selection())
                    dpg.add_menu_item(label="Paste",
                                      callback=lambda: self.paste_clipboard())
                    dpg.add_separator()
                    dpg.add_menu_item(label="Clear Path",
                                      shortcut="C",
                                      callback=lambda: (self.push_undo(), self.path_points.clear(),
                                                        setattr(self, 'status_msg', 'Path cleared')))
                    dpg.add_menu_item(label="Clear All Functions",
                                      callback=lambda: (self.push_undo(), self.functions.clear(),
                                                        setattr(self, 'status_msg', 'Functions cleared')))

                # ── View ──────────────────────────────────
                with dpg.menu(label="View"):
                    dpg.add_menu_item(label="Zoom In",    shortcut="+",  callback=lambda: self.zoom_in())
                    dpg.add_menu_item(label="Zoom Out",   shortcut="-",  callback=lambda: self.zoom_out())
                    dpg.add_menu_item(label="Reset Zoom",                callback=lambda: self.zoom_reset())
                    dpg.add_menu_item(label="Fit to Window",             callback=lambda: self.zoom_fit())
                    dpg.add_separator()
                    dpg.add_menu_item(label="Toggle Grid", check=True, default_value=self.show_grid,
                                      tag="menu_toggle_grid",
                                      callback=lambda s, a: setattr(self, 'show_grid', a))
                    dpg.add_menu_item(label="Toggle Path Points", check=True, default_value=self.show_path_points,
                                      tag="menu_toggle_pts",
                                      callback=lambda s, a: setattr(self, 'show_path_points', a))
                    dpg.add_menu_item(label="Toggle Labels", check=True, default_value=self.show_labels,
                                      tag="menu_toggle_labels",
                                      callback=lambda s, a: setattr(self, 'show_labels', a))
                    dpg.add_menu_item(label="Toggle Status Bar", check=True, default_value=self.show_status_bar,
                                      tag="menu_toggle_status",
                                      callback=lambda s, a: setattr(self, 'show_status_bar', a))
                    dpg.add_separator()
                    dpg.add_menu_item(label="Toggle Snap", check=True, default_value=self.snap_enabled,
                                      tag="menu_toggle_snap",
                                      callback=lambda s, a: (setattr(self, 'snap_enabled', a),
                                                             setattr(self, 'status_msg', f"Snap: {'ON' if a else 'OFF'}")))

                # ── Tools ─────────────────────────────────
                with dpg.menu(label="Tools"):
                    dpg.add_menu_item(label="Place Start Position", shortcut="P",
                                      callback=lambda: (setattr(self, 'placing_start', True),
                                                        setattr(self, 'placing_function', False),
                                                        setattr(self, 'status_msg', 'Click to place START')))
                    dpg.add_menu_item(label="Place Function...", shortcut="F",
                                      callback=lambda: self._toggle("function_window"))
                    dpg.add_separator()
                    dpg.add_menu_item(label="Generate AutoData.java",
                                      callback=lambda: self._run_convert())

                # ── Help ──────────────────────────────────
                with dpg.menu(label="Help"):
                    dpg.add_menu_item(label="Keyboard Shortcuts", shortcut="H",
                                      callback=lambda: self._toggle("help_window"))
                    dpg.add_menu_item(label="About",
                                      callback=lambda: self._toggle("about_window"))

            # Canvas
            dpg.add_drawlist(tag="canvas", width=INITIAL_WINDOW_W, height=INITIAL_WINDOW_H)

        # ── Status bar ────────────────────────────────────────
        with dpg.window(label="Status", tag="status_window", no_title_bar=True,
                        no_move=True, no_resize=True, no_close=True,
                        no_scrollbar=True, width=INITIAL_WINDOW_W, height=80,
                        pos=[0, MENU_BAR_HEIGHT]):
            dpg.add_text("", tag="status_text_1")
            dpg.add_text("", tag="status_text_2")
            dpg.add_text("", tag="status_text_3")
            dpg.add_text("", tag="status_text_4")

        # ── Help window ───────────────────────────────────────
        with dpg.window(label="Help — Path Tracer Pro", tag="help_window",
                        show=False, width=560, height=580, pos=[100, 50]):
            dpg.add_text("KEYBOARD SHORTCUTS", color=(100, 200, 255))
            dpg.add_separator()
            dpg.add_spacer(height=5)
            for k, d in [("H","Help"), ("P","Place start"), ("S","Save"), ("L","Load"),
                         ("C","Clear path"), ("G","Toggle snap"), ("F","Function menu"),
                         ("Z","Undo"), ("Y","Redo"), ("ESC","Cancel / close")]:
                dpg.add_text(f"  [{k}]  {d}")
            dpg.add_spacer(height=10)
            dpg.add_text("MOUSE", color=(100, 200, 255))
            dpg.add_separator()
            dpg.add_spacer(height=5)
            for k, d in [("Left drag","Draw path"), ("Right click","Context menu"),
                         ("Middle drag","Pan"), ("Scroll","Zoom")]:
                dpg.add_text(f"  {k}: {d}")
            dpg.add_spacer(height=10)
            dpg.add_text("WORKFLOW", color=(100, 200, 255))
            dpg.add_separator()
            dpg.add_spacer(height=5)
            for line in ["1. P — place START", "2. Right-click START to set rotation",
                         "3. F — add function waypoints", "4. Left-drag to draw path",
                         "5. S — save", "6. Tools > Generate AutoData.java"]:
                dpg.add_text(f"  {line}")
            dpg.add_spacer(height=10)
            dpg.add_text("LEGEND", color=(100, 200, 255))
            dpg.add_separator()
            dpg.add_spacer(height=5)
            dpg.add_text("  White ○ + arrow: Start", color=COL_START)
            dpg.add_text("  Yellow ○: Rotate Only", color=COL_FUNC_ROT)
            dpg.add_text("  Green □: Wait Till Complete", color=COL_FUNC_WAIT)
            dpg.add_text("  Blue □: Run While Moving", color=COL_FUNC_MOVE)
            dpg.add_text("  Red line: Path", color=COL_PATH)

        # ── About window ─────────────────────────────────────
        with dpg.window(label="About", tag="about_window", show=False,
                        width=360, height=180, pos=[250, 200], no_resize=True):
            dpg.add_text("Path Tracer Pro", color=(100, 200, 255))
            dpg.add_text("DearPyGui Edition")
            dpg.add_spacer(height=8)
            dpg.add_text("FTC autonomous path planning tool.")
            dpg.add_text("Draw paths, place functions, export to Java.")
            dpg.add_spacer(height=8)
            dpg.add_text("144×144 in field  •  45° angle snapping")
            dpg.add_spacer(height=8)
            dpg.add_button(label="Close", width=-1,
                           callback=lambda: dpg.configure_item("about_window", show=False))

        # ── Preferences window ────────────────────────────────
        with dpg.window(label="Preferences", tag="prefs_window", show=False,
                        width=400, height=420, pos=[200, 100]):
            dpg.add_text("PATH", color=(100, 200, 255)); dpg.add_separator()
            dpg.add_input_float(label="Step Size (in)", tag="pref_step_size",
                                default_value=self.prefs["step_size"],
                                min_value=0.1, max_value=10.0, step=0.1, width=150)
            dpg.add_input_int(label="Path Thickness (px)", tag="pref_path_thickness",
                              default_value=self.prefs["path_thickness"],
                              min_value=1, max_value=10, step=1, width=150)
            dpg.add_input_int(label="Point Radius (px)", tag="pref_point_radius",
                              default_value=self.prefs["point_radius"],
                              min_value=1, max_value=10, step=1, width=150)
            dpg.add_color_edit(label="Path Color", tag="pref_path_color",
                               default_value=self.prefs["path_color"], no_alpha=False, width=150)
            dpg.add_spacer(height=10)
            dpg.add_text("GRID", color=(100, 200, 255)); dpg.add_separator()
            dpg.add_input_int(label="Snap Size (in)", tag="pref_snap_inches",
                              default_value=self.prefs["snap_inches"],
                              min_value=1, max_value=72, step=4, width=150)
            dpg.add_input_int(label="Grid Offset (in)", tag="pref_grid_offset",
                              default_value=self.prefs["grid_offset"],
                              min_value=-72, max_value=72, step=4, width=150)
            dpg.add_spacer(height=10)
            dpg.add_text("GENERAL", color=(100, 200, 255)); dpg.add_separator()
            dpg.add_input_int(label="Default Zoom", tag="pref_default_scale",
                              default_value=self.prefs["default_scale"],
                              min_value=MIN_SCALE, max_value=MAX_SCALE, step=1, width=150)
            dpg.add_checkbox(label="Auto-save on exit", tag="pref_auto_save",
                             default_value=self.prefs["auto_save"])
            dpg.add_spacer(height=15)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply & Save", width=150, callback=lambda: self._prefs_apply())
                dpg.add_button(label="Cancel", width=150,
                               callback=lambda: dpg.configure_item("prefs_window", show=False))

        # ── Function placement window ─────────────────────────
        with dpg.window(label="Function Placement", tag="function_window",
                        show=False, width=320, height=400, pos=[200, 100]):
            dpg.add_text("ACTION TYPE", color=(100, 200, 255)); dpg.add_separator()
            dpg.add_button(label="Rotate Only (R)", width=-1,
                           callback=lambda: self.func_menu_set_action("rotate_only"))
            dpg.add_button(label="Function (F)", width=-1,
                           callback=lambda: self.func_menu_set_action("function"))
            dpg.add_spacer(height=10)
            dpg.add_text("FUNCTION TYPE", color=(100, 200, 255)); dpg.add_separator()
            dpg.add_button(label="Wait Till Complete (W)", width=-1,
                           callback=lambda: self.func_menu_set_type("wait_till"))
            dpg.add_button(label="Run While Moving (M)", width=-1,
                           callback=lambda: self.func_menu_set_type("run_while_moving"))
            dpg.add_spacer(height=10)
            dpg.add_text("TEMPLATES", color=(100, 200, 255)); dpg.add_separator()
            with dpg.group(tag="template_list_group"):
                pass
            self._rebuild_template_list()
            dpg.add_spacer(height=10)
            dpg.add_text("Add new template:", color=(180, 180, 180))
            with dpg.group(horizontal=True):
                dpg.add_input_text(tag="new_template_input", width=200, on_enter=True,
                                   callback=self.func_menu_add_template)
                dpg.add_button(label="Add", callback=self.func_menu_add_template)

        # ── Context menus ─────────────────────────────────────
        with dpg.window(tag="ctx_start", show=False, popup=True, no_title_bar=True, width=220):
            dpg.add_menu_item(label="Delete Start", callback=lambda: self.ctx_start_delete())
            dpg.add_separator()
            dpg.add_menu_item(label="Rotate +45°", callback=lambda: self.ctx_start_rotate(45))
            dpg.add_menu_item(label="Rotate +90°", callback=lambda: self.ctx_start_rotate(90))
            dpg.add_menu_item(label="Rotate -45°", callback=lambda: self.ctx_start_rotate(-45))
            dpg.add_separator()
            for deg in [0, 90, 180, 270, 315]:
                dpg.add_menu_item(label=f"Set {deg}°", callback=lambda d=deg: self.ctx_start_set_rot(d))

        with dpg.window(tag="ctx_func", show=False, popup=True, no_title_bar=True, width=240):
            dpg.add_menu_item(label="Delete Function", callback=lambda: self.ctx_func_delete())
            dpg.add_menu_item(label="Copy Function", callback=lambda: self.copy_selection())
            dpg.add_menu_item(label="Cut Function", callback=lambda: self.cut_selection())
            dpg.add_menu_item(label="Toggle Type", tag="ctx_func_toggle_type",
                              callback=lambda: self.ctx_func_toggle_type())
            dpg.add_separator()
            dpg.add_menu_item(label="Rotate +45°", callback=lambda: self.ctx_func_rotate(45))
            dpg.add_menu_item(label="Rotate +90°", callback=lambda: self.ctx_func_rotate(90))
            dpg.add_menu_item(label="Rotate -45°", callback=lambda: self.ctx_func_rotate(-45))
            dpg.add_menu_item(label="Set Rotation 0°",
                              callback=lambda: (self.push_undo(), setattr(self._ctx_func, 'rotation', 0))
                              if hasattr(self, '_ctx_func') else None)

        with dpg.window(tag="ctx_general", show=False, popup=True, no_title_bar=True, width=180):
            dpg.add_menu_item(label="Clear Path",
                              callback=lambda: (self.push_undo(), self.path_points.clear(),
                                                setattr(self, 'status_msg', 'Path cleared')))
            dpg.add_menu_item(label="Paste", callback=lambda: self.paste_clipboard())
            dpg.add_separator()
            dpg.add_menu_item(label="Save", callback=lambda: self.save_all())
            dpg.add_menu_item(label="Load", callback=lambda: self.load_all())
            dpg.add_menu_item(label="Toggle Snap",
                              callback=lambda: (setattr(self, 'snap_enabled', not self.snap_enabled),
                                                setattr(self, 'status_msg', f"Snap: {'ON' if self.snap_enabled else 'OFF'}")))

        # ── Input handlers ────────────────────────────────────
        with dpg.handler_registry():
            dpg.add_mouse_down_handler(callback=self.on_mouse_down)
            dpg.add_mouse_release_handler(callback=self.on_mouse_release)
            dpg.add_mouse_move_handler(callback=self.on_mouse_move)
            dpg.add_mouse_wheel_handler(callback=self.on_mouse_wheel)
            dpg.add_key_press_handler(callback=self.on_key_press)
            # Environment editor handlers
            dpg.add_mouse_down_handler(callback=self.env_editor._on_mouse_down)
            dpg.add_mouse_release_handler(callback=self.env_editor._on_mouse_release)
            dpg.add_mouse_move_handler(callback=self.env_editor._on_mouse_move)
            dpg.add_mouse_wheel_handler(callback=self.env_editor._on_mouse_wheel)
            dpg.add_key_press_handler(callback=self.env_editor._on_key)

        # ── Theme ─────────────────────────────────────────────
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (30, 30, 30, 255))
                dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg, (35, 35, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (40, 40, 50, 255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (50, 50, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 60, 80, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (70, 80, 110, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (90, 100, 130, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (40, 45, 55, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Header, (50, 55, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (65, 70, 90, 255))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (80, 85, 110, 255))
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (40, 40, 50, 240))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_PopupRounding, 4)
        dpg.bind_theme(global_theme)

        with dpg.theme() as status_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (20, 20, 20, 180))
        dpg.bind_item_theme("status_window", status_theme)

        dpg.setup_dearpygui()
        dpg.show_viewport()

    # ── Run loop ─────────────────────────────────────────────────
    def update_status(self):
        dpg.configure_item("status_window", show=self.show_status_bar)
        if not self.show_status_bar:
            return
        snap = "ON" if self.snap_enabled else "OFF"
        start = (f"({self.start_pos[0]:.0f}, {self.start_pos[1]:.0f}) @ {self.start_pos[2]}°"
                 if self.start_pos else "NOT SET — Press P")
        mode = ""
        if self.placing_start:
            mode = " | MODE: Placing Start"
        elif self.placing_function:
            mode = f" | MODE: Placing {self.selected_action}"
        dpg.set_value("status_text_1",
                      f"Zoom: {self.scale}x  |  Snap: {snap} ({self.snap_inches}in)  |  "
                      f"Undo: {len(self.undo_stack)}  Redo: {len(self.redo_stack)}")
        dpg.set_value("status_text_2",
                      f"Points: {len(self.path_points)}  |  Functions: {len(self.functions)}  |  "
                      f"Start: {start}{mode}")
        dpg.set_value("status_text_3", self.status_msg)
        dpg.set_value("status_text_4",
                      f"File: {os.path.basename(self.current_path_file) if self.current_path_file else '(unsaved)'}"
                      f"  |  Env: {self.active_env.metadata.name if self.active_env else 'None'}")

    def resize_to_viewport(self):
        vw = dpg.get_viewport_client_width()
        vh = dpg.get_viewport_client_height()
        dpg.configure_item("drawlist_window", width=vw, height=vh)
        dpg.configure_item("canvas", width=vw, height=vh)
        dpg.configure_item("status_window", width=vw)

    def run(self):
        self.build()
        while dpg.is_dearpygui_running():
            self.resize_to_viewport()
            self.update_status()
            self.render()
            # Environment editor
            self.active_env = self.env_editor.get_env()
            self.env_editor.resize()
            self.env_editor.render()
            dpg.render_dearpygui_frame()
        if self.prefs.get("auto_save"):
            self.save_all()
        dpg.destroy_context()


if __name__ == "__main__":
    PathTracer().run()