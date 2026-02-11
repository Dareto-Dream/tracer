#!/usr/bin/env python3
"""
environment.py — FRC/FTC Environment definition and visual editor.
File format: .frctenv (JSON)
"""

import dearpygui.dearpygui as dpg
import json
import math
import os
from typing import List, Dict, Optional, Tuple, Any

# ── Default palette ──────────────────────────────────────────────────
PAL_OBS      = [180, 60, 60, 180]
PAL_ZONE_RED = [255, 40, 40, 50]
PAL_ZONE_BLU = [40, 40, 255, 50]
PAL_ZONE_NEU = [200, 200, 200, 40]
PAL_WAYPOINT = [255, 200, 0, 255]
PAL_START_R  = [255, 80, 80, 200]
PAL_START_B  = [80, 80, 255, 200]

EDITOR_BG    = (25, 25, 30, 255)
EDITOR_GRID  = (45, 45, 50, 255)

_uid_counter = 0
def _uid(prefix="obj"):
    global _uid_counter
    _uid_counter += 1
    return f"{prefix}_{_uid_counter}"


# ═════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ═════════════════════════════════════════════════════════════════════

class EnvMetadata:
    """Top-level field and robot metadata."""
    def __init__(self):
        self.name = "Untitled Environment"
        self.season = ""
        self.description = ""
        self.field_width_in = 144
        self.field_height_in = 144
        self.inches_per_tile = 24
        self.tile_columns = 6
        self.tile_rows = 6
        self.robot_width_in = 18
        self.robot_length_in = 18
        self.background_image = ""

    def to_dict(self):
        return self.__dict__.copy()

    @staticmethod
    def from_dict(d):
        m = EnvMetadata()
        for k, v in d.items():
            if hasattr(m, k):
                setattr(m, k, v)
        return m


class StartPosition:
    def __init__(self, **kw):
        self.id = kw.get("id", _uid("start"))
        self.label = kw.get("label", "Start")
        self.alliance = kw.get("alliance", "red")
        self.x = kw.get("x", 12.0)
        self.y = kw.get("y", 12.0)
        self.rotation = kw.get("rotation", 0.0)

    def to_dict(self):
        return {"id": self.id, "label": self.label, "alliance": self.alliance,
                "x": self.x, "y": self.y, "rotation": self.rotation}

    @staticmethod
    def from_dict(d):
        return StartPosition(**d)


class Obstruction:
    """Something the robot cannot cross."""
    def __init__(self, **kw):
        self.id = kw.get("id", _uid("obs"))
        self.label = kw.get("label", "Obstruction")
        self.shape = kw.get("shape", "rectangle")
        self.x = kw.get("x", 0.0)
        self.y = kw.get("y", 0.0)
        self.width = kw.get("width", 24.0)
        self.height = kw.get("height", 24.0)
        self.radius = kw.get("radius", 12.0)
        self.x2 = kw.get("x2", 24.0)
        self.y2 = kw.get("y2", 0.0)
        self.rotation = kw.get("rotation", 0.0)
        self.color = kw.get("color", list(PAL_OBS))

    def to_dict(self):
        base = {"id": self.id, "label": self.label, "shape": self.shape,
                "x": self.x, "y": self.y, "rotation": self.rotation, "color": self.color}
        if self.shape == "rectangle":
            base.update({"width": self.width, "height": self.height})
        elif self.shape == "circle":
            base["radius"] = self.radius
        elif self.shape == "line":
            base.update({"x2": self.x2, "y2": self.y2})
        return base

    @staticmethod
    def from_dict(d):
        return Obstruction(**d)


class Zone:
    """A colored region (scoring zone, parking zone, etc.)."""
    def __init__(self, **kw):
        self.id = kw.get("id", _uid("zone"))
        self.label = kw.get("label", "Zone")
        self.x = kw.get("x", 0.0)
        self.y = kw.get("y", 0.0)
        self.width = kw.get("width", 48.0)
        self.height = kw.get("height", 48.0)
        self.color = kw.get("color", list(PAL_ZONE_NEU))
        self.alliance = kw.get("alliance", "neutral")

    def to_dict(self):
        return {"id": self.id, "label": self.label, "x": self.x, "y": self.y,
                "width": self.width, "height": self.height,
                "color": self.color, "alliance": self.alliance}

    @staticmethod
    def from_dict(d):
        return Zone(**d)


class Waypoint:
    """A named point of interest on the field."""
    def __init__(self, **kw):
        self.id = kw.get("id", _uid("wp"))
        self.label = kw.get("label", "Waypoint")
        self.x = kw.get("x", 72.0)
        self.y = kw.get("y", 72.0)
        self.radius = kw.get("radius", 4.0)
        self.color = kw.get("color", list(PAL_WAYPOINT))

    def to_dict(self):
        return {"id": self.id, "label": self.label, "x": self.x, "y": self.y,
                "radius": self.radius, "color": self.color}

    @staticmethod
    def from_dict(d):
        return Waypoint(**d)


class ValidFunction:
    """A function name allowed in paths for this environment."""
    def __init__(self, **kw):
        self.name = kw.get("name", "unnamed")
        self.description = kw.get("description", "")
        self.color = kw.get("color", [0, 255, 0, 255])

    def to_dict(self):
        return {"name": self.name, "description": self.description, "color": self.color}

    @staticmethod
    def from_dict(d):
        return ValidFunction(**d)


# ── Top-level environment ────────────────────────────────────────────

