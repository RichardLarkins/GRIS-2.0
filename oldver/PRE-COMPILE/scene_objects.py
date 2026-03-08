import math
import random
import os

def normalize(v):
    norm = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if norm == 0: return[0.0, 0.0, 0.0]
    return [v[0]/norm, v[1]/norm, v[2]/norm]

def dot(v1, v2):
    return v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]

def intersect_plane(ray_origin, ray_dir, plane_point, plane_normal):
    denom = dot(ray_dir, plane_normal)
    if abs(denom) < 1e-6: return None
    t = dot(sub(plane_point, ray_origin), plane_normal) / denom
    if t >= 0: return add(ray_origin, mul(ray_dir, t))
    return None

def sub(v1, v2): return [v1[0]-v2[0], v1[1]-v2[1], v1[2]-v2[2]]
def add(v1, v2): return [v1[0]+v2[0], v1[1]+v2[1], v1[2]+v2[2]]
def mul(v, s): return [v[0]*s, v[1]*s, v[2]*s]
def cross(a, b): return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]

def ray_box_intersect(ray_origin, ray_dir, box_min, box_max):
    tmin = -float('inf')
    tmax = float('inf')
    for i in range(3):
        if ray_dir[i] != 0:
            tx1 = (box_min[i] - ray_origin[i]) / ray_dir[i]
            tx2 = (box_max[i] - ray_origin[i]) / ray_dir[i]
            tmin = max(tmin, min(tx1, tx2))
            tmax = min(tmax, max(tx1, tx2))
        elif ray_origin[i] < box_min[i] or ray_origin[i] > box_max[i]:
            return None
    if tmax >= tmin and tmax >= 0:
        return tmin if tmin > 0 else tmax
    return None

def dist_ray_to_segment(ray_origin, ray_dir, p1, p2):
    u = ray_dir
    v = sub(p2, p1)
    w = sub(ray_origin, p1)
    a, b, c = dot(u, u), dot(u, v), dot(v, v)
    d, e = dot(u, w), dot(v, w)
    denom = a*c - b*b
    if denom < 1e-5: return float('inf')
    tc = (a*e - b*d) / denom
    if tc < 0: tc = 0
    elif tc > 1: tc = 1
    sc = (b*tc - d) / a
    P_closest = add(ray_origin, mul(u, sc))
    Q_closest = add(p1, mul(v, tc))
    dist_vec = sub(P_closest, Q_closest)
    return math.sqrt(dot(dist_vec, dist_vec))

def load_mtl_file(filename):
    materials, current_mat = {}, None
    if not os.path.exists(filename): return materials
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                parts = line.split()
                cmd = parts[0]
                if cmd == 'newmtl':
                    current_mat = parts[1]
                    materials[current_mat] = {'texture': None, 'diffuse':[1.0, 1.0, 1.0]}
                elif current_mat:
                    if cmd == 'Kd':
                        try: materials[current_mat]['diffuse'] =[float(x) for x in parts[1:4]]
                        except: pass
                    elif cmd == 'map_Kd':
                        materials[current_mat]['texture'] = line.split(' ', 1)[1].strip()
    except Exception as e:
        pass
    return materials

def load_obj_file(filename):
    vertices, normals, texcoords = [], [],[]
    material_groups, current_material, mtllib = {}, "Default", None
    if not os.path.exists(filename): return [], [],[], {}, None
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                parts = line.split()
                cmd = parts[0]
                if cmd == 'v': vertices.append([float(x) for x in parts[1:4]])
                elif cmd == 'vn': normals.append([float(x) for x in parts[1:4]])
                elif cmd == 'vt': texcoords.append([float(x) for x in parts[1:3]])
                elif cmd == 'mtllib': mtllib = line.split(' ', 1)[1]
                elif cmd == 'usemtl': current_material = parts[1]
                elif cmd == 'f':
                    if current_material not in material_groups:
                        material_groups[current_material] =[]
                    face_verts =[]
                    for p in parts[1:]:
                        vals = p.split('/')
                        vi = int(vals[0]) - 1
                        vt = int(vals[1]) - 1 if len(vals) > 1 and vals[1] else -1
                        vn = int(vals[2]) - 1 if len(vals) > 2 and vals[2] else -1
                        face_verts.append((vi, vt, vn))
                    material_groups[current_material].append(face_verts)
    except Exception as e:
        pass
    return vertices, normals, texcoords, material_groups, mtllib

