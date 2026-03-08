import sys
import json
import math
import copy
import os
import webbrowser
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets, QtOpenGL, QtMultimedia
from PyQt5.QtWidgets import QToolButton, QColorDialog, QFileDialog, QMessageBox, QAction
from OpenGL.GL import *
from OpenGL.GLU import *

from pypresence import Presence
import time

from custom_file_dialog import CustomFileDialog
from ai_settings import AISettingsDialog
from general_settings import GeneralSettingsDialog


from scene_objects import (
    normalize, dot, intersect_plane, sub, add, mul, cross,
    ray_box_intersect, dist_ray_to_segment, load_mtl_file, load_obj_file,
    Camera, SceneObject, Brush, EraserEntity
)

PROJECT_ROOT = Path(__file__).resolve().parent


for folder in ["gui", "special", "models"]:
    (PROJECT_ROOT / "materials" / folder).mkdir(parents=True, exist_ok=True)

BASE_BG = "#A4A4A4"
PANEL_BG = "#AEAEAE"
INPUT_BG = "#D0D0D0"
HOVER_GREEN = "#00FF00"
PRESS_GREEN = "#00CC00"
HOVER_RED = "#FF0000"
PRESS_RED = "#CC0000"
FONT_FAMILY = "Forum"

def get_3d_border(sunken=False, width=2):
    if sunken:
        return f"border-top: {width}px solid #606060; border-left: {width}px solid #606060; border-bottom: {width}px solid #E0E0E0; border-right: {width}px solid #E0E0E0;"
    return f"border-top: {width}px solid #E0E0E0; border-left: {width}px solid #E0E0E0; border-bottom: {width}px solid #606060; border-right: {width}px solid #606060;"

def get_btn_style(hover_bg=HOVER_GREEN, press_bg=PRESS_GREEN):
    return f"""
        QPushButton, QToolButton {{
            background-color: {PANEL_BG};
            {get_3d_border(False, 2)}
            color: black;
            font-family: "{FONT_FAMILY}";
        }}
        QPushButton:hover, QToolButton:hover {{
            background-color: {hover_bg};
        }}
        QPushButton:pressed, QToolButton:pressed {{
            background-color: {press_bg};
            {get_3d_border(True, 2)}
        }}
        QToolButton::menu-indicator {{ image: none; }}
    """