class Environment:
    FORMAT_VERSION = "1.0"

    def __init__(self):
        self.metadata = EnvMetadata()
        self.start_positions: List[StartPosition] = []
        self.obstructions: List[Obstruction] = []
        self.zones: List[Zone] = []
        self.waypoints: List[Waypoint] = []
        self.valid_functions: List[ValidFunction] = []
        self.filepath: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "format_version": self.FORMAT_VERSION,
            "metadata": self.metadata.to_dict(),
            "start_positions": [s.to_dict() for s in self.start_positions],
            "obstructions": [o.to_dict() for o in self.obstructions],
            "zones": [z.to_dict() for z in self.zones],
            "waypoints": [w.to_dict() for w in self.waypoints],
            "valid_functions": [f.to_dict() for f in self.valid_functions],
        }

    @staticmethod
    def from_dict(d) -> "Environment":
        env = Environment()
        env.metadata = EnvMetadata.from_dict(d.get("metadata", {}))
        env.start_positions = [StartPosition.from_dict(s) for s in d.get("start_positions", [])]
        env.obstructions = [Obstruction.from_dict(o) for o in d.get("obstructions", [])]
        env.zones = [Zone.from_dict(z) for z in d.get("zones", [])]
        env.waypoints = [Waypoint.from_dict(w) for w in d.get("waypoints", [])]
        env.valid_functions = [ValidFunction.from_dict(f) for f in d.get("valid_functions", [])]
        return env

    def save(self, filepath: Optional[str] = None):
        fp = filepath or self.filepath
        if not fp:
            raise ValueError("No filepath specified")
        if not fp.endswith(".frctenv"):
            fp += ".frctenv"
        with open(fp, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        self.filepath = fp

    @staticmethod
    def load(filepath: str) -> "Environment":
        with open(filepath, "r") as f:
            data = json.load(f)
        env = Environment.from_dict(data)
        env.filepath = filepath
        return env

    @staticmethod
    def default() -> "Environment":
        """Create a sensible FTC default environment."""
        env = Environment()
        env.metadata.name = "FTC Field"
        env.metadata.season = "2024-2025"
        env.metadata.field_width_in = 144
        env.metadata.field_height_in = 144
        env.metadata.inches_per_tile = 24
        env.metadata.tile_columns = 6
        env.metadata.tile_rows = 6
        env.metadata.robot_width_in = 18
        env.metadata.robot_length_in = 18
        env.start_positions = [
            StartPosition(id="red_close",  label="Red Close",  alliance="red",  x=12, y=132, rotation=0),
            StartPosition(id="red_far",    label="Red Far",    alliance="red",  x=36, y=132, rotation=0),
            StartPosition(id="blue_close", label="Blue Close", alliance="blue", x=132, y=12, rotation=180),
            StartPosition(id="blue_far",   label="Blue Far",   alliance="blue", x=108, y=12, rotation=180),
        ]
        env.valid_functions = [
            ValidFunction(name="intake",  description="Pick up game element", color=[0, 220, 100, 255]),
            ValidFunction(name="outtake", description="Release game element", color=[220, 100, 0, 255]),
            ValidFunction(name="score",   description="Score in target",      color=[255, 215, 0, 255]),
            ValidFunction(name="park",    description="Park robot",           color=[100, 100, 255, 255]),
        ]
        return env


# ═════════════════════════════════════════════════════════════════════
#  VISUAL EDITOR
# ═════════════════════════════════════════════════════════════════════

class EnvironmentEditor:
    TOOL_SELECT   = "select"
    TOOL_START    = "start"
    TOOL_OBS_RECT = "obs_rect"
    TOOL_OBS_CIRC = "obs_circle"
    TOOL_OBS_LINE = "obs_line"
    TOOL_ZONE     = "zone"
    TOOL_WAYPOINT = "waypoint"

    def __init__(self, on_save_callback=None, on_close_callback=None):
        self.env: Optional[Environment] = None
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback
        self.scale = 4.0
        self.offset_x = 250.0
        self.offset_y = 40.0
        self.tool = self.TOOL_SELECT
        self.selected_obj = None
        self.selected_type: Optional[str] = None
        self.dragging = False
        self.drag_start_field = (0, 0)
        self.drag_obj_origin = (0, 0)
        self.placing = False
        self.place_anchor = None
        self.panning = False
        self.pan_start = None
        self.pan_offset_start = None
        self.win_tag = "env_editor_window"
        self.canvas_tag = "env_canvas"
        self.panel_tag = "env_panel"
        self.built = False

    def _f2s(self, fx, fy):
        return fx * self.scale + self.offset_x, fy * self.scale + self.offset_y

    def _s2f(self, sx, sy):
        return (sx - self.offset_x) / self.scale, (sy - self.offset_y) / self.scale

    def _local_mouse(self):
        gpos = dpg.get_mouse_pos(local=False)
        wpos = dpg.get_item_pos(self.canvas_tag)
        return gpos[0] - wpos[0], gpos[1] - wpos[1]

    def open_new(self):
        self.env = Environment.default()
        self._show()

    def open_file(self, filepath):
        self.env = Environment.load(filepath)
        self._show()

    def close(self):
        self.env = None
        self.selected_obj = None
        self.selected_type = None
        if self.built:
            dpg.configure_item(self.win_tag, show=False)
            dpg.configure_item("env_props_window", show=False)
        if self.on_close_callback:
            self.on_close_callback()

    def _show(self):
        if not self.built:
            self._build()
        self._refresh_lists()
        self._refresh_properties()
        self._refresh_metadata_fields()
        dpg.configure_item(self.win_tag, show=True)

    def get_env(self) -> Optional[Environment]:
        return self.env

    def save(self):
        if not self.env:
            return
        if self.env.filepath:
            self.env.save()
            if self.on_save_callback:
                self.on_save_callback(self.env)
        else:
            dpg.show_item("env_save_dialog")

    def save_as(self):
        dpg.show_item("env_save_dialog")

    def _on_save_dialog(self, sender, app_data):
        if app_data and "file_path_name" in app_data:
            fp = app_data["file_path_name"]
            if not fp.endswith(".frctenv"):
                fp += ".frctenv"
            self.env.save(fp)
            dpg.set_item_label(self.win_tag, f"Environment Editor — {os.path.basename(fp)}")
            if self.on_save_callback:
                self.on_save_callback(self.env)

    def _on_open_dialog(self, sender, app_data):
        if app_data and "file_path_name" in app_data:
            self.open_file(app_data["file_path_name"])

    def _select(self, obj, obj_type):
        self.selected_obj = obj
        self.selected_type = obj_type
        self._refresh_properties()

    def _deselect(self):
        self.selected_obj = None
        self.selected_type = None
        self._refresh_properties()

    def _hit_test(self, fx, fy):
        if not self.env:
            return None, None
        rw = self.env.metadata.robot_width_in / 2
        rl = self.env.metadata.robot_length_in / 2
        for sp in reversed(self.env.start_positions):
            if abs(fx - sp.x) < rw and abs(fy - sp.y) < rl:
                return sp, "start"
        for wp in reversed(self.env.waypoints):
            if math.hypot(fx - wp.x, fy - wp.y) < max(wp.radius, 4):
                return wp, "wp"
        for obs in reversed(self.env.obstructions):
            if obs.shape == "rectangle":
                if obs.x <= fx <= obs.x + obs.width and obs.y <= fy <= obs.y + obs.height:
                    return obs, "obs"
            elif obs.shape == "circle":
                if math.hypot(fx - obs.x, fy - obs.y) <= obs.radius:
                    return obs, "obs"
            elif obs.shape == "line":
                dx, dy = obs.x2 - obs.x, obs.y2 - obs.y
                ln = math.hypot(dx, dy) or 1
                t = max(0, min(1, ((fx - obs.x) * dx + (fy - obs.y) * dy) / (ln * ln)))
                px, py = obs.x + t * dx, obs.y + t * dy
                if math.hypot(fx - px, fy - py) < 4:
                    return obs, "obs"
        for z in reversed(self.env.zones):
            if z.x <= fx <= z.x + z.width and z.y <= fy <= z.y + z.height:
                return z, "zone"
        return None, None

    def _delete_selected(self):
        if not self.selected_obj or not self.env:
            return
        lists = {"start": self.env.start_positions, "obs": self.env.obstructions,
                 "zone": self.env.zones, "wp": self.env.waypoints}
        lst = lists.get(self.selected_type)
        if lst is not None:
            lst[:] = [o for o in lst if o is not self.selected_obj]
        self._deselect()
        self._refresh_lists()

    # ── Mouse ────────────────────────────────────────────────────
    def _on_mouse_down(self, sender, app_data):
        if not self.env or not self.built or not dpg.is_item_shown(self.win_tag):
            return
        if not dpg.is_item_hovered(self.win_tag):
            return
        button = app_data
        mx, my = self._local_mouse()
        fx, fy = self._s2f(mx, my)

        if button == 0:
            if self.tool == self.TOOL_SELECT:
                obj, otype = self._hit_test(fx, fy)
                if obj:
                    self._select(obj, otype)
                    self.dragging = True
                    self.drag_start_field = (fx, fy)
                    self.drag_obj_origin = (obj.x, obj.y)
                else:
                    self._deselect()
            elif self.tool == self.TOOL_START:
                sp = StartPosition(x=round(fx), y=round(fy), rotation=0,
                                   label=f"Start {len(self.env.start_positions)+1}", alliance="red")
                self.env.start_positions.append(sp)
                self._select(sp, "start")
                self._refresh_lists()
                self.tool = self.TOOL_SELECT
                self._update_tool_label()
            elif self.tool == self.TOOL_WAYPOINT:
                wp = Waypoint(x=round(fx), y=round(fy),
                              label=f"Waypoint {len(self.env.waypoints)+1}")
                self.env.waypoints.append(wp)
                self._select(wp, "wp")
                self._refresh_lists()
                self.tool = self.TOOL_SELECT
                self._update_tool_label()
            elif self.tool in (self.TOOL_OBS_RECT, self.TOOL_OBS_CIRC,
                               self.TOOL_OBS_LINE, self.TOOL_ZONE):
                if not self.placing:
                    self.placing = True
                    self.place_anchor = (fx, fy)
                else:
                    self._finish_placement(fx, fy)
        elif button == 1:
            if self.placing:
                self.placing = False
                self.place_anchor = None
            else:
                self.tool = self.TOOL_SELECT
                self._update_tool_label()
        elif button == 2:
            self.panning = True
            gpos = dpg.get_mouse_pos(local=False)
            self.pan_start = (gpos[0], gpos[1])
            self.pan_offset_start = (self.offset_x, self.offset_y)

    def _on_mouse_release(self, sender, app_data):
        if not self.built or not dpg.is_item_shown(self.win_tag):
            return
        if app_data == 0:
            if self.dragging:
                self.dragging = False
                self._refresh_properties()
        elif app_data == 2:
            self.panning = False

    def _on_mouse_move(self, sender, app_data):
        if not self.env or not self.built or not dpg.is_item_shown(self.win_tag):
            return
        if self.panning and self.pan_start:
            gpos = dpg.get_mouse_pos(local=False)
            self.offset_x = self.pan_offset_start[0] + gpos[0] - self.pan_start[0]
            self.offset_y = self.pan_offset_start[1] + gpos[1] - self.pan_start[1]
        if self.dragging and self.selected_obj:
            mx, my = self._local_mouse()
            fx, fy = self._s2f(mx, my)
            dx = fx - self.drag_start_field[0]
            dy = fy - self.drag_start_field[1]
            self.selected_obj.x = round(self.drag_obj_origin[0] + dx, 1)
            self.selected_obj.y = round(self.drag_obj_origin[1] + dy, 1)

    def _on_mouse_wheel(self, sender, app_data):
        if not self.env or not self.built or not dpg.is_item_shown(self.win_tag):
            return
        if not dpg.is_item_hovered(self.win_tag):
            return
        mx, my = self._local_mouse()
        fx, fy = self._s2f(mx, my)
        old = self.scale
        self.scale = max(1, min(15, self.scale + (0.5 if app_data > 0 else -0.5)))
        if old != self.scale:
            nsx, nsy = self._f2s(fx, fy)
            self.offset_x += mx - nsx
            self.offset_y += my - nsy

    def _finish_placement(self, fx, fy):
        ax, ay = self.place_anchor
        x0, y0 = min(ax, fx), min(ay, fy)
        w, h = abs(fx - ax), abs(fy - ay)
        if self.tool == self.TOOL_OBS_RECT:
            w = max(w, 12); h = max(h, 12)
            obs = Obstruction(shape="rectangle", x=round(x0), y=round(y0),
                              width=round(w), height=round(h),
                              label=f"Obstacle {len(self.env.obstructions)+1}")
            self.env.obstructions.append(obs)
            self._select(obs, "obs")
        elif self.tool == self.TOOL_OBS_CIRC:
            r = max(4, round(math.hypot(fx - ax, fy - ay)))
            obs = Obstruction(shape="circle", x=round(ax), y=round(ay), radius=r,
                              label=f"Obstacle {len(self.env.obstructions)+1}")
            self.env.obstructions.append(obs)
            self._select(obs, "obs")
        elif self.tool == self.TOOL_OBS_LINE:
            obs = Obstruction(shape="line", x=round(ax), y=round(ay),
                              x2=round(fx), y2=round(fy),
                              label=f"Wall {len(self.env.obstructions)+1}")
            self.env.obstructions.append(obs)
            self._select(obs, "obs")
        elif self.tool == self.TOOL_ZONE:
            w = max(w, 24); h = max(h, 24)
            zone = Zone(x=round(x0), y=round(y0), width=round(w), height=round(h),
                        label=f"Zone {len(self.env.zones)+1}")
            self.env.zones.append(zone)
            self._select(zone, "zone")
        self.placing = False
        self.place_anchor = None
        self.tool = self.TOOL_SELECT
        self._update_tool_label()
        self._refresh_lists()

    def _on_key(self, sender, app_data):
        if not self.env or not self.built or not dpg.is_item_shown(self.win_tag):
            return
        if app_data in (dpg.mvKey_Delete, dpg.mvKey_Back):
            self._delete_selected()

    # ── Rendering ────────────────────────────────────────────────
    def render(self):
        if not self.env or not self.built or not dpg.is_item_shown(self.win_tag):
            return
        dl = self.canvas_tag
        dpg.delete_item(dl, children_only=True)
        fw = self.env.metadata.field_width_in
        fh = self.env.metadata.field_height_in
        ipt = self.env.metadata.inches_per_tile

        # Field rect
        x0, y0 = self._f2s(0, 0)
        x1, y1 = self._f2s(fw, fh)
        dpg.draw_rectangle((x0, y0), (x1, y1), color=(60,60,60,255), fill=(40,40,45,255), parent=dl)

        # Tile grid
        spacing = ipt * self.scale
        if spacing >= 4:
            gx = x0
            while gx <= x1:
                dpg.draw_line((gx, y0), (gx, y1), color=EDITOR_GRID, thickness=1, parent=dl)
                gx += spacing
            gy = y0
            while gy <= y1:
                dpg.draw_line((x0, gy), (x1, gy), color=EDITOR_GRID, thickness=1, parent=dl)
                gy += spacing

        # Zones
        for z in self.env.zones:
            za, zb = self._f2s(z.x, z.y), self._f2s(z.x + z.width, z.y + z.height)
            fill = tuple(z.color)
            border = tuple(c if i < 3 else 120 for i, c in enumerate(z.color))
            dpg.draw_rectangle(za, zb, color=border, fill=fill, parent=dl)
            dpg.draw_text((za[0]+4, za[1]+4), z.label, color=(255,255,255,180), size=11, parent=dl)
            if self.selected_obj is z:
                dpg.draw_rectangle((za[0]-2,za[1]-2),(zb[0]+2,zb[1]+2),
                                   color=(255,255,0,200), thickness=2, parent=dl)

        # Obstructions
        for obs in self.env.obstructions:
            col = tuple(obs.color)
            sel = self.selected_obj is obs
            if obs.shape == "rectangle":
                a, b = self._f2s(obs.x, obs.y), self._f2s(obs.x+obs.width, obs.y+obs.height)
                dpg.draw_rectangle(a, b, color=col, fill=col, parent=dl)
                dpg.draw_text((a[0]+2, a[1]+2), obs.label, color=(255,255,255,200), size=10, parent=dl)
                if sel:
                    dpg.draw_rectangle((a[0]-2,a[1]-2),(b[0]+2,b[1]+2),
                                       color=(255,255,0,200), thickness=2, parent=dl)
            elif obs.shape == "circle":
                cx, cy = self._f2s(obs.x, obs.y)
                r = obs.radius * self.scale
                dpg.draw_circle((cx,cy), r, color=col, fill=col, parent=dl)
                dpg.draw_text((cx-20, cy-r-16), obs.label, color=(255,255,255,200), size=10, parent=dl)
                if sel:
                    dpg.draw_circle((cx,cy), r+3, color=(255,255,0,200), thickness=2, parent=dl)
            elif obs.shape == "line":
                a, b = self._f2s(obs.x, obs.y), self._f2s(obs.x2, obs.y2)
                dpg.draw_line(a, b, color=col, thickness=max(3, int(3*self.scale)), parent=dl)
                mid = ((a[0]+b[0])/2, (a[1]+b[1])/2 - 14)
                dpg.draw_text(mid, obs.label, color=(255,255,255,200), size=10, parent=dl)
                if sel:
                    dpg.draw_line(a, b, color=(255,255,0,200), thickness=max(5, int(5*self.scale)), parent=dl)

        # Waypoints
        for wp in self.env.waypoints:
            wx, wy = self._f2s(wp.x, wp.y)
            r = max(3, wp.radius * self.scale)
            dpg.draw_circle((wx,wy), r, color=tuple(wp.color), fill=tuple(wp.color), parent=dl)
            dpg.draw_text((wx+r+3, wy-6), wp.label, color=tuple(wp.color), size=11, parent=dl)
            if self.selected_obj is wp:
                dpg.draw_circle((wx,wy), r+3, color=(255,255,0,200), thickness=2, parent=dl)

        # Start positions
        rw = self.env.metadata.robot_width_in
        rl = self.env.metadata.robot_length_in
        for sp in self.env.start_positions:
            sx, sy = self._f2s(sp.x, sp.y)
            hw, hl = rw/2*self.scale, rl/2*self.scale
            col = PAL_START_R if sp.alliance == "red" else PAL_START_B if sp.alliance == "blue" else [200,200,200,180]
            col = tuple(col)
            dpg.draw_rectangle((sx-hw, sy-hl), (sx+hw, sy+hl), color=col, fill=(*col[:3],60), parent=dl)
            a = math.radians(sp.rotation)
            al = max(hw, hl) + 8
            ex, ey = sx + math.cos(a)*al, sy + math.sin(a)*al
            dpg.draw_line((sx,sy), (ex,ey), color=col, thickness=2, parent=dl)
            asz = 7; la = a + math.radians(150); ra = a - math.radians(150)
            dpg.draw_triangle((ex,ey),(ex+math.cos(la)*asz,ey+math.sin(la)*asz),
                              (ex+math.cos(ra)*asz,ey+math.sin(ra)*asz), color=col, fill=col, parent=dl)
            dpg.draw_text((sx-hw, sy-hl-16), sp.label, color=col, size=11, parent=dl)
            if self.selected_obj is sp:
                dpg.draw_rectangle((sx-hw-3,sy-hl-3),(sx+hw+3,sy+hl+3),
                                   color=(255,255,0,200), thickness=2, parent=dl)

        # Placement preview
        if self.placing and self.place_anchor and dpg.is_item_hovered(self.win_tag):
            mx, my = self._local_mouse()
            fx, fy = self._s2f(mx, my)
            ax, ay = self.place_anchor
            pc = (255,255,255,100)
            if self.tool == self.TOOL_OBS_RECT:
                dpg.draw_rectangle(self._f2s(min(ax,fx),min(ay,fy)),
                                   self._f2s(max(ax,fx),max(ay,fy)), color=pc, thickness=2, parent=dl)
            elif self.tool == self.TOOL_OBS_CIRC:
                cx, cy = self._f2s(ax, ay)
                r = math.hypot(fx-ax, fy-ay) * self.scale
                dpg.draw_circle((cx,cy), max(2,r), color=pc, thickness=2, parent=dl)
            elif self.tool == self.TOOL_OBS_LINE:
                dpg.draw_line(self._f2s(ax,ay), self._f2s(fx,fy), color=pc, thickness=2, parent=dl)
            elif self.tool == self.TOOL_ZONE:
                dpg.draw_rectangle(self._f2s(min(ax,fx),min(ay,fy)),
                                   self._f2s(max(ax,fx),max(ay,fy)),
                                   color=(100,200,255,80), fill=(100,200,255,30), parent=dl)

        # Cursor coords
        if dpg.is_item_hovered(self.win_tag):
            mx, my = self._local_mouse()
            fx, fy = self._s2f(mx, my)
            if 0 <= fx <= fw and 0 <= fy <= fh:
                dpg.draw_text((mx+15, my-5), f"({fx:.1f}, {fy:.1f})",
                              color=(200,200,200,180), size=11, parent=dl)

    def render_on_main(self, dl, f2s_func):
        """Draw environment objects onto the path tracer's main drawlist."""
        if not self.env:
            return
        env = self.env
        for z in env.zones:
            a, b = f2s_func(z.x, z.y), f2s_func(z.x+z.width, z.y+z.height)
            dpg.draw_rectangle(a, b, color=tuple(z.color[:3])+(80,), fill=tuple(z.color), parent=dl)
        for obs in env.obstructions:
            col = tuple(obs.color)
            if obs.shape == "rectangle":
                dpg.draw_rectangle(f2s_func(obs.x,obs.y),
                                   f2s_func(obs.x+obs.width,obs.y+obs.height),
                                   color=col, fill=col, parent=dl)
            elif obs.shape == "circle":
                cx, cy = f2s_func(obs.x, obs.y)
                rx, _ = f2s_func(obs.x+obs.radius, obs.y)
                dpg.draw_circle((cx,cy), max(2, rx-cx), color=col, fill=col, parent=dl)
            elif obs.shape == "line":
                dpg.draw_line(f2s_func(obs.x,obs.y), f2s_func(obs.x2,obs.y2),
                              color=col, thickness=3, parent=dl)
        for wp in env.waypoints:
            wx, wy = f2s_func(wp.x, wp.y)
            rx, _ = f2s_func(wp.x+wp.radius, wp.y)
            dpg.draw_circle((wx,wy), max(2, rx-wx), color=tuple(wp.color), fill=tuple(wp.color), parent=dl)

    # ── Build GUI ────────────────────────────────────────────────
    def _build(self):
        if self.built:
            return
        self.built = True

        with dpg.file_dialog(directory_selector=False, show=False,
                             callback=self._on_save_dialog, tag="env_save_dialog",
                             width=600, height=400, default_filename="field.frctenv"):
            dpg.add_file_extension(".frctenv", color=(0,255,100,255))
            dpg.add_file_extension(".*")

        with dpg.window(label="Environment Editor", tag=self.win_tag,
                        show=False, width=1100, height=750, pos=[40, 30],
                        on_close=lambda: self.close()):
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="Save", callback=lambda: self.save())
                    dpg.add_menu_item(label="Save As...", callback=lambda: self.save_as())
                    dpg.add_separator()
                    dpg.add_menu_item(label="Close", callback=lambda: self.close())
                with dpg.menu(label="Edit"):
                    dpg.add_menu_item(label="Delete Selected", shortcut="Del",
                                      callback=lambda: self._delete_selected())
                with dpg.menu(label="Add"):
                    dpg.add_menu_item(label="Start Position", callback=lambda: self._set_tool(self.TOOL_START))
                    dpg.add_menu_item(label="Obstacle (Rectangle)", callback=lambda: self._set_tool(self.TOOL_OBS_RECT))
                    dpg.add_menu_item(label="Obstacle (Circle)", callback=lambda: self._set_tool(self.TOOL_OBS_CIRC))
                    dpg.add_menu_item(label="Obstacle (Line/Wall)", callback=lambda: self._set_tool(self.TOOL_OBS_LINE))
                    dpg.add_menu_item(label="Zone", callback=lambda: self._set_tool(self.TOOL_ZONE))
                    dpg.add_menu_item(label="Waypoint", callback=lambda: self._set_tool(self.TOOL_WAYPOINT))

            # Toolbar
            with dpg.group(horizontal=True):
                dpg.add_button(label="Select", callback=lambda: self._set_tool(self.TOOL_SELECT), width=60)
                dpg.add_text("|")
                dpg.add_button(label="Start", callback=lambda: self._set_tool(self.TOOL_START), width=55)
                dpg.add_button(label="Rect", callback=lambda: self._set_tool(self.TOOL_OBS_RECT), width=50)
                dpg.add_button(label="Circle", callback=lambda: self._set_tool(self.TOOL_OBS_CIRC), width=55)
                dpg.add_button(label="Line", callback=lambda: self._set_tool(self.TOOL_OBS_LINE), width=50)
                dpg.add_button(label="Zone", callback=lambda: self._set_tool(self.TOOL_ZONE), width=50)
                dpg.add_button(label="Waypoint", callback=lambda: self._set_tool(self.TOOL_WAYPOINT), width=70)
                dpg.add_text("|"); dpg.add_text("Tool:", color=(150,150,150))
                dpg.add_text("Select", tag="env_tool_label", color=(100,200,255))
            dpg.add_separator()

            with dpg.group(horizontal=True):
                # Left panel
                with dpg.child_window(tag=self.panel_tag, width=240, height=-1, border=True):
                    with dpg.tab_bar():
                        with dpg.tab(label="Objects"):
                            dpg.add_text("START POSITIONS", color=(100,200,255))
                            with dpg.group(tag="env_list_starts"): pass
                            dpg.add_spacer(height=6)
                            dpg.add_text("OBSTRUCTIONS", color=(100,200,255))
                            with dpg.group(tag="env_list_obs"): pass
                            dpg.add_spacer(height=6)
                            dpg.add_text("ZONES", color=(100,200,255))
                            with dpg.group(tag="env_list_zones"): pass
                            dpg.add_spacer(height=6)
                            dpg.add_text("WAYPOINTS", color=(100,200,255))
                            with dpg.group(tag="env_list_wps"): pass
                            dpg.add_spacer(height=10)
                            dpg.add_button(label="Delete Selected", width=-1,
                                           callback=lambda: self._delete_selected())

                        with dpg.tab(label="Metadata"):
                            dpg.add_input_text(label="Name", tag="env_meta_name", width=140)
                            dpg.add_input_text(label="Season", tag="env_meta_season", width=140)
                            dpg.add_input_text(label="Desc", tag="env_meta_desc", width=140)
                            dpg.add_separator()
                            dpg.add_input_int(label="Width (in)", tag="env_meta_fw", width=100, step=12)
                            dpg.add_input_int(label="Height (in)", tag="env_meta_fh", width=100, step=12)
                            dpg.add_input_int(label="In/Tile", tag="env_meta_ipt", width=100, step=6)
                            dpg.add_input_int(label="Tile Cols", tag="env_meta_tc", width=100, step=1)
                            dpg.add_input_int(label="Tile Rows", tag="env_meta_tr", width=100, step=1)
                            dpg.add_separator()
                            dpg.add_input_int(label="Robot W", tag="env_meta_rw", width=100, step=1)
                            dpg.add_input_int(label="Robot L", tag="env_meta_rl", width=100, step=1)
                            dpg.add_input_text(label="BG Image", tag="env_meta_bg", width=140)
                            dpg.add_spacer(height=8)
                            dpg.add_button(label="Apply Metadata", width=-1,
                                           callback=lambda: self._apply_metadata())

                        with dpg.tab(label="Functions"):
                            dpg.add_text("Valid functions for this env:", color=(180,180,180))
                            dpg.add_spacer(height=4)
                            with dpg.group(tag="env_list_funcs"): pass
                            dpg.add_spacer(height=8)
                            dpg.add_input_text(label="Name", tag="env_new_func_name", width=130)
                            dpg.add_input_text(label="Desc", tag="env_new_func_desc", width=130)
                            dpg.add_button(label="Add Function", width=-1,
                                           callback=lambda: self._add_valid_function())

                # Canvas
                with dpg.child_window(tag="env_canvas_wrapper", width=-1, height=-1,
                                      no_scrollbar=True, border=True):
                    dpg.add_drawlist(tag=self.canvas_tag, width=800, height=650)

        # Properties floating window
        with dpg.window(label="Properties", tag="env_props_window", show=False,
                        width=280, height=320, pos=[860, 100]):
            dpg.add_text("No selection", tag="env_props_title", color=(100,200,255))
            dpg.add_separator()
            with dpg.group(tag="env_props_body"): pass

    def _set_tool(self, tool):
        self.tool = tool
        self.placing = False
        self.place_anchor = None
        self._update_tool_label()

    def _update_tool_label(self):
        labels = {self.TOOL_SELECT: "Select", self.TOOL_START: "Place Start",
                  self.TOOL_OBS_RECT: "Draw Rect Obstacle", self.TOOL_OBS_CIRC: "Draw Circle Obstacle",
                  self.TOOL_OBS_LINE: "Draw Line/Wall", self.TOOL_ZONE: "Draw Zone",
                  self.TOOL_WAYPOINT: "Place Waypoint"}
        if dpg.does_item_exist("env_tool_label"):
            dpg.set_value("env_tool_label", labels.get(self.tool, "Select"))

    def _refresh_lists(self):
        if not self.env:
            return
        for tag, items, otype in [("env_list_starts", self.env.start_positions, "start"),
                                   ("env_list_obs", self.env.obstructions, "obs"),
                                   ("env_list_zones", self.env.zones, "zone"),
                                   ("env_list_wps", self.env.waypoints, "wp")]:
            dpg.delete_item(tag, children_only=True)
            for obj in items:
                lbl = getattr(obj, "label", getattr(obj, "name", obj.id))
                dpg.add_selectable(label=lbl, parent=tag,
                                   callback=lambda s, a, u=(obj, otype): self._select(u[0], u[1]))
        dpg.delete_item("env_list_funcs", children_only=True)
        for i, vf in enumerate(self.env.valid_functions):
            with dpg.group(horizontal=True, parent="env_list_funcs"):
                dpg.add_text(f"• {vf.name}", color=tuple(vf.color))
                dpg.add_button(label="X", width=20, height=18,
                               callback=lambda s, a, idx=i: self._remove_valid_function(idx))

    def _refresh_properties(self):
        if not dpg.does_item_exist("env_props_body"):
            return
        dpg.delete_item("env_props_body", children_only=True)
        if not self.selected_obj:
            dpg.set_value("env_props_title", "No selection")
            dpg.configure_item("env_props_window", show=False)
            return
        obj = self.selected_obj
        dpg.set_value("env_props_title",
                      f"{self.selected_type.upper()}: {getattr(obj, 'label', getattr(obj, 'name', ''))}")
        dpg.configure_item("env_props_window", show=True)
        p = "env_props_body"
        if hasattr(obj, "label"):
            dpg.add_input_text(label="Label", default_value=obj.label, parent=p,
                               callback=lambda s,a: setattr(obj,'label',a), on_enter=True, width=140)
        dpg.add_input_float(label="X", default_value=obj.x, parent=p,
                            callback=lambda s,a: setattr(obj,'x',a), on_enter=True, width=100, step=1)
        dpg.add_input_float(label="Y", default_value=obj.y, parent=p,
                            callback=lambda s,a: setattr(obj,'y',a), on_enter=True, width=100, step=1)
        if hasattr(obj, "rotation"):
            dpg.add_input_float(label="Rotation", default_value=obj.rotation, parent=p,
                                callback=lambda s,a: setattr(obj,'rotation',a), on_enter=True, width=100, step=15)
        if hasattr(obj, "alliance"):
            dpg.add_combo(label="Alliance", items=["red","blue","neutral"],
                          default_value=obj.alliance, parent=p, width=100,
                          callback=lambda s,a: setattr(obj,'alliance',a))
        if self.selected_type == "obs":
            dpg.add_text(f"Shape: {obj.shape}", parent=p, color=(180,180,180))
            if obj.shape == "rectangle":
                dpg.add_input_float(label="Width", default_value=obj.width, parent=p,
                                    callback=lambda s,a: setattr(obj,'width',a), on_enter=True, width=100, step=1)
                dpg.add_input_float(label="Height", default_value=obj.height, parent=p,
                                    callback=lambda s,a: setattr(obj,'height',a), on_enter=True, width=100, step=1)
            elif obj.shape == "circle":
                dpg.add_input_float(label="Radius", default_value=obj.radius, parent=p,
                                    callback=lambda s,a: setattr(obj,'radius',a), on_enter=True, width=100, step=1)
            elif obj.shape == "line":
                dpg.add_input_float(label="X2", default_value=obj.x2, parent=p,
                                    callback=lambda s,a: setattr(obj,'x2',a), on_enter=True, width=100, step=1)
                dpg.add_input_float(label="Y2", default_value=obj.y2, parent=p,
                                    callback=lambda s,a: setattr(obj,'y2',a), on_enter=True, width=100, step=1)
            dpg.add_color_edit(label="Color", default_value=obj.color, parent=p,
                               callback=lambda s,a: setattr(obj,'color',[int(c) for c in a[:4]]), width=140)
        if self.selected_type == "zone":
            dpg.add_input_float(label="Width", default_value=obj.width, parent=p,
                                callback=lambda s,a: setattr(obj,'width',a), on_enter=True, width=100, step=1)
            dpg.add_input_float(label="Height", default_value=obj.height, parent=p,
                                callback=lambda s,a: setattr(obj,'height',a), on_enter=True, width=100, step=1)
            dpg.add_color_edit(label="Color", default_value=obj.color, parent=p,
                               callback=lambda s,a: setattr(obj,'color',[int(c) for c in a[:4]]), width=140)
        if self.selected_type == "wp":
            dpg.add_input_float(label="Radius", default_value=obj.radius, parent=p,
                                callback=lambda s,a: setattr(obj,'radius',a), on_enter=True, width=100, step=0.5)
            dpg.add_color_edit(label="Color", default_value=obj.color, parent=p,
                               callback=lambda s,a: setattr(obj,'color',[int(c) for c in a[:4]]), width=140)
        dpg.add_spacer(height=8, parent=p)
        dpg.add_button(label="Delete", parent=p, width=-1, callback=lambda: self._delete_selected())

    def _refresh_metadata_fields(self):
        if not self.env:
            return
        m = self.env.metadata
        for tag, val in [("env_meta_name", m.name), ("env_meta_season", m.season),
                         ("env_meta_desc", m.description), ("env_meta_fw", m.field_width_in),
                         ("env_meta_fh", m.field_height_in), ("env_meta_ipt", m.inches_per_tile),
                         ("env_meta_tc", m.tile_columns), ("env_meta_tr", m.tile_rows),
                         ("env_meta_rw", m.robot_width_in), ("env_meta_rl", m.robot_length_in),
                         ("env_meta_bg", m.background_image)]:
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, val)
        label = f"Environment Editor — {m.name}"
        if self.env.filepath:
            label += f" ({os.path.basename(self.env.filepath)})"
        dpg.set_item_label(self.win_tag, label)

    def _apply_metadata(self):
        if not self.env:
            return
        m = self.env.metadata
        m.name = dpg.get_value("env_meta_name")
        m.season = dpg.get_value("env_meta_season")
        m.description = dpg.get_value("env_meta_desc")
        m.field_width_in = dpg.get_value("env_meta_fw")
        m.field_height_in = dpg.get_value("env_meta_fh")
        m.inches_per_tile = dpg.get_value("env_meta_ipt")
        m.tile_columns = dpg.get_value("env_meta_tc")
        m.tile_rows = dpg.get_value("env_meta_tr")
        m.robot_width_in = dpg.get_value("env_meta_rw")
        m.robot_length_in = dpg.get_value("env_meta_rl")
        m.background_image = dpg.get_value("env_meta_bg")
        self._refresh_metadata_fields()

    def _add_valid_function(self):
        if not self.env:
            return
        name = dpg.get_value("env_new_func_name").strip()
        desc = dpg.get_value("env_new_func_desc").strip()
        if not name or any(vf.name == name for vf in self.env.valid_functions):
            return
        self.env.valid_functions.append(ValidFunction(name=name, description=desc))
        dpg.set_value("env_new_func_name", "")
        dpg.set_value("env_new_func_desc", "")
        self._refresh_lists()

    def _remove_valid_function(self, idx):
        if self.env and 0 <= idx < len(self.env.valid_functions):
            self.env.valid_functions.pop(idx)
            self._refresh_lists()

    def resize(self):
        if not self.built or not dpg.is_item_shown(self.win_tag):
            return
        if dpg.does_item_exist("env_canvas_wrapper"):
            w = dpg.get_item_width("env_canvas_wrapper")
            h = dpg.get_item_height("env_canvas_wrapper")
            if w > 10 and h > 10:
                dpg.configure_item(self.canvas_tag, width=w-4, height=h-4)