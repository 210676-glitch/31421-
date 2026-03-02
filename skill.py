# skill.py 
from panda3d.core import Vec3
import math

def skill(base, q_cd, e_cd, key, force_e, enemy_system, moonlight, skillmoon, normal_cd):
    current_time = base.globalClock.getFrameTime()
    recover = 0

    if key == "q" and current_time > q_cd:
        player_pos = base.model_butterfly.getPos()
        facing = get_facing_vector(base)
        cone_angle = 90
        cone_range = 120
        targets = gather_targets_in_cone(base, player_pos, facing, cone_range, cone_angle)
        total_hits = 0
        for t in targets:
            to_target = (t["position"] - player_pos)
            to_target.setZ(0)
            if to_target.length() == 0:
                angle = 0
            else:
                to_target.normalize()
                angle = math.degrees(math.acos(max(-1.0, min(1.0, facing.dot(to_target)))))
            angle_factor = max(0.4, 1.0 - (angle / cone_angle))
            damage = int(80 * angle_factor)
            if t["type"] == "enemy" and t.get("enemy"):
                t["enemy"]["health"] -= damage
                t["enemy"]["model"].setColor(1, 0.5, 0.5, 1)
                base.taskMgr.doMethodLater(0.2, lambda task, e=t['enemy']: reset_enemy_color(base, e), f"reset_q_color_{id(t['enemy'])}")
                if t["enemy"]["health"] <= 0:
                    enemy_system.kill_enemy(t["enemy"])
                total_hits += 1
            elif t["type"] == "boss" and hasattr(base, 'boss_system') and base.boss_system and base.boss_system.boss_alive:
                base.boss_system.damage_boss(damage)
                total_hits += 1
            elif t["type"] == "crystal" and hasattr(base, 'crystal_system') and base.crystal_system:
                base.crystal_system.damage_crystal(t["crystal_index"])
                total_hits += 1
        q_cd = current_time + 13.0
        skillmoon = "double"
        force_e = 1
        if total_hits > 0:
            print(f"Q 命中 {total_hits} 個目標")

    elif key == "e":
        if force_e == 1:
            player_pos = base.model_butterfly.getPos()
            target = find_best_target(base, player_pos, max_range=300)
            damage = 0
            if moonlight >= 50:
                damage = moonlight * 6
                moonlight = 0
            else:
                moonlight = min(100, moonlight + 70)
                recover = 150
            if target:
                if target["type"] == "enemy" and target.get("enemy"):
                    target["enemy"]["health"] -= damage
                    target["enemy"]["model"].setColor(1, 0.3, 0.3, 1)
                    base.taskMgr.doMethodLater(0.2, lambda task, e=target['enemy']: reset_enemy_color(base, e), f"reset_e_color_{id(target['enemy'])}")
                    if target["enemy"]["health"] <= 0:
                        enemy_system.kill_enemy(target["enemy"])
                    print(f"E(蓄力) 命中敵人造成 {damage} 傷害")
                    force_e = 0
                elif target["type"] == "boss" and hasattr(base, 'boss_system') and base.boss_system and base.boss_system.boss_alive:
                    base.boss_system.damage_boss(damage)
                    print(f"E(蓄力) 命中 Boss，造成 {damage} 傷害")
                    force_e = 0
                elif target["type"] == "crystal" and hasattr(base, 'crystal_system') and base.crystal_system:
                    base.crystal_system.damage_crystal(target['crystal_index'])
                    print(f"E(蓄力) 命中水晶 {target['crystal_index']}")
                    force_e = 0
            else:
                aoe_range = 120
                hits = damage_enemies_in_radius(base, enemy_system, player_pos, aoe_range, damage)
                print(f"E(蓄力) 在周圍造成 {damage} 傷害，命中 {hits} 個敵人")
                force_e = 0
        else:
            current_time = base.globalClock.getFrameTime()
            if current_time > e_cd:
                player_pos = base.model_butterfly.getPos()
                facing = get_facing_vector(base)
                cone_angle = 60
                cone_range = 80
                targets = gather_targets_in_cone(base, player_pos, facing, cone_range, cone_angle)
                hits = 0
                for t in targets:
                    dmg = 40
                    if t["type"] == "enemy" and t.get("enemy"):
                        t["enemy"]["health"] -= dmg
                        t["enemy"]["model"].setColor(1, 0.5, 0.5, 1)
                        base.taskMgr.doMethodLater(0.2, lambda task, e=t['enemy']: reset_enemy_color(base, e), f"reset_e_color_{id(t['enemy'])}")
                        if t["enemy"]["health"] <= 0:
                            enemy_system.kill_enemy(t["enemy"])
                        hits += 1
                    elif t["type"] == "boss" and hasattr(base, 'boss_system') and base.boss_system and base.boss_system.boss_alive:
                        base.boss_system.damage_boss(dmg)
                        hits += 1
                    elif t["type"] == "crystal" and hasattr(base, 'crystal_system') and base.crystal_system:
                        base.crystal_system.damage_crystal(t['crystal_index'])
                        hits += 1
                e_cd = current_time + 5.0
                if skillmoon == "full":
                    skillmoon = "empty"
                elif skillmoon == "empty":
                    skillmoon = "full"
                if hits > 0:
                    print(f"E 命中 {hits} 個目標")
    elif key == "mouse1" and current_time > normal_cd:
        hits, dash_distance, moonlight, recover = normal_attack_with_moon_rule(
            base, enemy_system, moonlight, skillmoon
        )
        normal_cd = current_time + 0.3

    return q_cd, e_cd, force_e, moonlight, skillmoon, recover, normal_cd

