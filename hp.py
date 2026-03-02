# hp.py 
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, Point3

class PlayerHPSystem:
    def __init__(self, base, max_health=400):
        self.base = base
        self.max_health = max_health
        self.current_health = max_health
        self.is_invulnerable = False
        self.invulnerability_duration = 1.0
        self.last_damage_time = 0.0

        # 月光系統
        self.moonlight = 50
        self.skillmoon = "full"

        # 狀態效果
        self._stunned = False
        self._slow_ratio = 1.0
        self._stun_task_name = "player_end_stun"
        self._slow_task_name = "player_end_slow"

        # UI 元素 / Textures (may be None)
        self.hp_bg_texture = None
        self.hp_red_texture = None
        self.hp_yellow_texture = None
        self.hp_green_texture = None
        self.moon_new_texture = None
        self.moon_crescent_texture = None
        self.moon_quarter_texture = None
        self.moon_gibbous_texture = None
        self.moon_full_texture = None

        self.hp_background = None
        self.hp_foreground = None
        self.moon_icon = None
        self.hp_text = None
        self.moonlight_text = None
        self.objective_text = None
        self.skill_text = None
        self.position_text = None

        # 嘗試載入貼圖（容錯）
        self._try_load_textures()

        # 初始化 UI
        self.setup_ui_display()

    def _try_load_textures(self):
        try:
            self.hp_bg_texture = self.base.loader.loadTexture("model/ui/hp/hp_bar_bg.png")
        except Exception:
            self.hp_bg_texture = None
        try:
            self.hp_red_texture = self.base.loader.loadTexture("model/ui/hp/hp_bar_fg_red.png")
        except Exception:
            self.hp_red_texture = None
        try:
            self.hp_yellow_texture = self.base.loader.loadTexture("model/ui/hp/hp_bar_fg_yellow.png")
        except Exception:
            self.hp_yellow_texture = None
        try:
            self.hp_green_texture = self.base.loader.loadTexture("model/ui/hp/hp_bar_fg_green.png")
        except Exception:
            self.hp_green_texture = None
        try:
            self.moon_new_texture = self.base.loader.loadTexture("model/ui/moon/moon_new.png")
        except Exception:
            self.moon_new_texture = None
        try:
            self.moon_crescent_texture = self.base.loader.loadTexture("model/ui/moon/moon_crescent.png")
        except Exception:
            self.moon_crescent_texture = None
        try:
            self.moon_quarter_texture = self.base.loader.loadTexture("model/ui/moon/moon_quarter.png")
        except Exception:
            self.moon_quarter_texture = None
        try:
            self.moon_gibbous_texture = self.base.loader.loadTexture("model/ui/moon/moon_gibbous.png")
        except Exception:
            self.moon_gibbous_texture = None
        try:
            self.moon_full_texture = self.base.loader.loadTexture("model/ui/moon/moon_full.png")
        except Exception:
            self.moon_full_texture = None

    def setup_ui_display(self):
        # If textures loaded, create image UI; otherwise create text UI
        if self.hp_bg_texture and self.hp_red_texture and self.moon_new_texture:
            self.create_image_ui()
        else:
            self.create_text_ui()

        # common texts
        try:
            self.objective_text = OnscreenText(
                text="Explore and clear regions",
                pos=(1.0, 0.9),
                scale=0.04,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True
            )
            self.skill_text = OnscreenText(
                text=self.get_skill_text(),
                pos=(1.0, -0.8),
                scale=0.1,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True
            )
            self.position_text = OnscreenText(
                text=self.get_position_text(),
                pos=(-1.0, 0.9),
                scale=0.04,
                fg=(1, 1, 1, 1),
                align=TextNode.ALeft,
                mayChange=True
            )
        except Exception:
            pass

    def create_image_ui(self):
        try:
            self.hp_background = OnscreenImage(image=self.hp_bg_texture, pos=(0, 0, -0.8), scale=(0.3, 1, 0.03))
            self.hp_foreground = OnscreenImage(image=self.hp_red_texture, pos=(0, 0, -0.8), scale=(0.3, 1, 0.025))
            self.moon_icon = OnscreenImage(image=self.get_moon_texture(), pos=(-1.3, 0, -0.7), scale=(0.18, 3, 0.18))
            self.moonlight_text = OnscreenText(text=f"{self.moonlight}/100", pos=(-1.2, -0.75), scale=0.04,
                                               fg=(1,1,1,1), align=TextNode.ALeft, mayChange=True)
            self.hp_text = OnscreenText(text=f"{self.current_health}/{self.max_health}", pos=(0, -0.85),
                                       scale=0.04, fg=(1,1,1,1), align=TextNode.ACenter, mayChange=True)
        except Exception:
            # fallback
            self.create_text_ui()

    def create_text_ui(self):
        try:
            self.hp_text = OnscreenText(text=self.get_hp_bar_text(), pos=(0, -0.8), scale=0.05,
                                        fg=(1,1,1,1), align=TextNode.ACenter, mayChange=True)
            self.moonlight_text = OnscreenText(text=self.get_moonlight_text(), pos=(-1.3, -0.7), scale=0.04,
                                               fg=(0.7,0.7,1,1), align=TextNode.ALeft, mayChange=True)
        except Exception:
            pass

    # ---------- Helpers for moon / HUD ----------
    def get_moon_texture(self):
        if self.moonlight <= 20:
            return self.moon_new_texture
        elif self.moonlight <= 40:
            return self.moon_crescent_texture
        elif self.moonlight <= 60:
            return self.moon_quarter_texture
        elif self.moonlight <= 80:
            return self.moon_gibbous_texture
        else:
            return self.moon_full_texture

    def get_hp_bar_text(self):
        bar_length = 20
        if self.max_health <= 0:
            return f"[{'?'*bar_length}] 0/0"
        filled = int((self.current_health / self.max_health) * bar_length)
        filled = max(0, min(bar_length, filled))
        empty = bar_length - filled
        bar = "[" + "█" * filled + "░" * empty + "]"
        return f"{bar} {self.current_health}/{self.max_health}"

    def get_moonlight_text(self):
        if self.moonlight <= 20:
            icon = "🌑"
        elif self.moonlight <= 40:
            icon = "🌒"
        elif self.moonlight <= 60:
            icon = "🌓"
        elif self.moonlight <= 80:
            icon = "🌔"
        else:
            icon = "🌕"
        return f"{icon} {self.moonlight}/100"

    def get_skill_text(self):
        current_time = self.base.globalClock.getFrameTime()
        q_status = "READY"
        if hasattr(self.base, 'q_cd') and current_time < getattr(self.base, 'q_cd', 0):
            q_time = self.base.q_cd - current_time
            q_status = f"{q_time:.1f}s"
        e_status = "READY"
        if hasattr(self.base, 'e_cd') and current_time < getattr(self.base, 'e_cd', 0):
            e_time = self.base.e_cd - current_time
            e_status = f"{e_time:.1f}s"
        e_effect = ""
        if hasattr(self.base, 'force_e') and getattr(self.base, 'force_e', 0) == 1:
            e_effect = " [強化]"
        return f"Q: {q_status}\nE: {e_status}{e_effect}"

    def get_position_text(self):
        if hasattr(self.base, 'model_butterfly'):
            pos = self.base.model_butterfly.getPos()
            scene_name = getattr(self.base, 'current_scene', 'UNKNOWN').upper()
            return f"{scene_name} - Pos: ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})"
        return "Position: (0.0, 0.0, 0.0)"

    # ---------- State API ----------
    def is_stunned(self):
        return self._stunned

    def get_slow_ratio(self):
        return self._slow_ratio

    def stun(self, duration):
        if duration <= 0:
            return
        self._stunned = True
        try:
            self.base.taskMgr.remove(self._stun_task_name)
        except Exception:
            pass
        def end_stun(task):
            self._stunned = False
            return task.done
        try:
            self.base.taskMgr.doMethodLater(duration, end_stun, self._stun_task_name)
        except Exception:
            pass

    def apply_slow(self, ratio, duration):
        if ratio <= 0:
            ratio = 0.01
        self._slow_ratio = ratio
        try:
            self.base.taskMgr.remove(self._slow_task_name)
        except Exception:
            pass
        if duration > 0:
            def end_slow(task):
                self._slow_ratio = 1.0
                return task.done
            try:
                self.base.taskMgr.doMethodLater(duration, end_slow, self._slow_task_name)
            except Exception:
                pass

    # ---------- Update / damage / heal ----------
    def update_display(self, dt=0):
        try:
            if self.hp_foreground is not None:
                hp_ratio = max(0.0, min(1.0, self.current_health / max(1.0, self.max_health)))
                self.hp_foreground.setScale(0.3 * hp_ratio, 1, 0.025)
                # choose texture if possible
                try:
                    if hp_ratio > 0.7 and self.hp_red_texture:
                        self.hp_foreground.setImage(self.hp_red_texture)
                    elif hp_ratio > 0.3 and self.hp_yellow_texture:
                        self.hp_foreground.setImage(self.hp_yellow_texture)
                    elif self.hp_green_texture:
                        self.hp_foreground.setImage(self.hp_green_texture)
                except Exception:
                    pass
                try:
                    if self.moon_icon:
                        self.moon_icon.setImage(self.get_moon_texture())
                except Exception:
                    pass
        except Exception:
            pass

        if self.hp_text is not None:
            if self.hp_foreground is None:
                try:
                    self.hp_text.setText(self.get_hp_bar_text())
                    self.moonlight_text.setText(self.get_moonlight_text())
                except Exception:
                    pass
            else:
                try:
                    self.hp_text.setText(f"{self.current_health}/{self.max_health}")
                    self.moonlight_text.setText(f"{self.moonlight}/100，{self.skillmoon}")
                except Exception:
                    pass

        if self.skill_text is not None:
            try:
                self.skill_text.setText(self.get_skill_text())
            except Exception:
                pass
        if self.position_text is not None:
            try:
                self.position_text.setText(self.get_position_text())
            except Exception:
                pass

    def update_moonlight(self, moonlight, skillmoon):
        self.moonlight = max(0, min(100, int(moonlight)))
        self.skillmoon = skillmoon
        self.update_display()

    def take_damage(self, damage):
        current_time = self.base.globalClock.getFrameTime()
        if self.is_invulnerable and (current_time - self.last_damage_time) < self.invulnerability_duration:
            return False
        self.current_health = max(0, int(self.current_health - damage))
        self.last_damage_time = current_time
        self.is_invulnerable = True
        print(f"玩家受到 {damage} 點傷害！剩餘HP: {self.current_health}")
        self.update_display()
        try:
            self.apply_damage_effect()
            self.base.taskMgr.doMethodLater(self.invulnerability_duration, self.end_invulnerability, "end_invulnerability")
        except Exception:
            pass
        if self.current_health <= 0:
            self.die()
        return True

    def apply_damage_effect(self):
        if hasattr(self.base, 'model_butterfly'):
            self.start_flashing_effect()

    def start_flashing_effect(self):
        self.flash_count = 0
        try:
            self.base.taskMgr.add(self.flashing_task, "flashing_task")
        except Exception:
            pass

    def flashing_task(self, task):
        try:
            if self.flash_count >= 6:
                self.base.model_butterfly.setColor(1, 1, 1, 1)
                return task.done
            if self.flash_count % 2 == 0:
                self.base.model_butterfly.setColor(1, 0.5, 0.5, 0.7)
            else:
                self.base.model_butterfly.setColor(1, 1, 1, 1)
            self.flash_count += 1
        except Exception:
            return task.done
        return task.cont

    def end_invulnerability(self, task):
        self.is_invulnerable = False
        return task.done

    def heal(self, amount):
        self.current_health = min(self.max_health, int(self.current_health + amount))
        print(f"玩家恢復 {amount} 點HP！當前HP: {self.current_health}")
        self.update_display()

    def die(self):
        print("玩家死亡！")
        try:
            if hasattr(self.base, 'model_butterfly'):
                self.base.model_butterfly.setColor(0.5, 0.5, 0.5, 1)
        except Exception:
            pass
        try:
            self.base.taskMgr.doMethodLater(3.0, self.game_over, "game_over")
        except Exception:
            pass

    def game_over(self, task):
        defeat_text = OnscreenText(
            text="you have been Defeated!",
            pos=(0, 0),
            scale=0.1,
            fg=(1, 0, 0, 1),
            align=TextNode.ACenter,
            mayChange=False
        )
        self.base.taskMgr.doMethodLater(3.0, lambda task: defeat_text.destroy(), "remove_victory_text")
        print("遊戲結束")
        return task.done

    def reset(self):
        print("reset")
        self.current_health = self.max_health
        self.is_invulnerable = False
        self.moonlight = 50
        self.skillmoon = "full"
        self._stunned = False
        self._slow_ratio = 1.0
        self.update_display()
        try:
            if hasattr(self.base, 'model_butterfly'):
                self.base.model_butterfly.setColor(1, 1, 1, 1)
        except Exception:
            pass