# area2.py 
from panda3d.core import Vec3, LineSegs
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode
import math

class Area2System:
    def __init__(self, base, ground_system, enemy_system):
        self.base = base
        self.ground_system = ground_system
        self.enemy_system = enemy_system
        
        # 場景模型
        self.ground_tile = None
        self.area_boundary = None
        
        # Area2 設定
        self.arena_center = Vec3(0, 0, 5)
        self.arena_radius = 1000  # 半徑1000的場地
        
        # UI
        self.area_text = None
        self.objective_text = None
        
        # 載入場景資源
        self.load_scene_assets()
        self.setup_display()
        
        print("Area2 圓形場地初始化完成")
    
    def load_scene_assets(self):
        """載入Area2場景資源（包含容錯）"""
        print("載入Area2圓形場地資源...")
        crystal_model = self.base.loader.loadModel("model/background/crystal.glb")
        try:
            self.ground_tile = self.base.loader.loadModel("model/background/area2.egg")
        except Exception:
            try:
                self.ground_tile = self.base.loader.loadModel("models/box.egg")
            except Exception:
                self.ground_tile = None
        tex =self.base.loader.loadTexture("model/background/images/12.png")
        self.ground_tile.setTexture(tex, 1)
        if self.ground_tile:
            try:
                self.ground_tile.setScale(100)
                self.ground_tile.setPos(0, 0, -20)
                self.ground_tile.setHpr(0, 0, 0)
                self.ground_tile.reparentTo(self.base.render)
            except Exception:
                pass
        # 創建邊界
        self.create_area_boundary()
        print("Area2場景資源載入完成")
    
    def create_area_boundary(self):
        """創建圓形場地邊界"""
        lines = LineSegs()
        lines.setColor(0, 1, 1, 0.8)  # 青色邊界
        lines.setThickness(4.0)
        
        segments = 64
        for i in range(segments + 1):
            angle = (i / segments) * 360.0
            x = math.cos(math.radians(angle)) * self.arena_radius
            y = math.sin(math.radians(angle)) * self.arena_radius
            if i == 0:
                lines.moveTo(self.arena_center.x + x, self.arena_center.y + y, 2)
            else:
                lines.drawTo(self.arena_center.x + x, self.arena_center.y + y, 2)
        
        try:
            boundary_node = lines.create()
            self.area_boundary = self.base.render.attachNewNode(boundary_node)
        except Exception:
            self.area_boundary = None
    
    def setup_display(self):
        """設置顯示文字"""
        try:
            self.area_text = OnscreenText(
                text="AREA 2 - Boss Arena",
                pos=(0.8, 0.9),
                scale=0.05,
                fg=(0, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True
            )
            self.objective_text = OnscreenText(
                text="Defeat the Boss!",
                pos=(0.8, 0.85),
                scale=0.04,
                fg=(1, 1, 1, 1),
                align=TextNode.ARight,
                mayChange=True
            )
        except Exception:
            self.area_text = None
            self.objective_text = None
    
    def set_player_start_position(self):
        """設置玩家起始位置"""
        start_pos = Vec3(0, 800, 5)  # 在場地邊緣開始
        try:
            self.base.model_butterfly.setPos(start_pos)
        except Exception:
            pass
        print(f"Area2玩家起始位置: {start_pos}")
    
    def show_scene(self):
        """顯示Area2場景"""
        try:
            if self.ground_tile: self.ground_tile.show()
            if self.area_boundary: self.area_boundary.show()
        except Exception:
            pass
        print("Area2場景顯示")
    
    def hide_scene(self):
        """隱藏Area2場景"""
        try:
            if self.ground_tile: self.ground_tile.hide()
            if self.area_boundary: self.area_boundary.hide()
        except Exception:
            pass
        print("Area2場景隱藏")
    
    def is_in_arena(self, position):
        """檢查位置是否在圓形場地內"""
        try:
            distance_from_center = (position - self.arena_center).length()
            return distance_from_center <= self.arena_radius
        except Exception:
            return False
    
    def restrict_player_movement(self, new_pos):
        """限制玩家在圓形場地內移動"""
        try:
            if not self.is_in_arena(new_pos):
                direction = new_pos - self.arena_center
                direction.setZ(0)
                if direction.length() > 0:
                    direction.normalize()
                    clamped_pos = self.arena_center + direction * (self.arena_radius - 1)
                    clamped_pos.z = new_pos.z
                    return clamped_pos
        except Exception:
            pass
        return new_pos
    
    def update_display(self):
        """更新顯示信息"""
        try:
            if self.area_text and self.objective_text:
                self.area_text.setText("AREA 2 - Boss Arena")
                self.objective_text.setText("Defeat the Boss!")
        except Exception:
            pass
    
    def update(self, dt):
        """每幀更新"""
        self.update_display()
    
    def get_arena_info(self):
        """獲取場地資訊"""
        return {'center': self.arena_center, 'radius': self.arena_radius}
    
    def cleanup(self):
        """清理Area2場景資源"""
        print("清理Area2場景資源...")
        try:
            if self.ground_tile: self.ground_tile.removeNode()
        except Exception:
            pass
        try:
            if self.area_boundary: self.area_boundary.removeNode()
        except Exception:
            pass
        try:
            if self.area_text: self.area_text.destroy()
            if self.objective_text: self.objective_text.destroy()
        except Exception:
            pass
        print("Area2場景資源清理完成")