# ----------------- helpers -----------------
def get_facing_vector(base):
    h = base.model_butterfly.getHpr().x
    rad = math.radians(h)
    return Vec3(math.cos(rad), math.sin(rad), 0)

def angle_between_vec(a, b):
    if a.length() == 0 or b.length() == 0:
        return 0.0
    dot = max(-1.0, min(1.0, a.dot(b)))
    return math.degrees(math.acos(dot))

def reset_enemy_color(base, enemy):
    if enemy['alive']:
        enemy['model'].setColor(1, 1, 1, 1)

def gather_targets_in_cone(base, origin, facing, max_range, half_angle_deg):
    results = []
    if hasattr(base, 'floating_ui') and base.floating_ui and base.floating_ui.lockon_icon:
        lock = getattr(base.floating_ui.lockon_icon, '_target', None)
        if lock:
            try:
                pos = lock.getPos()
                found_enemy = find_enemy_by_model(base, lock)
                if found_enemy:
                    results.append({"type" : "enemy", "enemy" : found_enemy, "position" : pos})
            except Exception:
                pass

    if hasattr(base, 'boss_system') and base.boss_system and getattr(base.boss_system, 'boss_alive', False):
        boss_pos = base.boss_system.boss["model"].getPos()
        to_boss = boss_pos - origin
        to_boss.setZ(0)
        if to_boss.length() <= max_range:
            vec = Vec3(to_boss)
            vec.normalize()
            ang = angle_between_vec(facing, vec)
            if ang <= half_angle_deg:
                results.append({"type" : "boss", "position" : boss_pos})

    if (hasattr(base, 'crystal_system') and base.crystal_system and hasattr(base.crystal_system, 'crystals')):
        for c in base.crystal_system.crystals:
            if not c["alive"]:
                continue
            pos = c["model"].getPos()
            to_c = pos - origin
            to_c.setZ(0)
            if to_c.length() <= max_range:
                vec = Vec3(to_c)
                vec.normalize()
                ang = angle_between_vec(facing, vec)
                if ang <= half_angle_deg:
                    results.append({"type" : "crystal", "position" : pos, "crystal_index" : c["index"]})

    if hasattr(base, 'enemy_system'):
        for enemy in base.enemy_system.enemies:
            if not enemy["alive"]:
                continue
            pos = enemy["model"].getPos()
            to_e = pos - origin
            to_e.setZ(0)
            if to_e.length() <= max_range:
                vec = Vec3(to_e)
                if vec.length() > 0:
                    vec.normalize()
                ang = angle_between_vec(facing, vec)
                if ang <= half_angle_deg:
                    results.append({"type" : "enemy", "enemy" : enemy, "position" : pos})

    def priority_key(t):
        p = 0
        if t["type"] == "boss":
            p = -1000
        elif t["type"] == "crystal":
            p = -900
        elif t["type"] == "enemy":
            et = t.get("enemy", {}).get("type") if t.get("enemy") else None
            p = -800 if et == "archer" else -700
        dist = (t["position"] - origin).length()
        return (p, dist)
    unique = []
    seen_pos = set()
    for t in results:
        key = (round(t["position"].x, 1), round(t["position"].y, 1), t.get("type"))
        if key in seen_pos:
            continue
        seen_pos.add(key)
        unique.append(t)
    unique.sort(key=priority_key)
    return unique

