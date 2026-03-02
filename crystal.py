from panda3d.core import Vec3
import math

class CrystalSystem:
    def __init__(self, base, ground_system, arena_center):
        self.base = base
        self.ground_system = ground_system
        self.arena_center = arena_center
        self.crystals = []
        self.crystal_attack_count = {}
        self.crystals_required_hits = 4
        self.crystal_attack_range = 80

    def create_crystal(self, position, index):
        crystal_model = self.base.loader.loadModel("model/background/crystal.glb")
        crystal_model.setScale(1)
        crystal_model.setHpr(0, 90, 0)
        crystal_model.setPos(position)
        crystal_model.reparentTo(self.base.render)
        crystal_data = {
            "model": crystal_model,
            "position": position,
            "index": index,
            "hits_required": self.crystals_required_hits,
            "current_hits": 0,
            "alive": True
        }
        self.crystals.append(crystal_data)
        self.crystal_attack_count[index] = 0
        return crystal_data

    def spawn_crystals(self, count, radius=None, height=5):
        self.cleanup_crystals()
        if count <= 0:
            return []
        radius = getattr(self, "arena_radius", 200) if radius is None else radius
        angle_step = 360.0 / count
        created = []
        for i in range(count):
            angle_deg = i * angle_step
            rad = math.radians(angle_deg)
            x = self.arena_center.x + math.cos(rad) * radius
            y = self.arena_center.y + math.sin(rad) * radius
            pos = Vec3(x, y, height)
            c = self.create_crystal(pos, i)
            created.append(c)
        return created

    def check_crystal_hit(self, attacker_pos, attack_range=80):
        hits = 0
        for crystal in self.crystals:
            if not crystal["alive"]:
                continue
            crystal_pos = crystal["model"].getPos()
            distance = (crystal_pos - attacker_pos).length()
            if distance <= attack_range:
                self.damage_crystal(crystal["index"])
                hits += 1
        return hits

    def damage_crystal(self, crystal_index):
        for crystal in self.crystals:
            if crystal["index"] == crystal_index and crystal["alive"]:
                crystal["current_hits"] += 1
                crystal["model"].setColor(1, 0.5, 0.5, 1)
                self.base.taskMgr.doMethodLater(0.2, lambda task, idx=crystal_index: self.reset_crystal_color(idx), f"reset_crystal_color_{crystal_index}")
                self.update_crystal_visual(crystal)
                if crystal["current_hits"] >= crystal["hits_required"]:
                    crystal["alive"] = False
                    crystal["model"].hide()
                break

    def update_crystal_visual(self, crystal):
        if not crystal["alive"]:
            return
        hit_ratio = crystal["current_hits"] / crystal["hits_required"]
        if hit_ratio < 0.33:
            crystal["model"].setColor(0.8, 1, 1, 1)
        elif hit_ratio < 0.66:
            crystal["model"].setColor(0.5, 0.8, 1, 1)
        else:
            crystal["model"].setColor(0.3, 0.5, 1, 1)

    def reset_crystal_color(self, crystal_index):
        for crystal in self.crystals:
            if crystal["index"] == crystal_index and crystal["alive"]:
                self.update_crystal_visual(crystal)
                break

    def check_all_crystals_destroyed(self):
        return all(not c["alive"] for c in self.crystals) and len(self.crystals) > 0

    def get_crystal_status(self):
        alive_count = sum(1 for c in self.crystals if c["alive"])
        total_count = len(self.crystals)
        return alive_count, total_count

    def cleanup_crystals(self):
        for crystal in self.crystals:
            if crystal.get("model"):
                crystal["model"].removeNode()
        self.crystals.clear()
        self.crystal_attack_count.clear()

    def update(self, dt):
        pass