
"""Единый формат данных для танцев."""
import json
import os
import time

K_TIME = "t"
K_POINTS = "pts"

class Dance:
    def __init__(self, name="", artist="", difficulty="Medium", bpm=120):
        self.name = name
        self.artist = artist
        self.difficulty = difficulty
        self.bpm = bpm
        self.audio_path = ""
        self.video_path = ""
        self.poses = []  # [{K_TIME: float, K_POINTS: {name: {x,y,z,vis}}}, ...]
        self.created = time.time()

    def add_pose(self, t, landmarks):
        points = {}
        for i, lm in enumerate(landmarks):
            points[str(i)] = {
                "x": float(lm.x) if hasattr(lm, "x") else float(lm[0]),
                "y": float(lm.y) if hasattr(lm, "y") else float(lm[1]),
                "z": float(lm.z) if hasattr(lm, "z") else float(lm[2]),
                "v": float(lm.visibility) if hasattr(lm, "visibility") and lm.visibility is not None else 1.0,
            }
        self.poses.append({K_TIME: float(t), K_POINTS: points})

    def to_dict(self):
        return {
            "name": self.name, "artist": self.artist,
            "difficulty": self.difficulty, "bpm": self.bpm,
            "audio_path": self.audio_path, "video_path": self.video_path,
            "poses": self.poses, "created": self.created,
        }

    @staticmethod
    def from_dict(d):
        dance = Dance(
            d.get("name", ""), d.get("artist", ""),
            d.get("difficulty", "Medium"), d.get("bpm", 120)
        )
        dance.audio_path = d.get("audio_path", "")
        dance.video_path = d.get("video_path", "")
        dance.created = d.get("created", time.time())
        # Миграция старых форматов
        for p in d.get("poses", []):
            t = p.get(K_TIME, p.get("time", p.get("timestamp", 0.0)))
            pts = p.get(K_POINTS, p.get("points", p.get("landmarks", {})))
            dance.poses.append({K_TIME: float(t), K_POINTS: pts})
        return dance

def save_dance(dance, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dance.to_dict(), f, ensure_ascii=False, indent=2)

def load_dance(path):
    with open(path, "r", encoding="utf-8") as f:
        return Dance.from_dict(json.load(f))