class CanvasWidget(QtWidgets.QWidget):
    colorPicked = QtCore.pyqtSignal(QtGui.QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_width = 1024
        self.image_height = 768
        self.image = QtGui.QImage(self.image_width, self.image_height, QtGui.QImage.Format_ARGB32)
        self.image.fill(QtCore.Qt.white)
        
        self.preview_image = None
        self.drawing = False
        self.panning = False
        self.last_mouse_pos = QtCore.QPoint()
        
        self.scale_factor = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        
        self.brush_color = QtCore.Qt.black
        self.brush_width = 5
        self.eraser_width = 20
        self.hardness = 100
        self.current_tool = "brush"
        
        self.shape_type = "Rectangle"
        
        self.line_type = "Line"
        
        self.curve_status = 0
        self.curve_p1 = QtCore.QPoint()
        self.curve_p2 = QtCore.QPoint()
        self.curve_control = QtCore.QPoint()
        
        self.outline_mode = False
        self.cached_stamp = None
        self.cached_stamp_params = None

        self.undo_stack = []
        self.redo_stack = []
        self.save_state_to_undo()

    def reset_canvas(self, outline_mode):
        self.outline_mode = outline_mode
        if self.outline_mode: self.image.fill(QtCore.Qt.transparent)
        else: self.image.fill(QtCore.Qt.white)
        self.undo_stack.clear(); self.redo_stack.clear()
        self.curve_status = 0
        self.save_state_to_undo()
        self.update()

    def save_state_to_undo(self):
        if len(self.undo_stack) >= 30: self.undo_stack.pop(0)
        self.undo_stack.append(self.image.copy())
        self.redo_stack.clear()

    def undo(self):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.image = self.undo_stack[-1].copy()
            self.update()

    def redo(self):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(state)
            self.image = state.copy()
            self.update()

    def set_tool(self, tool):
        self.current_tool = tool
        self.curve_status = 0 
        self.preview_image = None
        self.update()

    def set_color(self, color): self.brush_color = color

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        painter.translate(self.offset_x, self.offset_y)
        painter.scale(self.scale_factor, self.scale_factor)
        
        if self.outline_mode:
            painter.fillRect(0, 0, self.image_width, self.image_height, QtGui.QBrush(QtCore.Qt.white, QtCore.Qt.Dense7Pattern))
        else:
            painter.fillRect(0, 0, self.image_width, self.image_height, QtCore.Qt.white)

        painter.drawImage(0, 0, self.image)

        if self.preview_image and (self.drawing or self.curve_status != 0):
            painter.drawImage(0, 0, self.preview_image)
            
        painter.setPen(QtGui.QPen(QtCore.Qt.gray, 1, QtCore.Qt.DashLine))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(0, 0, self.image_width, self.image_height)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        new_scale = self.scale_factor * factor
        if 0.1 <= new_scale <= 5.0:
            mouse_pos = event.pos()
            vec_x = mouse_pos.x() - self.offset_x
            vec_y = mouse_pos.y() - self.offset_y
            self.offset_x += vec_x * (1 - factor)
            self.offset_y += vec_y * (1 - factor)
            self.scale_factor = new_scale
            self.update()

    def mousePressEvent(self, event):
        self.last_mouse_pos = event.pos()
        if event.button() == QtCore.Qt.RightButton:
            self.panning = True
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            return

        if event.button() == QtCore.Qt.LeftButton:
            pt = self.map_to_image(event.pos())
            if not (0 <= pt.x() < self.image_width and 0 <= pt.y() < self.image_height): return

            if self.current_tool == "line_curve":
                if self.line_type == "Line":
                    self.curve_p1 = pt
                    self.curve_p2 = pt
                    self.drawing = True
                    
                elif self.line_type == "Curve":
                    if self.curve_status == 0:
                        self.curve_p1 = pt
                        self.curve_p2 = pt
                        self.curve_status = 1
                        self.drawing = True
                    elif self.curve_status == 2:
                        self.curve_control = pt
                        self.drawing = True
            
            elif self.current_tool == "fill": 
                self.perform_flood_fill(pt)
                self.save_state_to_undo()
            elif self.current_tool == "picker":
                col = self.image.pixelColor(pt)
                self.set_color(col)
                self.colorPicked.emit(col)
            else:
                self.drawing = True
                self.start_point = pt
                self.last_draw_pt = pt
                if self.current_tool != "shapes":
                    self.draw_soft_line(pt, pt)

    def mouseMoveEvent(self, event):
        if self.panning:
            delta = event.pos() - self.last_mouse_pos
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_mouse_pos = event.pos()
            self.update()
            return

        if (event.buttons() & QtCore.Qt.LeftButton) and self.drawing:
            pt = self.map_to_image(event.pos())
            
            if self.current_tool == "line_curve":
                self.preview_image = QtGui.QImage(self.image.size(), QtGui.QImage.Format_ARGB32)
                self.preview_image.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(self.preview_image)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                
                if self.line_type == "Line":
                    self.curve_p2 = pt
                    self._draw_curve_preview(painter, self.curve_p1, self.curve_p2, None)
                
                elif self.line_type == "Curve":
                    if self.curve_status == 1:
                        self.curve_p2 = pt
                        self._draw_curve_preview(painter, self.curve_p1, self.curve_p2, None)
                    elif self.curve_status == 2:
                        self.curve_control = pt
                        self._draw_curve_preview(painter, self.curve_p1, self.curve_p2, self.curve_control)
                    
                painter.end()
                self.update()
                
            elif self.current_tool == "shapes":
                self.preview_image = QtGui.QImage(self.image.size(), QtGui.QImage.Format_ARGB32)
                self.preview_image.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(self.preview_image)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                self._draw_actual_shape(painter, self.start_point, pt)
                painter.end()
                self.update()
                
            elif self.current_tool in ["brush", "eraser"]:
                self.draw_soft_line(self.last_draw_pt, pt)
                self.last_draw_pt = pt

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)

        if event.button() == QtCore.Qt.LeftButton:
            
            if self.current_tool == "line_curve" and self.drawing:
                self.drawing = False
                
                if self.line_type == "Line":
                    pt = self.map_to_image(event.pos())
                    painter = QtGui.QPainter(self.image)
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)
                    self._draw_curve_preview(painter, self.curve_p1, pt, None)
                    painter.end()
                    self.preview_image = None
                    self.save_state_to_undo()
                    self.update()

                elif self.line_type == "Curve":
                    if self.curve_status == 1:
                        self.curve_status = 2
                        self.update()
                    elif self.curve_status == 2:
                        painter = QtGui.QPainter(self.image)
                        painter.setRenderHint(QtGui.QPainter.Antialiasing)
                        self._draw_curve_preview(painter, self.curve_p1, self.curve_p2, self.curve_control)
                        painter.end()
                        self.preview_image = None
                        self.curve_status = 0
                        self.save_state_to_undo()
                        self.update()
            
            elif self.current_tool == "shapes" and self.drawing:
                self.drawing = False
                pt = self.map_to_image(event.pos())
                painter = QtGui.QPainter(self.image)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                self._draw_actual_shape(painter, self.start_point, pt)
                painter.end()
                self.preview_image = None
                self.save_state_to_undo()
                self.update()
                
            elif self.current_tool in ["brush", "eraser"] and self.drawing:
                self.drawing = False
                self.save_state_to_undo()

    def map_to_image(self, widget_pt):
        x = int((widget_pt.x() - self.offset_x) / self.scale_factor)
        y = int((widget_pt.y() - self.offset_y) / self.scale_factor)
        return QtCore.QPoint(x, y)

    def _draw_curve_preview(self, painter, p1, p2, ctrl=None):
        pen_col = QtGui.QColor(self.brush_color)
        painter.setPen(QtGui.QPen(pen_col, self.brush_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        path = QtGui.QPainterPath()
        path.moveTo(p1)
        if ctrl is None: path.lineTo(p2)
        else: path.quadTo(ctrl, p2)
        painter.drawPath(path)

    def _draw_actual_shape(self, painter, start, end):
        pen_col = QtGui.QColor(self.brush_color)
        painter.setPen(QtGui.QPen(pen_col, self.brush_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        rect = QtCore.QRect(start, end).normalized()
        if self.shape_type == "Rectangle": painter.drawRect(rect)
        elif self.shape_type == "Ellipse": painter.drawEllipse(rect)
        elif self.shape_type == "Triangle":
            path = QtGui.QPainterPath()
            path.moveTo(rect.left() + rect.width() / 2, rect.top())
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left(), rect.bottom())
            path.closeSubpath()
            painter.drawPath(path)

    def get_brush_stamp(self, color, width, hardness, is_eraser_clear):
        params = (color.rgba(), width, hardness, is_eraser_clear)
        if self.cached_stamp_params == params: return self.cached_stamp
        stamp = QtGui.QImage(width, width, QtGui.QImage.Format_ARGB32)
        stamp.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(stamp); p.setRenderHint(QtGui.QPainter.Antialiasing)
        grad = QtGui.QRadialGradient(width/2, width/2, width/2)
        c = QtGui.QColor(QtCore.Qt.black if is_eraser_clear else color)
        c0 = QtGui.QColor(c); c0.setAlpha(0)
        grad.setColorAt(0, c); grad.setColorAt(max(0.001, hardness/100), c); grad.setColorAt(1, c0)
        p.setPen(QtCore.Qt.NoPen); p.setBrush(QtGui.QBrush(grad)); p.drawEllipse(0,0,width,width); p.end()
        self.cached_stamp = stamp; self.cached_stamp_params = params
        return stamp

    def draw_soft_line(self, start, end):
        painter = QtGui.QPainter(self.image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        is_eraser = (self.current_tool == "eraser")
        width = self.eraser_width if is_eraser else self.brush_width
        if is_eraser and self.outline_mode: color = QtGui.QColor(QtCore.Qt.transparent)
        elif is_eraser: color = QtGui.QColor(QtCore.Qt.white)
        else: color = QtGui.QColor(self.brush_color)
        mode = QtGui.QPainter.CompositionMode_DestinationOut if (is_eraser and self.outline_mode) else QtGui.QPainter.CompositionMode_SourceOver
        painter.setCompositionMode(mode)
        if self.hardness >= 99:
            c = QtCore.Qt.transparent if (is_eraser and self.outline_mode) else color
            m = QtGui.QPainter.CompositionMode_Clear if (is_eraser and self.outline_mode) else QtGui.QPainter.CompositionMode_SourceOver
            painter.setCompositionMode(m)
            painter.setPen(QtGui.QPen(c, width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            painter.drawLine(start, end)
        else:
            d = math.hypot(end.x()-start.x(), end.y()-start.y())
            steps = max(1, int(d / (width * 0.1)))
            stamp = self.get_brush_stamp(color, width, self.hardness, (is_eraser and self.outline_mode))
            for i in range(steps+1):
                t = i/steps
                painter.drawImage(QtCore.QRectF(start.x()+(end.x()-start.x())*t - width/2, start.y()+(end.y()-start.y())*t - width/2, width, width), stamp)
        self.update()

    def perform_flood_fill(self, start_pt):
        x, y = start_pt.x(), start_pt.y()
        w, h = self.image_width, self.image_height
        target_val = self.image.pixel(x, y)
        replace_col = QtGui.QColor(self.brush_color)
        replace_val = replace_col.rgb()
        if target_val == replace_val: return
        painter = QtGui.QPainter(self.image); painter.setPen(QtGui.QPen(replace_col))
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if self.image.pixel(cx, cy) != target_val: continue
            lx = cx
            while lx > 0 and self.image.pixel(lx - 1, cy) == target_val: lx -= 1
            rx = cx
            while rx < w - 1 and self.image.pixel(rx + 1, cy) == target_val: rx += 1
            painter.drawLine(lx, cy, rx, cy)
            for ny in (cy - 1, cy + 1):
                if 0 <= ny < h:
                    i = lx
                    while i <= rx:
                        if self.image.pixel(i, ny) == target_val:
                            stack.append((i, ny))
                            while i <= rx and self.image.pixel(i, ny) == target_val: i += 1
                        else: i += 1
        painter.end()
        self.update()
        
class GLViewport(QtOpenGL.QGLWidget):
    hoverObjectChanged = QtCore.pyqtSignal(str)
    objectSelected = QtCore.pyqtSignal(int)
    requestModelImport = QtCore.pyqtSignal(int)
    objectPlaced = QtCore.pyqtSignal()
    playSound = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera = Camera()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)
        self.keys_pressed = set()
        self.last_mouse_pos = None
        self.mouse_rotate = False
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_from_input)
        self.timer.start(16)
        
        self.scene_objects = []
        self.hovered_object_index = None
        self.selected_object_indices =[]
        self.selected_vertex_index = None
        self.undo_stack, self.redo_stack = [],[]
        
        self.int_menu_mode = False
        self.placement_mode = False
        self.placement_object_type = None
        self.move_mode = False
        self.edit_mode = False
        self.add_ai_mode = False
        self.remove_ai_mode = False
        self.snap_enabled = False
        
        self.floor_texture_id = None
        self.missing_texture_id = None
        self.new_light1_texture_id = None
        self.material_textures = {}
        
        self.ctrl_pressed = False
        self.hovered_gizmo_axis = None
        self.dragging_gizmo_axis = None
        self.clipboard =[]
        self.last_drag_angle = 0.0
        self.drag_start_mouse = None
        self.drag_start_obj_pos = None
        self.display_lists = {}
        self.custom_model_lists = {}
        self.ai_paused = False
        self.ai_speed_mult = 1.0  

    def local_to_world(self, obj, local_pos):
        x, y, z = local_pos
        x, y, z = x * obj.scale[0], y * obj.scale[1], z * obj.scale[2]
        rz = math.radians(obj.rotation[2])
        x, y = x*math.cos(rz) - y*math.sin(rz), x*math.sin(rz) + y*math.cos(rz)
        ry = math.radians(obj.rotation[1])
        x, z = x*math.cos(ry) + z*math.sin(ry), -x*math.sin(ry) + z*math.cos(ry)
        rx = math.radians(obj.rotation[0])
        y, z = y*math.cos(rx) - z*math.sin(rx), y*math.sin(rx) + z*math.cos(rx)
        return [x + obj.position[0], y + obj.position[1], z + obj.position[2]]

    def world_to_local_vec(self, obj, world_vec):
        x, y, z = world_vec
        rx = math.radians(-obj.rotation[0])
        y, z = y*math.cos(rx) - z*math.sin(rx), y*math.sin(rx) + z*math.cos(rx)
        ry = math.radians(-obj.rotation[1])
        x, z = x*math.cos(ry) + z*math.sin(ry), -x*math.sin(ry) + z*math.cos(ry)
        rz = math.radians(-obj.rotation[2])
        x, y = x*math.cos(rz) - y*math.sin(rz), x*math.sin(rz) + y*math.cos(rz)
        return [x / obj.scale[0], y / obj.scale[1], z / obj.scale[2]]

    def convert_to_custom_mesh(self, obj):
        if getattr(obj, "custom_vertices", None) is not None: return
        sx, sy, sz = obj.scale
        hsx, hsy, hsz = sx / 2.0, sy / 2.0, sz / 2.0
        obj.custom_vertices = [
            [-hsx, -hsy,  hsz],[ hsx, -hsy,  hsz], [ hsx,  hsy,  hsz],[-hsx,  hsy,  hsz], # Front
            [-hsx, -hsy, -hsz],[ hsx, -hsy, -hsz], [ hsx,  hsy, -hsz],[-hsx,  hsy, -hsz]  # Back
        ]
        obj.faces =[
            ([0, 1, 2, 3], [0,0,1]), ([5, 4, 7, 6], [0,0,-1]), ([3, 2, 6, 7], [0,1,0]),
            ([4, 5, 1, 0], [0,-1,0]), ([1, 5, 6, 2],[1,0,0]), ([4, 0, 3, 7], [-1,0,0])
        ]
        obj.scale = [1.0, 1.0, 1.0]

    def calculate_normal(self, p1, p2, p3):
        v1, v2 = [p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]], [p3[0]-p1[0], p3[1]-p1[1], p3[2]-p1[2]]
        c = [v1[1]*v2[2] - v1[2]*v2[1], v1[2]*v2[0] - v1[0]*v2[2], v1[0]*v2[1] - v1[1]*v2[0]]
        norm = math.sqrt(c[0]**2 + c[1]**2 + c[2]**2)
        return [c[0]/norm, c[1]/norm, c[2]/norm] if norm != 0 else[0,0,1]

    
    def copy_selection(self):
        if not self.selected_object_indices: return False
        self.clipboard =[copy.deepcopy(self.scene_objects[i]) for i in self.selected_object_indices if i < len(self.scene_objects)]
        return True

    def paste_selection(self):
        if not self.clipboard: return False
        self.save_undo_snapshot()
        self.unselect_all()
        new_indices, start_idx =[], len(self.scene_objects)
        for obj in self.clipboard:
            new_obj = copy.deepcopy(obj)
            new_obj.position[0] += 0.5
            new_obj.position[2] += 0.5
            new_obj.selected = True
            self.scene_objects.append(new_obj)
            new_indices.append(start_idx)
            start_idx += 1
        self.selected_object_indices = new_indices
        self.objectSelected.emit(new_indices[0] if new_indices else -1)
        self.move_mode = True
        self.update()
        return True
    
    def save_undo_snapshot(self):
        if len(self.undo_stack) > 50: self.undo_stack.pop(0)
        self.undo_stack.append(copy.deepcopy(self.scene_objects))
        self.redo_stack.clear()
        
    def undo_action(self):
        if not self.undo_stack: return
        self.redo_stack.append(copy.deepcopy(self.scene_objects))
        self.scene_objects = self.undo_stack.pop()
        self.selected_object_indices, self.hovered_object_index =[], None
        self.update()
        
    def redo_action(self):
        if not self.redo_stack: return
        self.undo_stack.append(copy.deepcopy(self.scene_objects))
        self.scene_objects = self.redo_stack.pop()
        self.selected_object_indices, self.hovered_object_index =[], None
        self.update()

    def update_from_input(self):
        if "W" in self.keys_pressed: self.camera.move("forward")
        if "S" in self.keys_pressed: self.camera.move("back")
        if "A" in self.keys_pressed: self.camera.move("left")
        if "D" in self.keys_pressed: self.camera.move("right")
        if "Q" in self.keys_pressed or "PAGEUP" in self.keys_pressed: self.camera.move("up")
        if "E" in self.keys_pressed or "PAGEDOWN" in self.keys_pressed: self.camera.move("down")


        bounds = 25.0 if self.int_menu_mode else 10.0
        if not self.ai_paused:
            iters = 2 if self.ai_speed_mult == 2.0 else 1
            bounds = 25.0 if self.int_menu_mode else 10.0
            
            objects_to_remove =[]
            
            for _ in range(iters):
                for obj in self.scene_objects:
                    obj.update_ai(self.int_menu_mode, bounds, self.scene_objects)
                    if getattr(obj, "pending_sound", None):
                        self.playSound.emit(obj.pending_sound)
                        obj.pending_sound = None
                    
                    if getattr(obj, "ai_type", "") == "Eraser":
                        if obj.hit_target:
                            objects_to_remove.append(obj)
                            if obj.target_obj in self.scene_objects:
                                objects_to_remove.append(obj.target_obj)
                        elif obj.target_obj not in self.scene_objects:
                            objects_to_remove.append(obj)

            if objects_to_remove:
                played_beep = False
                for o in set(objects_to_remove):
                    if getattr(o, "ai_type", "") == "Eraser" and o.hit_target and not played_beep:
                        if not self.window().app_config.get("disable_delete_sound", False):
                            bp1 = str(PROJECT_ROOT / "sound" / "system" / "beep.wav")
                            bp2 = str(PROJECT_ROOT / "sound" / "beep.wav")
                            self.playSound.emit(bp1 if os.path.exists(bp1) else bp2)
                            played_beep = True
                            
                    if o in self.scene_objects:
                        self.scene_objects.remove(o)
                self.selected_object_indices =[]
        self.update()

    def unselect_all(self):
        for obj in self.scene_objects: obj.selected = False
        self.selected_object_indices =[]
        self.selected_vertex_index = None
        self.move_mode = self.edit_mode = self.placement_mode = self.add_ai_mode = self.remove_ai_mode = False
        self.hovered_gizmo_axis = self.dragging_gizmo_axis = None
        self.update()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Control: self.ctrl_pressed = True
        if event.modifiers() & QtCore.Qt.ControlModifier:
            if event.key() == QtCore.Qt.Key_Z: self.undo_action(); return
            if event.key() == QtCore.Qt.Key_Y: self.redo_action(); return

        if event.key() == QtCore.Qt.Key_Escape:
            self.unselect_all()
            super().keyPressEvent(event)
            return

        key_map = {
            QtCore.Qt.Key_W: "W", QtCore.Qt.Key_S: "S", QtCore.Qt.Key_A: "A", QtCore.Qt.Key_D: "D",
            QtCore.Qt.Key_Q: "Q", QtCore.Qt.Key_E: "E", QtCore.Qt.Key_PageUp: "PAGEUP", QtCore.Qt.Key_PageDown: "PAGEDOWN"
        }
        
        if event.key() in key_map: self.keys_pressed.add(key_map[event.key()])
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Control: self.ctrl_pressed = False
        key_map = {
            QtCore.Qt.Key_W: "W", QtCore.Qt.Key_S: "S", QtCore.Qt.Key_A: "A", QtCore.Qt.Key_D: "D",
            QtCore.Qt.Key_Q: "Q", QtCore.Qt.Key_E: "E", QtCore.Qt.Key_PageUp: "PAGEUP", QtCore.Qt.Key_PageDown: "PAGEDOWN"
        }
        if event.key() in key_map and key_map[event.key()] in self.keys_pressed: self.keys_pressed.remove(key_map[event.key()])
        super().keyReleaseEvent(event)

    def get_ray_from_mouse(self, x, y):
        viewport, modelview, projection = glGetIntegerv(GL_VIEWPORT), glGetDoublev(GL_MODELVIEW_MATRIX), glGetDoublev(GL_PROJECTION_MATRIX)
        winX, winY = float(x), float(viewport[3] - y)
        try:
            p_near = gluUnProject(winX, winY, 0.0, modelview, projection, viewport)
            p_far = gluUnProject(winX, winY, 1.0, modelview, projection, viewport)
            return list(p_near), normalize(sub(p_far, p_near))
        except: return [0,0,0],[0,0,-1]

    def mousePressEvent(self, event):
        self.setFocus()
        self.activateWindow()
        if event.button() == QtCore.Qt.LeftButton:
            if (self.move_mode or self.edit_mode) and self.selected_object_indices and self.hovered_gizmo_axis:
                self.save_undo_snapshot()
                self.dragging_gizmo_axis, self.drag_start_mouse = self.hovered_gizmo_axis, event.pos()
                
                obj = self.scene_objects[self.selected_object_indices[0]]
                if self.edit_mode and getattr(obj, "custom_vertices", None) and self.selected_vertex_index is not None:
                    self.drag_start_obj_pos = {'vertex_start': list(obj.custom_vertices[self.selected_vertex_index])}
                elif self.dragging_gizmo_axis in['SX', 'SY', 'SZ']:
                    self.drag_start_obj_pos = {idx: self.scene_objects[idx].scale.copy() for idx in self.selected_object_indices}
                else:
                    self.drag_start_obj_pos = {idx: self.scene_objects[idx].position.copy() for idx in self.selected_object_indices}
                return

            if self.placement_mode: self.place_object()
            elif self.add_ai_mode: self.add_ai_to_object()
            elif self.remove_ai_mode: self.remove_ai_from_object()
            else: self.perform_raycast_selection(event.x(), event.y())
        elif event.button() == QtCore.Qt.RightButton:
            self.mouse_rotate, self.last_mouse_pos = True, event.pos()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.perform_raycast_selection(event.x(), event.y())
            if self.selected_object_indices:
                idx = self.selected_object_indices[0]
                if self.scene_objects[idx].type == "Model": self.requestModelImport.emit(idx)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.dragging_gizmo_axis:
            self.dragging_gizmo_axis, self.drag_start_mouse, self.drag_start_obj_pos = None, None, None
        if event.button() == QtCore.Qt.RightButton:
            self.mouse_rotate, self.last_mouse_pos = False, None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.mouse_rotate and self.last_mouse_pos is not None:
            self.camera.add_mouse_delta(event.x() - self.last_mouse_pos.x(), event.y() - self.last_mouse_pos.y())
            self.last_mouse_pos = event.pos()
            self.update()
        elif self.dragging_gizmo_axis: self.handle_gizmo_drag(event.x(), event.y())
        else:
            self.check_hover(event.x(), event.y())
            self.check_gizmo_hover(event.x(), event.y())
        super().mouseMoveEvent(event)

    def handle_gizmo_drag(self, x, y):
        if not self.selected_object_indices: return
        obj = self.scene_objects[self.selected_object_indices[0]]
        
        if self.edit_mode and getattr(obj, "custom_vertices", None) and self.selected_vertex_index is not None:
            if not self.drag_start_mouse: return
            dx, dy = x - self.drag_start_mouse.x(), y - self.drag_start_mouse.y()
            val = (dx if self.dragging_gizmo_axis == 'X' else -dy if self.dragging_gizmo_axis == 'Y' else -dx) * 0.02
            
            delta_world =[val if self.dragging_gizmo_axis == 'X' else 0, 
                           val if self.dragging_gizmo_axis == 'Y' else 0, 
                           val if self.dragging_gizmo_axis == 'Z' else 0]
            delta_local = self.world_to_local_vec(obj, delta_world)
            new_local_v = list(self.drag_start_obj_pos['vertex_start'])
            new_local_v =[new_local_v[i] + delta_local[i] for i in range(3)]
            
            if self.snap_enabled: new_local_v =[round(v*2)/2 for v in new_local_v]
            obj.custom_vertices[self.selected_vertex_index] = new_local_v
            self.update(); return


        if self.dragging_gizmo_axis in ['SX', 'SY', 'SZ']:
            if not self.drag_start_mouse: return
            dx, dy = x - self.drag_start_mouse.x(), y - self.drag_start_mouse.y()
            val = (dx if self.dragging_gizmo_axis == 'SX' else -dy if self.dragging_gizmo_axis == 'SY' else -dx) * 0.02
            
            for idx in self.selected_object_indices:
                new_scale = list(self.drag_start_obj_pos[idx])
                axis_idx = {'SX': 0, 'SY': 1, 'SZ': 2}[self.dragging_gizmo_axis]
                new_scale[axis_idx] = max(0.1, new_scale[axis_idx] + val)
                if self.snap_enabled: new_scale[axis_idx] = max(0.1, round(new_scale[axis_idx]*2)/2)
                self.scene_objects[idx].scale = new_scale
            self.update(); return

        pivot_pos = obj.position
        if self.dragging_gizmo_axis in['X', 'Y', 'Z']:
            if not self.drag_start_mouse: return
            dx, dy = x - self.drag_start_mouse.x(), y - self.drag_start_mouse.y()
            val = (dx if self.dragging_gizmo_axis == 'X' else -dy if self.dragging_gizmo_axis == 'Y' else -dx) * 0.02
            for idx in self.selected_object_indices:
                new_pos = list(self.drag_start_obj_pos[idx])
                new_pos[{'X':0, 'Y':1, 'Z':2}[self.dragging_gizmo_axis]] += val
                if self.snap_enabled: new_pos =[round(v*2)/2 for v in new_pos]
                self.scene_objects[idx].position = new_pos

        elif self.dragging_gizmo_axis in ['RX', 'RY', 'RZ']:
            ray_origin, ray_dir = self.get_ray_from_mouse(x, y)
            normal =[1,0,0] if self.dragging_gizmo_axis == 'RX' else[0,1,0] if self.dragging_gizmo_axis == 'RY' else[0,0,1]
            hit = intersect_plane(ray_origin, ray_dir, pivot_pos, normal)
            if hit:
                local_hit = sub(hit, pivot_pos)
                angle = math.degrees(math.atan2(local_hit[1] if self.dragging_gizmo_axis in ['RX','RZ'] else local_hit[0],
                                                local_hit[2] if self.dragging_gizmo_axis in ['RX','RY'] else local_hit[0]))
                if self.drag_start_mouse is None:
                    self.drag_start_mouse, self.last_drag_angle = QtCore.QPoint(x,y), angle
                    return
                delta, self.last_drag_angle = angle - self.last_drag_angle, angle
                axis_idx = {'RX':0, 'RY':1, 'RZ':2}[self.dragging_gizmo_axis]
                for idx in self.selected_object_indices:
                    obj = self.scene_objects[idx]
                    obj.rotation[axis_idx] += delta
                    if self.snap_enabled: obj.rotation[axis_idx] = round(obj.rotation[axis_idx] / 15.0) * 15.0
        self.update()
        
    def perform_raycast_selection(self, x, y):
        ray_origin, ray_dir = self.get_ray_from_mouse(x, y)
        
        if self.edit_mode and self.selected_object_indices:
            obj = self.scene_objects[self.selected_object_indices[0]]
            if getattr(obj, "custom_vertices", None):
                min_dist, hit_idx = float('inf'), None
                for i, v in enumerate(obj.custom_vertices):
                    w_pos = self.local_to_world(obj, v)
                    v_box_min = [w_pos[0]-0.2, w_pos[1]-0.2, w_pos[2]-0.2]
                    v_box_max =[w_pos[0]+0.2, w_pos[1]+0.2, w_pos[2]+0.2]
                    dist = ray_box_intersect(ray_origin, ray_dir, v_box_min, v_box_max)
                    if dist is not None and dist < min_dist:
                        min_dist, hit_idx = dist, i
                if hit_idx is not None:
                    self.selected_vertex_index = hit_idx
                    self.update()
                    return

        min_dist, hit_index = float('inf'), None
        for i, obj in enumerate(self.scene_objects):
            dist = ray_box_intersect(ray_origin, ray_dir, *obj.get_aabb())
            if dist is not None and dist < min_dist: min_dist, hit_index = dist, i
                
        if hit_index is not None:
            self.hovered_object_index = hit_index
            self.try_select_object()
        elif not self.ctrl_pressed and not self.placement_mode:
            self.unselect_all()

    def check_gizmo_hover(self, x, y):
        self.hovered_gizmo_axis = None
        if not self.selected_object_indices or self.add_ai_mode or self.remove_ai_mode or self.placement_mode:
            self.update(); return

        obj = self.scene_objects[self.selected_object_indices[0]]
        pos = obj.position
        draw_rings = True
        is_scale = False

        if self.edit_mode:
            draw_rings = False
            if getattr(obj, "custom_vertices", None) is not None:
                if self.selected_vertex_index is not None:
                    pos = self.local_to_world(obj, obj.custom_vertices[self.selected_vertex_index])
                else:
                    is_scale = True
            else:
                is_scale = True
        elif not self.move_mode:
            self.update(); return

        ray_origin, ray_dir = self.get_ray_from_mouse(x, y)
        dist_x = dist_ray_to_segment(ray_origin, ray_dir, pos, [pos[0]+1.5, pos[1], pos[2]])
        dist_y = dist_ray_to_segment(ray_origin, ray_dir, pos, [pos[0], pos[1]+1.5, pos[2]])
        dist_z = dist_ray_to_segment(ray_origin, ray_dir, pos, [pos[0], pos[1], pos[2]+1.5])
        
        closest_dist, hit_type = float('inf'), None
        if dist_x < 0.15 and dist_x < closest_dist: closest_dist, hit_type = dist_x, 'SX' if is_scale else 'X'
        if dist_y < 0.15 and dist_y < closest_dist: closest_dist, hit_type = dist_y, 'SY' if is_scale else 'Y'
        if dist_z < 0.15 and dist_z < closest_dist: closest_dist, hit_type = dist_z, 'SZ' if is_scale else 'Z'

        if draw_rings:
            for axis, norm, i1, i2 in[('RX',[1,0,0], 1, 2), ('RY',[0,1,0], 0, 2), ('RZ',[0,0,1], 0, 1)]:
                hit = intersect_plane(ray_origin, ray_dir, pos, norm)
                if hit and abs(math.sqrt((hit[i1]-pos[i1])**2 + (hit[i2]-pos[i2])**2) - 1.0) < 0.15:
                    self.hovered_gizmo_axis = axis; self.update(); return

        if hit_type: self.hovered_gizmo_axis = hit_type
        self.update()

    def check_hover(self, x, y):
        ray_origin, ray_dir = self.get_ray_from_mouse(x, y)
        min_dist, hover_idx = float('inf'), None
        for i, obj in enumerate(self.scene_objects):
            dist = ray_box_intersect(ray_origin, ray_dir, *obj.get_aabb())
            if dist is not None and dist < min_dist: min_dist, hover_idx = dist, i
        self.hovered_object_index = hover_idx
        self.hoverObjectChanged.emit(self.scene_objects[hover_idx].type if hover_idx is not None else "")

    def add_ai_to_object(self):
        count = 0
        if self.hovered_object_index is not None:
            self.save_undo_snapshot()
            obj = self.scene_objects[self.hovered_object_index]
            if not obj.has_ai:
                obj.has_ai = True
                obj.ai_type = "DMNPC_TLEET_WDYMS"
                obj.ai_vertex_dir = [0, 1, 0]
                obj.ai_timer = 0
                obj.ai_bend_amount = [0.0, 0.0]
                obj.ai_squash_stretch = 1.0
                count = 1
        self.add_ai_mode = False
        if hasattr(self.window(), "play_click"): self.window().play_click()
        if hasattr(self.window(), "update_comment"): self.window().update_comment(f"Add AI: Added AI to {count} object(s)")

    def remove_ai_from_object(self):
        count = 0
        if self.hovered_object_index is not None:
            self.save_undo_snapshot()
            if self.scene_objects[self.hovered_object_index].has_ai:
                self.scene_objects[self.hovered_object_index].has_ai = False
                count = 1
        self.remove_ai_mode = False
        if hasattr(self.window(), "play_click"): self.window().play_click()
        if hasattr(self.window(), "update_comment"): self.window().update_comment(f"Remove AI: Removed AI from {count} object(s)")

    def place_object(self):
        self.save_undo_snapshot()
        front = self.camera.get_front()
        pos =[self.camera.pos[0] + front[0]*3.0, 0.5, self.camera.pos[2] + front[2]*3.0]
        
        if self.placement_object_type == "Torus": pos[1] = 0.3
        elif self.placement_object_type in ["Square", "Circle", "Oval", "Triangle"]: pos[1] = 0.01

        if self.snap_enabled: pos =[round(p*2)/2 for p in pos]
             
        if self.placement_object_type == "Brush":
            new_obj = Brush(pos)
        else:
            new_obj = SceneObject(self.placement_object_type, pos)

        if self.placement_object_type == "Model":
            error_model_path = PROJECT_ROOT / "models" / "error.obj"
            if error_model_path.exists():
                new_obj.model_path = str(error_model_path)
                if str(error_model_path) not in self.custom_model_lists: self.register_custom_model(str(error_model_path))
        
        self.scene_objects.append(new_obj)
        self.placement_mode = False
        self.update()
        self.objectPlaced.emit()

    def try_select_object(self):
        if self.hovered_object_index is not None:
            if self.ctrl_pressed:
                if self.hovered_object_index in self.selected_object_indices:
                    self.selected_object_indices.remove(self.hovered_object_index)
                    self.scene_objects[self.hovered_object_index].selected = False
                else:
                    self.selected_object_indices.append(self.hovered_object_index)
                    self.scene_objects[self.hovered_object_index].selected = True
            else:
                for obj in self.scene_objects: obj.selected = False
                self.selected_object_indices =[self.hovered_object_index]
                self.scene_objects[self.hovered_object_index].selected = True
                
            if self.selected_object_indices:
                self.objectSelected.emit(self.selected_object_indices[0])
                self.move_mode = True
                self.edit_mode = False
            else:
                self.move_mode = False
            self.update()

    def unselect_all(self):
        for obj in self.scene_objects: obj.selected = False
        self.selected_object_indices =[]
        self.move_mode = self.edit_mode = self.placement_mode = self.add_ai_mode = self.remove_ai_mode = False
        self.hovered_gizmo_axis = self.dragging_gizmo_axis = None
        self.update()

    def load_scene_from_dict(self, data):
        self.scene_objects =[]
        cam = data.get("camera", {})
        self.camera.pos, self.camera.yaw, self.camera.pitch = cam.get("pos",[0.0, 2.0, 6.0]), cam.get("yaw", -90.0), cam.get("pitch", -20.0)
        self.int_menu_mode = data.get("int_menu_mode", False)
        
        for od in data.get("objects",[]):
            o_type = od.get("type", "Cube")
            if o_type == "Brush":
                obj = Brush(od.get("position"), color=od.get("color", None))
            else:
                obj = SceneObject(o_type, od.get("position"), color=od.get("color", None))
                
            obj.scale, obj.rotation, obj.has_ai = od.get("scale",[1.0, 1.0, 1.0]), od.get("rotation",[0.0, 0.0, 0.0]), od.get("has_ai", False)
            obj.ai_vertex_dir, obj.original_position, obj.model_path = od.get("ai_vertex_dir",[0, 1, 0]), od.get("original_position", None), od.get("model_path", None)
            
            obj.material = od.get("material", None)
            obj.custom_vertices = od.get("custom_vertices", None)
            obj.faces = od.get("faces", None)

            obj.ai_type = od.get("ai_type", "None")
            obj.ai_config = od.get("ai_config", {})
            obj.ai_state = od.get("ai_state", "WANDER")
            
            if obj.type == "Model" and obj.model_path and obj.model_path not in self.custom_model_lists:
                self.register_custom_model(obj.model_path)
            self.scene_objects.append(obj)
            
        self.selected_object_indices, self.hovered_object_index =[], None
        self.undo_stack.clear(); self.redo_stack.clear()
        self.update()

    def append_objects_from_dict(self, data):
        self.save_undo_snapshot()
        for od in data.get("objects",[]):
            o_type = od.get("type", "Cube")
            if o_type == "Brush":
                obj = Brush(od.get("position"), color=od.get("color", None))
            else:
                obj = SceneObject(o_type, od.get("position"), color=od.get("color", None))
                
            obj.scale, obj.rotation, obj.has_ai = od.get("scale",[1.0, 1.0, 1.0]), od.get("rotation",[0.0, 0.0, 0.0]), od.get("has_ai", False)
            obj.ai_vertex_dir, obj.model_path = od.get("ai_vertex_dir",[0, 1, 0]), od.get("model_path", None)
            obj.material = od.get("material", None)

            obj.ai_type = od.get("ai_type", "None")
            obj.ai_config = od.get("ai_config", {})
            obj.ai_state = od.get("ai_state", "WANDER")
            
            if obj.type == "Model" and obj.model_path and obj.model_path not in self.custom_model_lists:
                self.register_custom_model(obj.model_path)
            self.scene_objects.append(obj)
        self.update()

    def get_material_texture(self, path):
        if not path: return 0
        if path in self.material_textures: return self.material_textures[path]
        
        if not os.path.exists(path):
            return self.missing_texture_id
            
        image = QtGui.QImage(path)
        if image.isNull(): return self.missing_texture_id
        image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width(), image.height(), 0, GL_RGBA, GL_UNSIGNED_BYTE, ptr.asstring())
        self.material_textures[path] = tex_id
        return tex_id

    def load_texture(self, filename):
        path = PROJECT_ROOT / "materials/special" / filename
        if not path.exists(): return None
        image = QtGui.QImage(str(path))
        if image.isNull(): return None
        image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width(), image.height(), 0, GL_RGBA, GL_UNSIGNED_BYTE, ptr.asstring())
        return tex_id

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING); glEnable(GL_LIGHT0); glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_NORMALIZE)
        
        glLightfv(GL_LIGHT0, GL_AMBIENT,[0.4, 0.4, 0.4, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE,[0.6, 0.6, 0.6, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR,[0.3, 0.3, 0.3, 1.0])
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR,[0.2, 0.2, 0.2, 1.0])
        glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 20.0)

        self.floor_texture_id = self.load_texture("floor.png")
        self.missing_texture_id = self.load_texture("missing.png")
        self.new_light1_texture_id = self.load_texture("new_light1.png") or self.missing_texture_id
        
        self.display_lists = {}
        shapes =[("Cube", lambda: self.draw_cube(1.0)), ("Brush", lambda: self.draw_cube(1.0)), ("Sphere", lambda: self.draw_sphere(1.0, 20, 20)),
                  ("Cone", lambda: self.draw_cone(1.0, 20)), ("Cylinder", lambda: self.draw_cylinder(1.0, 20)),
                  ("Torus", lambda: self.draw_torus(0.3, 0.15, 20, 20)), ("3D Oval", lambda: self.draw_3d_oval(1.0, 20, 20)),
                  ("Square", lambda: self.draw_square(1.0)), ("Circle", lambda: self.draw_circle(1.0, 30)),
                  ("Oval", lambda: self.draw_oval(1.0, 30)), ("Triangle", lambda: self.draw_triangle(1.0))]
        for shape, func in shapes:
            lid = glGenLists(1)
            glNewList(lid, GL_COMPILE)
            func()
            glEndList()
            self.display_lists[shape] = lid
            
        error_path = PROJECT_ROOT / "models" / "error.obj"
        if error_path.exists(): self.register_custom_model(str(error_path))

    def register_custom_model(self, path):
        if not os.path.exists(path): return
        verts, norms, uvs, mat_groups, mtl_filename = load_obj_file(path)
        if not verts: return

        loaded_materials = {}
        def try_load_texture(t_path):
            tex_name = Path(t_path).name
            model_name = Path(path).stem
            candidates =[
                PROJECT_ROOT / "materials" / "models" / model_name / tex_name,
                PROJECT_ROOT / "materials" / "models" / tex_name,
                Path(path).parent / tex_name,
                Path(path).parent / "textures" / tex_name
            ]
            for p in candidates:
                if p.exists() and p.is_file():
                    image = QtGui.QImage(str(p))
                    if not image.isNull():
                        image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
                        ptr = image.bits()
                        ptr.setsize(image.byteCount())
                        tex_id = glGenTextures(1)
                        glBindTexture(GL_TEXTURE_2D, tex_id)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width(), image.height(), 0, GL_RGBA, GL_UNSIGNED_BYTE, ptr.asstring())
                        return tex_id
            return 0

        if mtl_filename:
            raw_materials = load_mtl_file(str(Path(path).parent / mtl_filename))
            for mat_name, props in raw_materials.items():
                tex_id = try_load_texture(props['texture']) if props['texture'] else 0
                if not tex_id: tex_id = self.new_light1_texture_id if self.new_light1_texture_id else self.missing_texture_id
                loaded_materials[mat_name] = {'tex_id': tex_id, 'diffuse': props['diffuse'], 'texture': props['texture']}

        lid = glGenLists(1)
        glNewList(lid, GL_COMPILE)
        if not loaded_materials:
            loaded_materials["Default"] = {'tex_id': self.new_light1_texture_id or self.missing_texture_id, 'diffuse':[1,1,1]}

        for mat_name, faces in mat_groups.items():
            mat = loaded_materials.get(mat_name, loaded_materials.get("Default"))
            
            tex_path = mat.get('texture', '') if mat else ''
            name_check = f"{mat_name} {tex_path} {Path(path).stem}".lower()
            is_trans = "_trans" in name_check or "_glass" in name_check
            is_cutout = "_alpha" in name_check or "_cutout" in name_check

            if mat and mat['tex_id'] > 0:
                glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, mat['tex_id'])
            else:
                glDisable(GL_TEXTURE_2D)
                if not mat: 
                    glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, self.missing_texture_id)

            def draw_faces():
                glBegin(GL_TRIANGLES)
                for face in faces:
                    v0_idx, vt0_idx, vn0_idx = face[0]
                    for i in range(1, len(face)-1):
                        for v_idx, vt_idx, vn_idx in [face[0], face[i], face[i+1]]:
                            if 0 <= vn_idx < len(norms): glNormal3f(*norms[vn_idx])
                            if 0 <= vt_idx < len(uvs): glTexCoord2f(*uvs[vt_idx])
                            glVertex3f(*verts[v_idx])
                glEnd()

            if is_trans:
                glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glDepthMask(GL_FALSE)
                
                if mat and mat['tex_id'] > 0: glColor4f(1.0, 1.0, 1.0, 0.5)
                else: glColor4f(*(mat['diffuse'] + [0.5]))
                
                glEnable(GL_CULL_FACE)
                glCullFace(GL_FRONT)
                draw_faces()
                glCullFace(GL_BACK)
                draw_faces()
                glDisable(GL_CULL_FACE)
                
                glDepthMask(GL_TRUE)
                glDisable(GL_BLEND)
                
            elif is_cutout:
                glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glEnable(GL_ALPHA_TEST); glAlphaFunc(GL_GREATER, 0.5)
                
                if mat and mat['tex_id'] > 0: glColor3f(1.0, 1.0, 1.0)
                else: glColor3f(*mat['diffuse'])
                
                draw_faces()
                
                glDisable(GL_ALPHA_TEST)
                glDisable(GL_BLEND)
                
            else:
                if mat and mat['tex_id'] > 0: glColor3f(1.0, 1.0, 1.0)
                else: glColor3f(*mat['diffuse'])
                draw_faces()

        glEndList()
        self.custom_model_lists[path] = lid
        
    def resizeGL(self, w, h):
        glViewport(0, 0, w, max(h, 1))
        glMatrixMode(GL_PROJECTION); glLoadIdentity()
        gluPerspective(60.0, w / float(max(h, 1)), 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        fx, fy, fz = self.camera.get_front()
        ux, uy, uz = self.camera.get_up()
        px, py, pz = self.camera.pos
        gluLookAt(px, py, pz, px + fx, py + fy, pz + fz, ux, uy, uz)
        glLightfv(GL_LIGHT0, GL_POSITION,[px + 5, py + 10, pz + 5, 1.0])

        self.draw_skybox(px, py, pz)
        self.draw_floor()
        
        opaque_objs =[]
        trans_objs =[]
        
        for obj in self.scene_objects:
            is_trans = False
            mat_path = getattr(obj, "material", None)
            
            if mat_path and ("_trans" in mat_path.lower() or "_glass" in mat_path.lower()):
                is_trans = True
            elif obj.type == "Model" and obj.model_path and ("_trans" in obj.model_path.lower() or "_glass" in obj.model_path.lower()):
                is_trans = True
                
            if is_trans:
                trans_objs.append(obj)
            else:
                opaque_objs.append(obj)
                
        trans_objs.sort(key=lambda o: (o.position[0]-px)**2 + (o.position[1]-py)**2 + (o.position[2]-pz)**2, reverse=True)
        
        for obj in opaque_objs: self.draw_object(obj)
        for obj in trans_objs: self.draw_object(obj)

        if self.edit_mode and self.selected_object_indices:
            obj = self.scene_objects[self.selected_object_indices[0]]
            if getattr(obj, "custom_vertices", None) is not None:
                self.draw_vertices(obj)

        if (self.move_mode or self.edit_mode) and self.selected_object_indices: 
            self.draw_gizmo()
    
    def draw_vertices(self, obj):
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_DEPTH_TEST)
        for i, v in enumerate(obj.custom_vertices):
            w_pos = self.local_to_world(obj, v)
            glColor3f(1.0, 1.0, 0.0) if i == self.selected_vertex_index else glColor3f(1.0, 0.0, 0.0)
            glPushMatrix()
            glTranslatef(*w_pos)
            self.draw_cube(0.15)
            glPopMatrix()
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
    
    def draw_skybox(self, px, py, pz):
        skybox_tex = self.window().app_config.get("world_skybox", "")
        if not skybox_tex or not os.path.exists(skybox_tex):
            return
        
        tex_id = self.get_material_texture(skybox_tex)
        if not tex_id:
            return
        
        glDisable(GL_LIGHTING)
        glDepthMask(GL_FALSE)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glColor3f(1.0, 1.0, 1.0)
        
        glPushMatrix()
        glTranslatef(px, py, pz)
        
        s = 50.0
        glBegin(GL_QUADS)
        glTexCoord2f(0,0); glVertex3f(-s, -s, s); glTexCoord2f(1,0); glVertex3f( s, -s, s)
        glTexCoord2f(1,1); glVertex3f( s,  s, s); glTexCoord2f(0,1); glVertex3f(-s,  s, s)
        glTexCoord2f(1,0); glVertex3f(-s, -s,-s); glTexCoord2f(1,1); glVertex3f(-s,  s,-s)
        glTexCoord2f(0,1); glVertex3f( s,  s,-s); glTexCoord2f(0,0); glVertex3f( s, -s,-s)
        glTexCoord2f(0,0); glVertex3f(-s, -s,-s); glTexCoord2f(1,0); glVertex3f(-s, -s, s)
        glTexCoord2f(1,1); glVertex3f(-s,  s, s); glTexCoord2f(0,1); glVertex3f(-s,  s,-s)
        glTexCoord2f(1,0); glVertex3f( s, -s,-s); glTexCoord2f(1,1); glVertex3f( s,  s,-s)
        glTexCoord2f(0,1); glVertex3f( s,  s, s); glTexCoord2f(0,0); glVertex3f( s, -s, s)
        glTexCoord2f(0,1); glVertex3f(-s,  s,-s); glTexCoord2f(0,0); glVertex3f(-s,  s, s)
        glTexCoord2f(1,0); glVertex3f( s,  s, s); glTexCoord2f(1,1); glVertex3f( s,  s,-s)
        glTexCoord2f(0,0); glVertex3f(-s, -s,-s); glTexCoord2f(1,0); glVertex3f( s, -s,-s)
        glTexCoord2f(1,1); glVertex3f( s, -s, s); glTexCoord2f(0,1); glVertex3f(-s, -s, s)
        glEnd()
        
        glPopMatrix()
        glDepthMask(GL_TRUE)
        glEnable(GL_LIGHTING)

    def draw_floor(self):
        size, repeats = (1000.0, 500.0) if self.int_menu_mode else (10.0, 5.0) 
        
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.floor_texture_id if self.floor_texture_id else 0)
        glColor3f(1.0, 1.0, 1.0); glBegin(GL_QUADS); glNormal3f(0, 1, 0)
        glTexCoord2f(0.0, 0.0); glVertex3f(-size, 0.0, -size)
        glTexCoord2f(repeats, 0.0); glVertex3f(size, 0.0, -size)
        glTexCoord2f(repeats, repeats); glVertex3f(size, 0.0, size)
        glTexCoord2f(0.0, repeats); glVertex3f(-size, 0.0, size)
        glEnd(); glDisable(GL_TEXTURE_2D)

    def draw_gizmo(self):
        if not self.selected_object_indices or self.add_ai_mode or self.remove_ai_mode or self.placement_mode: return
        obj = self.scene_objects[self.selected_object_indices[0]]
        
        draw_rings = True
        is_scale = False
        
        if self.edit_mode:
            draw_rings = False
            if getattr(obj, "custom_vertices", None) is not None:
                if self.selected_vertex_index is not None:
                    x, y, z = self.local_to_world(obj, obj.custom_vertices[self.selected_vertex_index])
                else:
                    x, y, z = obj.position
                    is_scale = True
            else:
                x, y, z = obj.position
                is_scale = True
        elif self.move_mode:
            x, y, z = obj.position
        else: return

        glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING); glDisable(GL_TEXTURE_2D)
        
        len_axis = 1.5
        glLineWidth(3.0); glBegin(GL_LINES)
        
        c_x = (1,1,0) if self.hovered_gizmo_axis in ['X','SX'] or self.dragging_gizmo_axis in ['X','SX'] else (1,0,0)
        c_y = (1,1,0) if self.hovered_gizmo_axis in ['Y','SY'] or self.dragging_gizmo_axis in ['Y','SY'] else (0,1,0)
        c_z = (1,1,0) if self.hovered_gizmo_axis in['Z','SZ'] or self.dragging_gizmo_axis in ['Z','SZ'] else (0,0,1)
        
        glColor3f(*c_x); glVertex3f(x,y,z); glVertex3f(x+len_axis,y,z)
        glColor3f(*c_y); glVertex3f(x,y,z); glVertex3f(x,y+len_axis,z)
        glColor3f(*c_z); glVertex3f(x,y,z); glVertex3f(x,y,z+len_axis)
        glEnd()
        
        end_s = 0.2
        if is_scale:
            glPushMatrix(); glTranslatef(x+len_axis,y,z); glColor3f(*c_x); self.draw_cube(end_s); glPopMatrix()
            glPushMatrix(); glTranslatef(x,y+len_axis,z); glColor3f(*c_y); self.draw_cube(end_s); glPopMatrix()
            glPushMatrix(); glTranslatef(x,y,z+len_axis); glColor3f(*c_z); self.draw_cube(end_s); glPopMatrix()
        else:
            glPushMatrix(); glTranslatef(x+len_axis,y,z); glRotatef(-90,0,0,1); glColor3f(*c_x); self.draw_cone(end_s, 10); glPopMatrix()
            glPushMatrix(); glTranslatef(x,y+len_axis,z); glColor3f(*c_y); self.draw_cone(end_s, 10); glPopMatrix()
            glPushMatrix(); glTranslatef(x,y,z+len_axis); glRotatef(90,1,0,0); glColor3f(*c_z); self.draw_cone(end_s, 10); glPopMatrix()

        if draw_rings:
            r_ring = 1.0; glLineWidth(2.0)
            glPushMatrix(); glTranslatef(x,y,z); glRotatef(90,0,1,0); glRotatef(90,1,0,0)
            glColor3f(1,1,0) if self.hovered_gizmo_axis == 'RX' or self.dragging_gizmo_axis == 'RX' else glColor3f(1,0,0); self.draw_circle_line(r_ring, 32); glPopMatrix()
            glPushMatrix(); glTranslatef(x,y,z)
            glColor3f(1,1,0) if self.hovered_gizmo_axis == 'RY' or self.dragging_gizmo_axis == 'RY' else glColor3f(0,1,0); self.draw_circle_line(r_ring, 32); glPopMatrix()
            glPushMatrix(); glTranslatef(x,y,z); glRotatef(90,1,0,0)
            glColor3f(1,1,0) if self.hovered_gizmo_axis == 'RZ' or self.dragging_gizmo_axis == 'RZ' else glColor3f(0,0,1); self.draw_circle_line(r_ring, 32); glPopMatrix()
            
        glLineWidth(1.0); glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING)

    def draw_circle_line(self, r, segs):
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            theta = 2.0 * math.pi * float(i)/segs
            glVertex3f(r*math.cos(theta), 0, r*math.sin(theta))
        glEnd()

    def draw_object(self, obj):
        glPushMatrix()
        
        jx, jy, jz = getattr(obj, 'jitter_offset',[0.0, 0.0, 0.0])
        px, py, pz = obj.position[0] + jx, obj.position[1] + jy, obj.position[2] + jz
        glTranslatef(px, py, pz)
        
        if obj.ai_type == "Siuef" and obj.speech_timer > 0:
            glColor3f(1.0, 0.5, 0.0)
            self.renderText(0.0, 0.3, 0.0, obj.speech_text, QtGui.QFont(FONT_FAMILY, 14, QtGui.QFont.Bold))
        
        use_gris_physics = True
        if obj.ai_type == "DMNPC_TLEET_WDYMS" and obj.ai_config.get("dmnpc_phys") == "Model":
            use_gris_physics = False
        if obj.ai_type == "Siuef":
            use_gris_physics = False

        if obj.has_ai and use_gris_physics:
            glRotatef(obj.ai_look_rotation[1], 0, 1, 0)
            glRotatef(obj.ai_look_rotation[0], 1, 0, 0)
            
        glRotatef(obj.rotation[0], 1, 0, 0)
        glRotatef(obj.rotation[1], 0, 1, 0)
        glRotatef(obj.rotation[2], 0, 0, 1)

        if obj.has_ai and use_gris_physics:
            glMultMatrixf([1.0, 0.0, 0.0, 0.0, obj.ai_bend_amount[0], obj.ai_squash_stretch, obj.ai_bend_amount[1], 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0])

        glScalef(obj.scale[0], obj.scale[1], obj.scale[2])

        if obj.selected:
            glDisable(GL_LIGHTING); glLineWidth(3.0); glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glColor3f(1.0, 1.0, 0.0); self.draw_shape(obj, 1.05)
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL); glLineWidth(1.0); glEnable(GL_LIGHTING)

        self.draw_shape(obj, 1.0)
        
        if obj.has_ai and obj.ai_type != "Siuef":
            glDisable(GL_LIGHTING); glColor3f(1, 0, 1)
            glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(0, 1.0, 0); glEnd()
            glEnable(GL_LIGHTING)
        glPopMatrix()

    def draw_shape(self, obj, scale):
        glPushMatrix(); glScalef(scale, scale, scale)
        is_trans = False
        is_cutout = False
        
        is_model = (obj.type == "Model")
        
        if not is_model:
            mat_path = getattr(obj, "material", None)
            if mat_path:
                name = mat_path.lower()
                if "_trans" in name or "_glass" in name: is_trans = True
                if "_alpha" in name or "_cutout" in name: is_cutout = True

            if obj.color:
                glDisable(GL_TEXTURE_2D)
                if is_trans: glColor4f(obj.color[0], obj.color[1], obj.color[2], 0.5)
                else: glColor3f(*obj.color)
            else:
                glEnable(GL_TEXTURE_2D)
                if is_trans: glColor4f(1.0, 1.0, 1.0, 0.5)
                else: glColor3f(1.0, 1.0, 1.0)
                
                if mat_path: glBindTexture(GL_TEXTURE_2D, self.get_material_texture(mat_path))
                else: glBindTexture(GL_TEXTURE_2D, self.missing_texture_id or 0)

        def draw_geom():
            if getattr(obj, "custom_vertices", None) is not None:
                for face_indices, _ in obj.faces:
                    glBegin(GL_QUADS)
                    p1 = obj.custom_vertices[face_indices[0]]
                    p2 = obj.custom_vertices[face_indices[1]]
                    p3 = obj.custom_vertices[face_indices[2]]
                    glNormal3f(*self.calculate_normal(p1, p2, p3))
                    tex_coords =[(0,0), (1,0), (1,1), (0,1)]
                    for i, v_idx in enumerate(face_indices):
                        glTexCoord2f(*tex_coords[i])
                        glVertex3f(*obj.custom_vertices[v_idx])
                    glEnd()
            elif is_model:
                glCallList(self.custom_model_lists.get(obj.model_path) or self.custom_model_lists.get(str(PROJECT_ROOT / "models" / "error.obj")) or self.display_lists.get("Cube", 0))
            elif obj.type in self.display_lists: 
                glCallList(self.display_lists[obj.type])
            else: 
                self.draw_cube(1.0)

        if is_model:
            draw_geom()
        else:
            if is_trans:
                glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glDepthMask(GL_FALSE)
                
                glEnable(GL_CULL_FACE)
                glCullFace(GL_FRONT)
                draw_geom()
                glCullFace(GL_BACK)
                draw_geom()
                glDisable(GL_CULL_FACE)
                
                glDepthMask(GL_TRUE)
                glDisable(GL_BLEND)
            elif is_cutout:
                glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glEnable(GL_ALPHA_TEST); glAlphaFunc(GL_GREATER, 0.5)
                draw_geom()
                glDisable(GL_ALPHA_TEST)
                glDisable(GL_BLEND)
            else:
                draw_geom()

        glPopMatrix(); glDisable(GL_TEXTURE_2D)
	
    def draw_cube(self, s):
        hs = s / 2.0
        for norm, pts in [
            ((0,0,1),[(-hs,-hs,hs), (hs,-hs,hs), (hs,hs,hs), (-hs,hs,hs)]),
            ((0,0,-1),[(-hs,-hs,-hs), (-hs,hs,-hs), (hs,hs,-hs), (hs,-hs,-hs)]),
            ((0,1,0),[(-hs,hs,-hs), (-hs,hs,hs), (hs,hs,hs), (hs,hs,-hs)]),
            ((0,-1,0),[(-hs,-hs,-hs), (hs,-hs,-hs), (hs,-hs,hs), (-hs,-hs,hs)]),
            ((1,0,0),[(hs,-hs,-hs), (hs,hs,-hs), (hs,hs,hs), (hs,-hs,hs)]),
            ((-1,0,0),[(-hs,-hs,-hs), (-hs,-hs,hs), (-hs,hs,hs), (-hs,hs,-hs)])
        ]:
            glBegin(GL_QUADS); glNormal3f(*norm)
            for i, (tx, ty) in enumerate([(0,0), (1,0), (1,1), (0,1)]):
                glTexCoord2f(tx, ty); glVertex3f(*pts[i])
            glEnd()

    def draw_sphere(self, radius, slices, stacks):
        for i in range(stacks):
            lat0, lat1 = math.pi * (-0.5 + float(i) / stacks), math.pi * (-0.5 + float(i + 1) / stacks)
            z0, zr0 = radius * math.sin(lat0), radius * math.cos(lat0)
            z1, zr1 = radius * math.sin(lat1), radius * math.cos(lat1)
            glBegin(GL_QUAD_STRIP)
            for j in range(slices + 1):
                lng = 2 * math.pi * float(j) / slices
                x, y = math.cos(lng), math.sin(lng)
                u = float(j) / slices
                glNormal3f(x * math.cos(lat0), y * math.cos(lat0), math.sin(lat0)); glTexCoord2f(u, float(i) / stacks); glVertex3f(x * zr0, y * zr0, z0)
                glNormal3f(x * math.cos(lat1), y * math.cos(lat1), math.sin(lat1)); glTexCoord2f(u, float(i + 1) / stacks); glVertex3f(x * zr1, y * zr1, z1)
            glEnd()

    def draw_cone(self, height, slices):
        radius = height / 2.0
        glBegin(GL_TRIANGLE_FAN); glNormal3f(0, 1, 0); glTexCoord2f(0.5, 1.0); glVertex3f(0, height, 0)
        for i in range(slices + 1):
            angle = 2 * math.pi * i / slices
            x, z = radius * math.cos(angle), radius * math.sin(angle)
            l = math.sqrt(x*x + radius*radius + z*z)
            glNormal3f(x/l if l else 0, radius/l if l else 0, z/l if l else 0)
            glTexCoord2f(0.5 + 0.5 * math.cos(angle), 0.5 + 0.5 * math.sin(angle)); glVertex3f(x, 0, z)
        glEnd()
        glBegin(GL_TRIANGLE_FAN); glNormal3f(0, -1, 0); glTexCoord2f(0.5, 0.5); glVertex3f(0, 0, 0)
        for i in range(slices + 1):
            angle = 2 * math.pi * i / slices
            glTexCoord2f(0.5 + 0.5 * math.cos(-angle), 0.5 + 0.5 * math.sin(-angle)); glVertex3f(radius * math.cos(-angle), 0, radius * math.sin(-angle))
        glEnd()

    def draw_cylinder(self, height, slices):
        radius = height / 3.0
        glBegin(GL_QUAD_STRIP)
        for i in range(slices + 1):
            angle = 2 * math.pi * i / slices
            x, z = radius * math.cos(angle), radius * math.sin(angle)
            glNormal3f(x / radius, 0, z / radius)
            glTexCoord2f(float(i) / slices, 0.0); glVertex3f(x, 0, z)
            glTexCoord2f(float(i) / slices, 1.0); glVertex3f(x, height, z)
        glEnd()
        for y_pos, norm_y, mult in[(height, 1, 1), (0, -1, -1)]:
            glBegin(GL_TRIANGLE_FAN); glNormal3f(0, norm_y, 0); glTexCoord2f(0.5, 0.5); glVertex3f(0, y_pos, 0)
            for i in range(slices + 1):
                angle = mult * 2 * math.pi * i / slices
                glTexCoord2f(0.5 + 0.5 * math.cos(angle), 0.5 + 0.5 * math.sin(angle)); glVertex3f(radius * math.cos(angle), y_pos, radius * math.sin(angle))
            glEnd()

    def draw_torus(self, major_radius, minor_radius, major_segments, minor_segments):
        for i in range(major_segments):
            glBegin(GL_QUAD_STRIP)
            for j in range(minor_segments + 1):
                for k in range(2):
                    s, t = (i + k) % major_segments, j % minor_segments
                    angle1, angle2 = 2 * math.pi * s / major_segments, 2 * math.pi * t / minor_segments
                    cx = (major_radius + minor_radius * math.cos(angle2))
                    glNormal3f(math.cos(angle2) * math.cos(angle1), math.sin(angle2), math.cos(angle2) * math.sin(angle1))
                    glTexCoord2f(float(s) / major_segments, float(j) / minor_segments)
                    glVertex3f(cx * math.cos(angle1), minor_radius * math.sin(angle2), cx * math.sin(angle1))
            glEnd()

    def draw_3d_oval(self, size, slices, stacks):
        glPushMatrix(); glScalef(1.0, 0.7, 0.6); self.draw_sphere(size, slices, stacks); glPopMatrix()

    def draw_square(self, size):
        hs = size / 2.0
        glBegin(GL_QUADS); glNormal3f(0, 1, 0)
        for tx, ty, x, z in[(0,0,-hs,-hs), (1,0,hs,-hs), (1,1,hs,hs), (0,1,-hs,hs)]:
            glTexCoord2f(tx, ty); glVertex3f(x, 0, z)
        glEnd()

    def draw_circle(self, radius, segments):
        glBegin(GL_TRIANGLE_FAN); glNormal3f(0, 1, 0); glTexCoord2f(0.5, 0.5); glVertex3f(0, 0, 0)
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            glTexCoord2f(0.5 + 0.5 * math.cos(angle), 0.5 + 0.5 * math.sin(angle)); glVertex3f(radius * math.cos(angle), 0, radius * math.sin(angle))
        glEnd()

    def draw_oval(self, size, segments):
        glPushMatrix(); glScalef(1.0, 1.0, 0.6); self.draw_circle(size, segments); glPopMatrix()

    def draw_triangle(self, size):
        glBegin(GL_TRIANGLES); glNormal3f(0, 1, 0)
        for tx, ty, x, z in[(0.5,1.0,0,size), (0.0,0.0,-size,-size), (1.0,0.0,size,-size)]:
            glTexCoord2f(tx, ty); glVertex3f(x, 0, z)
        glEnd()


