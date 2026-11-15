"""Experimental drainage routing for a finite global height map.

This is *not* a full hydrological simulator. It links upland source tiles to
existing lakes (or boundaries if no lakes exist) through a cost field that favors downhill
travel. Basins may require small artificial outlets; true erosion and flow
accumulation are future work.
"""

import heapq
import math
import random
from opensimplex import OpenSimplex

from config import DEEP, MOUNTAIN, SHALLOW


def _meander_path(path, terrain, n, seed):
    """Add broad bends to a drainage centerline, with endpoints fixed.

    The shortest-path drainage network establishes the *destination* first.
    This subsequent geometry pass displaces intermediate waypoints sideways
    with a low-frequency sinusoid. A small rasterizer reconnects the path.
    Blocked mountains/lakes trigger fallback to the original segment.

    This approximates visible meanders; it does not model sediment erosion.
    """
    if len(path) < 20:
        return path
    rng = random.Random(seed)
    amplitude = min(6.0, max(2.0, len(path) / 23))
    period = rng.uniform(28, 43)
    phase = rng.random() * math.tau
    points = [(k % n, k // n) for k in path]

    def raster_line(a, b):
        """Integer Bresenham; always includes both endpoints."""
        x0,y0 = a
        x1,y1 = b
        dx,dy = abs(x1-x0),abs(y1-y0)
        sx,sy = (1 if x0<x1 else -1),(1 if y0<y1 else -1)
        error = dx-dy
        cells = []
        while True:
            cells.append(y0*n+x0)
            if (x0,y0)==(x1,y1):
                break
            twice = 2*error
            old_x,old_y = x0,y0
            if twice > -dy:
                error -= dy
                x0 += sx
            if twice < dx:
                error += dx
                y0 += sy
            if x0 != old_x and y0 != old_y:
                # Add a cardinal step so the river never jumps diagonally.
                cells.append(old_y*n+x0)
        return cells

    waypoints = []
    for i in range(0,len(points),3):
        prev = points[max(0,i-5)]
        nxt = points[min(len(points)-1,i+5)]
        tx,ty = nxt[0]-prev[0],nxt[1]-prev[1]
        length = math.hypot(tx,ty) or 1
        # Fade displacement near source and outlet so connections are retained.
        taper = math.sin(math.pi*i/(len(points)-1))**1.2
        displacement = amplitude*math.sin(i*math.tau/period+phase)*taper
        x = round(points[i][0] - ty/length*displacement)
        y = round(points[i][1] + tx/length*displacement)
        x = min(n-1,max(0,x))
        y = min(n-1,max(0,y))
        waypoints.append((x,y))
    waypoints.append(points[-1])

    result = [path[0]]
    for i in range(1,len(waypoints)):
        segment = raster_line(waypoints[i-1],waypoints[i])
        if any(terrain[k] in (DEEP,MOUNTAIN) for k in segment[:-1]):
            # A bend must not cut through an obstacle; retain the safe route.
            return path
        result.extend(segment[1:])
    # Keep the original endpoint even after detours.
    if result[-1] != path[-1]:
        result.extend(raster_line((result[-1]%n,result[-1]//n),points[-1])[1:])
    return result


def carve_rivers(terrain, elevation, size, seed, count):
    """Return river paths and mark their tiles as shallow water in place.

    Multi-source Dijkstra starts at lakes, falling back to boundaries only
    when no lakes exist. Traveling from a
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

    has_lake = DEEP in terrain

    def outlet(k):
        x, y = k % n, k // n
        return terrain[k] == DEEP if has_lake else (
            x == 0 or y == 0 or x == n-1 or y == n-1)

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
            variation = (meander_noise.noise2(xx / 17, yy / 17) + 1) * 1.3
            new_cost = cost + 1.0 + 100.0 * climb + variation
            if new_cost < distance[neighbor]:
                distance[neighbor] = new_cost
                downstream[neighbor] = current
                heapq.heappush(queue, (new_cost, neighbor))

    rng = random.Random(seed + 1209)
    margin = max(3, n // 12)
    candidates = [k for k in range(length)
                  if elevation[k] > 0.15 and terrain[k] not in (MOUNTAIN, DEEP)
                  and margin <= k%n < n-margin
                  and margin <= k//n < n-margin
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
        path = _meander_path(path, terrain, n, seed + 41*len(paths))
        starts.append((sx,sy))
        paths.append(path)
        for k in path:
            if terrain[k] != DEEP:
                terrain[k] = SHALLOW

    return paths
