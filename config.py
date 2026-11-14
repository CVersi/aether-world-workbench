"""Shared constants, world presets and settlement blueprint footprints."""
from dataclasses import dataclass
from pathlib import Path
import pygame

SIZE = (1160, 760)
MAP_RECT = pygame.Rect(20, 75, 740, 650)
PANEL_X = 790
SAVE_DIR = Path(__file__).resolve().parent / "saved_worlds"
TERRAIN_NAMES = ["Grass", "Forest", "Sand", "Shallow water", "Deep water", "Rock", "Mountain", "Road"]
COLORS = [(115, 164, 82), (48, 109, 66), (205, 184, 119), (82, 161, 196),
          (40, 98, 156), (132, 130, 116), (100, 103, 114), (159, 124, 86)]
GRASS, FOREST, SAND, SHALLOW, DEEP, ROCK, MOUNTAIN, ROAD = range(8)
PASSABLE_ON_FOOT = {GRASS, FOREST, SAND, SHALLOW, ROCK, ROAD}


@dataclass
class Parameters:
    size: int = 256
    elevation_scale: float = 100.0
    detail_strength: float = 0.20
    water_level: float = -0.58
    mountain_level: float = 0.80
    moisture_scale: float = 73.0
    forest_threshold: float = 0.14
    min_beach_lake: int = 100
    shallow_lake_max: int = 35
    settlement_count: int = 9


BLUEPRINTS = {
    "story_hub": {"size": (20, 20), "label": "Story hub", "kind": "hub"},
    "village": {"size": (24, 20), "label": "Village", "kind": "settlement"},
    "outpost": {"size": (12, 12), "label": "Outpost", "kind": "outpost"},
    "farm": {"size": (30, 24), "label": "Farm", "kind": "farm"},
    "castle": {"size": (44, 40), "label": "Castle", "kind": "castle"},
}


