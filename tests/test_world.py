"""Small tests that catch accidental behavior changes while refactoring."""
import tempfile
import unittest
from pathlib import Path

from config import GRASS, DEEP, Parameters
from generation.algorithms import water_components, find_route
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


if __name__ == '__main__':
    unittest.main()
