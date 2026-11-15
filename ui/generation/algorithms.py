"""Reusable, engine-independent geography and pathfinding algorithms."""
import heapq
from collections import deque
from config import DEEP, MOUNTAIN, FOREST, ROCK, SHALLOW, ROAD, ANCIENT, TRAIL, RUINS
from opensimplex import OpenSimplex

def water_components(terrain, n):
    """4-connected water regions, avoiding diagonal-only connections."""
    seen = bytearray(n * n)
    regions = []
    for start in range(n * n):
        if seen[start] or terrain[start] != DEEP:
            continue
        region = []
        queue = deque([start])
        seen[start] = 1
        while queue:
            k = queue.popleft()
            region.append(k)
            x, y = k % n, k // n
            for xx, yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0 <= xx < n and 0 <= yy < n:
                    nxt = yy*n + xx
                    if not seen[nxt] and terrain[nxt] == DEEP:
                        seen[nxt] = 1
                        queue.append(nxt)
        regions.append(region)
    return regions


def find_route(terrain, n, start, goal, elevation=None, seed=0, ancient=False):
    """A* road routing with slope costs and smoothly varying terrain preferences.

    The optional elevation field penalizes steep roads. Low-frequency noise
    varies construction costs across a plain, favoring broad winding corridors.
    A road remains a four-connected sequence of traversable tiles.
    """
    a = start[1]*n + start[0]
    b = goal[1]*n + goal[0]
    frontier = [(0, a)]
    cost = {a: 0}
    parent = {}
    # Use its own deterministic noise field, independent of terrain generation.
    road_noise = OpenSimplex(seed + 731)
    # Cache preferences so the same coordinate is not resampled repeatedly.
    preferences = {}
    steps = 0
    while frontier and steps < n * n:
        _, u = heapq.heappop(frontier)
        steps += 1
        if u == b:
            path = []
            while u != a:
                path.append(u)
                u = parent[u]
            path.reverse()
            return path
        x, y = u % n, u // n
        for xx, yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if not (0 <= xx < n and 0 <= yy < n):
                continue
            v = yy*n+xx
            tile = terrain[v]
            if tile in (DEEP, MOUNTAIN) and not ancient:
                continue
            if v not in preferences:
                noise = road_noise.noise2(xx / 18.0, yy / 18.0)
                preferences[v] = (noise + 1) * 1.4
            slope = abs(elevation[v] - elevation[u]) if elevation is not None else 0
            # Clearing forest is comparatively easy with tools and labor.
            # Ancient routes can span difficult terrain via surviving works.
            tile_cost = {FOREST: 1.08, ROCK: 5, SHALLOW: 9,
                         DEEP: 19, MOUNTAIN: 22, ROAD: .75,
                         ANCIENT: .75, TRAIL: 1.1, RUINS: 2}
            step = (tile_cost.get(tile, 1)
                    + 50 * slope + preferences[v])
            new_cost = cost[u] + step
            if new_cost < cost.get(v, float("inf")):
                parent[v] = u
                cost[v] = new_cost
                priority = new_cost + abs(xx-goal[0]) + abs(yy-goal[1])
                heapq.heappush(frontier, (priority, v))
    return []


