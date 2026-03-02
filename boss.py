# boss.py 
from panda3d.core import Vec3
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode
import math
import random
import os

import joblib

from crystal import CrystalSystem

# 嘗試延後 import AILogger（若未提供該檔案則不影響遊戲）
try:
    from boss_ai_logging import AILogger
except Exception:
    AILogger = None


class BossSystem:
    def __init__(self, base, ground_system, enemy_system, arena_center, arena_radius):
        self.base = base
        self.ground_system = ground_system
        self.enemy_system = enemy_system

        self.arena_center = arena_center
        self.arena_radius = arena_radius

        self.crystal_system = CrystalSystem(base, ground_system, arena_center)

        self.boss = None
        self.boss_alive = False
        self.current_phase = 1
        self.boss_health = 1000
        self.max_boss_health = 1000

        self.boss_move_speed = 5.0 * 60

        self.attack_cooldown = 0
        self.is_attacking = False

        self.attack_cycle = []
        self.current_attack_index = 0
        self.is_in_attack_cycle = False

        self.available_skills = ["projectile", "spikes", "line_spikes"]

        self.attack_timers = {
            "combo_thrust": 0,
            "projectile": 0.5,
            "spikes": 1,
            "line_spikes": 2
        }

        self.attack_cooldowns = {
            "combo_thrust": 2.0,
            "projectile": 5.0,
            "spikes": 7.0,
            "line_spikes": 10.0
        }

        self.attack_winddown_times = {
            "combo_thrust": 1.4,
            "projectile": 1.0,
            "spikes": 1.4,
            "line_spikes": 1.8
        }

        self.attack_damages = {
            "combo_thrust": [30, 25, 50, 100],#若不躲開更高的傷害
            "projectile": 25,
            "spikes": 30,
            "line_spikes": 60
        }

        self.attack_ranges = {
            "combo_thrust": 80,
            "projectile": 600,
            "spikes": 35,
            "line_spikes": 60
        }

        self.model_paths = {
            "boss": "model/enemy/boss/hiro.glb",
            "projectile": "model/weapon/spike.glb",
            "spike": "model/weapon/weapon.egg",
            "fallback": "models/box.egg"
        }

        self.combo_thrust_state = "ready"
        self.combo_thrust_direction = None
        self.combo_thrust_target_pos = None

        # new: support multi-thrust before combo slashes
        self.combo_thrust_count = 0
        self.combo_thrust_total = 3  # perform 3 thrusts before the 3-hit slash combo

        self.spike_warnings = []
        self.active_spikes = []
        self.active_projectiles = []
        self.default_projectile_speed = 360

        self.line_spike_warnings = []
        self.active_line_spikes = []

        self.death_backlash_active = False
        self.death_backlash_count = 0
        self.death_backlash_timer = 0
        self.death_backlash_duration = 8.0

        self.last_player_pos = None
        self.flank_direction = None
        self.last_attack_time = 0
        self.attack_interval = 3.5

        # AI model related
        self.ai_model = None
        self.model_feature_names = None
        self.use_ai = False
        self.ai_decision_interval = 0.5
        self.last_ai_decision_time = 0

        # AILogger if available
        self.ai_logger = AILogger() if AILogger is not None else None

        self.boss_health_text = None
        self.phase_text = None

        # track knockback task name to avoid multiple overlapping tasks
        self._knockback_task_name = "player_knockback_task"

        self.setup_display()
        self.spawn_boss()
        self.load_ai_model()

        print("Boss系統初始化完成")
        # face task intentionally removed elsewhere; HPR baseline handled where needed

    # ---------------- display / spawn ----------------
    def setup_display(self):
        self.boss_health_text = OnscreenText(
            text=f"BOSS HP: {self.boss_health}/{self.max_boss_health}",
            pos=(0, 0.9),
            scale=0.05,
            fg=(1, 0, 0, 1),
            align=TextNode.ACenter,
            mayChange=True
        )
        self.phase_text = OnscreenText(
            text="PHASE 1",
            pos=(0, 0.85),
            scale=0.04,
            fg=(1, 1, 0, 1),
            align=TextNode.ACenter,
            mayChange=True
        )

    def spawn_boss(self):
        boss_pos = Vec3(self.arena_center.x, self.arena_center.y, 10)
        boss_model = self.base.loader.loadModel(self.model_paths["boss"])
        boss_model.setScale(60)
        boss_model.setPos(boss_pos)
        # 設定初始 HPR 包含 (0,90,90) 偏移（作為模型基線）
        boss_model.setHpr(0, 90, 90)
        boss_model.reparentTo(self.base.render)
        self.boss = {"model": boss_model, "position": boss_pos, "health": self.boss_health, "alive": True, "type": "boss"}
        self.boss_alive = True
        print("Boss生成成功！")

    # ---------------- AI 模型載入 ----------------
    def load_ai_model(self):
        possible_paths = ['boss_ai_model.pkl', 'models/boss_ai_model.pkl']
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    loaded = joblib.load(path)
                    if isinstance(loaded, dict) and "model" in loaded and "label_encoder" in loaded:
                        self.ai_model = loaded
                        self.model_feature_names = loaded.get("feature_names", None)
                        self.use_ai = True
                        print(f"AI 模型加載成功 (dict) : {path}")
                        return
                    else:
                        self.ai_model = {"model": loaded, "label_encoder": None}
                        self.model_feature_names = None
                        self.use_ai = False
                        print(f"AI 模型加載為單一物件：{path}（需要 feature_names 才能啟用）")
                        return
                except Exception as e:
                    print(f"載入 AI 模型失敗: {e}")
        print("未找到AI模型，使用規則決策")

    # ---------------- utility: build features for model ----------------
    def _gather_basic_features(self):
        try:
            boss_pos = self.boss['model'].getPos() if self.boss and self.boss.get('model') else self.boss.get('position') if self.boss else Vec3(0, 0, 0)
        except Exception:
            boss_pos = Vec3(0, 0, 0)
        try:
            player_pos = self.base.model_butterfly.getPos()
        except Exception:
            player_pos = Vec3(0, 0, 0)
        try:
            player_hp = getattr(self.base.player_hp_system, 'current_health', -1)
        except Exception:
            player_hp = -1
        distance = (player_pos - boss_pos).length() if boss_pos and player_pos else 0.0
        crystals_alive = 0
        try:
            crystals_alive = sum(1 for c in self.crystal_system.crystals if c["alive"]) if self.crystal_system else 0
        except Exception:
            crystals_alive = 0

        features = {
            "phase": int(self.current_phase),
            "boss_hp": float(self.boss_health),
            "boss_max_hp": float(self.max_boss_health),
            "boss_x": float(boss_pos.x),
            "boss_y": float(boss_pos.y),
            "player_hp": float(player_hp),
            "player_x": float(player_pos.x),
            "player_y": float(player_pos.y),
            "distance": float(distance),
            "death_backlash_active": 1 if self.death_backlash_active else 0,
            "crystals_alive": int(crystals_alive)
        }
        return features

    def _build_feature_vector(self, available_skills):
        if not self.model_feature_names:
            return None
        basic = self._gather_basic_features()
        skill_flags = {}
        for s in available_skills:
            skill_flags[f"skill_has_{s}"] = 1
        X = []
        for name in self.model_feature_names:
            if name in basic:
                X.append(basic[name])
            elif name.startswith("skill_has_"):
                X.append(1 if skill_flags.get(name, 0) else 0)
            else:
                X.append(0)
        return X

    # ---------------- AI / logging decision wrapper ----------------
    def decide_skill(self, available_skills):
        chosen_skill = None
        used_model = False
        if self.use_ai and self.ai_model and self.ai_model.get("model") and self.ai_model.get("label_encoder") and self.model_feature_names:
            try:
                X = self._build_feature_vector(available_skills)
                if X is not None:
                    model = self.ai_model["model"]
                    le = self.ai_model["label_encoder"]
                    pred_idx = model.predict([X])[0]
                    try:
                        pred_label = le.inverse_transform([pred_idx])[0] if le is not None else pred_idx
                    except Exception:
                        pred_label = pred_idx
                    if isinstance(pred_label, str) and pred_label in available_skills:
                        chosen_skill = pred_label
                        used_model = True
                    else:
                        chosen_skill = random.choice(available_skills) if available_skills else None
                else:
                    chosen_skill = random.choice(available_skills) if available_skills else None
            except Exception as e:
                print(f"[Boss AI] 模型決策失敗，回退到隨機 (err: {e})")
                chosen_skill = random.choice(available_skills) if available_skills else None
        else:
            chosen_skill = random.choice(available_skills) if available_skills else None

        try:
            if self.ai_logger and chosen_skill:
                basic = self._gather_basic_features()
                record = {
                    "phase": basic.get("phase", 0),
                    "boss_hp": basic.get("boss_hp", 0),
                    "boss_max_hp": basic.get("boss_max_hp", 0),
                    "boss_x": basic.get("boss_x", 0),
                    "boss_y": basic.get("boss_y", 0),
                    "player_hp": basic.get("player_hp", -1),
                    "player_x": basic.get("player_x", 0),
                    "player_y": basic.get("player_y", 0),
                    "distance": basic.get("distance", 0),
                    "available_skills": list(available_skills),
                    "chosen_skill": chosen_skill,
                    "death_backlash_active": bool(self.death_backlash_active),
                    "crystals_alive": basic.get("crystals_alive", 0)
                }
                self.ai_logger.log(record)
        except Exception as e:
            print(f"[Boss AI Logger] log failed: {e}")

        return chosen_skill, used_model

    # ---------------- projectile / spike helpers ----------------
    def create_projectile_model(self, start_pos, direction):
        projectile_model = self.base.loader.loadModel(self.model_paths["projectile"])
        projectile_model.setScale(20)
        projectile_model.setPos(start_pos + Vec3(0, 0, 5))
        projectile_model.lookAt(start_pos + direction)
        projectile_model.reparentTo(self.base.render)
        projectile_data = {
            "model": projectile_model,
            "position": start_pos,
            "direction": direction,
            "speed": self.default_projectile_speed,
            "damage": self.attack_damages["projectile"],
            "max_distance": self.attack_ranges["projectile"],
            "distance_traveled": 0,
            "active": True
        }
        self.active_projectiles.append(projectile_data)

    def spike_attack(self, player_pos):
        num_spikes = 6 if self.current_phase == 1 else 10
        for i in range(num_spikes):
            angle = random.uniform(0, 360)
            distance = random.uniform(50, 200)
            x = player_pos.x + math.cos(math.radians(angle)) * distance
            y = player_pos.y + math.sin(math.radians(angle)) * distance
            spike_pos = Vec3(x, y, 5)
            if (spike_pos - self.arena_center).length() < self.arena_radius - 50:
                self.create_spike_warning(spike_pos)
        self.start_attack_winddown("spikes")
        self.continue_attack_cycle_after_skill("spikes")

    def update_projectiles(self, dt):
        projectiles_to_remove = []
        for i, projectile in enumerate(self.active_projectiles):
            if not projectile["active"]:
                continue
            move_distance = projectile["speed"] * dt
            projectile["distance_traveled"] += move_distance
            new_pos = projectile["position"] + projectile["direction"] * move_distance
            projectile["position"] = new_pos
            projectile["model"].setPos(new_pos)
            player_pos = self.base.model_butterfly.getPos()
            distance_to_player = (new_pos - player_pos).length()
            if distance_to_player < 25:
                if hasattr(self.base, 'player_hp_system'):
                    self.base.player_hp_system.take_damage(projectile["damage"])
                    # NOTE: stun was previously added in earlier iterations if desired
                    try:
                        self.base.player_hp_system.stun(1.2)
                    except Exception:
                        pass
                    print("玩家被Boss劍氣擊中並暈眩！")
                projectile["active"] = False
                projectiles_to_remove.append(i)
                continue
            if projectile["distance_traveled"] >= projectile["max_distance"]:
                projectile["active"] = False
                projectiles_to_remove.append(i)
        for i in sorted(projectiles_to_remove, reverse=True):
            projectile_data = self.active_projectiles.pop(i)
            if projectile_data["model"]:
                projectile_data["model"].removeNode()

    # ---------------- main behavior update ----------------
    def update_boss_behavior(self, dt):
        if not self.boss_alive or not self.boss:
            return
        for attack_type in self.attack_timers:
            if attack_type != "combo_thrust":
                self.attack_timers[attack_type] += dt
        player_pos = self.base.model_butterfly.getPos()
        boss_pos = self.boss["model"].getPos()
        current_time = self.base.globalClock.getFrameTime()
        if not self.is_attacking and not self.is_in_attack_cycle:
            if current_time - self.last_attack_time > self.attack_interval:
                self.last_attack_time = current_time
                self.start_attack_cycle()
        if not self.is_attacking and not self.is_in_attack_cycle:
            distance_to_player = (player_pos - boss_pos).length()
            if distance_to_player > 80 and distance_to_player < 1200:
                direction = (player_pos - boss_pos)
                direction.setZ(0)
                if direction.length() > 0:
                    direction.normalize()
                    move_vec = direction * self.boss_move_speed * dt
                    new_pos = boss_pos + move_vec
                    if (new_pos - self.arena_center).length() < self.arena_radius - 50:
                        self.boss["model"].setPos(new_pos)
                        self.boss["position"] = new_pos
            # 在 lookAt 後，統一把 pitch/roll 設為 (90,90)，yaw 用 lookAt 產生的 yaw（避免累加）
            try:
                self.boss["model"].lookAt(player_pos)
                h = self.boss["model"].getHpr().x
                self.boss["model"].setHpr(h, 90, 90)
            except Exception:
                pass
        if self.death_backlash_active:
            self.update_death_backlash(dt)
            return
        self.update_projectiles(dt)
        self.update_spikes(dt)
        self.update_line_spikes(dt)
        self.check_phase_transition()

    def start_attack_cycle(self):
        if not self.attack_cycle:
            self.attack_cycle = ["combo_thrust"]
            if self.available_skills:
                chosen_skill, used_model = self.decide_skill(self.available_skills)
                if chosen_skill:
                    self.attack_cycle.append(chosen_skill)
        self.is_in_attack_cycle = True
        self.current_attack_index = 0
        self.execute_next_attack()

    def execute_next_attack(self):
        if not self.is_in_attack_cycle or self.current_attack_index >= len(self.attack_cycle):
            self.attack_cycle = []
            self.is_in_attack_cycle = False
            return
        current_attack = self.attack_cycle[self.current_attack_index]
        player_pos = self.base.model_butterfly.getPos()
        boss_pos = self.boss["model"].getPos()
        if current_attack == "combo_thrust":
            self.combo_thrust_attack(player_pos, boss_pos)
        elif current_attack == "projectile":
            self.projectile_attack(player_pos, boss_pos)
        elif current_attack == "spikes":
            self.spike_attack(player_pos)
        elif current_attack == "line_spikes":
            self.line_spike_attack(player_pos, boss_pos)
        self.current_attack_index += 1

    # ---------------- combo thrust ----------------
    def combo_thrust_attack(self, player_pos, boss_pos):
        # Prepare multi-thrust sequence before the 3-hit slash combo
        self.combo_thrust_direction = (player_pos - boss_pos)
        self.combo_thrust_direction.setZ(0)
        if self.combo_thrust_direction.length() > 0:
            self.combo_thrust_direction.normalize()
        thrust_distance = 200
        # first target
        self.combo_thrust_target_pos = boss_pos + self.combo_thrust_direction * thrust_distance
        if (self.combo_thrust_target_pos - self.arena_center).length() > self.arena_radius - 50:
            direction_to_center = (self.arena_center - boss_pos)
            direction_to_center.setZ(0)
            direction_to_center.normalize()
            self.combo_thrust_target_pos = self.arena_center + direction_to_center * (self.arena_radius - 100)
        # initialize multi-thrust counters
        self.combo_thrust_state = "thrust"
        self.combo_thrust_count = 0
        self.combo_thrust_total = 3  # perform 3 thrusts
        self.start_smooth_thrust()

    def start_smooth_thrust(self):
        # allow repeated thrusts while combo_thrust_state == "thrust"
        if self.combo_thrust_state != "thrust":
            return
        thrust_duration = 0.8
        self.smooth_move_to_target(self.combo_thrust_target_pos, thrust_duration, self.on_thrust_complete)

    def smooth_move_to_target(self, target_pos, duration, callback):
        start_pos = self.boss["model"].getPos()
        start_time = self.base.globalClock.getFrameTime()
        def move_task(task):
            current_time = self.base.globalClock.getFrameTime()
            elapsed = current_time - start_time
            if elapsed >= duration:
                self.boss["model"].setPos(target_pos)
                self.boss["position"] = target_pos
                callback()
                return task.done
            progress = elapsed / duration
            current_pos = start_pos + (target_pos - start_pos) * progress
            self.boss["model"].setPos(current_pos)
            self.boss["position"] = current_pos
            return task.cont
        # 註冊任務
        self.base.taskMgr.add(move_task, "smooth_move")

    def on_thrust_complete(self):
        # called after each thrust move completes
        player_pos = self.base.model_butterfly.getPos()
        boss_pos = self.boss["model"].getPos()
        distance = (player_pos - boss_pos).length()
        # damage for a thrust hit uses the first entry in attack_damages["combo_thrust"]
        if distance < self.attack_ranges["combo_thrust"]:
            if hasattr(self.base, 'player_hp_system'):
                self.base.player_hp_system.take_damage(self.attack_damages["combo_thrust"][0])
                # each thrust can cause a knockback (reduced by rule)
                try:
                    self.apply_knockback_to_player(boss_pos, distance=140)
                except Exception:
                    pass
        # increment thrust count and either repeat thrust or start slash combo
        self.combo_thrust_count += 1
        if self.combo_thrust_count < self.combo_thrust_total:
            # schedule next thrust: move further ahead in same direction
            thrust_distance = 200
            next_target = self.boss["model"].getPos() + self.combo_thrust_direction * thrust_distance
            if (next_target - self.arena_center).length() > self.arena_radius - 50:
                direction_to_center = (self.arena_center - self.boss["model"].getPos())
                direction_to_center.setZ(0)
                direction_to_center.normalize()
                next_target = self.arena_center + direction_to_center * (self.arena_radius - 100)
            self.combo_thrust_target_pos = next_target
            # small delay between thrusts can be simulated by scheduling start_smooth_thrust or calling directly
            # We'll schedule immediately for snappy behavior
            self.base.taskMgr.doMethodLater(0.08, lambda task: (self.start_smooth_thrust(), task.done)[1], f"next_thrust_{self.combo_thrust_count}")
        else:
            # after completing all thrusts, proceed to 3-hit slash combo ("combo1" ... "combo3")
            self.combo_thrust_state = "combo1"
            self.start_combo_attack()

    def start_combo_attack(self):
        if self.combo_thrust_state.startswith("combo"):
            # compute index from state, then execute the corresponding small thrust/slash movement
            hit_index = int(self.combo_thrust_state[-1]) - 1
            self.execute_combo_thrust_hit(hit_index, self.combo_thrust_direction)

    def execute_combo_thrust_hit(self, hit_index, attack_direction):
        if not self.boss_alive:
            return
        boss_pos = self.boss["model"].getPos()
        thrust_distance = 30
        thrust_target_pos = boss_pos + attack_direction * thrust_distance
        if (thrust_target_pos - self.arena_center).length() > self.arena_radius - 50:
            direction_to_center = (self.arena_center - boss_pos)
            direction_to_center.setZ(0)
            direction_to_center.normalize()
            thrust_target_pos = self.arena_center + direction_to_center * (self.arena_radius - 100)
        self.smooth_move_to_target_small(thrust_target_pos, 0.3,
                                        lambda: self.check_combo_damage(hit_index, attack_direction))

    def smooth_move_to_target_small(self, target_pos, duration, callback):
        start_pos = self.boss["model"].getPos()
        start_time = self.base.globalClock.getFrameTime()
        def move_task(task):
            current_time = self.base.globalClock.getFrameTime()
            elapsed = current_time - start_time
            if elapsed >= duration:
                self.boss["model"].setPos(target_pos)
                self.boss["position"] = target_pos
                callback()
                return task.done
            progress = elapsed / duration
            current_pos = start_pos + (target_pos - start_pos) * progress
            self.boss["model"].setPos(current_pos)
            self.boss["position"] = current_pos
            return task.cont
        self.base.taskMgr.add(move_task, "smooth_move_small")

    def check_combo_damage(self, hit_index, attack_direction):
        player_pos = self.base.model_butterfly.getPos()
        boss_pos = self.boss["model"].getPos()
        distance = (player_pos - boss_pos).length()
        if distance < self.attack_ranges["combo_thrust"]:
            to_player = (player_pos - boss_pos)
            to_player.setZ(0)
            if to_player.length() > 0:
                to_player.normalize()
                dot_product = attack_direction.dot(to_player)
                angle = math.degrees(math.acos(max(-1, min(1, dot_product))))
            else:
                angle = 0
            if angle <= 60:
                if hasattr(self.base, 'player_hp_system'):
                    damage = self.attack_damages["combo_thrust"][hit_index + 1]
                    self.base.player_hp_system.take_damage(damage)
                    # 三連斬命中附帶暈眩 0.3 秒
                    try:
                        self.base.player_hp_system.stun(0.3)
                    except Exception:
                        pass
                    # 後續三次斬擊不造成擊退（依使用者要求）
        if hit_index < 2:
            next_state = f"combo{hit_index + 2}"
            self.combo_thrust_state = next_state
            self.base.taskMgr.doMethodLater(
                0.5,
                lambda task: self.start_combo_attack(),
                f"combo_thrust_{hit_index + 1}"
            )
        else:
            self.combo_thrust_state = "done"
            self.on_combo_thrust_complete()

    def on_combo_thrust_complete(self):
        self.combo_thrust_state = "ready"
        self.combo_thrust_direction = None
        self.combo_thrust_target_pos = None
        # reset thrust counters
        self.combo_thrust_count = 0
        self.start_attack_winddown("combo_thrust")
        self.continue_attack_cycle()

    def continue_attack_cycle(self):
        if self.is_in_attack_cycle:
            self.base.taskMgr.doMethodLater(
                self.attack_winddown_times["combo_thrust"],
                lambda task: self.execute_next_attack(),
                "continue_attack_cycle"
            )

    def start_attack_winddown(self, attack_type):
        self.attack_cooldown = self.attack_winddown_times[attack_type]
        self.is_attacking = True
        self.base.taskMgr.doMethodLater(
            self.attack_cooldown,
            lambda task: self.end_attack_winddown(),
            "end_attack_winddown"
        )

    def end_attack_winddown(self):
        self.attack_cooldown = 0
        self.is_attacking = False

    # ---------------- projectile / line spike ----------------
    def projectile_attack(self, player_pos, boss_pos):
        main_direction = (player_pos - boss_pos)
        main_direction.setZ(0)
        if main_direction.length() > 0:
            main_direction.normalize()
        angle_offsets = [-45, -30, 0, 30, 45]
        for angle_offset in angle_offsets:
            angle_rad = math.radians(angle_offset)
            cos_angle = math.cos(angle_rad)
            sin_angle = math.sin(angle_rad)
            rotated_direction = Vec3(
                main_direction.x * cos_angle - main_direction.y * sin_angle,
                main_direction.x * sin_angle + main_direction.y * cos_angle,
                0
            )
            rotated_direction.normalize()
            self.create_projectile_model(boss_pos, rotated_direction)
        self.start_attack_winddown("projectile")
        self.continue_attack_cycle_after_skill("projectile")

    def line_spike_attack(self, player_pos, boss_pos):
        self.boss["model"].setPos(self.arena_center)
        self.schedule_line_attacks(3)
        self.start_attack_winddown("line_spikes")
        self.continue_attack_cycle_after_skill("line_spikes")

    def continue_attack_cycle_after_skill(self, skill_type):
        self.base.taskMgr.doMethodLater(
            self.attack_winddown_times[skill_type],
            lambda task: self.continue_attack_cycle(),
            f"continue_after_{skill_type}"
        )

    # ---------------- phase / damage ----------------
    def check_phase_transition(self):
        if self.current_phase == 1 and self.boss_health <= 0:
            self.transition_to_phase_two()
        elif self.current_phase == 2 and self.boss_health <= 0 and not self.death_backlash_active:
            self.start_death_backlash()

    def transition_to_phase_two(self):
        self.current_phase = 2
        self.boss_health = 500
        self.max_boss_health = 500
        self.boss_move_speed = 8.0 * 0.7 * 60
        if self.boss and self.boss['model']:
            self.boss['model'].setColor(1, 0.2, 0.2, 1)
        self.update_display()

    def damage_boss(self, damage):
        if not self.boss_alive or self.death_backlash_active:
            return
        self.boss_health = max(0, self.boss_health - damage)
        if self.boss and self.boss['model']:
            self.boss['model'].setColor(1, 0.5, 0.5, 1)
            self.base.taskMgr.doMethodLater(0.2, lambda task: self.reset_boss_color(), "reset_boss_color")
        print(f"Boss受到 {damage} 點傷害！剩餘HP: {self.boss_health}")
        self.update_display()
        self.check_phase_transition()

    def reset_boss_color(self):
        if self.boss and self.boss['model']:
            if self.current_phase == 1:
                self.boss['model'].setColor(1, 1, 1, 1)
            else:
                self.boss['model'].setColor(1, 0.2, 0.2, 1)

    # ------------------ Death backlash (開始/管理水晶階段) ------------------
    def start_death_backlash(self):
        if self.death_backlash_active:
            return
        print("進入死亡回溯階段：生成水晶，保護boss最終階段")
        self.death_backlash_active = True
        self.death_backlash_timer = 0.0
        self.death_backlash_count += 1

        if self.boss and self.boss["model"]:
            self.boss["model"].setColor(0.5, 0.5, 0.8, 1)

        # 根據本次為第幾次 death_backlash 決定水晶數：第一次 5，第二次 4，... 第五次及以後為 1
        crystal_count = max(1, 6 - self.death_backlash_count)
        spawn_radius = max(120, min(250, self.arena_radius * 0.4))
        for i in range(crystal_count):
            ang = (i / crystal_count) * 360
            px = self.arena_center.x + math.cos(math.radians(ang)) * spawn_radius
            py = self.arena_center.y + math.sin(math.radians(ang)) * spawn_radius
            pos = Vec3(px, py, 5)
            self.crystal_system.create_crystal(pos, i)

        self.update_display()

    def update_death_backlash(self, dt):
        if not self.death_backlash_active:
            return
        self.death_backlash_timer += dt
        if self.death_backlash_timer >= self.death_backlash_duration:
            self.death_backlash_failed()
            return
        if self.crystal_system.check_all_crystals_destroyed():
            self.death_backlash_success()

    def death_backlash_success(self):
        self.boss_alive = False
        self.death_backlash_active = False
        if self.boss and self.boss["model"]:
            self.boss["model"].hide()
        self.crystal_system.cleanup_crystals()
        self.show_victory_message()

    def death_backlash_failed(self):
        self.death_backlash_active = False
        self.boss_health = int(self.max_boss_health * 0.6)
        self.crystal_system.cleanup_crystals()
        if self.boss and self.boss["model"]:
            self.boss["model"].setColor(1, 0.2, 0.2, 1)
        self.update_display()

    # ------------------ Spike (地刺) support functions ------------------
    def create_spike_warning(self, spike_pos):
        warning_model = self.base.loader.loadModel(self.model_paths["fallback"])
        warning_model.setScale(6, 6, 2)
        warning_model.setPos(spike_pos)
        warning_model.setColor(1, 0.6, 0.2, 0.4)
        warning_model.setTransparency(1)
        warning_model.reparentTo(self.base.render)
        warning_data = {
            "model": warning_model,
            "position": spike_pos
        }
        self.spike_warnings.append(warning_data)
        self.base.taskMgr.doMethodLater(
            0.5,
            lambda task, w=warning_data: self.activate_spike(w),
            f"activate_spike_{id(warning_data)}"
        )

    def activate_spike(self, warning_data):
        if warning_data not in self.spike_warnings:
            return
        try:
            if warning_data.get("model"):
                warning_data["model"].removeNode()
        except Exception:
            pass
        spike_model = self.base.loader.loadModel(self.model_paths["spike"])
        spike_model.setScale(6, 6, 15)
        spike_model.setPos(warning_data["position"])
        spike_model.setColor(1, 0.3, 0, 1)
        spike_model.reparentTo(self.base.render)
        self.active_spikes.append(spike_model)
        player_pos = self.base.model_butterfly.getPos()
        if (player_pos - warning_data["position"]).length() < 30:
            if hasattr(self.base, 'player_hp_system'):
                self.base.player_hp_system.take_damage(self.attack_damages["spikes"])
                print("玩家被地刺擊中！")
                # 地刺命中：平滑推開（使用改良的 apply_knockback）
                try:
                    self.apply_knockback_to_player(warning_data["position"], distance=140)
                except Exception:
                    pass
        self.base.taskMgr.doMethodLater(
            1.0,
            lambda task, m=spike_model, w=warning_data: self.remove_spike(m, w),
            f"remove_spike_{id(spike_model)}"
        )

    def remove_spike(self, spike_model, warning_data=None):
        try:
            if spike_model in self.active_spikes:
                spike_model.removeNode()
                self.active_spikes.remove(spike_model)
        except Exception:
            pass
        if warning_data and warning_data in self.spike_warnings:
            try:
                self.spike_warnings.remove(warning_data)
            except ValueError:
                pass

    def update_spikes(self, dt):
        self.spike_warnings = [w for w in self.spike_warnings if w.get("model")]

    # ------------------ Line spike / projectile helpers ------------------
    def schedule_line_attacks(self, count):
        if count <= 0:
            return
        delay = 1.0 if count == 3 else 0.8
        self.base.taskMgr.doMethodLater(
            delay,
            lambda task, c=count: self.execute_line_attack(c),
            f"line_attack_{count}"
        )

    def execute_line_attack(self, count):
        if not self.boss_alive:
            return
        player_pos = self.base.model_butterfly.getPos()
        boss_pos = self.boss["model"].getPos()
        direction = (player_pos - boss_pos)
        direction.setZ(0)
        if direction.length() > 0:
            direction.normalize()
        self.create_line_spike_warning(boss_pos, direction, 800, 40)
        if count > 1:
            self.schedule_line_attacks(count - 1)

    def create_line_spike_warning(self, start_pos, direction, length, width):
        warning_model = self.base.loader.loadModel(self.model_paths["fallback"])
        warning_model.setScale(length, width, 2)
        warning_model.setPos(start_pos)
        warning_model.lookAt(start_pos + direction)
        warning_model.setColor(1, 0, 0, 0.3)
        warning_model.reparentTo(self.base.render)
        warning_data = {
            "model": warning_model,
            "position": start_pos,
            "direction": direction,
            "length": length,
            "width": width
        }
        self.line_spike_warnings.append(warning_data)
        self.base.taskMgr.doMethodLater(
            0.3,
            lambda task, w=warning_data: self.activate_line_spike(w),
            f"activate_line_spike_{id(warning_data)}"
        )

    def activate_line_spike(self, warning_data):
        for warning in self.line_spike_warnings:
            if warning["model"] == warning_data["model"]:
                try:
                    warning["model"].removeNode()
                except Exception:
                    pass
                num_spikes = 15
                for i in range(num_spikes):
                    progress = i / (num_spikes - 1) if num_spikes > 1 else 0
                    distance = warning["length"] * (progress)
                    pos = warning["position"] + warning["direction"] * distance
                    spike_model = self.base.loader.loadModel(self.model_paths["spike"])
                    spike_model.setScale(6, 6, 15)
                    spike_model.setColor(1, 0.3, 0, 1)
                    spike_model.setPos(pos)
                    spike_model.reparentTo(self.base.render)
                    self.active_line_spikes.append(spike_model)
                self.check_line_spike_damage(warning["position"], warning["direction"], warning["length"], warning["width"])
                self.base.taskMgr.doMethodLater(
                    1.0,
                    lambda task, w=warning: self.remove_line_spike(w),
                    f"remove_line_spike_{id(warning)}"
                )
                break

    def check_line_spike_damage(self, start_pos, direction, length, width):
        player_pos = self.base.model_butterfly.getPos()
        to_player = player_pos - start_pos
        to_player.setZ(0)
        projection = to_player.dot(direction)
        perpendicular = Vec3(-direction.y, direction.x, 0)
        side_distance = abs(to_player.dot(perpendicular))
        if abs(projection) <= length and side_distance <= width:
            if hasattr(self.base, 'player_hp_system'):
                self.base.player_hp_system.take_damage(self.attack_damages["line_spikes"])
                print("玩家被連線地刺擊中！")
                # 線性地刺命中：平滑推開
                try:
                    hit_point = start_pos + direction * projection
                    self.apply_knockback_to_player(hit_point, distance=160)
                except Exception:
                    pass

    def remove_line_spike(self, warning_data):
        for spike in self.active_line_spikes[:]:
            try:
                spike.removeNode()
            except Exception:
                pass
            self.active_line_spikes.remove(spike)
        if warning_data in self.line_spike_warnings:
            self.line_spike_warnings.remove(warning_data)

    def update_line_spikes(self, dt):
        self.line_spike_warnings = [w for w in self.line_spike_warnings if w["model"]]

    # ------------------ Minions / summons ------------------
    def summon_minions(self):
        # 改為在階段一、二時召喚五隻 archer（不額外召 basic）
        player_pos = self.base.model_butterfly.getPos()
        spawned = 0
        for i in range(5):
            angle = random.uniform(0, 360)
            distance = random.uniform(150, 300)
            x = player_pos.x + math.cos(math.radians(angle)) * distance
            y = player_pos.y + math.sin(math.radians(angle)) * distance
            pos = Vec3(x, y, 5)
            if (pos - self.arena_center).length() < self.arena_radius - 50:
                self.enemy_system.create_enemy(pos, "archer", "boss_minion")
                spawned += 1
        # optional: log spawn
        if spawned > 0:
            print(f"召喚了 {spawned} 隻弓箭手作為小怪支援！")

    # ------------------ HUD / cleanup ------------------
    def update_display(self):
        if self.boss_health_text:
            if self.death_backlash_active:
                time_left = self.death_backlash_duration - self.death_backlash_timer
                crystals_alive, total_crystals = self.crystal_system.get_crystal_status()
                self.boss_health_text.setText(f"死亡回溯: {time_left:.1f}s | 水晶: {crystals_alive}/{total_crystals}")
            else:
                self.boss_health_text.setText(f"BOSS HP: {self.boss_health}/{self.max_boss_health}")
        if self.phase_text:
            if self.death_backlash_active:
                self.phase_text.setText(f"死亡回溯 ({self.death_backlash_count})")
            else:
                self.phase_text.setText(f"PHASE {self.current_phase}")

        # 若有 floating UI，順便更新 boss bar（百分比）
        try:
            if hasattr(self.base, 'floating_ui') and self.base.floating_ui:
                if self.max_boss_health > 0 and self.boss_alive:
                    percent = max(0.0, min(1.0, float(self.boss_health) / float(self.max_boss_health)))
                    self.base.floating_ui.show_boss_bar(percent)
                else:
                    self.base.floating_ui.hide_boss_bar()
        except Exception:
            pass

    def show_victory_message(self):
        victory_text = OnscreenText(
            text="VICTORY! Boss Defeated!",
            pos=(0, 0),
            scale=0.1,
            fg=(0, 1, 0, 1),
            align=TextNode.ACenter,
            mayChange=False
        )
        self.base.taskMgr.doMethodLater(3.0, lambda task: victory_text.destroy(), "remove_victory_text")

    def update(self, dt):
        if self.boss_alive:
            self.update_boss_behavior(dt)
        self.crystal_system.update(dt)

    def check_crystal_hit(self, attacker_pos, attack_range=80):
        return self.crystal_system.check_crystal_hit(attacker_pos, attack_range)

    def cleanup(self):
        if self.boss and self.boss["model"]:
            self.boss["model"].removeNode()
        for warning in self.spike_warnings:
            if warning.get("model"):
                try: warning["model"].removeNode()
                except Exception: pass
        self.spike_warnings.clear()
        for spike in self.active_spikes:
            if spike:
                try: spike.removeNode()
                except Exception: pass
        self.active_spikes.clear()
        for warning in self.line_spike_warnings:
            if warning.get("model"):
                try: warning["model"].removeNode()
                except Exception: pass
        self.line_spike_warnings.clear()
        for spike in self.active_line_spikes:
            if spike:
                try: spike.removeNode()
                except Exception: pass
        self.active_line_spikes.clear()
        for projectile in self.active_projectiles:
            if projectile.get("model"):
                try: projectile["model"].removeNode()
                except Exception: pass
        self.active_projectiles.clear()
        self.crystal_system.cleanup_crystals()
        if self.boss_health_text:
            self.boss_health_text.destroy()
        if self.phase_text:
            self.phase_text.destroy()
        for t in ["line_attack_", "activate_spike_", "activate_line_spike_", "remove_spike_", "remove_line_spike_"]:
            try:
                self.base.taskMgr.remove(f"{t}*")
            except Exception:
                pass
        try:
            self.base.taskMgr.remove("reset_boss_color")
        except Exception:
            pass
        # also remove possible knockback task
        try:
            self.base.taskMgr.remove(self._knockback_task_name)
        except Exception:
            pass
        print("Boss系統資源清理完成")

    # ------------------ Helpers: knockback (smooth) ------------------
    def apply_knockback_to_player(self, source_pos, distance=120, direction=None, duration=None):
        """
        平滑擊退（以插值移動玩家）：
        - distance：原始建議距離，會被減少 60%（實際距離 = distance * 0.4）
        - direction：可選 normalized Vec3，若提供會使用該方向（從 source -> player 為預設）
        - duration：可選持續時間（秒），若 None 則根據距離自訂一個合理值
        實作細節：
        - 以 base.taskMgr 新增一個任務做平滑插值（線性）
        - 若已有正在進行的擊退任務，會先移除舊任務（避免重疊）
        """
        try:
            player = self.base.model_butterfly
            if player is None:
                return
            player_pos = player.getPos()
            # 使用減少 60% 的規則：保留 40% 的距離
            actual_distance = distance * 0.4

            # 計算方向向量
            if direction is None:
                dir_vec = player_pos - source_pos
                dir_vec.setZ(0)
                if dir_vec.length() == 0:
                    dir_vec = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), 0)
                dir_vec.normalize()
            else:
                dir_vec = Vec3(direction)
                dir_vec.setZ(0)
                if dir_vec.length() == 0:
                    dir_vec = Vec3(0, 1, 0)
                else:
                    dir_vec.normalize()

            # 目標位置（嘗試 clamp 到 arena）
            target = player_pos + dir_vec * actual_distance
            margin = 10.0
            if hasattr(self, "arena_center") and hasattr(self, "arena_radius") and self.arena_center and self.arena_radius:
                from_center = (target - self.arena_center).length()
                max_allowed = max(0.0, self.arena_radius - margin)
                if from_center > max_allowed:
                    target = self.arena_center + dir_vec * max_allowed

            # 決定 z（使用 ground_system 以求合理高度）
            ground_z = None
            try:
                if self.ground_system and hasattr(self.ground_system, "get_ground_height"):
                    ground_z = self.ground_system.get_ground_height(target.x, target.y)
            except Exception:
                ground_z = None
            if ground_z is None:
                ground_z = target.z if target.z is not None else 5.0
            target.z = ground_z

            # prepare smooth task
            # duration default: 0.25..0.5s depending on distance (keep it snappy)
            if duration is None:
                # scale duration with actual_distance; clamp to [0.12, 0.6]
                duration = max(0.12, min(0.6, actual_distance / 360.0 + 0.12))

            # remove any existing knockback task
            try:
                self.base.taskMgr.remove(self._knockback_task_name)
            except Exception:
                pass

            start = player_pos
            start_time = self.base.globalClock.getFrameTime()

            def knockback_task(task):
                try:
                    now = self.base.globalClock.getFrameTime()
                    t = (now - start_time) / duration
                    if t >= 1.0:
                        # finalize
                        try:
                            player.setPos(target)
                        except Exception:
                            pass
                        return task.done
                    # linear interpolation
                    interp = start + (target - start) * t
                    try:
                        player.setPos(interp)
                    except Exception:
                        pass
                    return task.cont
                except Exception:
                    return task.done

            # register task
            try:
                self.base.taskMgr.add(knockback_task, self._knockback_task_name)
            except Exception:
                # fallback: instant set if task registration fails
                try:
                    player.setPos(target)
                except Exception:
                    pass
        except Exception:
            # silent fail to avoid crashing game logic
            return