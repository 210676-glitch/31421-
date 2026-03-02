from panda3d.core import loadPrcFile, Vec3, ClockObject, AmbientLight, DirectionalLight, Vec4
from direct.showbase.ShowBase import ShowBase
import butterfly, skill, ground, enemy
from hp import PlayerHPSystem
import area1, area2, boss
from floating_ui import FloatingUISystem

loadPrcFile("config/config.prc")

class Mygo(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

        self.current_scene = "area1"
        self.area1_system = None
        self.area2_system = None
        self.boss_system = None
        self.crystal_system = None

        self.camera_distance = 60
        self.camera_height = 36
        self.move_speed = 420.0

        self.globalClock = ClockObject.getGlobalClock()
        self.globalClock.setMode(ClockObject.MLimited)
        self.globalClock.setFrameRate(60)

        self.accept("window-event", self.on_window_event)

        self.final_scene = self.loader.loadModel("model/background/楓丹.egg")
        self.final_scene.setScale(20)
        self.final_scene.reparentTo(self.render)
        self.final_scene.hide()

        self.model_dragon = butterfly.dragon_box(self)
        self.model_butterfly = butterfly.butterfly_box_simple(self)
        self.taskMgr.add(self.camera_move, "WeaponMoveTask")

        self.player_hp_system = PlayerHPSystem(self)
        self.q_cd = 0
        self.e_cd = 0
        self.force_e = 0
        self.normal_cd = 0
        self.skillmoon = "full"
        self.moonlight = 40
        self.player_hp_system.update_moonlight(self.moonlight, self.skillmoon)

        self.setup_simple_ground_system()
        self.enemy_system = enemy.EnemySystem(self, self.ground_system)
        self.attack_system = enemy.AttackSystem()
        self.floating_ui = FloatingUISystem(self)
        self.area1_system = area1.Area1System(self, self.ground_system, self.enemy_system)

        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor(Vec4(0.5, 0.5, 0.5, 1))
        ambientNode = self.render.attachNewNode(ambientLight)
        self.render.setLight(ambientNode)

        dirLight = DirectionalLight("dirLight")
        dirLight.setColor(Vec4(0.8, 0.8, 0.8, 1))
        dirNode = self.render.attachNewNode(dirLight)
        dirNode.setHpr(45, -45, 0)
        self.render.setLight(dirNode)

        self.disableMouse()
        self.camera.setPos(0, 30, 30)

        self.key_map = {k: False for k in ["w","a","s","d","q","e","space","m","mouse1","f","o","r","t"]}
        for key in self.key_map:
            self.accept(key, self.apply_key, [key, True])
            self.accept(key+"-up", self.apply_key, [key, False])
        self.accept("mouse1", self.mouse_skill_trigger)

        self.taskMgr.add(self.apply_camera, "UpdateCameraTask")
        self.taskMgr.add(self.apply_virtual, "UpdateVirtual")
        self.taskMgr.add(self.q_state, "UpdateDragonTask")
        self.taskMgr.add(self.apply_gravity_wrapper, "GravityTask")
        self.taskMgr.add(self.update_enemies, "UpdateEnemiesTask")
        self.taskMgr.add(self.update_area_system, "UpdateAreaSystemTask")
        self.taskMgr.add(self.check_ground_system_switch, "CheckGroundSystemSwitch")
        self.taskMgr.add(self.update_ui_display, "UpdateUITask")

    def setup_simple_ground_system(self):
        class SimpleGroundSystem:
            def __init__(self):
                self.gravity = -140.0
                self.vertical_velocity = 0
                self.is_grounded = True
                self.jump_power = 108.0
            def get_ground_height(self, x, y):
                return 5.0
            def apply_gravity(self, model_butterfly, dt):
                pos = model_butterfly.getPos()
                if self.is_grounded:
                    pos.z = 5
                    self.vertical_velocity = 0
                else:
                    self.vertical_velocity += self.gravity * dt
                    pos.z += self.vertical_velocity * dt
                    if pos.z <= 5:
                        pos.z = 5
                        self.vertical_velocity = 0
                        self.is_grounded = True
                model_butterfly.setPos(pos)
                return self.is_grounded, self.vertical_velocity
            def jump(self):
                if self.is_grounded:
                    self.vertical_velocity = self.jump_power
                    self.is_grounded = False
                return self.is_grounded
        self.ground_system = SimpleGroundSystem()
        self.current_ground_type = "simple"

    def apply_virtual(self, task):
        mouse_x = self.mouseWatcherNode.getMouseX()
        mouse_y = self.mouseWatcherNode.getMouseY()
        self.camera.setHpr(self.camera.getHpr() + Vec3(-mouse_x*10, mouse_y*10, 0))
        
        if any(self.key_map.get(k) for k in ["w","a","s","d"]):
            hpr = self.camera.getHpr()
            self.model_butterfly.setHpr(hpr + Vec3(0, 90, 90))
        return task.cont

    def apply_key(self, key, value):
        self.key_map[key] = value
        if key == "space" and value:
            self.ground_system.jump()
        if key == "f" and value:
            self.area1_system.interact_with_portal() if self.current_scene == "area1" else None
        if key == "o" and value:
            if self.current_scene == "area1":
                self.area1_system.cheat(self.model_butterfly.getPos())
        if key == "q" and value:
            self.q_cd, self.e_cd, self.force_e, self.moonlight, self.skillmoon, recover, self.normal_cd = skill.skill(
                self, self.q_cd, self.e_cd, "q", self.force_e, self.enemy_system, self.moonlight, self.skillmoon, self.normal_cd
            )
            if recover > 0:
                self.player_hp_system.heal(recover)
        if key == "e" and value:
            self.q_cd, self.e_cd, self.force_e, self.moonlight, self.skillmoon, recover, self.normal_cd = skill.skill(
                self, self.q_cd, self.e_cd, "e", self.force_e, self.enemy_system, self.moonlight, self.skillmoon, self.normal_cd
            )
            if recover > 0:
                self.player_hp_system.heal(recover)
        if key == "t" and value:
            self.test_boss_skills()

    def apply_camera(self, task):
        dt = min(self.globalClock.getDt(), 0.016)
        if self.player_hp_system.is_stunned():
            return task.cont
        
        forward = self.camera.getQuat().getForward()
        right = self.camera.getQuat().getRight()
        move_vec = Vec3()
        if self.key_map["w"]: move_vec += forward
        if self.key_map["s"]: move_vec -= forward
        if self.key_map["a"]: move_vec -= right
        if self.key_map["d"]: move_vec += right
        move_vec.setZ(0)
        
        if move_vec.length() > 0:
            move_vec.normalize()
            speed_mod = self.player_hp_system.get_slow_ratio()
            move_vec *= self.move_speed * dt * speed_mod
        
        new_pos = self.model_butterfly.getPos() + move_vec
        
        if self.current_scene == "area1":
            new_pos = self.area1_system.restrict_player_movement(new_pos)
        elif self.current_scene == "area2":
            new_pos = self.area2_system.restrict_player_movement(new_pos)
        
        self.model_butterfly.setPos(new_pos)
        return task.cont

    def camera_move(self, task):
        butterfly_pos = self.model_butterfly.getPos()
        backward = -self.camera.getQuat().getForward()
        target = butterfly_pos + backward * self.camera_distance
        target.z = butterfly_pos.z + self.camera_height
        current = self.camera.getPos()
        self.camera.setPos(current + (target - current) * 0.3)
        return task.cont

    def q_state(self, task):
        if self.q_cd - 5 <= self.globalClock.getFrameTime():
            if self.skillmoon == "double":
                self.skillmoon = "full"
            self.force_e = 0
        return task.cont

    def mouse_skill_trigger(self):
        self.q_cd, self.e_cd, self.force_e, self.moonlight, self.skillmoon, recover, self.normal_cd = skill.skill(
            self, self.q_cd, self.e_cd, "mouse1", self.force_e, self.enemy_system, self.moonlight, self.skillmoon, self.normal_cd
        )
        if recover > 0:
            self.player_hp_system.heal(recover)

    def update_enemies(self, task):
        dt = min(self.globalClock.getDt(), 0.016)
        player_pos = self.model_butterfly.getPos()
        self.enemy_system.update_basic_enemies(player_pos, dt)
        boss_model = self.boss_system.boss["model"] if self.boss_system and self.boss_system.boss_alive else None
        self.floating_ui.update(dt, self.enemy_system.enemies, boss_model)
        return task.cont

    def update_ui_display(self, task):
        dt = min(self.globalClock.getDt(), 0.016)
        self.player_hp_system.update_display(dt)
        self.player_hp_system.update_moonlight(self.moonlight, self.skillmoon)
        return task.cont

    def update_area_system(self, task):
        dt = min(self.globalClock.getDt(), 0.016)
        if self.current_scene == "area1" and self.area1_system:
            self.area1_system.update(dt)
        elif self.current_scene == "area2" and self.area2_system:
            self.area2_system.update(dt)
        if self.boss_system:
            self.boss_system.update(dt)
        return task.cont

    def on_window_event(self, window):
        if window is None:
            self.cleanup()
            self.userExit()

    def cleanup(self):
        if self.area1_system: self.area1_system.cleanup()
        if self.area2_system: self.area2_system.cleanup()
        if self.boss_system: self.boss_system.cleanup()
        if self.enemy_system: self.enemy_system.cleanup()
        tasks = ["UpdateCameraTask","UpdateVirtual","GravityTask","WeaponMoveTask",
                 "UpdateEnemiesTask","UpdateAreaSystemTask","CheckGroundSystemSwitch","UpdateUITask","UpdateDragonTask"]
        for t in tasks:
            self.taskMgr.remove(t)
        self.model_butterfly.removeNode()
        self.model_dragon.removeNode()

    def check_ground_system_switch(self, task):
        if self.area1_system.boss_stage_loaded and self.current_ground_type == "simple":
            self.setup_fontaine_ground_system()
            self.enemy_system.ground_system = self.ground_system
        return task.cont

    def apply_gravity_wrapper(self, task):
        dt = min(self.globalClock.getDt(), 0.016)
        self.ground_system.apply_gravity(self.model_butterfly, dt)
        return task.cont

    def setup_fontaine_ground_system(self):
        self.ground_system = ground.GroundSystem()
        self.current_ground_type = "fontaine"
        self.model_butterfly.setPos(0, 120, 5)
        self.ground_system.create_portal(self)

    def setup_area2_ground_system(self):
        class Area2GroundSystem:
            def __init__(self, area2_system):
                self.area2_system = area2_system
                self.gravity = -140.0
                self.vertical_velocity = 0
                self.is_grounded = True
                self.jump_power = 108.0
            def get_ground_height(self, x, y):
                return 5.0
            def apply_gravity(self, model_butterfly, dt):
                pos = model_butterfly.getPos()
                if self.is_grounded:
                    pos.z = 5
                    self.vertical_velocity = 0
                else:
                    self.vertical_velocity += self.gravity * dt
                    pos.z += self.vertical_velocity * dt
                    if pos.z <= 5:
                        pos.z = 5
                        self.vertical_velocity = 0
                        self.is_grounded = True
                pos = self.area2_system.restrict_player_movement(pos)
                model_butterfly.setPos(pos)
                return self.is_grounded, self.vertical_velocity
            def jump(self):
                if self.is_grounded:
                    self.vertical_velocity = self.jump_power
                    self.is_grounded = False
                return self.is_grounded
        self.ground_system = Area2GroundSystem(self.area2_system)
        self.current_ground_type = "area2"

    def interact_with_portal(self):
        if self.current_scene == "fontaine" and self.ground_system.is_player_near_portal(self.model_butterfly.getPos()):
            self.load_area2_scene()

    def load_fontaine_scene(self):
        self.current_scene = "fontaine"
        if self.area1_system: self.area1_system.hide_scene()
        if self.area2_system: self.area2_system.hide_scene()
        if self.boss_system: self.boss_system.cleanup()
        self.final_scene.show()
        self.setup_fontaine_ground_system()
        self.ground_system.show_portal()
        self.model_butterfly.setPos(0, 120, 5)

    def load_area2_scene(self):
        self.current_scene = "area2"
        if self.area1_system: self.area1_system.hide_scene()
        self.final_scene.hide()
        if self.ground_system: self.ground_system.hide_portal()
        if not self.area2_system:
            self.area2_system = area2.Area2System(self, self.ground_system, self.enemy_system)
        self.area2_system.show_scene()
        self.setup_area2_ground_system()
        self.area2_system.set_player_start_position()
        arena_info = self.area2_system.get_arena_info()
        self.boss_system = boss.BossSystem(self, self.ground_system, self.enemy_system, arena_info['center'], arena_info['radius'])
        self.crystal_system = self.boss_system.crystal_system

if __name__ == "__main__":
    game = Mygo()
    game.run()