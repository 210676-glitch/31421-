from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import TextNode, Vec3, Point3

class FloatingUISystem:
    """管理傷害浮字、敵人/BOSS血條、目標鎖定UI（容錯與投影）"""
    def __init__(self, base):
        self.base = base
        self.active_texts = []      # list of {text, pos(Vec3), timer, duration}
        self.hp_bars = {}          # id(model) -> (fg, bg)
        self.boss_hp_bar = None
        self.lockon_icon = None

        # 資源路徑（可缺省）
        self.enemy_bar_fg = "model/ui/hp/enemy_bar_fg.png"
        self.enemy_bar_bg = "model/ui/hp/enemy_bar_bg.png"
        self.boss_bar_fg = "model/ui/hp/boss_bar_fg.png"
        self.boss_bar_bg = "model/ui/hp/boss_bar_bg.png"
        self.lockon_img  = "model/ui/lockon.png"

    # ---------- Helpers ----------
    def _project_to_screen(self, world_pos):
        """
        Project world_pos (Point3/Vec3) to normalized screen coords (-1..1).
        Returns (x, y) or None if not on screen / failure.
        """
        try:
            # convert to camera space
            cam_space = self.base.cam.getRelativePoint(self.base.render, Point3(world_pos))
            lens = self.base.cam.node().getLens()
            # lens.project may return a Point2 or (ok, Point2) depending on wrapper
            try:
                proj = lens.project(cam_space)
                # proj could be tuple (ok, pt) or a Point2-like object
                if isinstance(proj, tuple):
                    ok, pt = proj
                    if not ok:
                        return None
                    return (pt.x, pt.y)
                else:
                    return (proj.x, proj.y)
            except Exception:
                # fallback using projectPoint if available
                try:
                    pt2 = lens.projectPoint(cam_space)
                    return (pt2.x, pt2.y)
                except Exception:
                    return None
        except Exception:
            return None

    # ---------- Floating text ----------
    def spawn_floating_text(self, world_pos, value, color=(1,0.2,0.1,1), duration=0.9):
        try:
            text = OnscreenText(str(value), fg=color, pos=(0,0), scale=0.07,
                                align=TextNode.ACenter, mayChange=True)
        except Exception:
            # fallback silent
            return
        self.active_texts.append({'text': text, 'pos': Vec3(world_pos), 'timer': 0.0, 'duration': duration})

    # ---------- Enemy HP bars ----------
    def show_enemy_hp_bar(self, model, percent):
        key = id(model)
        if key not in self.hp_bars:
            try:
                bg = OnscreenImage(image=self.enemy_bar_bg, pos=(0, 0, 0), scale=(0.10, 1, 0.016))
                fg = OnscreenImage(image=self.enemy_bar_fg, pos=(0, 0, 0), scale=(0.10, 1, 0.011))
                for bar in (bg, fg):
                    try: bar.setTransparency(1)
                    except Exception: pass
            except Exception:
                # fallback to text
                fg = OnscreenText("", pos=(0,0), scale=0.04, mayChange=True)
                bg = fg
            self.hp_bars[key] = (fg, bg)
        fg, bg = self.hp_bars[key]
        try:
            # scale X is width: multiply by percent
            fg.setScale(0.10 * max(percent, 0.01), 1, 0.011)
            fg.show(); bg.show()
        except Exception:
            pass
        return fg, bg

    def hide_enemy_hp_bar(self, model):
        key = id(model)
        if key in self.hp_bars:
            fg, bg = self.hp_bars[key]
            try:
                fg.hide(); bg.hide()
            except Exception:
                pass

    def remove_enemy_hp_bar(self, model):
        key = id(model)
        if key in self.hp_bars:
            fg, bg = self.hp_bars.pop(key)
            try:
                fg.destroy(); bg.destroy()
            except Exception:
                pass

    # ---------- Lockon ----------
    def set_lockon(self, model):
        self.clear_lockon()
        try:
            icon = OnscreenImage(image=self.lockon_img, pos=(0,0,0), scale=(0.12,1,0.045))
            try: icon.setTransparency(1)
            except Exception: pass
            icon._target = model
            self.lockon_icon = icon
        except Exception:
            try:
                txt = OnscreenText("LOCK", fg=(1,1,0,1), pos=(0,0), scale=0.06, mayChange=True)
                txt._target = model
                self.lockon_icon = txt
            except Exception:
                self.lockon_icon = None

    def clear_lockon(self):
        if self.lockon_icon:
            try: self.lockon_icon.destroy()
            except Exception: pass
            self.lockon_icon = None

    # ---------- Boss bar ----------
    def show_boss_bar(self, percent):
        if not self.boss_hp_bar:
            try:
                bg = OnscreenImage(image=self.boss_bar_bg, pos=(0, 0, 0.94), scale=(0.65, 1, 0.042))
                fg = OnscreenImage(image=self.boss_bar_fg, pos=(0, 0, 0.94), scale=(0.65, 1, 0.03))
                try:
                    bg.setTransparency(1); fg.setTransparency(1)
                except Exception:
                    pass
            except Exception:
                fg = OnscreenText("", pos=(0,0.94), scale=0.06, mayChange=True)
                bg = fg
            self.boss_hp_bar = (fg, bg)
        fg, bg = self.boss_hp_bar
        try:
            fg.setScale(0.65 * max(percent, 0.01), 1, 0.03)
            fg.show(); bg.show()
        except Exception:
            pass

    def hide_boss_bar(self):
        if self.boss_hp_bar:
            fg, bg = self.boss_hp_bar
            try:
                fg.hide(); bg.hide()
            except Exception:
                pass

    # ---------- Update loop ----------
    def update(self, dt, enemies, boss_model=None):
        # update floating texts
        for entry in self.active_texts[:]:
            entry['timer'] += dt
            # float upward visually
            offset_z = 44 + entry['timer'] * 38
            world_pos = entry['pos'] + Vec3(0, 0, offset_z)
            screen = self._project_to_screen(world_pos)
            if screen:
                x, y = screen
                try:
                    entry['text'].setPos(x, y)
                except Exception:
                    try:
                        entry['text'].setPos(x, 0, y)
                    except Exception:
                        pass
            # fade out
            alpha = max(0.0, 1.0 - entry['timer'] / entry['duration'])
            try:
                entry['text'].setColorScale(1, 1, 1, alpha)
            except Exception:
                pass
            if entry['timer'] > entry['duration']:
                try: entry['text'].destroy()
                except Exception: pass
                self.active_texts.remove(entry)

        # update enemy HP bars positions
        for enemy in enemies:
            model = enemy.get("model")
            if not model or not enemy.get("alive"):
                # hide if present
                try:
                    self.hide_enemy_hp_bar(model)
                except Exception:
                    pass
                continue
            key = id(model)
            fg, bg = self.hp_bars.get(key, (None, None))
            pos3d = model.getPos() + Vec3(0, 0, 44)
            screen = self._project_to_screen(pos3d)
            if screen and fg and bg:
                x, y = screen
                try:
                    fg.setPos(x, 0, y)
                    bg.setPos(x, 0, y)
                except Exception:
                    pass

        # update lockon icon
        if self.lockon_icon and hasattr(self.lockon_icon, "_target"):
            target = getattr(self.lockon_icon, "_target", None)
            if target:
                try:
                    pos3d = target.getPos() + Vec3(0, 0, 62)
                    screen = self._project_to_screen(pos3d)
                    if screen:
                        x, y = screen
                        try:
                            # OnscreenImage uses (x, 0, y)
                            self.lockon_icon.setPos(x, 0, y)
                        except Exception:
                            try:
                                self.lockon_icon.setPos(x, y)
                            except Exception:
                                pass
                except Exception:
                    pass

        # update boss bar (position is UI anchored - no movement needed here)
        if boss_model:
            # show boss bar handled by caller via show_boss_bar(percent)
            pass