class Camera:
    def __init__(self):
        self.pos =[0.0, 2.0, 6.0]
        self.yaw = -90.0
        self.pitch = -20.0
        self.speed = 0.15
        self.sensitivity = 0.25

    def get_front(self):
        rad_yaw, rad_pitch = math.radians(self.yaw), math.radians(self.pitch)
        x = math.cos(rad_yaw) * math.cos(rad_pitch)
        y = math.sin(rad_pitch)
        z = math.sin(rad_yaw) * math.cos(rad_pitch)
        length = math.sqrt(x * x + y * y + z * z)
        return[x / length, y / length, z / length] if length > 0 else[0, 0, -1]

    def get_right(self):
        fx, fy, fz = self.get_front()
        ux, uy, uz = 0, 1, 0
        rx, ry, rz = fy * uz - fz * uy, fz * ux - fx * uz, fx * uy - fy * ux
        length = math.sqrt(rx * rx + ry * ry + rz * rz)
        return[rx / length, ry / length, rz / length] if length > 0 else[1, 0, 0]

    def get_up(self):
        fx, fy, fz = self.get_front()
        rx, ry, rz = self.get_right()
        return[ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx]

    def move(self, direction):
        front, right = self.get_front(), self.get_right()
        if direction == "forward":
            for i in range(3): self.pos[i] += front[i] * self.speed
        elif direction == "back":
            for i in range(3): self.pos[i] -= front[i] * self.speed
        elif direction == "left":
            for i in range(3): self.pos[i] -= right[i] * self.speed
        elif direction == "right":
            for i in range(3): self.pos[i] += right[i] * self.speed
        elif direction == "up": self.pos[1] += self.speed
        elif direction == "down": self.pos[1] -= self.speed

    def add_mouse_delta(self, dx, dy):
        self.yaw += dx * self.sensitivity
        self.pitch -= dy * self.sensitivity
        self.pitch = max(-89.0, min(89.0, self.pitch))

    def save_state(self): return {'pos': list(self.pos), 'yaw': self.yaw, 'pitch': self.pitch}
    def restore_state(self, state):
        if state:
            self.pos = list(state['pos']); self.yaw = state['yaw']; self.pitch = state['pitch']

    def set_observer_view(self):
        self.pos, self.yaw, self.pitch =[0.0, 15.0, 0.0], -90.0, -89.0

