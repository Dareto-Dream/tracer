import pygame
import json
import math
import os
from pygame.locals import *
from typing import List, Tuple, Optional

# Field configuration
FIELD_WIDTH_IN = 144
FIELD_HEIGHT_IN = 144
BACKGROUND_IMAGE = "field.png"
OUTPUT_FILE = "path.json"
FUNCTIONS_FILE = "functions.json"

# Initial window settings
DEFAULT_SCALE = 6
MIN_SCALE = 2
MAX_SCALE = 15
INITIAL_WINDOW_W = 1280
INITIAL_WINDOW_H = 960

# Path settings
STEP_SIZE = 0.5
GRID_INCHES = 24
SNAP_ANGLES = [math.radians(a) for a in [0, 45, 90, 135, 180, 225, 270, 315]]

# Colors
COLOR_BG = (30, 30, 30)
COLOR_GRID = (50, 50, 50)
COLOR_PATH = (255, 0, 0)
COLOR_FUNCTION = (0, 255, 0)
COLOR_UI_BG = (40, 40, 40, 200)
COLOR_UI_TEXT = (255, 255, 255)
COLOR_UI_HIGHLIGHT = (70, 70, 70)
COLOR_MENU_BG = (50, 50, 50, 230)
COLOR_MENU_BORDER = (100, 100, 100)

class Function:
    def __init__(self, name: str, x: float, y: float, rotation: float = 0, 
                 function_type: str = "wait_till", action: str = "function"):
        self.name = name
        self.x = x
        self.y = y
        self.rotation = rotation
        self.function_type = function_type  # "wait_till" or "run_while_moving"
        self.action = action  # "function" or "rotate_only"
        self.width = 12
        self.height = 12
    
    def to_dict(self):
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "type": self.function_type,
            "action": self.action
        }
    
    @staticmethod
    def from_dict(data):
        return Function(
            data["name"], 
            data["x"], 
            data["y"], 
            data.get("rotation", 0),
            data.get("type", "wait_till"),
            data.get("action", "function")
        )