class ToolboxButton(QtWidgets.QToolButton):
    swapRequested = QtCore.pyqtSignal(object, object)

    def __init__(self, title, icon_name=None, parent=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.setText(title)
        self.setFixedSize(90, 85)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.original_icon = None
        
        self.adjust_mode = False
        self.is_drag_target = False
        self.drag_start_pos = None
        self.setAcceptDrops(True)
        
        if icon_name:
            img_path = PROJECT_ROOT / "materials" / "gui" / icon_name
            if not img_path.exists(): img_path = PROJECT_ROOT / "assets" / icon_name
            if img_path.exists():
                pixmap = QtGui.QPixmap(str(img_path))
                scaled = pixmap.scaled(50, 45, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                icon = QtGui.QIcon(scaled)
                self.setIcon(icon)
                self.setIconSize(QtCore.QSize(50, 45))
                self.original_icon = icon

        self.setStyleSheet(get_btn_style() + "QToolButton { font-size: 10pt; font-weight: bold; padding-top: 2px; }")

    def set_color_visual(self, color):
        pixmap = QtGui.QPixmap(50, 45)
        pixmap.fill(color)
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 4))
        painter.drawRect(0, 0, 50, 45)
        painter.end()
        self.setIcon(QtGui.QIcon(pixmap))

    def mousePressEvent(self, event):
        if self.adjust_mode and event.button() == QtCore.Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.adjust_mode and self.drag_start_pos:
            if (event.pos() - self.drag_start_pos).manhattanLength() > 5:
                self.setDown(False)
                drag = QtGui.QDrag(self)
                mime = QtCore.QMimeData()
                mime.setText(self.objectName())
                drag.setMimeData(mime)
                
                pixmap = self.grab()
                drag.setPixmap(pixmap)
                drag.setHotSpot(event.pos())
                
                self.drag_start_pos = None
                drag.exec_(QtCore.Qt.MoveAction)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.adjust_mode:
            self.drag_start_pos = None
            self.setDown(False)
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if self.adjust_mode and event.source() != self and isinstance(event.source(), ToolboxButton):
            self.is_drag_target = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if self.adjust_mode:
            self.is_drag_target = False
            self.update()

    def dropEvent(self, event):
        if self.adjust_mode:
            self.is_drag_target = False
            self.update()
            source = event.source()
            if source and source != self and isinstance(source, ToolboxButton):
                self.swapRequested.emit(source, self)
                event.acceptProposedAction()

    def paintEvent(self, event):
        super().paintEvent(event)
        if getattr(self, "is_drag_target", False):
            painter = QtGui.QPainter(self)
            pen = QtGui.QPen(QtCore.Qt.white, 3, QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))
            painter.end()