def find_enemy_by_model(base, model):
    if not hasattr(base, 'enemy_system'):
        return None
    for enemy in base.enemy_system.enemies:
        if enemy["model"] == model:
            return enemy
    return None

def damage_enemies_in_radius(base, enemy_system, center, radius, damage):
    hits = 0
    if not hasattr(enemy_system, 'enemies'):
        return 0
    for enemy in enemy_system.enemies:
        if not enemy["alive"]:
            continue
        pos = enemy["model"].getPos()
        dist = (pos - center).length()
        if dist <= radius:
            enemy["health"] -= damage
            enemy["model"].setColor(1, 0.5, 0.5, 1)
            base.taskMgr.doMethodLater(0.2, lambda task, e=enemy: reset_enemy_color(base, e), f"reset_rad_color_{id(enemy)}")
            if enemy["health"] <= 0:
                enemy_system.kill_enemy(enemy)
            hits += 1
    return hits

def find_best_target(base, player_pos, max_range=500):
    targets = []
    if hasattr(base, 'floating_ui') and base.floating_ui and base.floating_ui.lockon_icon:
        lock = getattr(base.floating_ui.lockon_icon, '_target', None)
        if lock:
            try:
                pos = lock.getPos()
                enemy = find_enemy_by_model(base, lock)
                if enemy:
                    return {"type" : "enemy", "enemy" : enemy, "position" : pos, "distance" : (pos-player_pos).length()}
            except Exception:
                pass

    facing = get_facing_vector(base)

    if hasattr(base, 'boss_system') and base.boss_system and getattr(base.boss_system, 'boss_alive', False):
        boss_pos = base.boss_system.boss["model"].getPos()
        distance = (player_pos - boss_pos).length()
        if distance <= max_range:
            targets.append({"type" : "boss","position":boss_pos,"distance":distance,"priority":100})
    if (hasattr(base, 'crystal_system') and base.crystal_system and hasattr(base.crystal_system, 'crystals')):
        for crystal in base.crystal_system.crystals:
            if crystal["alive"]:
                crystal_pos = crystal["model"].getPos()
                distance = (player_pos - crystal_pos).length()
                if distance <= max_range:
                    targets.append({"type":"crystal","position":crystal_pos,"distance":distance,"crystal_index":crystal["index"],"priority":90})
    if hasattr(base, 'enemy_system'):
        for enemy in base.enemy_system.enemies:
            if enemy["alive"]:
                enemy_pos = enemy["model"].getPos()
                distance = (player_pos - enemy_pos).length()
                if distance <= max_range:
                    priority = 80 if enemy["type"] == "archer" else 70
                    vec = enemy_pos - player_pos
                    vec.setZ(0)
                    if vec.length() > 0:
                        vec.normalize()
                        ang = angle_between_vec(facing, vec)
                    else:
                        ang = 0
                    targets.append({"type":"enemy","enemy":enemy,"position":enemy_pos,"distance":distance,"priority":priority,"angle":ang})
    if not targets:
        return None
    def sort_key(t):
        ang = t.get("angle", 180)
        return (-t["priority"], t["distance"], ang)
    targets.sort(key=sort_key)
    # 回傳最近的（優先順序下已考慮距離）
    return targets[0]

def normal_attack_scan(moonlight, skillmoon):
    if skillmoon == "full" and moonlight < 100:
        return 30
    elif skillmoon == "empty" and moonlight > 10:
        return 45
    elif skillmoon == "double":
        if moonlight > 10:
            return 80
        else:
            return 60
    else:
        return 30

