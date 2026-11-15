"""Place secluded ruins and incomplete overgrown trails.

Ruins are not settlements: they deliberately prefer isolated wilderness.
Routes stop short of their final destination so discovery still matters.
"""

import math
import random

from config import FOREST, GRASS, ROCK, ROAD, ANCIENT, RUINS, TRAIL
from generation.algorithms import find_route


def place_ruins(terrain, elevation, size, seed, settlements, count):
    """Return (ruin_records, trail_records), modifying selected terrain cells.

    A ruin is a tiny irregular footprint rather than a huge square clearing.
    A trail ends 7–14 tiles away from it, representing a lost route whose
    final section has disappeared beneath vegetation.
    """
    n = size
    rng = random.Random(seed + 2809)
    ruins = []
    trails = []

    for _ in range(count):
        candidates = []
        for _attempt in range(450):
            x = rng.randrange(5, n - 5)
            y = rng.randrange(5, n - 5)
            k = y*n+x
            if terrain[k] not in (FOREST, ROCK, GRASS):
                continue
            if any(math.dist((x,y), s["center"]) < 28 for s in settlements):
                continue
            if any(math.dist((x,y), r["center"]) < 25 for r in ruins):
                continue
            # Prefer forested and rocky sites that have stayed secluded.
            score = (3 if terrain[k] == FOREST else 2 if terrain[k] == ROCK else 0)
            score += rng.random()
            candidates.append((score,x,y))
        if not candidates:
            break
        _,x,y = max(candidates)
        ruin_id = f"ruin_{len(ruins)+1}"
        ruins.append({"id":ruin_id,"center":[x,y],"kind":"forgotten_site"})

        if settlements:
            origin = min(settlements, key=lambda s:math.dist(s["center"],(x,y)))
            path = find_route(terrain,n,tuple(origin["center"]),(x,y),
                              elevation=elevation,seed=seed+len(ruins))
            # Leave the last part of the route hidden in wilderness.
            missing = rng.randint(7,14)
            visible = path[:-missing] if len(path)>missing+5 else []
            for k in visible:
                if terrain[k] in (FOREST,GRASS,ROCK):
                    terrain[k] = TRAIL
            if visible:
                trails.append({"from":origin["id"],"toward":ruin_id,
                               "type":"forgotten","tiles":visible,
                               "end": [visible[-1]%n,visible[-1]//n]})

        # A small irregular stone footprint; no broad rectangular clearing.
        for dx,dy in ((0,0),(-1,0),(1,0),(0,-1),(0,1),(1,1)):
            xx,yy = x+dx,y+dy
            k = yy*n+xx
            if terrain[k] in (FOREST,GRASS,ROCK):
                terrain[k] = RUINS

    return ruins,trails
