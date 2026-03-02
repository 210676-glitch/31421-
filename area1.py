from panda3d.core import Vec3, LineSegs
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode
import random

class Region:
    def __init__(self, x, y, enemy_count, region_id):
        self.position = Vec3(x, y, 5)
        self.enemy_count = enemy_count
        self.region_id = region_id
        self.is_complete = False
        self.enemies_spawned = False
        self.current_enemies = 0
        self.expected_enemies = sum(enemy_count.values()) if isinstance(enemy_count, dict) else int(enemy_count)
        self.spawn_radius = 200
        self.trigger_radius = 100
        self.bounds = {'min_x': x - 250, 'max_x': x + 250, 'min_y': y - 250, 'max_y': y + 250}

    def is_player_in_trigger(self, player_pos):
        distance = (player_pos - self.position).length()
        return distance <= self.trigger_radius

    def get_random_position_in_region(self):
        x = self.position.x + random.uniform(-self.spawn_radius, self.spawn_radius)
        y = self.position.y + random.uniform(-self.spawn_radius, self.spawn_radius)
        return Vec3(x, y, 5)

    def is_position_in_region(self, position):
        return (self.bounds['min_x'] <= position.x <= self.bounds['max_x'] and
                self.bounds['min_y'] <= position.y <= self.bounds['max_y'])

