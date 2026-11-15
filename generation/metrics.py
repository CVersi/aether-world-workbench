"""Physical world measurements and playability checks.

This module knows nothing about Pygame. It can later feed a Unity terrain mesh,
gameplay traversal rules, or a headless batch generator for testing many seeds.
"""

import math
from collections import deque

from config import DEEP, SHALLOW


def calculate_height_and_slope(noise_heights, size, meters_per_tile,
                               vertical_span_meters, sea_level):
    """Convert noise elevations into meters, then estimate local slope angles.

    Horizontal cell spacing is `meters_per_tile` in BOTH X and Z directions.
    Height is measured relative to the water threshold (sea level = 0 m).
    Negative heights represent lakebeds and underwater terrain.

    The central-difference gradient uses nearby heights to approximate
    dh/dx and dh/dz. At world boundaries, indices are clamped to avoid
    reading outside the heightmap. `atan(gradient)` converts rise/run to
    an angle in degrees. This is a simplified terrain slope, not collision.
    """
    if meters_per_tile <= 0 or vertical_span_meters <= 0:
        raise ValueError("Physical tile size and vertical span must be positive")

    heights = [round((value-sea_level)*vertical_span_meters, 3)
               for value in noise_heights]
    slopes = [0.0] * (size*size)
    for y in range(size):
        y0,y1 = max(0,y-1),min(size-1,y+1)
        for x in range(size):
            x0,x1 = max(0,x-1),min(size-1,x+1)
            dzdx = (heights[y*size+x1]-heights[y*size+x0]) / ((x1-x0 or 1)*meters_per_tile)
            dzdy = (heights[y1*size+x]-heights[y0*size+x]) / ((y1-y0 or 1)*meters_per_tile)
            slopes[y*size+x] = round(math.degrees(math.atan(math.hypot(dzdx,dzdy))),2)
    return heights, slopes


def analyze_world(terrain, slope_degrees, size, meters_per_tile,
                  settlements, max_walking_slope=35.0,
                  max_building_slope=12.0):
    """Compute navigation/connectivity metrics without changing any terrain.

    An area is walkable when it is not deep water and its local slope is
    within the chosen walking limit. This means a flat high-altitude plateau
    may be accessible while a steep lowland embankment is not.

    A flood fill finds the *largest connected* accessible region. This is
    much more meaningful than reporting only how many cells are walkable.
    """
    length = size*size
    accessible = bytearray(length)
    buildable_count = 0
    for k in range(length):
        land = terrain[k] != DEEP
        if land and slope_degrees[k] <= max_walking_slope:
            accessible[k] = 1
        if land and terrain[k] != SHALLOW and slope_degrees[k] <= max_building_slope:
            buildable_count += 1

    visited = bytearray(length)
    largest = 0
    for k in range(length):
        if not accessible[k] or visited[k]:
            continue
        visited[k] = 1
        queue = deque([k])
        count = 0
        while queue:
            cur = queue.popleft()
            count += 1
            x,y = cur%size,cur//size
            for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0 <= xx < size and 0 <= yy < size:
                    nxt = yy*size+xx
                    if accessible[nxt] and not visited[nxt]:
                        visited[nxt] = 1
                        queue.append(nxt)
        largest = max(largest,count)

    walkable = sum(accessible)
    distances = []
    for i, a in enumerate(settlements):
        for b in settlements[i+1:]:
            ax,ay = a["center"]
            bx,by = b["center"]
            kilometers = math.hypot(ax-bx,ay-by)*meters_per_tile/1000
            distances.append(kilometers)

    return {
        "physical_width_km": round(size*meters_per_tile/1000,3),
        "physical_area_km2": round((size*meters_per_tile/1000)**2,3),
        "walkable_percent": round(walkable/length*100,2),
        "connected_percent_of_walkable": round(largest/max(1,walkable)*100,2),
        "buildable_percent": round(buildable_count/length*100,2),
        "steep_percent": round(sum(s>max_walking_slope for s in slope_degrees)/length*100,2),
        "settlement_min_distance_km": round(min(distances),2) if distances else None,
        "settlement_max_distance_km": round(max(distances),2) if distances else None,
    }
