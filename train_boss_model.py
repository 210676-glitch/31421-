import os
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib

INPUT = "models/boss_ai_training.jsonl"
OUT_MODEL = "models/boss_ai_model.pkl"

def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                rows.append(json.loads(line))
            except:
                pass
    return rows

def featurize(rows):
    df = pd.DataFrame(rows)
    # 必要欄位檢查
    required = ["phase", "boss_hp", "boss_max_hp", "boss_x", "boss_y",
                "player_hp", "player_x", "player_y", "distance",
                "available_skills", "chosen_skill", "death_backlash_active", "crystals_alive"]
    for r in required:
        if r not in df.columns:
            df[r] = np.nan

    # 將 available_skills 做成幾個二元欄位（是否包含）
    skill_set = set()
    df["available_skills"] = df["available_skills"].apply(lambda x: x if isinstance(x, list) else [])
    for s in df["available_skills"]:
        for it in s:
            skill_set.add(it)
    skill_set = sorted(skill_set)

    for s in skill_set:
        df[f"skill_has_{s}"] = df["available_skills"].apply(lambda lst: 1 if s in lst else 0)

    # 基本數值欄位
    feature_names = [
        "phase", "boss_hp", "boss_max_hp", "boss_x", "boss_y",
        "player_hp", "player_x", "player_y", "distance",
        "death_backlash_active", "crystals_alive"
    ] + [f"skill_has_{s}" for s in skill_set]

    X = df[feature_names].fillna(0)

    # Label
    y = df["chosen_skill"].fillna("none").astype(str)
    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    return X.values, y_enc, le, feature_names

def main():
    assert os.path.exists(INPUT), f"找不到訓練檔案: {INPUT}"
    rows = load_jsonl(INPUT)
    if not rows:
        print("沒收集到任何資料。")
        return
    X, y, label_encoder, feature_names = featurize(rows)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    acc = clf.score(X_val, y_val)
    print(f"驗證集準確度: {acc:.3f}")
    
    os.makedirs(os.path.dirname(OUT_MODEL), exist_ok=True)
    joblib.dump({"model": clf, "label_encoder": label_encoder, "feature_names": feature_names}, OUT_MODEL)
    
if __name__ == "__main__":
    main()