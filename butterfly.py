# butterfly
from panda3d.core import *

def butterfly_box_simple(butterfly):
    """簡單載入角色模型（無動畫），模型朝向已設為預設正面（包含 0,90,90 偏移）"""
    try:
        model = butterfly.loader.loadModel("model/butterfly/ema.glb")
    except Exception:
        model = butterfly.loader.loadModel("models/box.egg")
    model.setScale(40)
    model.setPos(0, -500, 115)
    # 將初始面向包含 (0,90,90) 的偏移，之後每次把 yaw 設回來源值並固定 pitch/roll=90
    model.setHpr(0, 90, 90)
    model.reparentTo(butterfly.render)
    print("角色模型載入成功（簡單模式，預設正面 + (0,90,90) 偏移）")
    return model

def dragon_box(butterfly):
    try:
        model1 = butterfly.loader.loadModel("model/background/sky.glb")
    except Exception:
        model1 = butterfly.loader.loadModel("models/box.egg")
    tex =butterfly.loader.loadTexture("model/background/images/sky.jpg")
    model1.setTexture(tex, 1)
    model1.setScale(1000)
    model1.setPos(2500, 2500, 5)
    model1.setHpr(90, 0, 90)
    model1.reparentTo(butterfly.render)
    return model1