class PathTracer:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((INITIAL_WINDOW_W, INITIAL_WINDOW_H), RESIZABLE)
        pygame.display.set_caption("Path Tracer Pro")
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16)
        self.font_large = pygame.font.SysFont("consolas", 24)
        self.font_small = pygame.font.SysFont("consolas", 14)
        
        # View state
        self.scale = DEFAULT_SCALE
        self.offset_x = 0
        self.offset_y = 0
        self.fullscreen = False
        self.fullscreen_padding = 0
        
        # Path state
        self.drawing = False
        self.last_point = None
        self.path_points = []
        
        # Start position
        self.start_pos = None  # (x, y, rotation)
        self.placing_start = False
        
        # Function state
        self.functions = []
        self.function_templates = ["intake", "outtake", "score", "park"]
        self.selected_function = None
        self.selected_function_type = "wait_till"  # or "run_while_moving"
        self.selected_action = "function"  # or "rotate_only"
        self.placing_function = False
        self.dragging_function = None
        
        # Snap settings
        self.snap_enabled = False
        self.snap_inches = 24
        self.grid_offset = 0
        self.grid_offset_mode = False
        
        # UI state
        self.show_help = False
        self.show_settings = False
        self.show_function_menu = False
        self.context_menu_pos = None
        self.context_menu_items = []
        
        # Panning
        self.panning = False
        self.pan_start = None
        self.pan_offset_start = None
        
        # Load background
        self.load_background()
        self.load_functions()
        
    def load_background(self):
        if os.path.exists(BACKGROUND_IMAGE):
            self.bg_original = pygame.image.load(BACKGROUND_IMAGE).convert()
            self.update_background_scale()
        else:
            self.bg = None
            self.bg_original = None
    
    def update_background_scale(self):
        if self.bg_original:
            w = int(FIELD_WIDTH_IN * self.scale)
            h = int(FIELD_HEIGHT_IN * self.scale)
            self.bg = pygame.transform.scale(self.bg_original, (w, h))
        else:
            self.bg = None
    
    def load_functions(self):
        if os.path.exists(FUNCTIONS_FILE):
            try:
                with open(FUNCTIONS_FILE, "r") as f:
                    data = json.load(f)
                    self.functions = [Function.from_dict(f) for f in data.get("functions", [])]
                    self.function_templates = data.get("templates", self.function_templates)
                    
                    # Load start position
                    if "start_pos" in data:
                        sp = data["start_pos"]
                        self.start_pos = (sp["x"], sp["y"], sp["rotation"])
                    
                print(f"Loaded {len(self.functions)} functions")
                if self.start_pos:
                    print(f"Loaded start position at ({self.start_pos[0]:.1f}, {self.start_pos[1]:.1f}) facing {self.start_pos[2]}°")
            except Exception as e:
                print(f"Error loading functions: {e}")
    
    def save_functions(self):
        data = {
            "functions": [f.to_dict() for f in self.functions],
            "templates": self.function_templates
        }
        
        # Save start position
        if self.start_pos:
            data["start_pos"] = {
                "x": self.start_pos[0],
                "y": self.start_pos[1],
                "rotation": self.start_pos[2]
            }
        
        with open(FUNCTIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.functions)} functions")
        if self.start_pos:
            print(f"Saved start position")
    
    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            info = pygame.display.Info()
            self.screen = pygame.display.set_mode((info.current_w, info.current_h), FULLSCREEN)
            
            # Calculate padding to center the field
            field_w = FIELD_WIDTH_IN * self.scale
            field_h = FIELD_HEIGHT_IN * self.scale
            self.fullscreen_padding = min(
                (info.current_w - field_w) // 2,
                (info.current_h - field_h) // 2
            )
        else:
            self.screen = pygame.display.set_mode((INITIAL_WINDOW_W, INITIAL_WINDOW_H), RESIZABLE)
            self.fullscreen_padding = 0
        
        self.update_background_scale()
    
    def screen_to_field(self, sx: int, sy: int) -> Tuple[float, float]:
        """Convert screen coordinates to field coordinates (in inches)"""
        fx = (sx - self.offset_x - self.fullscreen_padding) / self.scale
        fy = (sy - self.offset_y - self.fullscreen_padding) / self.scale
        return fx, fy
    
    def field_to_screen(self, fx: float, fy: float) -> Tuple[int, int]:
        """Convert field coordinates to screen coordinates"""
        sx = int(fx * self.scale + self.offset_x + self.fullscreen_padding)
        sy = int(fy * self.scale + self.offset_y + self.fullscreen_padding)
        return sx, sy
    
    def snap_coord(self, x: float, y: float) -> Tuple[float, float]:
        if not self.snap_enabled:
            return x, y
        
        x_adj = x - self.grid_offset
        y_adj = y - self.grid_offset
        
        sx = round(x_adj / self.snap_inches) * self.snap_inches + self.grid_offset
        sy = round(y_adj / self.snap_inches) * self.snap_inches + self.grid_offset
        
        return sx, sy
    
    def zoom(self, delta: int, mouse_pos: Optional[Tuple[int, int]] = None):
        old_scale = self.scale
        self.scale = max(MIN_SCALE, min(MAX_SCALE, self.scale + delta))
        
        if mouse_pos and old_scale != self.scale:
            # Zoom towards mouse position
            mx, my = mouse_pos
            fx, fy = self.screen_to_field(mx, my)
            
            self.update_background_scale()
            
            new_sx, new_sy = self.field_to_screen(fx, fy)
            self.offset_x += mx - new_sx
            self.offset_y += my - new_sy
        else:
            self.update_background_scale()
    
    def draw_grid(self):
        spacing_px = int(GRID_INCHES * self.scale)
        offset_px = int(self.grid_offset * self.scale)
        
        start_x = self.fullscreen_padding + self.offset_x
        start_y = self.fullscreen_padding + self.offset_y
        
        field_w = int(FIELD_WIDTH_IN * self.scale)
        field_h = int(FIELD_HEIGHT_IN * self.scale)
        
        # Vertical lines
        x = start_x + (offset_px % spacing_px)
        while x <= start_x + field_w:
            pygame.draw.line(self.screen, COLOR_GRID, (x, start_y), (x, start_y + field_h), 1)
            x += spacing_px
        
        # Horizontal lines
        y = start_y + (offset_px % spacing_px)
        while y <= start_y + field_h:
            pygame.draw.line(self.screen, COLOR_GRID, (start_x, y), (start_x + field_w, y), 1)
            y += spacing_px
    
    def draw_path(self):
        if len(self.path_points) < 2:
            return
        
        for i in range(len(self.path_points) - 1):
            x1, y1 = self.path_points[i]
            x2, y2 = self.path_points[i + 1]
            
            sx1, sy1 = self.field_to_screen(x1, y1)
            sx2, sy2 = self.field_to_screen(x2, y2)
            
            pygame.draw.line(self.screen, COLOR_PATH, (sx1, sy1), (sx2, sy2), 3)
        
        # Draw points
        for x, y in self.path_points:
            sx, sy = self.field_to_screen(x, y)
            pygame.draw.circle(self.screen, COLOR_PATH, (sx, sy), 4)
    
    def draw_start_pos(self):
        """Draw the start position with a special marker"""
        if not self.start_pos:
            return
        
        x, y, rotation = self.start_pos
        sx, sy = self.field_to_screen(x, y)
        
        # Draw a large circle for start position
        radius = int(18 * self.scale)
        
        # Draw outer circle (white)
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), radius, 3)
        
        # Draw inner circle (green)
        pygame.draw.circle(self.screen, (0, 255, 0), (sx, sy), radius - 5, 2)
        
        # Draw direction arrow
        angle = math.radians(rotation)
        arrow_length = radius + 10
        end_x = sx + math.cos(angle) * arrow_length
        end_y = sy + math.sin(angle) * arrow_length
        
        # Main arrow line
        pygame.draw.line(self.screen, (255, 255, 255), (sx, sy), (end_x, end_y), 4)
        
        # Arrow head
        arrow_size = 10
        left_angle = angle + math.radians(150)
        right_angle = angle - math.radians(150)
        
        left_x = end_x + math.cos(left_angle) * arrow_size
        left_y = end_y + math.sin(left_angle) * arrow_size
        right_x = end_x + math.cos(right_angle) * arrow_size
        right_y = end_y + math.sin(right_angle) * arrow_size
        
        pygame.draw.polygon(self.screen, (255, 255, 255), [
            (end_x, end_y),
            (left_x, left_y),
            (right_x, right_y)
        ])
        
        # Draw "START" label
        label = self.font.render("START", True, (255, 255, 255))
        self.screen.blit(label, (sx - label.get_width()//2, sy - radius - 25))
        
        # Draw rotation angle
        angle_label = self.font_small.render(f"{rotation}°", True, (200, 200, 200))
        self.screen.blit(angle_label, (sx - angle_label.get_width()//2, sy + radius + 5))
    
    def draw_functions(self):
        for func in self.functions:
            sx, sy = self.field_to_screen(func.x, func.y)
            w = int(func.width * self.scale)
            h = int(func.height * self.scale)
            
            # Check if mouse is near this function during drawing (for visual feedback)
            mouse_near = False
            if self.drawing:
                mx, my = pygame.mouse.get_pos()
                fx, fy = self.screen_to_field(mx, my)
                dx = abs(fx - func.x)
                dy = abs(fy - func.y)
                if dx < func.width / 2 and dy < func.height / 2:
                    mouse_near = True
            
            # Choose color based on function type
            if func.action == "rotate_only":
                color = (255, 255, 0)  # Yellow for rotation only
            elif func.function_type == "wait_till":
                color = COLOR_FUNCTION  # Green
            else:  # run_while_moving
                color = (0, 150, 255)  # Blue
            
            # Brighten color if mouse is near during drawing
            if mouse_near:
                color = tuple(min(255, c + 50) for c in color)
                # Draw highlight circle
                pygame.draw.circle(self.screen, color, (sx, sy), int(w * 0.8), 2)
            
            # Draw rectangle (filled if wait_till, outline if run_while_moving)
            rect = pygame.Rect(sx - w//2, sy - h//2, w, h)
            if func.action == "rotate_only":
                pygame.draw.circle(self.screen, color, (sx, sy), w//2, 2)
            elif func.function_type == "wait_till":
                pygame.draw.rect(self.screen, color, rect, 2)
            else:
                pygame.draw.rect(self.screen, color, rect, 2)
                # Add diagonal lines to indicate "while moving"
                pygame.draw.line(self.screen, color, 
                               (sx - w//2, sy - h//2), 
                               (sx + w//2, sy + h//2), 1)
            
            # Draw rotation indicator
            angle = math.radians(func.rotation)
            end_x = sx + math.cos(angle) * w // 2
            end_y = sy + math.sin(angle) * h // 2
            pygame.draw.line(self.screen, color, (sx, sy), (end_x, end_y), 2)
            
            # Draw label with type indicator
            type_prefix = "R:" if func.action == "rotate_only" else ("W:" if func.function_type == "wait_till" else "M:")
            label_text = f"{type_prefix}{func.name}" if func.action != "rotate_only" else f"R:{func.rotation}°"
            label = self.font_small.render(label_text, True, color)
            self.screen.blit(label, (sx - label.get_width()//2, sy - h//2 - 20))
            
            # Show "SNAP!" text when mouse is near during drawing
            if mouse_near:
                snap_text = self.font_small.render("SNAP!", True, (255, 255, 255))
                self.screen.blit(snap_text, (sx - snap_text.get_width()//2, sy + h//2 + 5))
    
    def draw_ui(self):
        # Top bar
        info_lines = [
            f"Zoom: {self.scale}x | Pan: ({self.offset_x}, {self.offset_y})",
            f"Snap: {'ON' if self.snap_enabled else 'OFF'} | Grid: {self.snap_inches}in | Offset: {self.grid_offset}in",
            f"Points: {len(self.path_points)} | Functions: {len(self.functions)}",
        ]
        
        # Add start position status
        if self.start_pos:
            x, y, rot = self.start_pos
            info_lines.append(f"Start: ({x:.1f}, {y:.1f}) @ {rot}°")
        else:
            info_lines.append("⚠ START POSITION NOT SET - Press P to place")
        
        info_lines.append("Press H for Help")
        
        y = 10
        for i, line in enumerate(info_lines):
            # Highlight warning in red
            if "⚠" in line:
                color = (255, 100, 100)
            else:
                color = COLOR_UI_TEXT
                
            surf = self.font_small.render(line, True, color)
            bg_rect = pygame.Rect(5, y-2, surf.get_width()+10, surf.get_height()+4)
            s = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            s.fill(COLOR_UI_BG)
            self.screen.blit(s, bg_rect)
            self.screen.blit(surf, (10, y))
            y += surf.get_height() + 5
    
    def draw_help_menu(self):
        help_text = [
            "=== PATH TRACER PRO - HELP ===",
            "",
            "IMPORTANT: Place START position first (Press P)",
            "",
            "MOUSE CONTROLS:",
            "  Left Click + Drag: Draw path",
            "  Right Click: Context menu",
            "  Middle Click + Drag: Pan view",
            "  Scroll Wheel: Zoom in/out",
            "",
            "KEYBOARD SHORTCUTS:",
            "  H: Toggle this help menu",
            "  P: Place/Replace start position",
            "  S: Save path and functions",
            "  L: Load path and functions",
            "  C: Clear current path",
            "  G: Toggle grid snapping",
            "  F: Open function placement menu",
            "  Ctrl+F / F11: Toggle fullscreen",
            "  +/-: Adjust snap size (or grid offset in offset mode)",
            "  `: Toggle grid offset mode",
            "  ESC: Exit",
            "",
            "START POSITION:",
            "  Press P to place the start position",
            "  The arrow shows the robot's starting direction",
            "  Right-click on start to adjust rotation",
            "  You MUST place start before drawing paths",
            "  Path automatically starts from START position",
            "",
            "PATH DRAWING:",
            "  First click automatically connects to START",
            "  Click near a function to snap path to it",
            "  Path will highlight functions when near them",
            "  Great for ensuring path goes through functions",
            "",
            "FUNCTIONS:",
            "  Press F to open function menu",
            "  R: Rotate Only - just rotates robot to angle",
            "  F: Function - runs a function at this point",
            "    W: Wait Till Complete - stops and waits",
            "    M: Run While Moving - runs during movement",
            "  Select function type and click to place",
            "  Right-click on function to edit/delete",
            "",
            "FUNCTION COLORS:",
            "  White Circle + Arrow: Start Position",
            "  Yellow Circle: Rotate Only",
            "  Green Square: Wait Till Complete",
            "  Blue Square: Run While Moving",
            "",
            "Press H or ESC to close"
        ]
        
        # Calculate menu size
        max_width = max(self.font.render(line, True, COLOR_UI_TEXT).get_width() for line in help_text)
        line_height = self.font.get_height()
        menu_width = max_width + 40
        menu_height = len(help_text) * (line_height + 2) + 40
        
        screen_w, screen_h = self.screen.get_size()
        menu_x = (screen_w - menu_width) // 2
        menu_y = (screen_h - menu_height) // 2
        
        # Draw background
        s = pygame.Surface((menu_width, menu_height), pygame.SRCALPHA)
        s.fill(COLOR_MENU_BG)
        self.screen.blit(s, (menu_x, menu_y))
        
        # Draw border
        pygame.draw.rect(self.screen, COLOR_MENU_BORDER, (menu_x, menu_y, menu_width, menu_height), 2)
        
        # Draw text
        y = menu_y + 20
        for line in help_text:
            if line.startswith("==="):
                surf = self.font_large.render(line, True, COLOR_UI_TEXT)
            else:
                surf = self.font.render(line, True, COLOR_UI_TEXT)
            self.screen.blit(surf, (menu_x + 20, y))
            y += line_height + 2
    
    def draw_function_menu(self):
        menu_text = ["=== FUNCTION PLACEMENT ===", ""]
        menu_text.append("ACTION TYPE:")
        menu_text.append("R. Rotate Only (just rotate robot)")
        menu_text.append("F. Function (run a function)")
        menu_text.append("")
        
        if self.selected_action == "function":
            menu_text.append("FUNCTION TYPE:")
            menu_text.append("W. Wait Till Complete")
            menu_text.append("M. Run While Moving")
            menu_text.append("")
            menu_text.append("FUNCTIONS:")
            menu_text.extend([f"{i+1}. {name}" for i, name in enumerate(self.function_templates)])
            menu_text.append("")
            menu_text.append("A. Add new function type")
        
        menu_text.append("")
        menu_text.append(f"Current: {self.selected_action.upper()}")
        if self.selected_action == "function":
            menu_text.append(f"Type: {self.selected_function_type.upper()}")
            if self.selected_function:
                menu_text.append(f"Function: {self.selected_function}")
        menu_text.append("")
        menu_text.append("ESC. Cancel")
        
        max_width = max(self.font.render(line, True, COLOR_UI_TEXT).get_width() for line in menu_text)
        line_height = self.font.get_height()
        menu_width = max_width + 40
        menu_height = len(menu_text) * (line_height + 2) + 40
        
        screen_w, screen_h = self.screen.get_size()
        menu_x = (screen_w - menu_width) // 2
        menu_y = (screen_h - menu_height) // 2
        
        s = pygame.Surface((menu_width, menu_height), pygame.SRCALPHA)
        s.fill(COLOR_MENU_BG)
        self.screen.blit(s, (menu_x, menu_y))
        pygame.draw.rect(self.screen, COLOR_MENU_BORDER, (menu_x, menu_y, menu_width, menu_height), 2)
        
        y = menu_y + 20
        for line in menu_text:
            if line.startswith("==="):
                surf = self.font_large.render(line, True, COLOR_UI_TEXT)
            else:
                surf = self.font.render(line, True, COLOR_UI_TEXT)
            self.screen.blit(surf, (menu_x + 20, y))
            y += line_height + 2
    
    def draw_context_menu(self):
        if not self.context_menu_pos or not self.context_menu_items:
            return
        
        line_height = self.font.get_height()
        max_width = max(self.font.render(item[0], True, COLOR_UI_TEXT).get_width() for item in self.context_menu_items)
        menu_width = max_width + 40
        menu_height = len(self.context_menu_items) * (line_height + 10) + 10
        
        mx, my = self.context_menu_pos
        
        s = pygame.Surface((menu_width, menu_height), pygame.SRCALPHA)
        s.fill(COLOR_MENU_BG)
        self.screen.blit(s, (mx, my))
        pygame.draw.rect(self.screen, COLOR_MENU_BORDER, (mx, my, menu_width, menu_height), 2)
        
        mouse_x, mouse_y = pygame.mouse.get_pos()
        
        y = my + 5
        for i, (text, _) in enumerate(self.context_menu_items):
            item_rect = pygame.Rect(mx + 5, y, menu_width - 10, line_height + 4)
            
            if item_rect.collidepoint(mouse_x, mouse_y):
                pygame.draw.rect(self.screen, COLOR_UI_HIGHLIGHT, item_rect)
            
            surf = self.font.render(text, True, COLOR_UI_TEXT)
            self.screen.blit(surf, (mx + 20, y + 2))
            y += line_height + 10
    
    def handle_context_menu_click(self, pos):
        if not self.context_menu_pos or not self.context_menu_items:
            return
        
        mx, my = self.context_menu_pos
        line_height = self.font.get_height()
        
        y = my + 5
        for text, callback in self.context_menu_items:
            item_rect = pygame.Rect(mx + 5, y, 300, line_height + 4)
            if item_rect.collidepoint(pos):
                callback()
                self.context_menu_pos = None
                self.context_menu_items = []
                return
            y += line_height + 10
        
        self.context_menu_pos = None
        self.context_menu_items = []
    
    def show_context_menu_at(self, pos, items):
        self.context_menu_pos = pos
        self.context_menu_items = items
    
    def get_function_at_pos(self, fx, fy):
        for func in self.functions:
            dx = abs(fx - func.x)
            dy = abs(fy - func.y)
            if dx < func.width / 2 and dy < func.height / 2:
                return func
        return None
    
    def is_click_on_start(self, fx, fy):
        """Check if a click position is on the start position"""
        if not self.start_pos:
            return False
        
        sx, sy, _ = self.start_pos
        dx = abs(fx - sx)
        dy = abs(fy - sy)
        # 18 inch radius for start position
        return math.sqrt(dx*dx + dy*dy) < 18
    
    def save_path(self):
        data = {"path": [{"x": x, "y": y} for x, y in self.path_points]}
        with open(OUTPUT_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved path: {OUTPUT_FILE}")
        self.save_functions()
    
    def load_path(self):
        if os.path.exists(OUTPUT_FILE):
            try:
                with open(OUTPUT_FILE, "r") as f:
                    data = json.load(f)
                    self.path_points = [(p["x"], p["y"]) for p in data.get("path", [])]
                print(f"Loaded {len(self.path_points)} path points")
            except Exception as e:
                print(f"Error loading path: {e}")
        self.load_functions()
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                return False
            
            if event.type == VIDEORESIZE:
                self.update_background_scale()
            
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    if self.show_help:
                        self.show_help = False
                    elif self.show_function_menu:
                        self.show_function_menu = False
                        self.placing_function = False
                    elif self.context_menu_pos:
                        self.context_menu_pos = None
                        self.context_menu_items = []
                    else:
                        return False
                
                if event.key == K_h:
                    self.show_help = not self.show_help
                
                if event.key == K_p and not self.show_help and not self.show_function_menu:
                    # Toggle placing start position
                    self.placing_start = True
                    self.placing_function = False
                    print("Click to place start position (right-click to adjust rotation after placing)")
                
                if event.key == K_s and not self.show_help and not self.show_function_menu:
                    self.save_path()
                
                if event.key == K_l and not self.show_help and not self.show_function_menu:
                    self.load_path()
                
                if event.key == K_c and not self.show_help and not self.show_function_menu:
                    self.path_points.clear()
                    self.last_point = None
                    print("Cleared path")
                
                if event.key == K_g and not self.show_help and not self.show_function_menu:
                    self.snap_enabled = not self.snap_enabled
                    print(f"Grid snapping: {self.snap_enabled}")
                
                if event.key == K_f and not self.show_help:
                    if event.mod & KMOD_CTRL:
                        self.toggle_fullscreen()
                    else:
                        self.show_function_menu = not self.show_function_menu
                
                if event.key == K_F11:
                    self.toggle_fullscreen()
                
                if event.key == K_BACKQUOTE:
                    self.grid_offset_mode = not self.grid_offset_mode
                    print(f"Grid offset mode: {self.grid_offset_mode}")
                
                if event.key in (K_EQUALS, K_PLUS):
                    if self.grid_offset_mode:
                        self.grid_offset += 4
                        print(f"Grid offset: {self.grid_offset}")
                    else:
                        self.snap_inches += 4
                        print(f"Snap size: {self.snap_inches}")
                
                if event.key == K_MINUS:
                    if self.grid_offset_mode:
                        self.grid_offset -= 4
                        print(f"Grid offset: {self.grid_offset}")
                    else:
                        self.snap_inches = max(1, self.snap_inches - 4)
                        print(f"Snap size: {self.snap_inches}")
                
                # Function menu number keys
                if self.show_function_menu:
                    if event.key == K_r:
                        # Rotate only
                        self.selected_action = "rotate_only"
                        self.selected_function = None
                        self.placing_function = True
                        self.show_function_menu = False
                        print("Placing: Rotate Only")
                    elif event.key == K_f:
                        # Function action
                        self.selected_action = "function"
                        print("Action: Function")
                    elif event.key == K_w:
                        # Wait till complete
                        self.selected_function_type = "wait_till"
                        print("Type: Wait Till Complete")
                    elif event.key == K_m:
                        # Run while moving
                        self.selected_function_type = "run_while_moving"
                        print("Type: Run While Moving")
                    elif K_1 <= event.key <= K_9:
                        if self.selected_action == "function":
                            idx = event.key - K_1
                            if idx < len(self.function_templates):
                                self.selected_function = self.function_templates[idx]
                                self.placing_function = True
                                self.show_function_menu = False
                                print(f"Placing function: {self.selected_function} ({self.selected_function_type})")
                    elif event.key == K_a:
                        # Add new function type
                        print("Enter function name in console:")
                        # This is a simplified version; in a full implementation,
                        # you'd want a text input dialog
            
            if event.type == MOUSEWHEEL:
                if not self.show_help and not self.show_function_menu:
                    self.zoom(event.y, pygame.mouse.get_pos())
            
            if event.type == MOUSEBUTTONDOWN:
                if self.context_menu_pos:
                    self.handle_context_menu_click(event.pos)
                    continue
                
                if event.button == 1:  # Left click
                    if not self.show_help and not self.show_function_menu:
                        if self.placing_start:
                            # Place start position
                            fx, fy = self.screen_to_field(*event.pos)
                            fx, fy = self.snap_coord(fx, fy)
                            self.start_pos = (fx, fy, 0)  # Default rotation 0
                            self.placing_start = False
                            print(f"Placed start position at ({fx:.1f}, {fy:.1f})")
                        elif self.placing_function:
                            fx, fy = self.screen_to_field(*event.pos)
                            fx, fy = self.snap_coord(fx, fy)
                            
                            if self.selected_action == "rotate_only":
                                # For rotate only, use rotation as the "name"
                                new_func = Function("rotate", fx, fy, 0, "wait_till", "rotate_only")
                                self.functions.append(new_func)
                                print(f"Placed rotation point at ({fx:.1f}, {fy:.1f})")
                            elif self.selected_function:
                                new_func = Function(
                                    self.selected_function, 
                                    fx, fy, 
                                    0, 
                                    self.selected_function_type,
                                    self.selected_action
                                )
                                self.functions.append(new_func)
                                print(f"Placed {self.selected_function} ({self.selected_function_type}) at ({fx:.1f}, {fy:.1f})")
                        else:
                            # Only allow path drawing if start position is set
                            if not self.start_pos:
                                print("⚠ Please place start position first (Press P)")
                            else:
                                self.drawing = True
                                fx, fy = self.screen_to_field(*event.pos)
                                fx, fy = self.snap_coord(fx, fy)
                                
                                # If this is the first point and path is empty, start from start position
                                if len(self.path_points) == 0:
                                    start_x, start_y, _ = self.start_pos
                                    self.path_points.append((start_x, start_y))
                                    self.last_point = (start_x, start_y)
                                    print(f"Path starting from start position ({start_x:.1f}, {start_y:.1f})")
                                
                                # Check if clicking near a function - snap to it
                                clicked_func = self.get_function_at_pos(fx, fy)
                                if clicked_func:
                                    fx, fy = clicked_func.x, clicked_func.y
                                    print(f"Snapped to function '{clicked_func.name}' at ({fx:.1f}, {fy:.1f})")
                                
                                self.last_point = (fx, fy)
                                self.path_points.append(self.last_point)
                
                elif event.button == 2:  # Middle click
                    self.panning = True
                    self.pan_start = event.pos
                    self.pan_offset_start = (self.offset_x, self.offset_y)
                
                elif event.button == 3:  # Right click
                    if not self.show_help and not self.show_function_menu:
                        fx, fy = self.screen_to_field(*event.pos)
                        
                        # Check if clicking on start position
                        if self.is_click_on_start(fx, fy):
                            # Start position context menu
                            items = [
                                ("Delete Start Position", lambda: setattr(self, 'start_pos', None)),
                                ("Rotate +45°", lambda: setattr(self, 'start_pos', 
                                    (self.start_pos[0], self.start_pos[1], (self.start_pos[2] + 45) % 360))),
                                ("Rotate +90°", lambda: setattr(self, 'start_pos', 
                                    (self.start_pos[0], self.start_pos[1], (self.start_pos[2] + 90) % 360))),
                                ("Rotate -45°", lambda: setattr(self, 'start_pos', 
                                    (self.start_pos[0], self.start_pos[1], (self.start_pos[2] - 45) % 360))),
                                ("Set Rotation to 0°", lambda: setattr(self, 'start_pos', 
                                    (self.start_pos[0], self.start_pos[1], 0))),
                                ("Set Rotation to 90°", lambda: setattr(self, 'start_pos', 
                                    (self.start_pos[0], self.start_pos[1], 90))),
                                ("Set Rotation to 180°", lambda: setattr(self, 'start_pos', 
                                    (self.start_pos[0], self.start_pos[1], 180))),
                                ("Set Rotation to 270°", lambda: setattr(self, 'start_pos', 
                                    (self.start_pos[0], self.start_pos[1], 270))),
                            ]
                            self.show_context_menu_at(event.pos, items)
                            continue
                        
                        func = self.get_function_at_pos(fx, fy)
                        
                        if func:
                            # Function context menu
                            items = [
                                ("Delete Function", lambda f=func: self.functions.remove(f)),
                                ("Rotate +45°", lambda f=func: setattr(f, 'rotation', (f.rotation + 45) % 360)),
                                ("Rotate +90°", lambda f=func: setattr(f, 'rotation', (f.rotation + 90) % 360)),
                                ("Rotate -45°", lambda f=func: setattr(f, 'rotation', (f.rotation - 45) % 360)),
                                ("Set Rotation to 0°", lambda f=func: setattr(f, 'rotation', 0)),
                            ]
                            
                            # Add type toggle if it's a function action
                            if func.action == "function":
                                if func.function_type == "wait_till":
                                    items.insert(1, ("Change to Run While Moving", 
                                                    lambda f=func: setattr(f, 'function_type', 'run_while_moving')))
                                else:
                                    items.insert(1, ("Change to Wait Till Complete", 
                                                    lambda f=func: setattr(f, 'function_type', 'wait_till')))
                            
                            self.show_context_menu_at(event.pos, items)
                        elif self.placing_function:
                            # Cancel placement
                            self.placing_function = False
                            self.selected_function = None
                        elif self.placing_start:
                            # Cancel start placement
                            self.placing_start = False
                        else:
                            # General context menu
                            items = [
                                ("Clear Path", lambda: self.path_points.clear()),
                                ("Save", lambda: self.save_path()),
                                ("Load", lambda: self.load_path()),
                                ("Toggle Snap", lambda: setattr(self, 'snap_enabled', not self.snap_enabled)),
                            ]
                            self.show_context_menu_at(event.pos, items)
            
            if event.type == MOUSEBUTTONUP:
                if event.button == 1:
                    self.drawing = False
                    self.last_point = None
                elif event.button == 2:
                    self.panning = False
                    self.pan_start = None
            
            if event.type == MOUSEMOTION:
                if self.panning and self.pan_start:
                    dx = event.pos[0] - self.pan_start[0]
                    dy = event.pos[1] - self.pan_start[1]
                    self.offset_x = self.pan_offset_start[0] + dx
                    self.offset_y = self.pan_offset_start[1] + dy
        
        # Handle continuous drawing
        if self.drawing and self.last_point and not self.show_help and not self.show_function_menu:
            mx, my = pygame.mouse.get_pos()
            fx, fy = self.screen_to_field(mx, my)
            
            # Check if near a function - snap to it
            nearby_func = self.get_function_at_pos(fx, fy)
            if nearby_func:
                fx, fy = nearby_func.x, nearby_func.y
            else:
                fx, fy = self.snap_coord(fx, fy)
            
            lx, ly = self.last_point
            dx = fx - lx
            dy = fy - ly
            
            if abs(dx) > 0.05 or abs(dy) > 0.05:
                angle = math.atan2(dy, dx)
                best = min(SNAP_ANGLES, key=lambda a: abs(a - angle))
                
                new_x = lx + math.cos(best) * STEP_SIZE
                new_y = ly + math.sin(best) * STEP_SIZE
                
                # Check if the new point should snap to a function
                check_func = self.get_function_at_pos(new_x, new_y)
                if check_func:
                    new_x, new_y = check_func.x, check_func.y
                else:
                    new_x, new_y = self.snap_coord(new_x, new_y)
                
                self.last_point = (new_x, new_y)
                self.path_points.append(self.last_point)
        
        return True
    
    def run(self):
        running = True
        while running:
            self.screen.fill(COLOR_BG)
            
            # Draw field elements
            if self.bg:
                self.screen.blit(self.bg, (self.fullscreen_padding + self.offset_x, 
                                          self.fullscreen_padding + self.offset_y))
            
            self.draw_grid()
            self.draw_path()
            self.draw_start_pos()  # Draw start position
            self.draw_functions()
            
            # Draw UI
            self.draw_ui()
            
            if self.context_menu_pos:
                self.draw_context_menu()
            
            if self.show_help:
                self.draw_help_menu()
            
            if self.show_function_menu:
                self.draw_function_menu()
            
            # Draw path start indicator
            if self.start_pos and len(self.path_points) == 0 and not self.placing_function and not self.placing_start:
                # Show that path will start from start position
                mx, my = pygame.mouse.get_pos()
                start_x, start_y, _ = self.start_pos
                sx, sy = self.field_to_screen(start_x, start_y)
                
                # Draw dotted line from start to mouse
                pygame.draw.line(self.screen, (100, 255, 100), (sx, sy), (mx, my), 1)
                
                # Draw hint text
                hint = self.font_small.render("Path will start from START position", True, (100, 255, 100))
                self.screen.blit(hint, (mx + 10, my - 20))
            
            # Draw placement cursor for start position
            if self.placing_start:
                mx, my = pygame.mouse.get_pos()
                fx, fy = self.screen_to_field(mx, my)
                fx, fy = self.snap_coord(fx, fy)
                sx, sy = self.field_to_screen(fx, fy)
                
                radius = int(18 * self.scale)
                
                # Draw preview circle
                pygame.draw.circle(self.screen, (255, 255, 255, 128), (sx, sy), radius, 2)
                pygame.draw.circle(self.screen, (0, 255, 0, 128), (sx, sy), radius - 5, 1)
                
                # Draw preview arrow pointing right (0°)
                arrow_length = radius + 10
                end_x = sx + arrow_length
                end_y = sy
                pygame.draw.line(self.screen, (255, 255, 255, 128), (sx, sy), (end_x, end_y), 2)
                
                label = self.font_small.render("START (0°)", True, (255, 255, 255))
                self.screen.blit(label, (sx - label.get_width()//2, sy - radius - 25))
            
            # Draw placement cursor
            elif self.placing_function:
                mx, my = pygame.mouse.get_pos()
                fx, fy = self.screen_to_field(mx, my)
                fx, fy = self.snap_coord(fx, fy)
                sx, sy = self.field_to_screen(fx, fy)
                
                w = int(12 * self.scale)
                h = int(12 * self.scale)
                
                # Choose color based on action/type
                if self.selected_action == "rotate_only":
                    color = (255, 255, 0)  # Yellow
                    pygame.draw.circle(self.screen, color, (sx, sy), w//2, 2)
                    label = self.font_small.render("Rotate Only", True, color)
                elif self.selected_function_type == "wait_till":
                    color = COLOR_FUNCTION  # Green
                    rect = pygame.Rect(sx - w//2, sy - h//2, w, h)
                    pygame.draw.rect(self.screen, color, rect, 2)
                    label = self.font_small.render(f"Wait: {self.selected_function}", True, color)
                else:  # run_while_moving
                    color = (0, 150, 255)  # Blue
                    rect = pygame.Rect(sx - w//2, sy - h//2, w, h)
                    pygame.draw.rect(self.screen, color, rect, 2)
                    label = self.font_small.render(f"Move: {self.selected_function}", True, color)
                
                self.screen.blit(label, (sx - label.get_width()//2, sy - h//2 - 20))
            
            pygame.display.flip()
            self.clock.tick(60)
            
            running = self.handle_events()
        
        pygame.quit()

if __name__ == "__main__":
    app = PathTracer()
    app.run()