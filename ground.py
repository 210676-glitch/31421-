from panda3d.core import Vec3

class GroundSystem:
    def __init__(self):
        self.gravity = -140.0
        self.vertical_velocity = 0.0
        self.is_grounded = True
        self.jump_power = 108.0
        self.portal_position = Vec3(0, -900, 100)
        self.portal_model = None
        self.portal_radius = 50

        self.ground_regions = [
            {'name': 'region1', 'plane_eq': lambda x, y: (3*y - 132) / 14, 'contains_point': self._in_region1},
            {'name': 'region2', 'plane_eq': lambda x, y: (-85840*y - 34673995) / 453879, 'contains_point': self._in_region2},
            {'name': 'region3', 'plane_eq': lambda x, y: (3*y - 132) / 14, 'contains_point': self._in_region3},
            {'name': 'region4', 'plane_eq': lambda x, y: 0, 'contains_point': self._in_region4},
            {'name': 'region5', 'plane_eq': lambda x, y: 0, 'contains_point': self._in_region5}
        ]
        self.global_x_min = -537
        self.global_x_max = 537
        self.global_y_min = -1012
        self.global_y_max = 311

    def create_portal(self, base):
        self.portal_model = base.loader.loadModel("model/background/portal.egg")
        self.portal_model.setScale(100)
        self.portal_model.setPos(self.portal_position)
        self.portal_model.reparentTo(base.render)
        return self.portal_model

    def hide_portal(self):
        if self.portal_model:
            self.portal_model.hide()

    def show_portal(self):
        if self.portal_model:
            self.portal_model.show()

    def is_player_near_portal(self, player_pos):
        distance = (player_pos - self.portal_position).length()
        return distance <= self.portal_radius

    def _in_region1(self, x, y):
        if y < -166 or y > 44:
            return False
        if y == -166:
            x_min, x_max = 477, 537
        elif y == 44:
            x_min, x_max = 410, 480
        else:
            t = (y + 166) / (44 + 166)
            x_min = 477 + t * (410 - 477)
            x_max = 537 + t * (480 - 537)
        return x_min <= x <= x_max

    def _in_region2(self, x, y):
        if y < -1012 or y > -166:
            return False
        if y == -166:
            x_min, x_max = -537, 537
        elif y == -1012:
            x_min, x_max = -505, 505
        else:
            t = (y + 166) / (-1012 + 166)
            x_min = -537 + t * 32
            x_max = 537 + t * -32
        return x_min <= x <= x_max

    def _in_region3(self, x, y):
        if y < -166 or y > 44:
            return False
        if y == -166:
            x_min, x_max = -537, -477
        elif y == 44:
            x_min, x_max = -480, -410
        else:
            t = (y + 166) / (44 + 166)
            x_min = -537 + t * (-480 + 537)
            x_max = -477 + t * (-410 + 477)
        return x_min <= x <= x_max

    def _in_region4(self, x, y):
        if y < 44 or y > 311:
            return False
        if y == 44:
            x_min, x_max = -410, 410
        elif y == 311:
            x_min, x_max = 318, 318
        else:
            t = (y - 44) / (311 - 44)
            x_min = -410 + t * 728
            x_max = 410 + t * -92
        return x_min <= x <= x_max

    def _in_region5(self, x, y):
        if y < -166 or y > 44:
            return False
        if y == -166:
            x_min, x_max = -477, 477
        elif y == 44:
            x_min, x_max = -410, 410
        else:
            t = (y + 166) / (44 + 166)
            x_min = -477 + t * (-410 + 477)
            x_max = 477 + t * (410 - 477)
        return x_min <= x <= x_max

    def get_ground_height(self, x, y):
        if not (self.global_x_min <= x <= self.global_x_max and self.global_y_min <= y <= self.global_y_max):
            return 5.0
        max_z = None
        for region in self.ground_regions:
            if region['contains_point'](x, y):
                z = region['plane_eq'](x, y)
                if max_z is None or z > max_z:
                    max_z = z
        return max_z if max_z is not None else 5.0

    def clamp_to_bounds(self, x, y):
        x_clamped = max(self.global_x_min, min(x, self.global_x_max))
        y_clamped = max(self.global_y_min, min(y, self.global_y_max))
        return x_clamped, y_clamped

    def apply_gravity(self, model_butterfly, dt):
        butterfly_pos = model_butterfly.getPos()
        new_x, new_y = self.clamp_to_bounds(butterfly_pos.x, butterfly_pos.y)
        butterfly_pos.x = new_x
        butterfly_pos.y = new_y
        ground_z = self.get_ground_height(new_x, new_y)
        if self.is_grounded:
            butterfly_pos.z = ground_z
            self.vertical_velocity = 0.0
        else:
            self.vertical_velocity += self.gravity * dt
            butterfly_pos.z += self.vertical_velocity * dt
            if butterfly_pos.z <= ground_z:
                butterfly_pos.z = ground_z
                self.vertical_velocity = 0.0
                self.is_grounded = True
        model_butterfly.setPos(butterfly_pos)
        return self.is_grounded, self.vertical_velocity

    def jump(self):
        if self.is_grounded:
            self.vertical_velocity = self.jump_power
            self.is_grounded = False
            return True
        return False

    def debug_info(self, model_butterfly):
        pos = model_butterfly.getPos()
        ground_z = self.get_ground_height(pos.x, pos.y)
        region_names = [r['name'] for r in self.ground_regions if r['contains_point'](pos.x, pos.y)]
        portal_distance = (pos - self.portal_position).length()
        return f"位置: ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f}) | 地面: {ground_z:.1f} | 區域: {region_names} | 著地: {self.is_grounded} | 傳送門距離: {portal_distance:.1f}"