class Area1System:
    def __init__(self, base, ground_system, enemy_system):
        self.base = base
        self.ground_system = ground_system
        self.enemy_system = enemy_system
        self.setup_lod_system()
        self.loaded_regions = set()

        self.ground_tiles = []
        self.portal_model = None
        self.boundary_node = None
        self.region_visuals = []

        self.map_bounds = {'min_x': 0, 'max_x': 5000, 'min_y': 0, 'max_y': 5000}

        self.regions_matrix = self.create_region_matrix()
        self.all_regions = self.get_all_regions()

        self.active_region = None
        self.all_areas_cleared = False
        self.portal_spawned = False
        self.boss_stage_loaded = False

        self.area_text = None
        self.objective_text = None

        self.load_scene_assets()
        self.setup_display()
        self.set_player_start_position()
        print("Area1 初始化完成")

    def create_region_matrix(self):
        regions = [
            [Region(1000, 4000, {"basic": 2, "archer": 3}, "A1"), Region(3000, 4000, {"basic": 1, "archer": 7}, "A2")],
            [Region(1000, 2500, {"basic": 2, "archer": 4}, "B1"), Region(3000, 2500, {"basic": 3, "archer": 5}, "B2")],
            [Region(1000, 1000, {"basic": 3, "archer": 4}, "C1"), Region(3000, 1000, {"basic": 6, "archer": 1}, "C2")]
        ]
        return regions

    def get_all_regions(self):
        all_regions = []
        for row in self.regions_matrix:
            for region in row:
                all_regions.append(region)
        return all_regions

    def load_scene_assets(self):
        self.setup_area1_ground()
        self.create_portal()
        self.create_visuals()

    def setup_area1_ground(self):
        tile_count = 5
        total_size = 5000
        tile_coverage = total_size / tile_count
        offset = tile_coverage / 2
        for i in range(tile_count):
            for j in range(tile_count):
                tile = self.base.loader.loadModel("model/background/test.egg")
                pos_x = i * tile_coverage + offset
                pos_y = j * tile_coverage + offset
                tile.setScale(tile_coverage * 1.02)
                tile.setPos(pos_x, pos_y, -70)
                tile.reparentTo(self.base.render)
                self.ground_tiles.append(tile)

    def create_portal(self):
        portal_pos = Vec3(2500, 2500, 5)
        self.portal_model = self.base.loader.loadModel("model/background/portal.egg")
        self.portal_model.setScale(200)
        self.portal_model.setPos(portal_pos)
        self.portal_model.reparentTo(self.base.render)
        self.portal_model.hide()

    def create_visuals(self):
        self.create_boundary_visuals()
        self.create_region_visuals()

    def create_boundary_visuals(self):
        lines = LineSegs()
        lines.setColor(1, 0, 0, 0.8)
        lines.setThickness(3.0)
        bounds = self.map_bounds
        lines.moveTo(bounds['min_x'], bounds['min_y'], 1)
        lines.drawTo(bounds['max_x'], bounds['min_y'], 1)
        lines.drawTo(bounds['max_x'], bounds['max_y'], 1)
        lines.drawTo(bounds['min_x'], bounds['max_y'], 1)
        lines.drawTo(bounds['min_x'], bounds['min_y'], 1)
        boundary_node = lines.create()
        self.boundary_node = self.base.render.attachNewNode(boundary_node)

    def create_region_visuals(self):
        for row in self.regions_matrix:
            for region in row:
                lines = LineSegs()
                if region == self.active_region:
                    lines.setColor(1, 0, 0, 1)
                    lines.setThickness(3.0)
                elif region.is_complete:
                    lines.setColor(0, 1, 0, 1)
                    lines.setThickness(2.0)
                else:
                    lines.setColor(1, 1, 0, 1)
                    lines.setThickness(2.0)
                bounds = region.bounds
                lines.moveTo(bounds['min_x'], bounds['min_y'], 2)
                lines.drawTo(bounds['max_x'], bounds['min_y'], 2)
                lines.drawTo(bounds['max_x'], bounds['max_y'], 2)
                lines.drawTo(bounds['min_x'], bounds['max_y'], 2)
                lines.drawTo(bounds['min_x'], bounds['min_y'], 2)
                region_node = lines.create()
                visual = self.base.render.attachNewNode(region_node)
                self.region_visuals.append(visual)

    def setup_display(self):
        self.area_text = OnscreenText(text="Grassland Area", pos=(0.8, 0.9), scale=0.05, fg=(1, 1, 1, 1), align=TextNode.ARight, mayChange=True)
        self.objective_text = OnscreenText(text="Clear regions to unlock portal", pos=(0.8, 0.85), scale=0.04, fg=(1, 1, 1, 1), align=TextNode.ARight, mayChange=True)

    def set_player_start_position(self):
        start_pos = Vec3(2500, 2500, 5)
        self.base.model_butterfly.setPos(start_pos)

    def show_scene(self):
        for tile in self.ground_tiles:
            tile.show()
        if self.boundary_node:
            self.boundary_node.show()
        for visual in self.region_visuals:
            visual.show()
        if self.portal_model and self.portal_spawned:
            self.portal_model.show()

    def hide_scene(self):
        for tile in self.ground_tiles:
            tile.hide()
        if self.boundary_node:
            self.boundary_node.hide()
        for visual in self.region_visuals:
            visual.hide()
        if self.portal_model:
            self.portal_model.hide()

    def is_in_bounds(self, position):
        return (self.map_bounds['min_x'] <= position.x <= self.map_bounds['max_x'] and
                self.map_bounds['min_y'] <= position.y <= self.map_bounds['max_y'])

    def restrict_player_movement(self, new_pos):
        if not self.is_in_bounds(new_pos):
            clamped_x = max(self.map_bounds['min_x'], min(new_pos.x, self.map_bounds['max_x']))
            clamped_y = max(self.map_bounds['min_y'], min(new_pos.y, self.map_bounds['max_y']))
            return Vec3(clamped_x, clamped_y, new_pos.z)
        if self.active_region and not self.all_areas_cleared:
            return self.restrict_to_region(new_pos, self.active_region)
        return new_pos

    def restrict_to_region(self, position, region):
        bounds = region.bounds
        clamped_x = max(bounds['min_x'], min(position.x, bounds['max_x']))
        clamped_y = max(bounds['min_y'], min(position.y, bounds['max_y']))
        return Vec3(clamped_x, clamped_y, position.z)

    def check_region_triggers(self, player_pos):
        if self.active_region:
            self.check_active_region_completion()
            return
        for region in self.all_regions:
            if not region.is_complete and region.is_player_in_trigger(player_pos):
                self.activate_region(region)
                return

    def activate_region(self, region):
        self.active_region = region
        self.spawn_region_enemies(region)
        self.update_display()
        self.recreate_visuals()

    def spawn_region_enemies(self, region):
        if not region.enemies_spawned:
            region.current_enemies = getattr(region, 'expected_enemies', 0)
            spawned = 0
            basic_count = region.enemy_count.get("basic", 0) if isinstance(region.enemy_count, dict) else 0
            archer_count = region.enemy_count.get("archer", 0) if isinstance(region.enemy_count, dict) else 0
            for i in range(basic_count):
                enemy_pos = region.get_random_position_in_region()
                if region.is_position_in_region(enemy_pos):
                    enemy = self.enemy_system.create_enemy(enemy_pos, "basic", region.region_id)
                    if enemy:
                        spawned += 1
            for i in range(archer_count):
                enemy_pos = region.get_random_position_in_region()
                if region.is_position_in_region(enemy_pos):
                    enemy = self.enemy_system.create_enemy(enemy_pos, "archer", region.region_id)
                    if enemy:
                        spawned += 1
            region.current_enemies = spawned
            region.enemies_spawned = True

    def check_active_region_completion(self):
        if self.active_region and self.active_region.current_enemies <= 0:
            self.active_region.is_complete = True
            self.active_region = None
            if self.check_all_regions_complete() and not self.portal_spawned:
                self.spawn_boss_portal()
            self.update_display()
            self.recreate_visuals()

    def check_all_regions_complete(self):
        for region in self.all_regions:
            if not region.is_complete:
                return False
        self.all_areas_cleared = True
        return True

    def spawn_boss_portal(self):
        self.portal_spawned = True
        if self.portal_model:
            self.portal_model.show()
        self.update_display()

    def interact_with_portal(self):
        if not self.portal_spawned:
            return
        player_pos = self.base.model_butterfly.getPos()
        portal_pos = Vec3(2500, 2500, 5)
        distance = (player_pos - portal_pos).length()
        if distance < 100:
            self.load_fontaine_stage()

    def load_fontaine_stage(self):
        self.hide_scene()
        self.boss_stage_loaded = True
        if hasattr(self.base, 'load_fontaine_scene'):
            self.base.load_fontaine_scene()

    def cheat(self, pos):
        for region in self.all_regions:
            region.is_complete = True
            region.current_enemies = 0
        self.spawn_boss_portal()
        self.all_areas_cleared = True
        self.boss_stage_loaded = False

    def on_enemy_defeated(self):
        if self.active_region:
            self.active_region.current_enemies -= 1
            if self.active_region.current_enemies < 0:
                self.active_region.current_enemies = 0

    def update_display(self):
        if not self.area_text or not self.objective_text:
            return
        if self.boss_stage_loaded:
            self.area_text.setText("Fontaine")
            self.objective_text.setText("Explore the new area")
        elif self.active_region:
            self.area_text.setText(f"Active Region: {self.active_region.region_id}")
            remaining = self.active_region.current_enemies
            total_enemies = self.active_region.expected_enemies if hasattr(self.active_region, 'expected_enemies') else sum(self.active_region.enemy_count.values())
            self.objective_text.setText(f"Enemies: {remaining}/{total_enemies}")
        elif self.portal_spawned:
            self.area_text.setText("All Regions Cleared!")
            self.objective_text.setText("Go to portal and press F")
        else:
            completed = sum(1 for r in self.all_regions if r.is_complete)
            total = len(self.all_regions)
            self.area_text.setText(f"Regions: {completed}/{total}")
            self.objective_text.setText("Find and clear regions")

    def recreate_visuals(self):
        for visual in self.region_visuals:
            visual.removeNode()
        self.region_visuals.clear()
        self.create_region_visuals()

    def update(self, dt):
        player_pos = self.base.model_butterfly.getPos()
        self.check_region_triggers(player_pos)

    def setup_lod_system(self):
        self.lod_distances = {'high': 500, 'medium': 1000, 'low': 2000}

    def update_lod(self, player_pos):
        for tile in self.ground_tiles:
            tile.show()
            tile.setColorScale(1.0, 1.0, 1.0, 1.0)

    def cleanup(self):
        for tile in self.ground_tiles:
            tile.removeNode()
        self.ground_tiles.clear()
        if self.portal_model:
            self.portal_model.removeNode()
        if self.boundary_node:
            self.boundary_node.removeNode()
        for visual in self.region_visuals:
            visual.removeNode()
        self.region_visuals.clear()
        if self.area_text:
            self.area_text.destroy()
        if self.objective_text:
            self.objective_text.destroy()