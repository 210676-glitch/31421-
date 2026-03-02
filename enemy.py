import random
import math
from panda3d.core import Vec3

class EnemySystem:
    def __init__(self, base, ground_system):
        self.base = base
        self.ground_system = ground_system
        self.enemies = []
        self.enemy_models = []
        self.enemy_move_speed = 36
        self.attack_basic_range = 40
        self.attack_arrow_range = 200
        self.attack_archer_range = 200
        self.attack_basic_cooldown = 1.2
        self.attack_archer_cooldown = 5.0
        self.detection_range = 500
        self.arrows = []
        self.ENEMY_MODEL_FORWARD_OFFSET = 180.0

    def create_enemy(self, position, enemy_type, area_id="1-1"):
        if position is None:
            position = self.get_random_position_in_area1()
        if enemy_type == "basic":
            enemy_model = self.base.loader.loadModel("model/enemy/monster_hill/Hilichurls.egg")
            tex = self.base.loader.loadTexture("model/enemy/monster_hill/images/Monster_Hili_Wei_Tex_Diffuse.png")
            enemy_model.setTexture(tex, 1)
        elif enemy_type == "archer":
            enemy_model = self.base.loader.loadModel("model/enemy/archer/archer.egg")
            tex = self.base.loader.loadTexture("model/enemy/archer/images/MonEquip_IceClub_01_Tex_Diffuse.png")
            enemy_model.setTexture(tex, 1)
        else:
            enemy_model = self.base.loader.loadModel("model/enemy/monster_hill/Hilichurls.egg")
            tex = self.base.loader.loadTexture("model/enemy/monster_hill/images/Monster_Hili_Wei_Tex_Diffuse.png")
            enemy_model.setTexture(tex, 1)
            enemy_type = "basic"
        
        enemy_model.setScale(20)
        ground_z = self.ground_system.get_ground_height(position.x, position.y)
        position.z = ground_z
        enemy_model.setPos(position)
        enemy_model.reparentTo(self.base.render)
        
        hp = 100
        enemy_data = {
            "model": enemy_model,
            "position": position,
            "health": hp,
            "max_health": hp,
            "type": enemy_type,
            "alive": True,
            "state": "idle",
            "attack_timer": 0,
            "last_attack_time": 0,
            "target_position": None,
            "arrow": None,
            "area_id": area_id,
            "attack_cooldown": 0
        }
        self.enemies.append(enemy_data)
        self.enemy_models.append(enemy_model)
        return enemy_data

    def create_arrow(self, start_pos, target_pos, damage=20):
        arrow = self.base.loader.loadModel("model/weapon/arrow.egg")
        arrow.setScale(10)
        arrow.setPos(start_pos)
        arrow.lookAt(target_pos)
        current_hpr = arrow.getHpr() + Vec3(90, 0, 0)
        arrow.setHpr(current_hpr)
        arrow.reparentTo(self.base.render)
        
        direction = target_pos - start_pos
        if direction.length() > 0:
            direction.normalize()
        else:
            direction = Vec3(0, 1, 0)
        
        arrow_data = {
            "model": arrow,
            "position": start_pos,
            "direction": direction,
            "speed": 100,
            "damage": damage,
            "max_distance": self.attack_arrow_range,
            "distance_traveled": 0,
            "active": True
        }
        self.arrows.append(arrow_data)
        return arrow_data

    def update_arrows(self, dt, player_pos):
        arrows_to_remove = []
        for i, arrow_data in enumerate(list(self.arrows)):
            if not arrow_data.get("active", False):
                continue
            move_distance = arrow_data["speed"] * dt
            arrow_data["distance_traveled"] += move_distance
            new_pos = arrow_data["position"] + arrow_data["direction"] * move_distance
            arrow_data["position"] = new_pos
            arrow_data["model"].setPos(new_pos)
            distance_to_player = (new_pos - player_pos).length()
            if distance_to_player < 15:
                self.base.player_hp_system.take_damage(arrow_data["damage"])
                arrow_data["active"] = False
                arrows_to_remove.append(i)
                continue
            if arrow_data["distance_traveled"] >= arrow_data["max_distance"]:
                arrow_data["active"] = False
                arrows_to_remove.append(i)
        
        for i in sorted(arrows_to_remove, reverse=True):
            arrow_data = self.arrows.pop(i)
            if arrow_data.get("model"):
                arrow_data["model"].removeNode()

    def enemy_archer_attack(self, enemy, player_pos):
        enemy_pos = enemy["model"].getPos()
        arrow_start_pos = Vec3(enemy_pos.x, enemy_pos.y, enemy_pos.z + 10)
        self.create_arrow(arrow_start_pos, player_pos, damage=20)

    def restrict_enemy_to_area(self, enemy, new_pos):
        if hasattr(self.base, 'area_system'):
            area_system = self.base.area_system
            for region in area_system.all_regions:
                if region.region_id == enemy["area_id"]:
                    bounds = region.bounds
                    buffer = 10
                    clamped_x = max(bounds['min_x'] + buffer, min(new_pos.x, bounds['max_x'] - buffer))
                    clamped_y = max(bounds['min_y'] + buffer, min(new_pos.y, bounds['max_y'] - buffer))
                    if clamped_x != new_pos.x or clamped_y != new_pos.y:
                        enemy["state"] = "idle"
                        return Vec3(clamped_x, clamped_y, new_pos.z)
        return new_pos

    def update_basic_enemies(self, player_pos, dt):
        current_time = self.base.globalClock.getFrameTime()
        self.player_pos = player_pos
        self.update_arrows(dt, player_pos)
        
        for enemy in list(self.enemies):
            if not enemy["alive"]:
                continue
            if enemy["attack_cooldown"] > 0:
                enemy["attack_cooldown"] -= dt
            
            enemy_pos = enemy["model"].getPos()
            distance_to_player = (enemy_pos - player_pos).length()
            
            if enemy["state"] == "idle":
                if distance_to_player <= self.detection_range:
                    enemy["state"] = "chasing"
            elif enemy["state"] == "chasing":
                if enemy["type"] == "basic":
                    if distance_to_player <= self.attack_basic_range:
                        enemy["state"] = "attacking"
                        enemy["attack_timer"] = 0
                    else:
                        direction = player_pos - enemy_pos
                        direction.setZ(0)
                        if direction.length() > 0:
                            direction.normalize()
                            move_vec = direction * self.enemy_move_speed * dt
                            new_pos = enemy_pos + move_vec
                            new_pos = self.restrict_enemy_to_area(enemy, new_pos)
                            new_z = self.ground_system.get_ground_height(new_pos.x, new_pos.y)
                            new_pos.z = new_z
                            enemy["model"].setPos(new_pos)
                            look_at_point = Vec3(player_pos.x, player_pos.y, new_pos.z)
                            enemy["model"].lookAt(look_at_point)
                            h = enemy["model"].getHpr().x + self.ENEMY_MODEL_FORWARD_OFFSET
                            enemy["model"].setHpr(h, 90, 90)
                elif enemy["type"] == "archer":
                    if distance_to_player <= self.attack_archer_range:
                        enemy["state"] = "attacking"
                        enemy["attack_timer"] = 0
                    else:
                        direction = player_pos - enemy_pos
                        direction.setZ(0)
                        if direction.length() > 0:
                            direction.normalize()
                            move_vec = direction * self.enemy_move_speed * dt
                            new_pos = enemy_pos + move_vec
                            new_pos = self.restrict_enemy_to_area(enemy, new_pos)
                            new_z = self.ground_system.get_ground_height(new_pos.x, new_pos.y)
                            new_pos.z = new_z
                            enemy["model"].setPos(new_pos)
                            look_at_point = Vec3(player_pos.x, player_pos.y, new_pos.z)
                            enemy["model"].lookAt(look_at_point)
                            h = enemy["model"].getHpr().x + self.ENEMY_MODEL_FORWARD_OFFSET
                            enemy["model"].setHpr(h, 90, 90)
            elif enemy["state"] == "attacking":
                if enemy["type"] == "basic":
                    enemy["attack_timer"] += dt
                    if 0.4 <= enemy["attack_timer"] and enemy["attack_cooldown"] <= 0:
                        self.enemy_basic_attack(enemy, player_pos)
                        enemy["attack_cooldown"] = 1.0
                    if enemy["attack_timer"] >= self.attack_basic_cooldown:
                        enemy["state"] = "chasing"
                        enemy["last_attack_time"] = current_time
                elif enemy["type"] == "archer":
                    enemy["attack_timer"] += dt
                    if 0.4 <= enemy["attack_timer"] and enemy["attack_cooldown"] <= 0:
                        self.enemy_archer_attack(enemy, player_pos)
                        enemy["attack_cooldown"] = 2.0
                    if enemy["attack_timer"] >= self.attack_archer_cooldown:
                        enemy["state"] = "chasing"
                        enemy["last_attack_time"] = current_time
            
            if enemy["state"] != "idle" and distance_to_player > self.detection_range + 100:
                enemy["state"] = "idle"

    def enemy_basic_attack(self, enemy, player_pos):
        enemy_pos = enemy["model"].getPos()
        distance = (enemy_pos - player_pos).length()
        if distance <= self.attack_basic_range:
            self.base.player_hp_system.take_damage(10)

    def check_attack_hit(self, attacker_pos, attacker_hpr, attack_range=50, attack_angle=120, damage=25, attacker_owner=None):
        hits = 0
        enemies_to_remove = []
        for enemy in list(self.enemies):
            if not enemy["alive"]:
                continue
            enemy_pos = enemy["model"].getPos()
            distance = (enemy_pos - attacker_pos).length()
            if distance <= attack_range:
                enemy["health"] -= damage
                enemy["model"].setColor(1, 0.5, 0.5, 1)
                self.base.taskMgr.doMethodLater(0.2, lambda task, e=enemy: self.reset_enemy_color(e), f"reset_color_{id(enemy)}")
                hits += 1
                if enemy["health"] <= 0:
                    self.kill_enemy(enemy)
                    enemies_to_remove.append(enemy)
        
        for e in enemies_to_remove:
            if e in self.enemies:
                self.enemies.remove(e)

        if attacker_owner != "boss":
            if hasattr(self.base, 'boss_system') and self.base.boss_system and self.base.boss_system.boss_alive:
                boss_pos = self.base.boss_system.boss["model"].getPos()
                distance = (boss_pos - attacker_pos).length()
                if distance <= attack_range:
                    self.base.boss_system.damage_boss(damage)
                    hits += 1

        if hasattr(self.base, 'boss_system') and self.base.boss_system and self.base.boss_system.death_backlash_active:
            crystal_hits = self.base.boss_system.check_crystal_hit(attacker_pos, attack_range)
            hits += crystal_hits

        return hits

    def reset_enemy_color(self, enemy):
        if enemy["alive"]:
            enemy["model"].setColor(1, 1, 1, 1)

    def kill_enemy(self, enemy):
        enemy["alive"] = False
        if enemy.get("model"):
            enemy["model"].hide()
        if hasattr(self.base, 'area_system'):
            self.base.area_system.on_enemy_defeated()
        if hasattr(self.base, 'area1_system'):
            self.base.area1_system.on_enemy_defeated()

    def get_random_position_in_area1(self):
        x = random.uniform(-100, 100)
        y = random.uniform(-100, 100)
        z = self.ground_system.get_ground_height(x, y)
        return Vec3(x, y, z)

    def spawn_basic_enemies(self, count):
        for i in range(count):
            self.create_enemy(None, "basic")

    def spawn_archer_enemies(self, count):
        for i in range(count):
            self.create_enemy(None, "archer")

    def get_enemy_count(self):
        return sum(1 for enemy in self.enemies if enemy["alive"])

    def get_total_enemy_count(self):
        return len(self.enemies)

    def cleanup(self):
        for arrow_data in list(self.arrows):
            if arrow_data.get("model"):
                arrow_data["model"].removeNode()
        self.arrows.clear()
        for enemy_model in list(self.enemy_models):
            enemy_model.removeNode()
        self.enemies.clear()
        self.enemy_models.clear()

class AttackSystem:
    @staticmethod
    def normal_attack(enemy_system, player_pos, player_hpr):
        hits = enemy_system.check_attack_hit(player_pos, player_hpr, attack_range=50, attack_angle=120, damage=25)
        return hits

    @staticmethod
    def e_skill_attack(enemy_system, player_pos, player_hpr):
        hits = enemy_system.check_attack_hit(player_pos, player_hpr, attack_range=50, attack_angle=120, damage=50)
        return hits

    @staticmethod
    def q_skill_attack(enemy_system, player_pos, player_hpr):
        hits = enemy_system.check_attack_hit(player_pos, player_hpr, attack_range=80, attack_angle=180, damage=50)
        return hits

__all__ = ['EnemySystem', 'AttackSystem']