class ToolboxPlaceholder(QtWidgets.QWidget):
    swapRequested = QtCore.pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(90, 85)
        self.setAcceptDrops(True)
        self.adjust_mode = False
        self.is_drag_target = False

    def dragEnterEvent(self, event):
        if self.adjust_mode and isinstance(event.source(), ToolboxButton):
            self.is_drag_target = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if self.adjust_mode:
            self.is_drag_target = False
            self.update()

    def dropEvent(self, event):
        if self.adjust_mode:
            self.is_drag_target = False
            self.update()
            source = event.source()
            if source and isinstance(source, ToolboxButton):
                self.swapRequested.emit(source, self)
                event.acceptProposedAction()

    def paintEvent(self, event):
        super().paintEvent(event)
        if getattr(self, "is_drag_target", False):
            painter = QtGui.QPainter(self)
            pen = QtGui.QPen(QtCore.Qt.white, 3, QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))
            painter.end()

class TransportButton(QtWidgets.QPushButton):
    def __init__(self, symbol, font_size=24, parent=None):
        super().__init__(symbol, parent)
        self.setFixedSize(50, 50)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setStyleSheet(get_btn_style() + f"QPushButton {{ font: {font_size}pt '{FONT_FAMILY}'; font-weight: bold; padding-bottom: 4px; }}")