def normal_attack_with_moon_rule(base, enemy_system, moonlight, skillmoon):
    """
    普攻（鼠標 / normal attack）時只在該次攻擊期間顯示 lockon：
    - 如果找到目標，會把 floating_ui 設為該目標，並在短時間後自動清除（0.35s）。
    - 這樣視覺上表現為「普攻時鎖敵」，而不是每幀顯示 lockon。
    """
    player_pos = base.model_butterfly.getPos()
    player_hpr = base.model_butterfly.getHpr()
    target = find_best_target(base, player_pos, max_range=200)
    hits = 0
    dash_distance = 0
    damage = normal_attack_scan(moonlight, skillmoon)
    recover = 0

    SAFE_DISTANCE = 10.0
    MIN_DASH = 5.0
    MAX_DASH = 40.0

    # helper to set temporary lockon then clear after delay
    def set_temporary_lockon(model, duration=0.35):
        try:
            if not hasattr(base, 'floating_ui') or base.floating_ui is None:
                return
            # set lockon
            base.floating_ui.set_lockon(model)
            # remove any existing scheduled clear to avoid stacking
            try:
                base.taskMgr.remove('clear_lockon_after_normal')
            except Exception:
                pass
            def clear_task(task):
                try:
                    if hasattr(base, 'floating_ui') and base.floating_ui:
                        base.floating_ui.clear_lockon()
                except Exception:
                    pass
                return task.done
            base.taskMgr.doMethodLater(duration, clear_task, 'clear_lockon_after_normal')
        except Exception:
            pass

    if target:
        target_pos = target["position"]
        # set a temporary lockon to show the attacked target
        try:
            tgt_model = None
            if target["type"] == 'enemy' and target.get("enemy"):
                tgt_model = target["enemy"]["model"]
            elif target["type"] == 'boss' and hasattr(base, 'boss_system') and base.boss_system and base.boss_system.boss:
                tgt_model = base.boss_system.boss["model"]
            elif target["type"] == 'crystal' and hasattr(base, 'crystal_system') and base.crystal_system:
                tgt_crystal_model = None
                # attempts to fetch model from crystal system
                try:
                    for c in base.crystal_system.crystals:
                        if c.get("index") == target.get("crystal_index"):
                            tgt_crystal_model = c.get("model")
                            break
                except Exception:
                    tgt_crystal_model = None
                tgt_model = tgt_crystal_model
            if tgt_model:
                set_temporary_lockon(tgt_model, duration=0.35)
        except Exception:
            pass

        try:
            base.model_butterfly.lookAt(target_pos)
            h = base.model_butterfly.getHpr().x
            # 在每次結束朝向操作時加上 (0,90,90) 的偏移，確保不累加 yaw（h 來源於 lookAt）
            base.model_butterfly.setHpr(h, 90, 90)
        except Exception:
            pass
        dir_vec = Vec3(target_pos - player_pos)
        dir_vec.setZ(0)
        dist_to_target = dir_vec.length()
        if dist_to_target > 0:
            dir_vec.normalize()
        else:
            dir_vec = Vec3(0,1,0)
        hits = enemy_system.check_attack_hit(player_pos, base.model_butterfly.getHpr(), attack_range=50, attack_angle=120, damage=damage)
        if target["type"] == 'boss' and dist_to_target <= 50 and hasattr(base, 'boss_system') and getattr(base.boss_system, 'boss_alive', False):
            base.boss_system.damage_boss(damage)
            hits += 1
        elif target["type"] == 'crystal' and dist_to_target <= 50 and hasattr(base, 'crystal_system'):
            base.crystal_system.damage_crystal(target['crystal_index'])
            hits += 1
        if hits > 0 and skillmoon == 'full' and moonlight < 100:
            moonlight += 10
        elif hits > 0 and skillmoon == 'empty' and moonlight > 10:
            moonlight -= 20
        elif hits > 0 and skillmoon == 'double':
            if moonlight < 100:
                moonlight += 10
            if moonlight > 10:
                moonlight -= 20
                recover = 30
        if hits > 0 and dist_to_target > SAFE_DISTANCE + 0.1:
            desired = min(MAX_DASH, max(MIN_DASH, dist_to_target - SAFE_DISTANCE))
            dash_distance = max(0.0, min(desired, max(0.0, dist_to_target - SAFE_DISTANCE)))
            if dash_distance > 0:
                new_pos = player_pos + dir_vec * dash_distance
                final_dist = (target_pos - new_pos).length()
            
                base.model_butterfly.setPos(new_pos)
    else:
        # 無鎖定目標時的普攻行為（不會顯示 lockon）
        hits = enemy_system.check_attack_hit(player_pos, player_hpr, attack_range=50, attack_angle=120, damage=damage)
        if hits > 0 and skillmoon == "full" and moonlight < 100:
            moonlight += 10
        elif hits > 0 and skillmoon == "empty" and moonlight > 10:
            moonlight -= 20
        elif hits > 0 and skillmoon == "double":
            if moonlight < 100:
                moonlight += 10
            if moonlight > 10:
                moonlight -= 20
                recover = 25
        if hits == 0:
            dash_distance = 40
            heading_deg = base.model_butterfly.getHpr().x
            rad = math.radians(heading_deg)
            forward = Vec3(math.cos(rad), math.sin(rad), 0)
            new_pos = player_pos + forward * dash_distance
            base.model_butterfly.setPos(new_pos)

    moonlight = max(0, min(moonlight, 100))
    return hits, dash_distance, moonlight, recover