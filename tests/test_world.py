"""Small tests that catch accidental behavior changes while refactoring."""
import tempfile
import unittest
from pathlib import Path

from config import (GRASS, FOREST, ROCK, ROAD, ANCIENT, DEEP,
                    SHALLOW, RUINS, TRAIL, Parameters)
from generation.algorithms import water_components, find_route
from generation.hydrology import carve_rivers
from generation.ruins import place_ruins
from models.world_model import WorldModel


class AlgorithmTests(unittest.TestCase):
    def test_connected_water_excludes_diagonal_adjacency(self):
        # Four-neighbor flood fill: diagonally touching water is separate.
        tiles = [DEEP, GRASS, GRASS,
                 GRASS, DEEP, GRASS,
                 GRASS, GRASS, DEEP]
        self.assertEqual(sorted(map(len, water_components(tiles, 3))), [1, 1, 1])

    def test_road_avoids_deep_water(self):
        tiles = [GRASS] * 25
        tiles[2 * 5 + 2] = DEEP
        route = find_route(tiles, 5, (0, 2), (4, 2))
        self.assertTrue(route)
        self.assertNotIn(12, route)

    def test_ancient_route_can_cross_water_barrier(self):
        # A complete vertical barrier makes an overland route impossible.
        tiles = [GRASS] * 25
        for y in range(5):
            tiles[y * 5 + 2] = DEEP
        self.assertFalse(find_route(tiles, 5, (0, 2), (4, 2)))
        ancient = find_route(tiles, 5, (0, 2), (4, 2), ancient=True)
        self.assertTrue(ancient)
        self.assertTrue(any(tiles[k] == DEEP for k in ancient))

    def test_rivers_have_connected_tiles(self):
        n = 32
        # Sloping ground draining to the bottom map edge.
        heights = [1 - y / n for y in range(n) for _ in range(n)]
        terrain = [GRASS] * (n*n)
        paths = carve_rivers(terrain, heights, n, seed=7, count=3)
        for path in paths:
            self.assertTrue(all(terrain[k] == SHALLOW for k in path))
            for a,b in zip(path,path[1:]):
                self.assertEqual(abs(a//n-b//n)+abs(a%n-b%n),1)

    def test_ruins_stay_away_from_settlements(self):
        n = 128
        terrain = [FOREST] * (n*n)
        height = [0.3] * (n*n)
        settlements = [{"id":"hub","center":[64,64]}]
        ruins,trails = place_ruins(terrain,height,n,19,settlements,4)
        self.assertTrue(ruins)
        for ruin in ruins:
            x,y = ruin['center']
            self.assertGreaterEqual((x-64)**2+(y-64)**2,28**2)
        for trail in trails:
            destination = next(r for r in ruins if r['id']==trail['toward'])
            end_x,end_y = trail['end']
            rx,ry = destination['center']
            self.assertNotEqual((end_x,end_y),(rx,ry))


class WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A small map keeps tests quick, while still running the real generator.
        cls.world = WorldModel(Parameters(size=64, settlement_count=3), 123)
        cls.world.generate()

    def test_world_dimensions(self):
        self.assertEqual(len(self.world.terrain), 64 * 64)
        self.assertEqual(len(self.world.elevation), 64 * 64)

    def test_deterministic_generation(self):
        other = WorldModel(Parameters(size=64, settlement_count=3), 123)
        other.generate()
        self.assertEqual(self.world.terrain, other.terrain)
        self.assertEqual(self.world.settlements, other.settlements)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'example.world.json.gz'
            self.world.save(path)
            restored = WorldModel.load(path)
            self.assertEqual(restored.terrain, self.world.terrain)
            self.assertEqual(restored.routes, self.world.routes)
            self.assertEqual(restored.settlements, self.world.settlements)
            self.assertEqual(restored.objects, self.world.objects)
            self.assertEqual(restored.rivers, self.world.rivers)
            self.assertEqual(restored.ruins, self.world.ruins)

    def test_settlements_do_not_erase_natural_terrain(self):
        # Generate a reference map without settlements/roads/objects.
        natural = WorldModel(Parameters(size=64, settlement_count=3), 123)
        natural._place_settlements = lambda: None
        natural._connect_settlements = lambda: None
        natural._place_ruins = lambda: None
        natural._place_objects = lambda: None
        natural.generate()
        # Roads may replace tiles, but settlements may not overwrite terrain.
        for before, after in zip(natural.terrain, self.world.terrain):
            if before != after:
                self.assertIn(after, (ROAD, ANCIENT, RUINS, TRAIL))

    def test_objects_follow_terrain_rules(self):
        n = self.world.params.size
        for obj in self.world.objects:
            terrain = self.world.terrain[obj['y'] * n + obj['x']]
            if obj['type'] == 'tree':
                self.assertIn(terrain, (GRASS, FOREST))
            elif obj['type'] == 'rock':
                self.assertEqual(terrain, ROCK)
            else:
                self.fail('Unknown decorative object')


if __name__ == '__main__':
    unittest.main()