class DottedHeaderFrame(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; {get_3d_border(False, 2)} }}")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        
        pen_dark = QtGui.QPen(QtGui.QColor('#606060'))
        pen_dark.setStyle(QtCore.Qt.CustomDashLine)
        pen_dark.setDashPattern([6, 4]) 
        
        pen_light = QtGui.QPen(QtGui.QColor('#E0E0E0'))
        pen_light.setStyle(QtCore.Qt.CustomDashLine)
        pen_light.setDashPattern([6, 4]) 
        
        w, h = self.width(), self.height()
        offset = 2
        
        painter.setPen(pen_dark)
        painter.drawRect(offset, offset, w - offset*2 - 1, h - offset*2 - 1)
        
        painter.setPen(pen_light)
        painter.drawRect(offset + 1, offset + 1, w - offset*2 - 1, h - offset*2 - 1)

class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(28)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.drag_pos = None
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)
        
        icon_label = QtWidgets.QLabel()
        icon_label.setStyleSheet("border: none; background: transparent;")
        ico_path = PROJECT_ROOT / "icon.ico"
        if ico_path.exists():
            pix = QtGui.QPixmap(str(ico_path)).scaled(18, 18, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            icon_label.setPixmap(pix)
        layout.addWidget(icon_label)
        
        self.title_label = QtWidgets.QLabel("gris.exe - untitled.dme")
        self.title_label.setStyleSheet(f'color: black; font: 10pt "{FONT_FAMILY}"; border: none; background: transparent;')
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        self.min_btn = QtWidgets.QPushButton("<")
        self.max_btn = QtWidgets.QPushButton("—")
        self.close_btn = QtWidgets.QPushButton("X")
        
        for btn in (self.min_btn, self.max_btn):
            btn.setFixedSize(24, 24)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setFocusPolicy(QtCore.Qt.NoFocus)
            btn.setStyleSheet(get_btn_style() + "QPushButton { font-weight: bold; font-size: 9pt; }")
            layout.addWidget(btn)
            
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.close_btn.setStyleSheet(get_btn_style(HOVER_RED, PRESS_RED) + "QPushButton { font-weight: bold; font-size: 9pt; }")
        layout.addWidget(self.close_btn)
        
        self.min_btn.clicked.connect(parent.showMinimized)
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(parent.close)

    def toggle_maximize(self):
        if self.parent_window.isMaximized() or self.parent_window.isFullScreen(): self.parent_window.showNormal()
        else: self.parent_window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton: self.drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == QtCore.Qt.LeftButton: self.parent_window.move(event.globalPos() - self.drag_pos)
    def mouseReleaseEvent(self, event): self.drag_pos = None
    def mouseDoubleClickEvent(self, event): self.toggle_maximize()

class DialogTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="Dialog"):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(28)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.drag_pos = None
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)
        
        icon_label = QtWidgets.QLabel()
        icon_label.setStyleSheet("border: none; background: transparent;")
        ico_path = PROJECT_ROOT / "icon.ico"
        if ico_path.exists():
            pix = QtGui.QPixmap(str(ico_path)).scaled(18, 18, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            icon_label.setPixmap(pix)
        layout.addWidget(icon_label)
        
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet(f'color: black; font: 10pt "{FONT_FAMILY}"; border: none; background: transparent;')
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        self.close_btn = QtWidgets.QPushButton("X")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.close_btn.setStyleSheet(get_btn_style(HOVER_RED, PRESS_RED) + "QPushButton { font-weight: bold; font-size: 9pt; }")
        layout.addWidget(self.close_btn)
        
        self.close_btn.clicked.connect(parent.reject)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton: self.drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == QtCore.Qt.LeftButton: self.parent_window.move(event.globalPos() - self.drag_pos)
    def mouseReleaseEvent(self, event): self.drag_pos = None

class MaterialBrowserDialog(QtWidgets.QDialog):
    def __init__(self, parent, gl_view):
        super().__init__(parent)
        self.gl_view = gl_view
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        self.resize(550, 480)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        
        header_frame = DottedHeaderFrame(self)
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(0)
        self.title_bar = DialogTitleBar(self, "MATERIAL BROWSER")
        header_layout.addWidget(self.title_bar)
        layout.addWidget(header_frame)
        
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search materials...")
        self.search_bar.setStyleSheet(f"QLineEdit {{ background-color: #D0D0D0; {get_3d_border(True, 2)} font: 11pt '{FONT_FAMILY}'; padding: 4px; color: black; }}")
        self.search_bar.textChanged.connect(self.populate_grid)
        layout.addWidget(self.search_bar)
        
        sunken_frame = QtWidgets.QFrame()
        bg_path = PROJECT_ROOT / "materials" / "gui" / "bg.png"
        bg_path_str = str(bg_path).replace('\\', '/') if bg_path.exists() else ""
        bg_style = f"background-image: url({bg_path_str}); background-repeat: repeat;" if bg_path_str else f"background-color: {BASE_BG};"
        sunken_frame.setStyleSheet(f"QFrame {{ {bg_style} {get_3d_border(True, 3)} }}")
        
        sunken_layout = QtWidgets.QVBoxLayout(sunken_frame)
        sunken_layout.setContentsMargins(2, 2, 2, 2)
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ border: 1px solid #606060; background: #C0C0C0; width: 16px; margin: 16px 0 16px 0; }}
            QScrollBar::handle:vertical {{ background: {PANEL_BG}; {get_3d_border(False, 1)} min-height: 20px; }}
            QScrollBar::add-line:vertical {{ {get_3d_border(False, 1)} background: {PANEL_BG}; height: 16px; subcontrol-position: bottom; subcontrol-origin: margin; }}
            QScrollBar::sub-line:vertical {{ {get_3d_border(False, 1)} background: {PANEL_BG}; height: 16px; subcontrol-position: top; subcontrol-origin: margin; }}
        """)
        
        container = QtWidgets.QWidget()
        container.setStyleSheet("background: transparent;")
        self.grid = QtWidgets.QGridLayout(container)
        self.grid.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.grid.setSpacing(10)
        
        scroll.setWidget(container)
        sunken_layout.addWidget(scroll)
        layout.addWidget(sunken_frame)
        
        self.mat_widgets =[]
        self.load_materials()
        self.populate_grid()
        
    def load_materials(self):
        btn_reset = QtWidgets.QToolButton()
        btn_reset.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        btn_reset.setText("Default")
        btn_reset.setFixedSize(100, 100)
        btn_reset.setCursor(QtCore.Qt.PointingHandCursor)
        btn_reset.setStyleSheet(get_btn_style() + "QToolButton { font-size: 9pt; font-weight: bold; background-color: #D0D0D0; }")
        btn_reset.clicked.connect(lambda: self.apply_material(None))
        self.mat_widgets.append(("default", btn_reset))
        
        mat_dir = PROJECT_ROOT / "materials"
        valid_exts = {'.png', '.jpg', '.jpeg', '.bmp'}
        
        if mat_dir.exists():
            for root, dirs, files in os.walk(mat_dir):
                parts = [p.lower() for p in Path(root).parts]
                if "gui" in parts or "models" in parts:
                    continue
                for f in files:
                    p = Path(root) / f
                    if p.suffix.lower() in valid_exts:
                        mat_name = p.stem
                        mat_btn = QtWidgets.QToolButton()
                        mat_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                        mat_btn.setText(mat_name[:12])
                        mat_btn.setFixedSize(100, 100)
                        mat_btn.setCursor(QtCore.Qt.PointingHandCursor)
                        mat_btn.setStyleSheet(get_btn_style() + "QToolButton { font-size: 9pt; font-weight: bold; background-color: #D0D0D0; }")
                        
                        pixmap = QtGui.QPixmap(str(p)).scaled(64, 64, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                        mat_btn.setIcon(QtGui.QIcon(pixmap))
                        mat_btn.setIconSize(QtCore.QSize(64, 64))
                        
                        mat_path = str(p)
                        mat_btn.clicked.connect(lambda checked, pt=mat_path: self.apply_material(pt))
                        
                        self.mat_widgets.append((mat_name, mat_btn))

    def populate_grid(self, filter_text=""):
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
                
        row, col = 0, 0
        max_cols = 4
        for name, widget in self.mat_widgets:
            if filter_text == "" or filter_text.lower() in name.lower():
                self.grid.addWidget(widget, row, col)
                widget.show()
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            else:
                widget.hide()

    def apply_material(self, mat_path):
        if self.gl_view.selected_object_indices:
            self.gl_view.save_undo_snapshot()
            for idx in self.gl_view.selected_object_indices:
                obj = self.gl_view.scene_objects[idx]
                obj.material = mat_path
                obj.color = None
            self.gl_view.update()
            self.parent().update_comment(f"Material applied: {Path(mat_path).name if mat_path else 'Default'}")
        self.accept()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        ico_path = PROJECT_ROOT / "icon.ico"
        if ico_path.exists(): self.setWindowIcon(QtGui.QIcon(str(ico_path)))
            
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.resize(1042, 768)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        cursor_path = PROJECT_ROOT / "materials" / "gui" / "cursor.png"
        if not cursor_path.exists(): cursor_path = PROJECT_ROOT / "assets" / "cursor.png"
        if cursor_path.exists():
            QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtGui.QPixmap(str(cursor_path)), 0, 0))

        self.setup_sounds()
        
        self.config_path = PROJECT_ROOT / "gris_config.json"
        self.load_config()
        self.apply_general_settings()

        bg_path = PROJECT_ROOT / "materials" / "gui" / "bg.png"
        if not bg_path.exists(): bg_path = PROJECT_ROOT / "assets" / "bg.png"
        bg_path_str = str(bg_path).replace('\\', '/') if bg_path.exists() else ""

        self.current_mode, self.draw_mode_active = None, False
        self.hovered_object, self.selected_object, self.current_paint_color = None, None, None
        self.observer_mode = False
        self.saved_camera_state, self.saved_viewport_min_height, self.current_scene_path, self.unsaved_changes = None, None, None, False

        self.discord_client_id = "1479146565263429826"
        self.discord_rpc = None
        self.init_discord_rpc()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(1, 1, 1, 1)
        central_layout.setSpacing(0)

        self.app_frame_outer = QtWidgets.QFrame()
        self.app_frame_outer.setStyleSheet(f"QFrame#app_outer {{ background-color: {PANEL_BG}; {get_3d_border(False, 4)} }}")
        self.app_frame_outer.setObjectName("app_outer")
        central_layout.addWidget(self.app_frame_outer)

        outer_layout = QtWidgets.QVBoxLayout(self.app_frame_outer)
        outer_layout.setContentsMargins(4, 4, 4, 4)
        outer_layout.setSpacing(0)

        self.app_frame_inner = QtWidgets.QFrame()
        self.app_frame_inner.setObjectName("root")
        
        if bg_path_str:
            bg_style = f"background-image: url({bg_path_str}); background-repeat: repeat;"
        else:
            bg_style = f"background-color: {BASE_BG};"
            
        self.app_frame_inner.setStyleSheet(f"QFrame#root {{ {bg_style} {get_3d_border(True, 3)} }}")
        outer_layout.addWidget(self.app_frame_inner)

        root_layout = QtWidgets.QVBoxLayout(self.app_frame_inner)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_frame = DottedHeaderFrame(self)
        title_layout = QtWidgets.QVBoxLayout(self.title_frame)
        title_layout.setContentsMargins(4, 4, 4, 4) 
        title_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        title_layout.addWidget(self.title_bar)
        root_layout.addWidget(self.title_frame)

        self.menu_frame = DottedHeaderFrame(self)
        menu_layout = QtWidgets.QVBoxLayout(self.menu_frame)
        menu_layout.setContentsMargins(4, 2, 4, 2) 
        menu_layout.setSpacing(0)

        menubar = QtWidgets.QMenuBar()
        menubar.setNativeMenuBar(False)
        menubar.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        menubar.setFocusPolicy(QtCore.Qt.NoFocus)
        menubar.setStyleSheet(f"""
            QMenuBar {{ background-color: transparent; color: black; font: 11pt "{FONT_FAMILY}"; padding: 0px; border: none; }}
            QMenuBar::item {{ 
                padding: 4px 10px; 
                margin: 2px;
                background-color: {PANEL_BG};
                {get_3d_border(False, 2)}
            }}
            QMenuBar::item:selected {{ 
                background-color: {HOVER_GREEN}; 
                {get_3d_border(False, 2)}
            }}
            QMenuBar::item:pressed {{ 
                background-color: {PRESS_GREEN}; 
                {get_3d_border(True, 2)}
            }}
            QMenu {{ background-color: {PANEL_BG}; color: black; font: 11pt "{FONT_FAMILY}"; {get_3d_border(False, 2)} }}
            QMenu::item:selected {{ background-color: {HOVER_GREEN}; color: black; }}
        """)
        
        self.snap_action = QAction("Snap to Grid", self)
        self.snap_action.setCheckable(True)
        self.snap_action.triggered.connect(self.toggle_snap)
        
        menu_file = menubar.addMenu("File")
        menu_file.addAction("New").triggered.connect(self.action_new_scene)
        menu_file.addAction("Open...").triggered.connect(self.action_open_scene)
        menu_file.addAction("Save").triggered.connect(self.action_save_scene)
        menu_file.addAction("Save As...").triggered.connect(self.action_save_scene_as)
        menu_file.addSeparator(); menu_file.addAction("Exit").triggered.connect(self.close)

        menu_edit = menubar.addMenu("Edit")
        
        self.act_undo = menu_edit.addAction("Undo")
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(self.handle_undo)
        
        self.act_redo = menu_edit.addAction("Redo")
        self.act_redo.setShortcut("Ctrl+Y")
        self.act_redo.triggered.connect(self.handle_redo)
        
        menu_edit.addSeparator()
        menu_edit.addAction(self.snap_action) 
        
        menu_edit.addSeparator()
        
        act_copy = menu_edit.addAction("Copy"); act_copy.setShortcut("Ctrl+C"); act_copy.triggered.connect(self.handle_copy)
        act_paste = menu_edit.addAction("Paste"); act_paste.setShortcut("Ctrl+V"); act_paste.triggered.connect(self.handle_paste)
        
        menu_edit.addSeparator()
        
        act_add_ai = menu_edit.addAction("Add AI"); act_add_ai.setShortcut("F7"); act_add_ai.triggered.connect(self.handle_add_ai)
        act_rem_ai = menu_edit.addAction("Remove AI"); act_rem_ai.setShortcut("F6"); act_rem_ai.triggered.connect(self.handle_remove_ai)
        menu_edit.addSeparator()
        menu_edit.addAction("AI Settings...").triggered.connect(self.handle_ai_settings)
        menu_edit.addSeparator()
        menu_edit.addAction("General Settings...").triggered.connect(self.handle_general_settings)

        menu_view = menubar.addMenu("View")
        menu_view.addAction("Toggle Fullscreen").triggered.connect(self.toggle_fullscreen)
        menu_view.addAction("Show/Hide Toolbox").triggered.connect(self.toggle_toolbox)

        menu_help = menubar.addMenu("Help")
        menu_help.addAction("Help Topics").triggered.connect(self.handle_help_topics)

        menu_version = menubar.addMenu("Version")
        menu_version.addAction("About...").triggered.connect(self.show_about_dialog)

        menu_layout.addWidget(menubar)
        root_layout.addWidget(self.menu_frame)

        self.content = QtWidgets.QWidget()
        self.content.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.content.setStyleSheet("background-color: transparent;")
        self.content_layout = QtWidgets.QHBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)
        root_layout.addWidget(self.content)

        self.toolbox_container = QtWidgets.QFrame()
        self.toolbox_container.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.toolbox_container.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; {get_3d_border(False, 4)} }}")
        
        toolbox_main_layout = QtWidgets.QVBoxLayout(self.toolbox_container)
        toolbox_main_layout.setContentsMargins(10, 10, 10, 10)
        toolbox_main_layout.setSpacing(8)
        
        self.toolbox_stack = QtWidgets.QStackedLayout()
        
        self.page_std = QtWidgets.QWidget()
        page_std_layout = QtWidgets.QVBoxLayout(self.page_std)
        page_std_layout.setContentsMargins(0, 0, 0, 0)
        
        toolbox_label = QtWidgets.QLabel("TOOLBOX")
        toolbox_label.setAlignment(QtCore.Qt.AlignCenter)
        toolbox_label.setStyleSheet(f'font: bold 14pt "{FONT_FAMILY}"; color: black; background: transparent; border: none;')
        page_std_layout.addWidget(toolbox_label)

        self.adjusting_icons = False

        self.toolbox_grid = QtWidgets.QGridLayout()
        self.toolbox_grid.setSpacing(6)
        
        self.btn_create = ToolboxButton("CREATE\nOBJECT", "Create_Object.png")
        self.btn_create.setObjectName("btn_create")
        self.btn_delete = ToolboxButton("DELETE", "Delete.png")
        self.btn_delete.setObjectName("btn_delete")
        self.btn_edit = ToolboxButton("EDIT VERTEX", "Edit_Vertex.png")
        self.btn_edit.setObjectName("btn_edit")
        self.btn_observer = ToolboxButton("OBSERVER", "Observer.png")
        self.btn_observer.setObjectName("btn_observer")
        self.btn_load = ToolboxButton("LOAD OBJECT", "Load_Object.png")
        self.btn_load.setObjectName("btn_load")
        self.btn_paint = ToolboxButton("PAINT ATLAS", "Paint_Atlas.png")
        self.btn_paint.setObjectName("btn_paint")
        self.btn_int = ToolboxButton("INT_MENU", "Int_Menu.png")
        self.btn_int.setObjectName("btn_int")
        
        self.toolbox_buttons_list =[
            self.btn_create, self.btn_delete, self.btn_edit, 
            self.btn_observer, self.btn_load, self.btn_paint, self.btn_int
        ]
        
        for btn in self.toolbox_buttons_list:
            btn.swapRequested.connect(self.swap_toolbox_buttons)
            
        self.placeholders =[]

        for _ in range(10):
            ph = ToolboxPlaceholder(self)
            ph.swapRequested.connect(self.swap_toolbox_buttons)
            self.placeholders.append(ph)
            
        self.load_icon_layout()
        
        page_std_layout.addLayout(self.toolbox_grid)
        page_std_layout.addStretch()

        self.toggle_row = QtWidgets.QHBoxLayout()
        self.toggle_btn = QtWidgets.QPushButton("TOGGLE")
        self.adjust_btn = QtWidgets.QPushButton("ADJUST ICONS")
        
        for b in (self.toggle_btn, self.adjust_btn):
            b.setFixedHeight(28)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setFocusPolicy(QtCore.Qt.NoFocus)
            b.setStyleSheet(get_btn_style() + "QPushButton { font-size: 9pt; }")
            self.toggle_row.addWidget(b)
            
        self.toggle_btn.clicked.connect(self.handle_toggle_save)
        self.adjust_btn.clicked.connect(self.handle_adjust_reset)
        
        page_std_layout.addLayout(self.toggle_row)
        
        self.page_draw = QtWidgets.QWidget()
        page_draw_layout = QtWidgets.QVBoxLayout(self.page_draw)
        page_draw_layout.setContentsMargins(0,0,0,0)
        page_draw_layout.setSpacing(10)
        
        lbl_d = QtWidgets.QLabel("DRAW TOOLS")
        lbl_d.setAlignment(QtCore.Qt.AlignCenter)
        lbl_d.setStyleSheet(f'font: bold 14pt "{FONT_FAMILY}"; color: black; margin-bottom: 5px; background: transparent; border: none;')
        page_draw_layout.addWidget(lbl_d)
        
        d_grid = QtWidgets.QGridLayout()
        d_grid.setSpacing(6)
        
        self.btn_brush = ToolboxButton("BRUSH", "Brush.png")
        self.btn_eraser = ToolboxButton("ERASER", "Eraser.png")
        self.btn_fill = ToolboxButton("FILL", "Fill.png")
        self.btn_picker = ToolboxButton("PICKER", "Picker.png")
        self.btn_line = ToolboxButton("LINE & CURVE", "Line_Curve.png")
        self.btn_shapes = ToolboxButton("SHAPES", "Shapes.png")
        
        self.btn_color = ToolboxButton("COLOR", None)
        self.btn_color.set_color_visual(QtCore.Qt.black)
        
        self.combo_shape = QtWidgets.QComboBox()
        self.combo_shape.addItems(["Rectangle", "Ellipse", "Triangle"])
        self.combo_shape.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)} font: 10pt '{FONT_FAMILY}'; padding: 2px;")
        
        self.combo_line = QtWidgets.QComboBox()
        self.combo_line.addItems(["Line", "Curve"])
        self.combo_line.setStyleSheet(f"background-color: {INPUT_BG}; color: black; {get_3d_border(True, 1)} font: 10pt '{FONT_FAMILY}'; padding: 2px;")
        self.combo_line.currentTextChanged.connect(lambda v: setattr(self.canvas_widget, 'line_type', v))

        self.btn_brush.clicked.connect(lambda: self.set_draw_tool("brush"))
        self.btn_eraser.clicked.connect(lambda: self.set_draw_tool("eraser"))
        self.btn_fill.clicked.connect(lambda: self.set_draw_tool("fill"))
        self.btn_picker.clicked.connect(lambda: self.set_draw_tool("picker"))
        self.btn_line.clicked.connect(lambda: self.set_draw_tool("line_curve"))
        self.btn_shapes.clicked.connect(lambda: self.set_draw_tool("shapes"))
        self.btn_color.clicked.connect(self.pick_draw_color)
        self.combo_shape.currentTextChanged.connect(lambda v: setattr(self.canvas_widget, 'shape_type', v))
        
        
        d_grid.addWidget(self.btn_brush, 0, 0); d_grid.addWidget(self.btn_eraser, 0, 1)
        d_grid.addWidget(self.btn_fill, 1, 0);  d_grid.addWidget(self.btn_picker, 1, 1)
        d_grid.addWidget(self.btn_line, 2, 0);  d_grid.addWidget(self.btn_shapes, 2, 1)
        
        d_grid.addWidget(self.combo_line, 3, 0)
        d_grid.addWidget(self.combo_shape, 3, 1)
        
        d_grid.addWidget(self.btn_color, 4, 0)
        
        page_draw_layout.addLayout(d_grid)
        
        slider_style = """
            QSlider::groove:horizontal { border: 1px solid #999999; height: 8px; background: #B0B0B0; margin: 2px 0; }
            QSlider::handle:horizontal { background: #E0E0E0; border: 1px solid #5c5c5c; width: 14px; height: 14px; margin: -4px 0; border-radius: 2px; }
        """
        controls_layout = QtWidgets.QVBoxLayout()
        controls_layout.setSpacing(5)
        
        lbl_bs = QtWidgets.QLabel("Brush Size:")
        lbl_bs.setStyleSheet(f'font: 11pt "{FONT_FAMILY}"; color: black;')
        self.slider_brush = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_brush.setRange(1, 100); self.slider_brush.setValue(5)
        self.slider_brush.setStyleSheet(slider_style)
        self.slider_brush.valueChanged.connect(lambda v: setattr(self.canvas_widget, 'brush_width', v))
        controls_layout.addWidget(lbl_bs); controls_layout.addWidget(self.slider_brush)
        
        lbl_es = QtWidgets.QLabel("Eraser Size:")
        lbl_es.setStyleSheet(f'font: 11pt "{FONT_FAMILY}"; color: black;')
        self.slider_eraser = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_eraser.setRange(1, 100); self.slider_eraser.setValue(20)
        self.slider_eraser.setStyleSheet(slider_style)
        self.slider_eraser.valueChanged.connect(lambda v: setattr(self.canvas_widget, 'eraser_width', v))
        controls_layout.addWidget(lbl_es); controls_layout.addWidget(self.slider_eraser)
        
        lbl_hd = QtWidgets.QLabel("Brush Hardness:")
        lbl_hd.setStyleSheet(f'font: 11pt "{FONT_FAMILY}"; color: black;')
        self.slider_hard = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_hard.setRange(0, 100); self.slider_hard.setValue(100)
        self.slider_hard.setStyleSheet(slider_style)
        self.slider_hard.valueChanged.connect(lambda v: setattr(self.canvas_widget, 'hardness', v))
        controls_layout.addWidget(lbl_hd); controls_layout.addWidget(self.slider_hard)
        
        slider_frame = QtWidgets.QFrame()
        slider_frame.setStyleSheet(f"background-color: {PANEL_BG}; {get_3d_border(True, 2)}")
        slider_frame_layout = QtWidgets.QVBoxLayout(slider_frame)
        slider_frame_layout.addLayout(controls_layout)
        page_draw_layout.addWidget(slider_frame); page_draw_layout.addStretch()
        
        self.toolbox_stack.addWidget(self.page_std); self.toolbox_stack.addWidget(self.page_draw)
        toolbox_main_layout.addLayout(self.toolbox_stack)
        self.content_layout.addWidget(self.toolbox_container, 0)

        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(6)
        
        self.viewport_outer = QtWidgets.QFrame()
        self.viewport_outer.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.viewport_outer.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; {get_3d_border(False, 4)} }}")
        
        v_outer_layout = QtWidgets.QVBoxLayout(self.viewport_outer)
        v_outer_layout.setContentsMargins(4, 4, 4, 4)
        v_outer_layout.setSpacing(0)
        
        self.viewport_inner = QtWidgets.QFrame()
        self.viewport_inner.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.viewport_inner.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; {get_3d_border(True, 3)} }}")
        
        v_inner_layout = QtWidgets.QVBoxLayout(self.viewport_inner)
        v_inner_layout.setContentsMargins(0, 0, 0, 0)
        v_inner_layout.setSpacing(0)
        
        self.inner_stack = QtWidgets.QStackedWidget()
        self.inner_dark = QtWidgets.QFrame()
        self.inner_dark.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.inner_dark.setStyleSheet("QFrame { background-color: #000000; }")
        inner_l = QtWidgets.QVBoxLayout(self.inner_dark)
        inner_l.setContentsMargins(0,0,0,0)
        inner_l.setSpacing(0)
        
        self.gl_view = GLViewport(self.inner_dark)
        self.gl_view.setMinimumSize(600, 400)
        self.gl_view.hoverObjectChanged.connect(self.handle_viewport_hover)
        self.gl_view.objectSelected.connect(self.handle_object_selected)
        self.gl_view.requestModelImport.connect(self.handle_model_import)
        self.gl_view.objectPlaced.connect(self.play_create_obj)
        inner_l.addWidget(self.gl_view)
        
        self.canvas_widget = CanvasWidget()
        
        self.canvas_widget.colorPicked.connect(self.handle_color_picked)
        
        self.inner_stack.addWidget(self.inner_dark)
        self.inner_stack.addWidget(self.canvas_widget)
        
        v_inner_layout.addWidget(self.inner_stack)
        v_outer_layout.addWidget(self.viewport_inner)
        self.right_layout.addWidget(self.viewport_outer, 1)

        self.transport_frame = QtWidgets.QFrame()
        self.transport_frame.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.transport_frame.setStyleSheet("QFrame { background-color: transparent; }")
        
        transport_outer_layout = QtWidgets.QHBoxLayout(self.transport_frame)
        transport_outer_layout.setContentsMargins(0, 0, 0, 0)
        transport_outer_layout.setSpacing(0)
        
        strip = QtWidgets.QFrame()
        strip.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        strip.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        strip.setFixedSize(300, 70)
        
        strip_layout = QtWidgets.QHBoxLayout(strip)
        strip_layout.setContentsMargins(40, 10, 40, 10)
        strip_layout.setSpacing(35)
        
        self.pause_btn = TransportButton("||")
        self.stop_btn = TransportButton("■")
        self.play_btn = TransportButton("►►", font_size=14) 
        
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_ai)
        self.play_btn.clicked.connect(self.toggle_play_speed)

        strip_layout.addStretch()
        strip_layout.addWidget(self.pause_btn); strip_layout.addWidget(self.stop_btn); strip_layout.addWidget(self.play_btn)
        strip_layout.addStretch()
        
        transport_outer_layout.addStretch()
        transport_outer_layout.addWidget(strip)
        transport_outer_layout.addStretch()
        self.right_layout.addWidget(self.transport_frame, 0, alignment=QtCore.Qt.AlignHCenter)

        self.comment_label = QtWidgets.QLabel("")
        self.comment_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.comment_label.setStyleSheet(f'font: 14pt "{FONT_FAMILY}"; color: black; background-color: transparent; padding: 8px;')
        self.comment_label.setMinimumHeight(40)
        self.comment_label.setFocusPolicy(QtCore.Qt.NoFocus)
        self.right_layout.addWidget(self.comment_label, 0)
        self.right_layout.addStretch(0)
        
        self.content_layout.addLayout(self.right_layout, 1)

        self.create_menu = self.build_create_menu()
        self.paint_main_menu, self.paint_fill_menu = self.build_paint_menus()

        self.btn_create.clicked.connect(lambda: self.show_create_menu(self.toolbox_grid, self.toolbox_container))
        self.btn_paint.clicked.connect(lambda: self.show_paint_menu(self.btn_paint))
        self.btn_int.clicked.connect(self.show_int_menu_dialog)
        self.btn_delete.clicked.connect(self.handle_delete)
        self.btn_edit.clicked.connect(self.handle_edit_vertex)
        self.btn_observer.clicked.connect(self.toggle_observer_mode)
        self.btn_load.clicked.connect(self.action_load_objects_from_file)
        
        self.gl_view.playSound.connect(self.play_ai_sound)
        self.setup_background_sound()
        QtCore.QTimer.singleShot(100, self.gl_view.setFocus)


    def init_discord_rpc(self):
        try:
            self.discord_rpc = Presence(self.discord_client_id)
            self.discord_rpc.connect()
            self.update_discord_presence()
        except Exception as e:
            print(f"Failed to connect to Discord: {e}")

    def update_discord_presence(self):
        if self.discord_rpc:
            self.discord_rpc.update(
                large_image="gris_icon",
                start=int(time.time())
            )
    
    def closeEvent(self, event):
        if self.discord_rpc:
            self.discord_rpc.close()
        super().closeEvent(event)
    
    
    def show_material_browser(self):
        self.play_click()
        if not self.gl_view.selected_object_indices:
            self.update_comment("Select object(s) first to apply materials")
            return
        dialog = MaterialBrowserDialog(self, self.gl_view)
        dialog.exec_()
        self.gl_view.setFocus()

    def keyPressEvent(self, event):
        if self.draw_mode_active and event.key() == QtCore.Qt.Key_Escape:
            self.show_save_drawing_dialog()
            return
            
        if event.modifiers() & QtCore.Qt.ControlModifier:
            if event.key() == QtCore.Qt.Key_Z:
                if self.draw_mode_active:
                    self.canvas_widget.undo()
                else:
                    self.gl_view.undo_action()
                return
            if event.key() == QtCore.Qt.Key_Y:
                if self.draw_mode_active:
                    self.canvas_widget.redo()
                else:
                    self.gl_view.redo_action()
                return

        if event.key() == QtCore.Qt.Key_Escape:
            if self.observer_mode: self.toggle_observer_mode()
            else:
                self.gl_view.unselect_all()
                self.current_mode = self.current_paint_color = None
                self.update_comment("Unselected: All modes cleared")
            return
        self.gl_view.keyPressEvent(event); super().keyPressEvent(event)

    def toggle_toolbox(self):
        self.play_click()
        if self.toolbox_container.isVisible(): self.toolbox_container.hide()
        else: self.toolbox_container.show()


    def load_icon_layout(self):
        layout_map = self.app_config.get("toolbox_layout", {
            "btn_create": [0, 0], "btn_delete":[0, 1],
            "btn_edit": [1, 0], "btn_observer":[1, 1],
            "btn_load": [2, 0], "btn_paint":[2, 1],
            "btn_int": [3, 0]
        })
        
        for i in reversed(range(self.toolbox_grid.count())):
            item = self.toolbox_grid.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
                
        occupied = set()
        
        for btn in self.toolbox_buttons_list:
            pos = layout_map.get(btn.objectName())
            if pos:
                self.toolbox_grid.addWidget(btn, pos[0], pos[1])
                occupied.add((pos[0], pos[1]))
            else:
                self.toolbox_grid.addWidget(btn)

        placeholder_idx = 0
        MAX_ROWS = 6
        MAX_COLS = 2
        
        for r in range(MAX_ROWS):
            for c in range(MAX_COLS):
                if (r, c) not in occupied:
                    if placeholder_idx < len(self.placeholders):
                        ph = self.placeholders[placeholder_idx]
                        ph.adjust_mode = self.adjusting_icons
                        self.toolbox_grid.addWidget(ph, r, c)
                        placeholder_idx += 1

    def handle_toggle_save(self):
        self.play_click()
        if self.adjusting_icons:
            self.save_icon_layout()
            self.set_adjust_mode(False)
            self.update_comment("Icons layout saved.")
        else:
            self.toggle_toolbox()

    def handle_adjust_reset(self):
        self.play_click()
        if self.adjusting_icons:
            self.app_config["toolbox_layout"] = {
                "btn_create": [0, 0], "btn_delete": [0, 1],
                "btn_edit": [1, 0], "btn_observer": [1, 1],
                "btn_load": [2, 0], "btn_paint": [2, 1],
                "btn_int": [3, 0]
            }
            self.load_icon_layout()
            self.set_adjust_mode(False)
            self.save_config()
            self.update_comment("Icons layout reset to default.")
        else:
            self.set_adjust_mode(True)
            self.update_comment("Adjust Icons Mode: Drag and drop to reorder.")
            
    def set_adjust_mode(self, state):
        self.adjusting_icons = state
        
        for btn in self.toolbox_buttons_list:
            btn.adjust_mode = state
            
        for ph in self.placeholders:
            ph.adjust_mode = state
            
        if state:
            self.toggle_btn.setText("SAVE")
            self.adjust_btn.setText("RESET")
        else:
            self.toggle_btn.setText("TOGGLE")
            self.adjust_btn.setText("ADJUST ICONS")
            
    def save_icon_layout(self):
        new_layout = {}
        for i in range(self.toolbox_grid.count()):
            item = self.toolbox_grid.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ToolboxButton):
                btn = item.widget()
                row, col, rs, cs = self.toolbox_grid.getItemPosition(i)
                new_layout[btn.objectName()] = [row, col]
                
        self.app_config["toolbox_layout"] = new_layout
        self.save_config()

    def swap_toolbox_buttons(self, btn_source, btn_target):
        if not self.adjusting_icons: return
        idx_s = self.toolbox_grid.indexOf(btn_source)
        idx_t = self.toolbox_grid.indexOf(btn_target)
        if idx_s == -1 or idx_t == -1: return
        
        row_s, col_s, rs, cs = self.toolbox_grid.getItemPosition(idx_s)
        row_t, col_t, rt, ct = self.toolbox_grid.getItemPosition(idx_t)
        
        self.toolbox_grid.removeWidget(btn_source)
        self.toolbox_grid.removeWidget(btn_target)
        
        self.toolbox_grid.addWidget(btn_source, row_t, col_t)
        self.toolbox_grid.addWidget(btn_target, row_s, col_s)

    def show_about_dialog(self):
        self.play_click()
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        dialog.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QtWidgets.QLabel("GRIS\nBuild 2203 (Jan 14 1999)\n\nFSKY GRIS is a trademark of FSKY Corporation\nCopyrights (c) 1995-2005, FSKY Corporation, All rights reserved.")
        lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        lbl.setStyleSheet(f"color: black; font: 12pt '{FONT_FAMILY}';")
        layout.addWidget(lbl)
        
        layout.addSpacing(20)
        
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setFixedSize(120, 40)
        ok_btn.setCursor(QtCore.Qt.PointingHandCursor)
        ok_btn.setStyleSheet(get_btn_style() + "QPushButton { font-weight: bold; font-size: 12pt; }")
        ok_btn.clicked.connect(dialog.accept)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        dialog.resize(450, 250)
        dialog.move(self.frameGeometry().center() - dialog.rect().center())
        dialog.exec_()
        
    def handle_help_topics(self):
        self.play_click()
        
        help_file = PROJECT_ROOT / "FSKY" / "FSKY.html"
        
        if help_file.is_file():
            webbrowser.open(str(help_file))       
        
    def initiate_draw_mode(self):
        self.play_warning()
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        dialog.setModal(True)
        dialog.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        lbl = QtWidgets.QLabel("Would you like to enable the Outline mode?")
        lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        lbl.setStyleSheet(f'font: bold 14pt "{FONT_FAMILY}"; color: black;')
        layout.addWidget(lbl)
        
        for text, char, color, ret in[("Use regular Draw mode", "A", "red", 0), ("Switch to Outline mode", "B", "green", 1)]:
            btn = QtWidgets.QPushButton()
            btn.setFlat(True); btn.setCursor(QtCore.Qt.PointingHandCursor)
            h = QtWidgets.QHBoxLayout(btn); h.setContentsMargins(0,0,0,0)
            l_char = QtWidgets.QLabel(char); l_char.setStyleSheet(f'color: {color}; font: bold 16pt "{FONT_FAMILY}";')
            l_text = QtWidgets.QLabel(text); l_text.setStyleSheet(f'color: black; font: 14pt "{FONT_FAMILY}";')
            
            h.addWidget(l_char); h.addSpacing(15); h.addWidget(l_text); h.addStretch()
            
            btn.setMinimumHeight(45)
            btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: none; text-align: left; }} QPushButton:hover {{ background-color: {HOVER_GREEN}; }}")
            btn.clicked.connect(lambda _, r=ret: dialog.done(r))
            layout.addWidget(btn)
        
        dialog.resize(450, 200)
        dialog.move(self.frameGeometry().center() - dialog.rect().center())
        outline_mode = (dialog.exec_() == 1)
        
        self.draw_mode_active = True
        self.inner_stack.setCurrentWidget(self.canvas_widget)
        self.toolbox_stack.setCurrentWidget(self.page_draw)
        self.transport_frame.hide()
        self.canvas_widget.reset_canvas(outline_mode)
        self.update_comment("DRAW MODE: Press ESC to Finish.")

    def set_draw_tool(self, tool):
        self.play_click()
        self.canvas_widget.set_tool(tool)
        self.update_comment(f"Tool selected: {tool.upper()}")

    def handle_color_picked(self, color):
        self.btn_color.set_color_visual(color)
        self.set_draw_tool("brush")
        self.update_comment(f"Color Picked: {color.name().upper()}")

    def pick_draw_color(self):
        self.play_click()
        dialog = QColorDialog(self)
        dialog.setCurrentColor(self.canvas_widget.brush_color)
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        dialog.setStyleSheet(f"QColorDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}\n"
                             f"QLabel, QSpinBox, QLineEdit {{ background-color: #E0E0E0; color: black; font: 11pt '{FONT_FAMILY}'; }}\n"
                             + get_btn_style())
        if dialog.exec_() == QColorDialog.Accepted:
            color = dialog.selectedColor()
            if color.isValid():
                self.canvas_widget.set_color(color)
                self.btn_color.set_color_visual(color)
                self.set_draw_tool("brush")
        if self.draw_mode_active: self.canvas_widget.setFocus()

    def show_save_drawing_dialog(self):
        self.play_warning()
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        dialog.setModal(True)
        dialog.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QtWidgets.QLabel("SAVE AND QUIT?")
        label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        label.setStyleSheet(f'font: bold 14pt "{FONT_FAMILY}"; color: black;')
        layout.addWidget(label)
        
        for text, char, color, ret in[("Cancel", "A", "red", 0), ("Save and Quit", "B", "green", 1), ("Reset", "C", "blue", 2)]:
            btn = QtWidgets.QPushButton()
            btn.setFlat(True); btn.setCursor(QtCore.Qt.PointingHandCursor)
            h = QtWidgets.QHBoxLayout(btn); h.setContentsMargins(0,0,0,0)
            l_char = QtWidgets.QLabel(char); l_char.setStyleSheet(f'color: {color}; font: bold 16pt "{FONT_FAMILY}";')
            l_text = QtWidgets.QLabel(text); l_text.setStyleSheet(f'color: black; font: 14pt "{FONT_FAMILY}";')
            
            h.addWidget(l_char); h.addSpacing(15); h.addWidget(l_text); h.addStretch()
            
            btn.setMinimumHeight(45)
            btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: none; text-align: left; }} QPushButton:hover {{ background-color: {HOVER_GREEN}; }}")
            if ret == 0: btn.clicked.connect(dialog.reject)
            else: btn.clicked.connect(lambda _, r=ret: dialog.done(r))
            layout.addWidget(btn)
        
        dialog.resize(350, 250)
        dialog.move(self.frameGeometry().center() - dialog.rect().center())
        result = dialog.exec_()
        
        if result == 0: return
        elif result == 2: self.canvas_widget.reset_canvas(self.canvas_widget.outline_mode); return
        elif result == 1:
            dlg = CustomFileDialog(self, "SAVE DRAWING AS", "save", str(PROJECT_ROOT / "drawing.png"), ".png")
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                path = dlg.selected_file
                self.canvas_widget.image.save(path)
                self.update_comment(f"Drawing saved to {Path(path).name}")
                
            self.draw_mode_active = False
            self.inner_stack.setCurrentWidget(self.inner_dark)
            self.toolbox_stack.setCurrentWidget(self.page_std)
            self.transport_frame.show()
            self.gl_view.setFocus()

    def handle_model_import(self, idx):
        self.play_click()
        models_dir = PROJECT_ROOT / "models"
        if not models_dir.exists(): models_dir.mkdir(exist_ok=True)
        
        dlg = CustomFileDialog(self, "IMPORT OBJ MODEL", "open", str(models_dir), ".obj")
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            path = dlg.selected_file
            self.gl_view.scene_objects[idx].model_path = path
            self.gl_view.register_custom_model(path)
            self.gl_view.update()
            self.update_comment(f"Imported model: {Path(path).name}")

    def build_scene_dict(self):
        return {
            "version": 1,
            "camera": {"pos": self.gl_view.camera.pos, "yaw": self.gl_view.camera.yaw, "pitch": self.gl_view.camera.pitch},
            "int_menu_mode": self.gl_view.int_menu_mode,
            "objects":[{
                "type": obj.type, "position": obj.position, "scale": obj.scale, "rotation": obj.rotation,
                "color": obj.color, "has_ai": obj.has_ai, "ai_vertex_dir": obj.ai_vertex_dir,
                "original_position": obj.original_position, "model_path": obj.model_path,
                "material": getattr(obj, "material", None),
                "custom_vertices": getattr(obj, "custom_vertices", None),
                "faces": getattr(obj, "faces", None),          
                "ai_type": getattr(obj, "ai_type", "None"),
                "ai_config": getattr(obj, "ai_config", {}),
                "ai_state": getattr(obj, "ai_state", "WANDER")
            } for obj in self.gl_view.scene_objects]
        }

    def action_new_scene(self):
        self.play_click()
        if self.gl_view.scene_objects:
            res = QMessageBox.question(self, 'New Scene', 'Create new scene? Current scene will be cleared.', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if res == QMessageBox.No: return
        self.gl_view.scene_objects =[]
        self.gl_view.selected_object_indices, self.gl_view.hovered_object_index =[], None
        self.gl_view.camera = Camera()
        self.gl_view.int_menu_mode = False
        self.gl_view.undo_stack, self.gl_view.redo_stack = [],[]
        self.gl_view.update()
        self.current_scene_path = None
        self.update_comment("New scene created")

    def action_save_scene(self):
        if not self.current_scene_path: return self.action_save_scene_as()
        self.play_click()
        try:
            with open(self.current_scene_path, "w", encoding="utf-8") as f: json.dump(self.build_scene_dict(), f, indent=2)
            self.update_comment(f"Saved: {self.current_scene_path}")
            self.unsaved_changes = False
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save scene:\n{str(e)}")

    def action_save_scene_as(self):
        self.play_click()
        default_name = self.current_scene_path or str(PROJECT_ROOT / "untitled.dme")
        
        dlg = CustomFileDialog(self, "SAVE SCENE AS", "save", default_name, ".dme")
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            path = dlg.selected_file
            self.current_scene_path = path
            self.title_bar.title_label.setText(f"gris.exe - {Path(path).name}")
            self.action_save_scene()

    def action_open_scene(self):
        self.play_click()
        
        dlg = CustomFileDialog(self, "OPEN SCENE", "open", str(PROJECT_ROOT), ".dme")
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            path = dlg.selected_file
            try:
                with open(path, "r", encoding="utf-8") as f: data = json.load(f)
                self.gl_view.load_scene_from_dict(data)
                self.current_scene_path = path
                self.title_bar.title_label.setText(f"gris.exe - {Path(path).name}")
                self.update_comment(f"Loaded: {path}")
                self.unsaved_changes = False
            except Exception as e:
                QMessageBox.critical(self, "Open Error", f"Failed to open scene:\n{str(e)}")

    def action_load_objects_from_file(self):
        self.play_click()
        
        dlg = CustomFileDialog(self, "LOAD OBJECTS", "open", str(PROJECT_ROOT), ".dme")
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            path = dlg.selected_file
            try:
                with open(path, "r", encoding="utf-8") as f: data = json.load(f)
                self.gl_view.append_objects_from_dict(data)
                self.update_comment(f"Loaded objects from: {path}")
                self.unsaved_changes = True
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load objects:\n{str(e)}")

    def handle_add_ai(self):
        self.play_click()
        if self.gl_view.selected_object_indices:
            self.gl_view.save_undo_snapshot()
            count = 0
            for idx in self.gl_view.selected_object_indices:
                obj = self.gl_view.scene_objects[idx]
                if not obj.has_ai:
                    obj.has_ai = True
                    obj.ai_type = "DMNPC_TLEET_WDYMS"
                    obj.ai_vertex_dir =[0, 1, 0]
                    obj.ai_timer = 0
                    obj.ai_bend_amount = [0.0, 0.0]
                    obj.ai_squash_stretch = 1.0
                    count += 1
            self.update_comment(f"Add AI: Added AI to {count} object(s)")
            self.gl_view.update()
        else:
            self.gl_view.add_ai_mode, self.gl_view.remove_ai_mode = True, False
            self.update_comment("Add AI: Click on an object to add AI.")
            self.gl_view.setFocus()

    def handle_remove_ai(self):
        self.play_click()
        if self.gl_view.selected_object_indices:
            self.gl_view.save_undo_snapshot()
            count = 0
            for idx in self.gl_view.selected_object_indices:
                obj = self.gl_view.scene_objects[idx]
                if obj.has_ai:
                    obj.has_ai = False
                    count += 1
            self.update_comment(f"Remove AI: Removed AI from {count} object(s)")
            self.gl_view.update()
        else:
            self.gl_view.remove_ai_mode, self.gl_view.add_ai_mode = True, False
            self.update_comment("Remove AI: Click on an AI object to remove its AI.")
            self.gl_view.setFocus()
        
    def handle_ai_settings(self):
        if not self.gl_view.selected_object_indices:
            self.play_click()
            self.update_comment("Select an object to edit its AI settings.")
            return
            
        obj = self.gl_view.scene_objects[self.gl_view.selected_object_indices[0]]
        if not obj.has_ai:
            self.play_denied()
            self.update_comment("This object has no AI! Use Edit -> Add AI first.")
            return
            
        self.play_click()
        dlg = AISettingsDialog(self, obj)
        dlg.exec_()
        self.gl_view.update()

    def handle_general_settings(self):
        self.play_click()
        dlg = GeneralSettingsDialog(self)
        dlg.exec_()
        self.gl_view.setFocus()

    def toggle_observer_mode(self):
        self.play_click()
        if not self.observer_mode:
            self.observer_mode = True
            self.saved_camera_state = self.gl_view.camera.save_state()
            self.saved_viewport_min_height = self.viewport_outer.minimumHeight()
            
            self.anim_toolbox = QtCore.QPropertyAnimation(self.toolbox_container, b"maximumWidth")
            self.anim_toolbox.setDuration(400); self.anim_toolbox.setStartValue(self.toolbox_container.width()); self.anim_toolbox.setEndValue(0)
            self.anim_toolbox.setEasingCurve(QtCore.QEasingCurve.InOutCubic); self.anim_toolbox.finished.connect(lambda: self.toolbox_container.hide()); self.anim_toolbox.start()
            
            self.anim_comment = QtCore.QPropertyAnimation(self.comment_label, b"maximumHeight")
            self.anim_comment.setDuration(400); self.anim_comment.setStartValue(self.comment_label.height()); self.anim_comment.setEndValue(0)
            self.anim_comment.setEasingCurve(QtCore.QEasingCurve.InOutCubic); self.anim_comment.finished.connect(lambda: self.comment_label.hide()); self.anim_comment.start()
            
            self.anim_viewport = QtCore.QPropertyAnimation(self.viewport_outer, b"minimumHeight")
            self.anim_viewport.setDuration(400); self.anim_viewport.setStartValue(self.viewport_outer.height()); self.anim_viewport.setEndValue(self.content.height() - 100)
            self.anim_viewport.setEasingCurve(QtCore.QEasingCurve.InOutCubic); self.anim_viewport.start()
            
            QtCore.QTimer.singleShot(200, lambda: self.gl_view.camera.set_observer_view())
            self.update_comment("OBSERVER MODE: Top-down monitoring enabled.")
        else:
            self.observer_mode = False
            if self.saved_camera_state: self.gl_view.camera.restore_state(self.saved_camera_state)
            
            self.toolbox_container.show()
            self.anim_toolbox = QtCore.QPropertyAnimation(self.toolbox_container, b"maximumWidth")
            self.anim_toolbox.setDuration(400); self.anim_toolbox.setStartValue(0); self.anim_toolbox.setEndValue(260)
            self.anim_toolbox.setEasingCurve(QtCore.QEasingCurve.InOutCubic); self.anim_toolbox.start()
            
            self.comment_label.show()
            self.anim_comment = QtCore.QPropertyAnimation(self.comment_label, b"maximumHeight")
            self.anim_comment.setDuration(400); self.anim_comment.setStartValue(0); self.anim_comment.setEndValue(100)
            self.anim_comment.setEasingCurve(QtCore.QEasingCurve.InOutCubic); self.anim_comment.start()
            
            self.anim_viewport = QtCore.QPropertyAnimation(self.viewport_outer, b"minimumHeight")
            self.anim_viewport.setDuration(400); self.anim_viewport.setStartValue(self.viewport_outer.height()); self.anim_viewport.setEndValue(self.saved_viewport_min_height or 400)
            self.anim_viewport.setEasingCurve(QtCore.QEasingCurve.InOutCubic); self.anim_viewport.start()
            
            self.update_comment("Editing Mode: Toolbox restored.")

    def setup_sounds(self):
        sound_dir = PROJECT_ROOT / "sound"
        sys_dir = sound_dir / "system"
        for attr, file in[("click_sound", "click.mp3"), ("warning_sound", "warning.mp3"), ("create_obj_sound", "create_obj.mp3"), ("denied_sound", "denied.mp3")]:
            path = sys_dir / file if (sys_dir / file).exists() else sound_dir / file
            if path.exists():
                player = QtMultimedia.QMediaPlayer()
                player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl.fromLocalFile(str(path))))
                player.setVolume(70)
                setattr(self, attr, player)
            else: setattr(self, attr, None)

    def update_comment(self, text): self.comment_label.setText(text)

    def handle_viewport_hover(self, obj_type):
        if self.current_mode in["paint_fill", "paint_draw", "paint"] and obj_type:
            self.update_comment(f"Select {obj_type}?")

    def handle_object_selected(self, index):
        if self.current_mode in["paint_fill", "paint"]:
            if 0 <= index < len(self.gl_view.scene_objects):
                self.gl_view.save_undo_snapshot()
                self.gl_view.scene_objects[index].color = self.current_paint_color
                self.gl_view.scene_objects[index].material = None
                self.gl_view.update(); self.play_click()
                self.update_comment(f"Painted {self.gl_view.scene_objects[index].type}!" if self.current_paint_color else f"Restored default material for {self.gl_view.scene_objects[index].type}!")

    def load_config(self):
            self.app_config = {"window_mode": "Windowed", "delete_type": "Fast Delete", "disable_app_sounds": False, "disable_music": False, "disable_delete_sound": False, "world_skybox": ""}
            if self.config_path.exists():
                try:
                    with open(self.config_path, "r") as f: self.app_config.update(json.load(f))
                except: pass

    def save_config(self):
        with open(self.config_path, "w") as f: json.dump(self.app_config, f, indent=2)

    def apply_general_settings(self):
        if self.app_config.get("window_mode") == "Fullscreen" and not self.isFullScreen():
            self.showFullScreen()
        elif self.app_config.get("window_mode") == "Windowed" and self.isFullScreen():
            self.showNormal()

        if hasattr(self, 'player'):
            if (self.app_config.get("disable_music") and 
                self.player.state() == QtMultimedia.QMediaPlayer.PlayingState):
                self.player.pause()
            elif (not self.app_config.get("disable_music") and 
                  self.player.state() != QtMultimedia.QMediaPlayer.PlayingState):
                self.player.play()

        if hasattr(self, 'gl_view') and self.gl_view is not None:
            self.gl_view.update()

    def show_general_settings(self):
        self.play_click()
        dlg = GeneralSettingsDialog(self)
        dlg.exec_()

    def play_click(self):
        if self.app_config.get("disable_app_sounds"): return
        if self.click_sound: self.click_sound.stop(); self.click_sound.setPosition(0); self.click_sound.play()
    def play_warning(self):
        if self.app_config.get("disable_app_sounds"): return
        if self.warning_sound: self.warning_sound.stop(); self.warning_sound.setPosition(0); self.warning_sound.play()
    def play_create_obj(self):
        if self.app_config.get("disable_app_sounds"): return
        if self.create_obj_sound: self.create_obj_sound.stop(); self.create_obj_sound.setPosition(0); self.create_obj_sound.play()

    def play_denied(self):
        if self.app_config.get("disable_app_sounds"): return
        if hasattr(self, 'denied_sound') and self.denied_sound: 
            self.denied_sound.stop(); self.denied_sound.setPosition(0); self.denied_sound.play()

    def handle_delete(self):
        self.play_click()
        if not self.gl_view.selected_object_indices:
            self.update_comment("No objects selected to delete")
            return
           
        self.gl_view.save_undo_snapshot()
       
        if self.app_config.get("delete_type") == "Animated Deletion":
            for idx in self.gl_view.selected_object_indices:
                if idx < len(self.gl_view.scene_objects):
                    obj = self.gl_view.scene_objects[idx]
                    eraser = EraserEntity(list(self.gl_view.camera.pos), obj)
                    eraser.model_path = str(PROJECT_ROOT / "models" / "error.obj")
                    if eraser.model_path not in self.gl_view.custom_model_lists:
                        self.gl_view.register_custom_model(eraser.model_path)
                    self.gl_view.scene_objects.append(eraser)
            
            self.gl_view.selected_object_indices = []
            self.gl_view.update()
            self.update_comment("Animated Erase sequence initiated!")
            
        else:
            count = len(self.gl_view.selected_object_indices)
            for idx in sorted(self.gl_view.selected_object_indices, reverse=True):
                if 0 <= idx < len(self.gl_view.scene_objects):
                    del self.gl_view.scene_objects[idx]
            
            self.gl_view.selected_object_indices = []
            self.gl_view.update()
            self.update_comment(f"Deleted {count} object(s)!")

    def handle_edit_vertex(self):
        self.play_click()
        if self.gl_view.selected_object_indices:
            self.gl_view.edit_mode = not self.gl_view.edit_mode
            self.gl_view.move_mode = not self.gl_view.edit_mode

            obj = self.gl_view.scene_objects[self.gl_view.selected_object_indices[0]]
            if self.gl_view.edit_mode:
                if obj.type in ["Cube", "Brush"]:
                    self.gl_view.convert_to_custom_mesh(obj)
                    self.gl_view.selected_vertex_index = None
                    self.update_comment("Vertex Edit: Drag center cubes to Scale, or click red dots to Deform.")
                else:
                    self.update_comment("Vertex Edit: Drag center cubes to scale the object.")
            else:
                self.update_comment("MOVE MODE restored.")
            self.gl_view.update()
        else: 
            self.update_comment("Select object(s) first to edit")
        
    def toggle_snap(self):
        self.play_click()
        self.gl_view.snap_enabled = self.snap_action.isChecked()
        self.update_comment(f"Grid Snap: {'ON' if self.gl_view.snap_enabled else 'OFF'}"); self.gl_view.setFocus()

    def toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def build_create_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(f'QMenu {{ background-color: {PANEL_BG}; color: black; font: 12pt "{FONT_FAMILY}"; padding: 4px 6px; {get_3d_border(False, 2)} }}\n'
                           f'QMenu::item {{ padding: 4px 18px 4px 12px; background-color: transparent; }}\n'
                           f'QMenu::item:selected {{ background-color: {HOVER_GREEN}; color: black; }}\n'
                           f'QMenu::separator {{ height: 1px; margin: 2px 0 2px 0; background: #606060; }}')
        
        main_header = QtWidgets.QAction("Create Object:", menu); main_header.setEnabled(False); menu.addAction(main_header); menu.addSeparator()
        
        header_3d = QtWidgets.QAction("3D Objects:", menu); header_3d.setEnabled(False); menu.addAction(header_3d); menu.addSeparator()
        for label in["Brush", "Cube", "Sphere", "Cone", "Cylinder", "Torus", "3D Oval", "Model"]:
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, l=label: self.handle_create_object(l))
            action.hovered.connect(lambda l=label: self.update_comment(f"Selected: {l}"))
            
        menu.addSeparator()
        
        header_2d = QtWidgets.QAction("2D Objects:", menu); header_2d.setEnabled(False); menu.addAction(header_2d); menu.addSeparator()
        for label in["Square", "Circle", "Oval", "Triangle"]:
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, l=label: self.handle_create_object(l))
            action.hovered.connect(lambda l=label: self.update_comment(f"Selected: {l}"))
            
        return menu

    def handle_create_object(self, obj_name):
        self.play_click()
        self.selected_object = obj_name
        self.update_comment(f"Click in viewport to place {obj_name}")
        self.gl_view.placement_mode, self.gl_view.placement_object_type = True, obj_name
        self.gl_view.setFocus()

    def build_paint_menus(self):
        style = (f'QMenu {{ background-color: {PANEL_BG}; color: black; font: 12pt "{FONT_FAMILY}"; padding: 4px 6px; {get_3d_border(False, 2)} }}\n'
                 f'QMenu::item {{ padding: 4px 18px 4px 12px; background-color: transparent; }}\n'
                 f'QMenu::item:selected {{ background-color: {HOVER_GREEN}; color: black; }}\n'
                 f'QMenu::separator {{ height: 1px; margin: 2px 0 2px 0; background: #606060; }}')
        
        main_menu, fill_menu = QtWidgets.QMenu(self), QtWidgets.QMenu(self)
        main_menu.setStyleSheet(style); main_menu.setFixedWidth(160); fill_menu.setStyleSheet(style)
        
        main_menu.addAction("Material Browser...").triggered.connect(self.show_material_browser)
        main_menu.addSeparator()
        
        fill_act = main_menu.addAction("Fill Color"); fill_act.setMenu(fill_menu)
        main_menu.addAction("Draw 2D").triggered.connect(self.initiate_draw_mode)
        main_menu.addAction("Outline").triggered.connect(self.handle_outline)
        
        for name, rgb in {"Red": (1.0, 0.0, 0.0), "Yellow": (1.0, 1.0, 0.0), "Blue": (0.0, 0.0, 1.0),
                          "Purple": (0.5, 0.0, 0.5), "Orange": (1.0, 0.5, 0.0), "Green": (0.0, 1.0, 0.0),
                          "Black": (0.0, 0.0, 0.0), "White": (1.0, 1.0, 1.0), "Gray": (0.5, 0.5, 0.5),
                          "Brown": (0.6, 0.3, 0.0), "None": None}.items():
            fill_menu.addAction(name).triggered.connect(lambda checked=False, n=name, r=rgb: self.handle_fill_color(n, r))
        
        fill_menu.addSeparator(); fill_menu.addAction("Pick Hex").triggered.connect(self.pick_hex_color)
        return main_menu, fill_menu

    def show_create_menu(self, grid_layout, toolbox_container):
        self.play_click()
        self.current_mode = "create"
        global_pos = toolbox_container.mapToGlobal(QtCore.QPoint(toolbox_container.width(), 0))
        if delete_btn := grid_layout.itemAtPosition(0, 1).widget():
             global_pos.setY(delete_btn.mapToGlobal(QtCore.QPoint(0,0)).y())
        self.create_menu.popup(global_pos)

    def show_paint_menu(self, button):
        self.play_click()
        self.current_mode = "paint"
        self.update_comment("Select object to paint color")
        self.paint_main_menu.popup(button.mapToGlobal(button.rect().topRight()))

    def pick_hex_color(self):
        self.play_click()
        dialog = QColorDialog(self)
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        dialog.setStyleSheet(f"QColorDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}\n"
                             f"QLabel, QSpinBox, QLineEdit {{ background-color: #E0E0E0; color: black; font: 11pt '{FONT_FAMILY}'; }}\n"
                             + get_btn_style())
        if dialog.exec_() == QColorDialog.Accepted and (color := dialog.selectedColor()).isValid():
            self.current_paint_color, self.current_mode = (color.redF(), color.greenF(), color.blueF()), "paint_fill"
            self.update_comment(f"Click object to paint {color.name()}")
        self.gl_view.setFocus()

    def show_int_menu_dialog(self):
        self.play_warning()
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        dialog.setModal(True)
        dialog.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        dialog.setStyleSheet(f"QDialog {{ background-color: {PANEL_BG}; {get_3d_border(False, 3)} }}")
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        
        text = "Return to editing? AI objects will return to center." if self.gl_view.int_menu_mode else "Would you like to submit this to INT_MENU?"
        label = QtWidgets.QLabel(text)
        label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        label.setStyleSheet(f'font: bold 14pt "{FONT_FAMILY}"; color: black;') 
        layout.addWidget(label)
        
        for text, char, color, choice in[("Yes", "A", "red", "Yes"), ("No", "B", "green", "No")]:
            btn = QtWidgets.QPushButton()
            btn.setFlat(True); btn.setCursor(QtCore.Qt.PointingHandCursor)
            h = QtWidgets.QHBoxLayout(btn); h.setContentsMargins(0, 0, 0, 0)
            l_char = QtWidgets.QLabel(char); l_char.setStyleSheet(f'color: {color}; font: bold 16pt "{FONT_FAMILY}";')
            l_text = QtWidgets.QLabel(text); l_text.setStyleSheet(f'color: black; font: 14pt "{FONT_FAMILY}";')
            
            h.addWidget(l_char); h.addSpacing(15); h.addWidget(l_text); h.addStretch()
            
            btn.setMinimumHeight(45)
            btn.setStyleSheet(f"QPushButton {{ background-color: transparent; border: none; text-align: left; }} QPushButton:hover {{ background-color: {HOVER_GREEN}; }}")
            btn.clicked.connect(lambda _, c=choice: self.int_menu_response(dialog, c))
            layout.addWidget(btn)
        
        dialog.resize(550, 200) 
        dialog.move(self.frameGeometry().center() - dialog.rect().center())
        dialog.exec_()
        self.gl_view.setFocus()

    def int_menu_response(self, dialog, choice):
        self.play_click()
        if choice == "Yes":
            if not self.gl_view.int_menu_mode:
                for obj in self.gl_view.scene_objects:
                    if obj.has_ai: obj.original_position = obj.position.copy()
                self.gl_view.int_menu_mode = True
                self.update_comment("INT_MENU: Scene submitted to INT_MENU.")
            else:
                for obj in self.gl_view.scene_objects:
                    if obj.has_ai and obj.original_position:
                        obj.position, obj.original_position, obj.ai_move_target, obj.ai_look_target = obj.original_position.copy(), None, None, None
                self.gl_view.int_menu_mode = False
                self.update_comment("Edit Mode: Toolbox restored.")
            self.gl_view.update()
        dialog.accept()

    def setup_background_sound(self):
        sound_dir = PROJECT_ROOT / "sound"
        wav_path = sound_dir / "music" / "sbox.wav"
        if not wav_path.exists(): wav_path = sound_dir / "sbox.wav"
        if not wav_path.exists(): return
        self.player = QtMultimedia.QMediaPlayer()
        self.player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl.fromLocalFile(str(wav_path))))
        self.player.setVolume(50)
        self.player.mediaStatusChanged.connect(self.handle_media_status)
        self.player.play()

    def handle_media_status(self, status):
        if status == QtMultimedia.QMediaPlayer.EndOfMedia:
            self.player.setPosition(0); self.player.play()

    def handle_fill_color(self, color_name, rgb):
        self.play_click()
        self.current_paint_color, self.current_mode = rgb, "paint_fill"
        self.update_comment(f"Click object to paint {color_name}" if color_name != "None" else "Click object to remove color")
        self.gl_view.setFocus()
        
    def handle_outline(self):
        self.play_warning()
        self.update_comment("Outline only works with 2d objects!"); self.gl_view.setFocus()
    
    def handle_copy(self):
        if self.gl_view.copy_selection(): self.play_click(); self.update_comment("Objects copied to clipboard.")
        else: self.update_comment("Nothing selected to copy.")

    def handle_paste(self):
        if self.gl_view.paste_selection(): self.play_create_obj(); self.update_comment("Objects pasted from clipboard.")
        else: self.update_comment("Clipboard empty.")

    def play_ai_sound(self, path):
        if not os.path.exists(path): return
        if not hasattr(self, 'ai_audio_players'): self.ai_audio_players =[]
        
        if len(self.ai_audio_players) > 15:
            old_p = self.ai_audio_players.pop(0)
            old_p.stop()
            
        player = QtMultimedia.QMediaPlayer()
        player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl.fromLocalFile(path)))
        player.setVolume(80)
        player.play()
        self.ai_audio_players.append(player)

    def set_transport_style(self, btn, font_size, active=False):
        base = get_btn_style(hover_bg="#FFAA00", press_bg="#CC8800") if active else get_btn_style()
        btn.setStyleSheet(base + f"QPushButton {{ font: {font_size}pt '{FONT_FAMILY}'; font-weight: bold; padding-bottom: 4px; }}")

    def toggle_pause(self):
        self.play_click()
        self.gl_view.ai_paused = not self.gl_view.ai_paused
        self.set_transport_style(self.pause_btn, 24, self.gl_view.ai_paused)
        self.update_comment("AI Paused" if self.gl_view.ai_paused else "AI Resumed")

    def stop_ai(self):
        self.play_click()
        for obj in self.gl_view.scene_objects:
            if obj.has_ai and obj.original_position:
                obj.position = list(obj.original_position)
                obj.ai_move_target = None
                obj.ai_state = "WANDER"
                obj.target_prey = None
                obj.scale =[1.0, 1.0, 1.0]
                
        self.gl_view.ai_paused = True 
        self.set_transport_style(self.pause_btn, 24, True)
        self.gl_view.ai_speed_mult = 1.0
        self.set_transport_style(self.play_btn, 14, False)
        self.update_comment("AI Reset to Start Positions")
        self.gl_view.update()

    def toggle_play_speed(self):
        self.play_click()
        self.gl_view.ai_paused = False 
        self.set_transport_style(self.pause_btn, 24, False)
        
        if self.gl_view.ai_speed_mult == 1.0:
            self.gl_view.ai_speed_mult = 2.0
            self.set_transport_style(self.play_btn, 14, True) 
            self.update_comment("AI Speed: x2")
        else:
            self.gl_view.ai_speed_mult = 1.0
            self.set_transport_style(self.play_btn, 14, False)
            self.update_comment("AI Speed: x1")

    def handle_undo(self):
        if self.draw_mode_active:
            self.canvas_widget.undo()
            self.update_comment("Undo: Drawing action reverted")
        else:
            self.gl_view.undo_action()
            self.update_comment("Undo: 3D Scene reverted")

    def handle_redo(self):
        if self.draw_mode_active:
            self.canvas_widget.redo()
            self.update_comment("Redo: Drawing action restored")
        else:
            self.gl_view.redo_action()
            self.update_comment("Redo: 3D Scene restored")
            
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            if self.draw_mode_active:
                self.show_save_drawing_dialog()
            elif self.observer_mode: 
                self.toggle_observer_mode()
            else:
                self.gl_view.unselect_all()
                self.current_mode = self.current_paint_color = None
                self.update_comment("Unselected: All modes cleared")
            return
            
        super().keyPressEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())