class SceneObject:
    def __init__(self, obj_type, position, color=None):
        self.type = obj_type
        self.position = list(position)
        self.color = color
        self.selected = False
        self.scale =[1.0, 1.0, 1.0]
        self.rotation =[0.0, 0.0, 0.0]
        self.model_path = None
        self.material = None
        self.is_solid = False
        
        self.has_ai = False
        self.ai_vertex_dir =[0, 1, 0]
        self.ai_look_target = None
        self.ai_move_target = None
        self.ai_look_rotation =[0.0, 0.0, 0.0]
        self.ai_timer = 0
        self.ai_speed = 0.02
        self.ai_bend_amount =[0.0, 0.0]
        self.ai_squash_stretch = 1.0
        self.original_position = None
        
        self.jitter_offset =[0.0, 0.0, 0.0]
        
        self.ai_type = "None" 
        self.ai_config = {}
        self.ai_state = "WANDER"
        self.target_prey = None
        self.metal_reg_state = "WAIT"
        self.pending_sound = None
        
        self.speech_text = ""
        self.speech_timer = 0

    def get_aabb(self):
        sx, sy, sz = self.scale
        px, py, pz = self.position
        hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
        return[px - hx, py - hy, pz - hz],[px + hx, py + hy, pz + hz]

    def check_brush_collision(self, next_pos, all_objects):
        hx, _, hz = self.scale[0]/2.0, self.scale[1]/2.0, self.scale[2]/2.0
        for obj in all_objects:
            if obj is self or not obj.is_solid: continue
            b_min, b_max = obj.get_aabb()
            if (next_pos[0] + hx > b_min[0] and next_pos[0] - hx < b_max[0] and
                next_pos[2] + hz > b_min[2] and next_pos[2] - hz < b_max[2]):
                return True
        return False

    def distance_to(self, other_obj):
        dx = self.position[0] - other_obj.position[0]
        dy = self.position[1] - other_obj.position[1]
        dz = self.position[2] - other_obj.position[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def update_ai(self, int_menu_mode, bounds, all_objects):
        if not self.has_ai or self.ai_type == "None":
            self.jitter_offset = [0.0, 0.0, 0.0]
            return
            
        self.ai_timer += 1
        if self.speech_timer > 0: self.speech_timer -= 1
        
        if self.ai_timer % 180 == 0 and random.random() < 0.4:
            pass_snd = ""
            if self.ai_type == "FSKY_CAPTURE_CBSGY": pass_snd = self.ai_config.get("fsky_pass", "")
            elif self.ai_type == "DMNPC_TLEET_WDYMS": pass_snd = self.ai_config.get("dmnpc_pass", "")
            elif self.ai_type == "Siuef": pass_snd = self.ai_config.get("sil_pass", "")
            if pass_snd: self.pending_sound = pass_snd

        if self.ai_type == "Siuef":
            self.ai_speed = 0.05
            
            j = 0.1
            self.jitter_offset =[random.uniform(-j, j), random.uniform(-j, j), random.uniform(-j, j)]
            self.rotation =[180.0, 0.0, 0.0]
            self.scale = [1.0, 1.0, 1.0] 
            
            if self.ai_config.get("sil_speech") and self.speech_timer <= 0 and random.random() < 0.005:
                self.speech_text = random.choice([":Hi hello :D", ":spave", ":run", ":O"])
                self.speech_timer = 150

            if self.ai_timer % 60 == 0 or self.ai_move_target is None:
                self.ai_move_target = [
                    self.position[0] + random.uniform(-4, 4),
                    self.position[1],
                    self.position[2] + random.uniform(-4, 4)
                ]
            
            if int_menu_mode and self.ai_move_target:
                next_pos = list(self.position)
                dx = self.ai_move_target[0] - self.position[0]
                dz = self.ai_move_target[2] - self.position[2]
                dist = math.sqrt(dx*dx + dz*dz)
                if dist > 0.1:
                    next_pos[0] += (dx / dist) * self.ai_speed
                    next_pos[2] += (dz / dist) * self.ai_speed
                    if not self.check_brush_collision(next_pos, all_objects):
                        self.position[0] = next_pos[0]
                        self.position[2] = next_pos[2]
                    else:
                        self.ai_move_target = None
            return

        self.jitter_offset =[0.0, 0.0, 0.0]

        if self.ai_type == "DMNPC_TLEET_WDYMS":
            self.ai_speed = 0.03
            physics_type = self.ai_config.get("dmnpc_phys", "GRIS shape")
            
            if self.ai_timer % 120 == 0 or self.ai_move_target is None:
                self.ai_move_target = [
                    self.position[0] + random.uniform(-3, 3),
                    self.position[1],
                    self.position[2] + random.uniform(-3, 3)
                ]
                self.ai_look_target = list(self.ai_move_target)

            if int_menu_mode and self.ai_move_target:
                dx = self.ai_move_target[0] - self.position[0]
                dz = self.ai_move_target[2] - self.position[2]
                dist = math.sqrt(dx*dx + dz*dz)
                
                target_yaw = math.degrees(math.atan2(dz, dx))
                if physics_type == "Model":
                    self.rotation[1] = self.lerp_angle(self.rotation[1], target_yaw, 0.05)
                else:
                    self.ai_look_rotation[1] = self.lerp_angle(self.ai_look_rotation[1], target_yaw, 0.05)
                    self.ai_squash_stretch = 1.0 + math.sin(self.ai_timer * 0.2) * 0.05
                    self.ai_bend_amount[0] = self.lerp_value(self.ai_bend_amount[0], math.sin(self.ai_timer * 0.1)*0.2, 0.1)

                if dist > 0.1:
                    next_pos = list(self.position)
                    next_pos[0] += (dx / dist) * self.ai_speed
                    next_pos[2] += (dz / dist) * self.ai_speed
                    if not self.check_brush_collision(next_pos, all_objects):
                        self.position[0] = next_pos[0]
                        self.position[2] = next_pos[2]
                    else:
                        self.ai_move_target = None
            return

        if self.ai_type == "FSKY_CAPTURE_CBSGY":
            self.ai_speed = 0.07 
            ignore_collision = self.ai_config.get("fsky_ignore_col", False)
            radius = self.ai_config.get("fsky_radius", 15.0)
            
            reg_states =["PLAT", "SETREG", "CPU_POP", "NAN_CREG", "STOPREG_DIRTY", "WAIT", "THINK", "CPU_PUSH", "HALT"]
            if self.ai_timer % 5 == 0: self.metal_reg_state = random.choice(reg_states)

            if self.ai_state != "HALT" and random.random() < 0.002:
                self.ai_state = "HALT"
                self.ai_move_target = None
                self.target_prey = None
                self.ai_timer = 0
                
            if self.ai_state == "HALT":
                if self.ai_timer > 100: self.ai_state = "WANDER"
                return 
                
            if self.ai_state == "WANDER" and self.ai_timer % 30 == 0:
                best_prey, best_dist = None, radius
                for obj in all_objects:
                    if obj is self or not obj.has_ai: continue
                    if obj.ai_type == "FSKY_CAPTURE_CBSGY": continue 
                    d = self.distance_to(obj)
                    if d < best_dist:
                        if obj.ai_type == "Siuef": d -= 5.0
                        best_dist = d
                        best_prey = obj
                        
                if best_prey:
                    self.ai_state = "CAPTURE"
                    self.target_prey = best_prey
                    not_snd1 = self.ai_config.get("fsky_not1", "")
                    not_snd2 = self.ai_config.get("fsky_not2", "")
                    sounds = [s for s in[not_snd1, not_snd2] if s]
                    if sounds: self.pending_sound = random.choice(sounds)

            if self.ai_state == "CAPTURE":
                if not self.target_prey or not self.target_prey.has_ai:
                    self.ai_state = "WANDER"
                    return
                
                self.ai_move_target = list(self.target_prey.position)
                d = self.distance_to(self.target_prey)
                
                if d < 1.0: 
                    self.target_prey.has_ai = False
                    self.target_prey.ai_type = "None"
                    self.target_prey.scale =[1.0, 0.1, 1.0] 
                    self.target_prey.color = (0.3, 0.1, 0.1) 
                    self.target_prey.type = "Cube" 
                    
                    cap_snd = self.ai_config.get("fsky_cap", "")
                    if cap_snd: self.pending_sound = cap_snd
                    
                    self.ai_state = "WANDER"
                    self.target_prey = None

            if self.ai_state == "WANDER" and (self.ai_move_target is None or self.ai_timer % 60 == 0):
                self.ai_move_target =[
                    self.position[0] + random.uniform(-6, 6),
                    self.position[1] + random.uniform(-1, 2), 
                    self.position[2] + random.uniform(-6, 6)
                ]

            if int_menu_mode and self.ai_move_target:
                next_pos = list(self.position)
                dx = self.ai_move_target[0] - self.position[0]
                dy = self.ai_move_target[1] - self.position[1]
                dz = self.ai_move_target[2] - self.position[2]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                
                if dist > 0.1:
                    next_pos[0] += (dx / dist) * self.ai_speed
                    next_pos[1] += (dy / dist) * self.ai_speed
                    next_pos[2] += (dz / dist) * self.ai_speed
                    
                    target_yaw = math.degrees(math.atan2(dz, dx))
                    self.ai_look_rotation[1] = self.lerp_angle(self.ai_look_rotation[1], target_yaw, 0.1)
                    self.ai_bend_amount[0] = self.lerp_value(self.ai_bend_amount[0], (dy/dist) * 0.5, 0.1)
                    
                    if ignore_collision or not self.check_brush_collision(next_pos, all_objects):
                        self.position = list(next_pos)
                    else:
                        self.ai_move_target = None 

    def lerp_angle(self, current, target, factor):
        diff = target - current
        while diff > 180: diff -= 360
        while diff < -180: diff += 360
        return current + diff * factor

    def lerp_value(self, current, target, factor):
        return current + (target - current) * factor

class Brush(SceneObject):
    def __init__(self, position, color=None):
        super().__init__("Brush", position, color)
        self.is_solid = True
        self.scale =[2.0, 2.0, 2.0]

class EraserEntity(SceneObject):
    def __init__(self, position, target_obj):
        super().__init__("Model", position)
        self.target_obj = target_obj
        self.hit_target = False
        self.has_ai = True
        self.ai_type = "Eraser"
        
        self.ai_speed = 0.06
        self.scale = [0.85, 0.85, 0.85]
        
        self.velocity = [0.0, 0.0, 0.0]
        self.reaim_timer = 0
        self.aim_offset = [0.0, 0.0, 0.0]
        
    def update_ai(self, int_menu_mode, bounds, all_objects):
        if self.hit_target or not self.target_obj:
            return
            
        self.ai_timer += 1
        self.reaim_timer += 1
        
        if self.reaim_timer >= 5:
            self.reaim_timer = 0
            self.aim_offset = [
                random.uniform(-1.25, 1.25),
                random.uniform(-0.8, 1.35),
                random.uniform(-1.2, 1.2)
            ]
        
        tx = self.target_obj.position[0] + self.aim_offset[0]
        ty = self.target_obj.position[1] + self.aim_offset[1]
        tz = self.target_obj.position[2] + self.aim_offset[2]
        
        dx = tx - self.position[0]
        dy = ty - self.position[1]
        dz = tz - self.position[2]
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        
        if dist < 0.95:                         
            self.hit_target = True
            return
        
        dir_x = dx / dist
        dir_y = dy / dist
        dir_z = dz / dist
        
        self.velocity[0] = self.velocity[0] * 0.78 + dir_x * self.ai_speed
        self.velocity[1] = self.velocity[1] * 0.78 + dir_y * self.ai_speed
        self.velocity[2] = self.velocity[2] * 0.78 + dir_z * self.ai_speed
        
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        self.position[2] += self.velocity[2]
        
        if self.ai_timer % 3 == 0:
            self.position[0] += random.uniform(-0.09, 0.09)
            self.position[1] += random.uniform(-0.06, 0.10)
            self.position[2] += random.uniform(-0.08, 0.08)
        
