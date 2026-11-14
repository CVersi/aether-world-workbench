"""One world snapshot: generation, settlement layout, routes and persistence.

Future iterations can move the individual pipeline stages into smaller
strategy objects without changing the data contract used by the UI.
"""
import gzip
import json
import math
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from opensimplex import OpenSimplex

from config import (Parameters, BLUEPRINTS, GRASS, FOREST, SAND, SHALLOW,
                    DEEP, ROCK, MOUNTAIN, ROAD, PASSABLE_ON_FOOT, SAVE_DIR)
from generation.algorithms import water_components, find_route

class WorldModel:
    """Global geography, settlements and roads; no Pygame rendering dependencies."""

    def __init__(self, params, seed):
        self.params, self.seed = params, seed
        self.terrain = []
        self.elevation = []
        self.moisture = []
        self.settlements = []
        self.routes = []
        self.lakes = []

    def generate(self):
        n = self.params.size
        p = self.params
        elevation_noise = OpenSimplex(self.seed)
        detail_noise = OpenSimplex(self.seed + 11)
        moisture_noise = OpenSimplex(self.seed + 29)
        self.elevation, self.moisture, self.terrain = [], [], []
        # Layer broad hills with smaller details, then calculate independent moisture.
        for y in range(n):
            for x in range(n):
                base = elevation_noise.noise2(x / p.elevation_scale, y / p.elevation_scale)
                detail = detail_noise.noise2(x / (p.elevation_scale * 0.27),
                                             y / (p.elevation_scale * 0.27))
                height = base + p.detail_strength * detail
                moisture = moisture_noise.noise2(x / p.moisture_scale, y / p.moisture_scale)
                self.elevation.append(round(height, 4))
                self.moisture.append(round(moisture, 4))
                if height < p.water_level:
                    tile = DEEP
                elif height > p.mountain_level:
                    tile = MOUNTAIN
                elif height > p.mountain_level - 0.12:
                    tile = ROCK
                elif moisture > p.forest_threshold:
                    tile = FOREST
                else:
                    tile = GRASS
                self.terrain.append(tile)

        # Convert small connected bodies to shallow, crossable water.
        # Beaches only grow around sufficiently large lakes, not puddles.
        regions = water_components(self.terrain, n)
        self.lakes = [len(region) for region in regions]
        for region in regions:
            if len(region) <= p.shallow_lake_max:
                for k in region:
                    self.terrain[k] = SHALLOW
            if len(region) >= p.min_beach_lake:
                for k in region:
                    x, y = k % n, k // n
                    for xx, yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                        if 0 <= xx < n and 0 <= yy < n:
                            neighbor = yy*n+xx
                            if self.terrain[neighbor] == GRASS:
                                self.terrain[neighbor] = SAND
        self._place_settlements()
        self._connect_settlements()

    def _place_settlements(self):
        """Score plausible areas, reserve rectangular lots and avoid overlap."""
        n, p = self.params.size, self.params
        rng = random.Random(self.seed + 87)
        self.settlements = []
        blueprints = ["story_hub", "castle", "village", "village", "farm", "outpost"]
        while len(blueprints) < p.settlement_count:
            blueprints.append(rng.choice(["village", "outpost", "farm"]))
        for name in blueprints[:p.settlement_count]:
            w, h = BLUEPRINTS[name]["size"]
            # Keep footprints proportional on small prototype maps.
            if w >= n//3 or h >= n//3:
                continue
            candidates = []
            for _ in range(400):
                x = rng.randint(3, n-w-4)
                y = rng.randint(3, n-h-4)
                cx, cy = x+w//2, y+h//2
                if any(abs(cx-s["center"][0]) < (w+s["size"][0])//2+10 and
                       abs(cy-s["center"][1]) < (h+s["size"][1])//2+10
                       for s in self.settlements):
                    continue
                # Sample entire lot; prefer land already flat and buildable.
                region = [self.terrain[yy*n+xx] for yy in range(y,y+h,2) for xx in range(x,x+w,2)]
                suitable = sum(t in (GRASS, FOREST, SAND) for t in region) / len(region)
                if suitable < 0.93:
                    continue
                nearby = 0
                r = 16
                for yy in range(max(0,cy-r),min(n,cy+r),3):
                    for xx in range(max(0,cx-r),min(n,cx+r),3):
                        if self.terrain[yy*n+xx] in (SHALLOW,DEEP):
                            nearby += 1
                score = suitable + min(nearby, 8)*0.015
                if name == "story_hub":
                    score -= (abs(cx-n//2)+abs(cy-n//2))/n
                candidates.append((score,x,y))
            if not candidates:
                # Try a smaller fallback for the mandatory hub only.
                if name == "story_hub":
                    x = n//2-w//2
                    y = n//2-h//2
                    for yy in range(y,y+h):
                        for xx in range(x,x+w):
                            self.terrain[yy*n+xx] = GRASS
                else:
                    continue
            else:
                _,x,y = max(candidates)
            # Reserve a clean, buildable town lot; detailed buildings come later.
            for yy in range(y,y+h):
                for xx in range(x,x+w):
                    self.terrain[yy*n+xx] = GRASS
            self.settlements.append({"id": f"{name}_{len(self.settlements)+1}",
                                     "blueprint": name, "x": x, "y": y,
                                     "size": [w,h], "center": [x+w//2,y+h//2]})

    def _connect_settlements(self):
        """Connect sites to closest existing road network where feasible."""
        self.routes = []
        if not self.settlements:
            return
        connected = [self.settlements[0]]
        for settlement in self.settlements[1:]:
            nearest = min(connected, key=lambda s:
                          math.dist(s["center"], settlement["center"]))
            path = find_route(self.terrain, self.params.size,
                              tuple(nearest["center"]), tuple(settlement["center"]))
            if path:
                for k in path:
                    if self.terrain[k] not in (DEEP,MOUNTAIN):
                        self.terrain[k] = ROAD
                self.routes.append({"from": nearest["id"], "to": settlement["id"],
                                    "tiles": path})
                connected.append(settlement)

    def statistics(self):
        counts = Counter(self.terrain)
        walkable = sum(counts[k] for k in PASSABLE_ON_FOOT)
        return counts, walkable / max(1,len(self.terrain))*100

    def save(self, path):
        """Save fully materialized geography, not only a seed."""
        SAVE_DIR.mkdir(exist_ok=True)
        payload = {"format_version":1,"seed":self.seed,"parameters":asdict(self.params),
                   "terrain":self.terrain,"elevation":self.elevation,"moisture":self.moisture,
                   "settlements":self.settlements,"routes":self.routes,"lakes":self.lakes}
        with gzip.open(path,"wt",encoding="utf-8") as f:
            json.dump(payload,f,separators=(",",":"))

    @classmethod
    def load(cls,path):
        with gzip.open(path,"rt",encoding="utf-8") as f:
            data = json.load(f)
        if data.get("format_version") != 1:
            raise ValueError("Unsupported world save format")
        p = Parameters(**data["parameters"])
        model = cls(p,int(data["seed"]))
        for key in ("terrain","elevation","moisture","settlements","routes","lakes"):
            setattr(model,key,data[key])
        if len(model.terrain) != p.size*p.size:
            raise ValueError("Invalid saved terrain dimensions")
        return model


