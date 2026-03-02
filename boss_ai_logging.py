import os
import json
import time

class AILogger:
    """
    簡單的 AI 決策 logger：將每次 boss 做決定時的特徵與 label（chosen_skill）
    以 JSONL 格式寫入 models/boss_ai_training.jsonl（每行一個 JSON）。
    """
    def __init__(self, out_dir="models", filename="boss_ai_training.jsonl"):
        self.out_dir = out_dir
        self.filename = filename
        os.makedirs(self.out_dir, exist_ok=True)
        self.filepath = os.path.join(self.out_dir, self.filename)
        # 若想要每次開遊戲重新開始新檔，取消下列註解：
        # with open(self.filepath, "w") as f: pass

    def log(self, record: dict):
        """
        record: dict 包含你希望的特徵與 label，例如:
          {
            "ts": 123456789,
            "phase": 1,
            "boss_hp": 1200,
            "boss_max_hp": 1200,
            "boss_x": 0.0,
            "boss_y": 0.0,
            "player_hp": 500,
            "player_x": ...,
            "player_y": ...,
            "distance": 300.0,
            "available_skills": ["projectile","spikes"],
            "chosen_skill": "projectile",
            "death_backlash_active": False,
            "crystals_alive": 0
          }
        """
        record["ts"] = time.time()
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            # 不要讓 logging 影響遊戲主流程
            print(f"[AILogger] 寫檔失敗: {e}")