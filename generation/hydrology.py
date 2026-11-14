"""Experimental drainage routing for a finite global height map.

This is *not* a full hydrological simulator. It links upland source tiles to
existing lakes or the map boundary through a cost field that favors downhill
travel. Basins may require small artificial outlets; true erosion and flow
accumulation are future work.
"""

import heapq
import random
from opensimplex import OpenSimplex

from config import DEEP, MOUNTAIN, SHALLOW


def carve_rivers(terrain, elevation, size, seed, count):
    """Return river paths and mark their tiles as shallow water in place.

    Multi-source Dijkstra starts at lakes and map boundaries. Traveling from a
    source back through the predecessor links traces a connected outlet route.
    The uphill penalty discourages unnatural routes while still allowing a
    shallow depression to drain instead of creating a disconnected stream.
    """
    if count <= 0:
        return []

    n = size
    length = n * n
    distance = [float("inf")] * length
    downstream = [-1] * length
    queue = []
    meander_noise = OpenSimplex(seed + 2003)

    def outlet(k):
        x, y = k % n, k // n
        return terrain[k] == DEEP or x == 0 or y == 0 or x == n-1 or y == n-1

    for k in range(length):
        if outlet(k):
            distance[k] = 0.0
            heapq.heappush(queue, (0.0, k))

    while queue:
        cost, current = heapq.heappop(queue)
        if cost > distance[current]:
            continue
        x, y = current % n, current // n
        for xx, yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if not (0 <= xx < n and 0 <= yy < n):
                continue
            neighbor = yy*n+xx
            if terrain[neighbor] == MOUNTAIN:
                continue
            # Imagine flowing from neighbor to current: uphill is expensive.
            climb = max(0.0, elevation[current] - elevation[neighbor])
            # Gentle coherent variation avoids mathematically rigid lines
            # without allowing rivers to zigzag randomly at every tile.
            variation = (meander_noise.noise2(xx / 13, yy / 13) + 1) * .35
            new_cost = cost + 1.0 + 100.0 * climb + variation
            if new_cost < distance[neighbor]:
                distance[neighbor] = new_cost
                downstream[neighbor] = current
                heapq.heappush(queue, (new_cost, neighbor))

    rng = random.Random(seed + 1209)
    candidates = [k for k in range(length)
                  if elevation[k] > 0.15 and terrain[k] not in (MOUNTAIN, DEEP)
                  and downstream[k] >= 0 and distance[k] > n * 0.10]
    rng.shuffle(candidates)

    paths = []
    starts = []
    spacing_sq = max(14, n//7) ** 2
    for start in candidates:
        if len(paths) >= count:
            break
        sx, sy = start % n, start // n
        if any((sx-x)**2 + (sy-y)**2 < spacing_sq for x,y in starts):
            continue
        path = []
        cell = start
        reached_outlet = False
        while cell >= 0 and len(path) <= length:
            if terrain[cell] == DEEP:
                reached_outlet = True
                break
            path.append(cell)
            if downstream[cell] == -1:
                # This is a map-edge outlet; the last river tile is valid.
                reached_outlet = True
                break
            cell = downstream[cell]
        if len(path) < n // 10 or not reached_outlet:
            continue
        starts.append((sx,sy))
        paths.append(path)
        for k in path:
            if terrain[k] != DEEP:
                terrain[k] = SHALLOW

    return paths
