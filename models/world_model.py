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
                    DEEP, ROCK, MOUNTAIN, ROAD, ANCIENT, PASSABLE_ON_FOOT, SAVE_DIR)
from generation.algorithms import water_components, find_route
from generation.hydrology import carve_rivers
from generation.ruins import place_ruins
from generation.metrics import calculate_height_and_slope, analyze_world

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
        self.rivers = []
        self.objects = []
        self.ruins = []
        self.height_m = []
        self.slope_degrees = []
        self.validation = {}

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
        # Rivers are formed before civilizations are placed, so settlements
        # can eventually use them as transport and freshwater opportunities.
        self.rivers = carve_rivers(self.terrain, self.elevation, n,
                                  self.seed, p.river_count)
        self._place_settlements()
        self._connect_settlements()
        self._place_ruins()
        self._place_objects()
        self._calculate_physical_metrics()

    def _calculate_physical_metrics(self):
        """Calculate metric heights, grades, and world playability statistics.

        We intentionally do this *after* terrain and road generation, because
        connectivity should describe the world the player actually receives.
        The raw OpenSimplex elevations remain unchanged for compatibility.
        """
        p = self.params
        self.height_m, self.slope_degrees = calculate_height_and_slope(
            self.elevation, p.size, p.meters_per_tile,
            p.vertical_span_meters, p.water_level)
        self.validation = analyze_world(
            self.terrain, self.slope_degrees, p.size,
            p.meters_per_tile, self.settlements,
            p.max_walking_slope, p.max_building_slope)

    def _place_ruins(self):
        """Add secluded ancient sites and partial trails after modern routes."""
        self.ruins, trails = place_ruins(
            self.terrain, self.elevation, self.params.size,
            self.seed, self.settlements, self.params.ruins_count)
        self.routes.extend(trails)

    def _place_settlements(self):
        """Reserve a settlement REGION without changing existing terrain.

        Each blueprint records a maximum development area. Future building
        placement will use small individual footprints inside that region.
        """
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
                # Sample the region. A settlement can include trees and paths,
                # but its center needs to be accessible and relatively flat.
                region = [self.terrain[yy*n+xx] for yy in range(y,y+h,2) for xx in range(x,x+w,2)]
                suitable = sum(t in (GRASS, FOREST, SAND) for t in region) / len(region)
                if suitable < 0.85 or self.terrain[cy*n+cx] not in (GRASS, FOREST, SAND):
                    continue
                # Favor low relief rather than flattening the entire lot.
                samples = [self.elevation[yy*n+xx] for yy in range(y,y+h,3)
                           for xx in range(x,x+w,3)]
                relief = max(samples) - min(samples)
                if relief > 0.35:
                    continue
                nearby = 0
                r = 16
                for yy in range(max(0,cy-r),min(n,cy+r),3):
                    for xx in range(max(0,cx-r),min(n,cx+r),3):
                        if self.terrain[yy*n+xx] in (SHALLOW,DEEP):
                            nearby += 1
                score = suitable + min(nearby, 8)*0.015 - relief
                if name == "story_hub":
                    score -= (abs(cx-n//2)+abs(cy-n//2))/n
                candidates.append((score,x,y))
            if not candidates:
                # Required hub fallback: find an existing walkable site,
                # do NOT rewrite a large rectangle of forest or water.
                if name == "story_hub":
                    valid = [(abs(xx-n//2)+abs(yy-n//2),xx,yy)
                             for yy in range(h//2,n-h//2)
                             for xx in range(w//2,n-w//2)
                             if self.terrain[yy*n+xx] in (GRASS,FOREST,SAND)]
                    if not valid:
                        raise RuntimeError("World contains no suitable story hub tile")
                    _,cx,cy = min(valid)
                    x,y = cx-w//2, cy-h//2
                else:
                    continue
            else:
                _,x,y = max(candidates)
            # Critically, DO NOT alter terrain here. The region is only metadata.
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
                              tuple(nearest["center"]), tuple(settlement["center"]),
                              elevation=self.elevation, seed=self.seed)
            if path:
                for k in path:
                    if self.terrain[k] not in (DEEP,MOUNTAIN):
                        self.terrain[k] = ROAD
                self.routes.append({"from": nearest["id"], "to": settlement["id"],
                                    "tiles": path, "type": "modern"})
                connected.append(settlement)

        # A single ancient route is an illustrative surviving infrastructure
        # link. It can use expensive mountain/water crossings that modern A*
        # refuses, without implying the present population can build them.
        hub = next((s for s in self.settlements if s["blueprint"] == "story_hub"), None)
        castle = next((s for s in self.settlements if s["blueprint"] == "castle"), None)
        if hub and castle:
            relic_path = find_route(self.terrain, self.params.size,
                                    tuple(hub["center"]), tuple(castle["center"]),
                                    elevation=self.elevation, seed=self.seed + 19,
                                    ancient=True)
            if relic_path:
                for k in relic_path:
                    self.terrain[k] = ANCIENT
                self.routes.append({"from": hub["id"], "to": castle["id"],
                                    "tiles": relic_path, "type": "ancient"})

    def _place_objects(self):
        """Place simple trees and boulders on valid terrain, away from town cores.

        The object records can later be mapped to sprite IDs or Unity prefabs.
        A coarse sampling grid and a seeded RNG prevent flicker/overcrowding.
        """
        n = self.params.size
        rng = random.Random(self.seed + 901)
        self.objects = []
        # Every three tiles, consider one slightly jittered location.
        for y in range(1,n-2,3):
            for x in range(1,n-2,3):
                xx = x + rng.randrange(3)
                yy = y + rng.randrange(3)
                tile = self.terrain[yy*n+xx]
                if any(abs(xx-s["center"][0]) < 5 and
                       abs(yy-s["center"][1]) < 5 for s in self.settlements):
                    continue
                if tile == FOREST and rng.random() < .72:
                    kind = "tree"
                elif tile == GRASS and rng.random() < .075:
                    kind = "tree"
                elif tile == ROCK and rng.random() < .25:
                    kind = "rock"
                else:
                    continue
                self.objects.append({"type":kind,"x":xx,"y":yy})

    def statistics(self):
        counts = Counter(self.terrain)
        walkable = sum(counts[k] for k in PASSABLE_ON_FOOT)
        return counts, walkable / max(1,len(self.terrain))*100

    def save(self, path):
        """Save fully materialized geography, not only a seed."""
        SAVE_DIR.mkdir(exist_ok=True)
        payload = {"format_version":1,"seed":self.seed,"parameters":asdict(self.params),
                   "terrain":self.terrain,"elevation":self.elevation,"moisture":self.moisture,
                   "settlements":self.settlements,"routes":self.routes,"lakes":self.lakes,
                   "objects":self.objects,"rivers":self.rivers,"ruins":self.ruins,
                   "height_m":self.height_m,"slope_degrees":self.slope_degrees,
                   "validation":self.validation}
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
        # Older v0.1 saves don't have environmental objects.
        model.objects = data.get("objects",[])
        model.rivers = data.get("rivers",[])
        model.ruins = data.get("ruins",[])
        # Old v0.1–v0.4 snapshots don't contain physical-height data.
        # Derive it from their saved noise elevations without regenerating
        # their geography or changing any roads, settlements, or ruins.
        if "height_m" in data and "slope_degrees" in data and "validation" in data:
            model.height_m = data["height_m"]
            model.slope_degrees = data["slope_degrees"]
            model.validation = data["validation"]
        else:
            model._calculate_physical_metrics()
        if len(model.terrain) != p.size*p.size:
            raise ValueError("Invalid saved terrain dimensions")
        return model


