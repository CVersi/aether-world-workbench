"""Pygame workbench UI: sliders, map preview, input and controls."""
import random
import json
from collections import Counter
from pathlib import Path
from datetime import datetime
import pygame

from config import (SIZE, MAP_RECT, PANEL_X, SAVE_DIR, COLORS,
                    GRASS, FOREST, SAND, SHALLOW, DEEP, ROCK, MOUNTAIN, ROAD,
                    Parameters)
from models.world_model import WorldModel
from ui.slider import Slider

class Workbench:
    def __init__(self, load_path=None):
        pygame.init()
        self.screen = pygame.display.set_mode(SIZE)
        pygame.display.set_caption("The Fractured Aether — World Workbench")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas",16)
        self.small = pygame.font.SysFont("consolas",13)
        self.title = pygame.font.SysFont("consolas",25,bold=True)
        self.params = Parameters()
        self.seed = 12345
        self.sliders = [
            Slider("Elevation scale","elevation_scale",112,30,230,5),
            Slider("Detail strength","detail_strength",166,0,0.6,.02),
            Slider("Water level","water_level",220,-.8,-.05,.01),
            Slider("Mountain level","mountain_level",274,.15,.95,.01),
            Slider("Moisture scale","moisture_scale",328,20,190,5),
            Slider("Forest threshold", "forest_threshold",382,-.5,.6,.02),
            Slider("Min lake size for beach","min_beach_lake",436,0,800,10),
            Slider("Max shallow lake size","shallow_lake_max",490,0,200,5),
            Slider("Settlement count","settlement_count",544,1,18,1),
            Slider("River sources","river_count",590,0,12,1),
        ]
        self.buttons = [("Generate",pygame.Rect(790,650,100,31)),
                        ("New seed",pygame.Rect(899,650,105,31)),
                        ("Save map",pygame.Rect(1013,650,110,31)),
                        ("Load latest",pygame.Rect(790,689,150,30))]
        self.layer = 0
        self.preview = None
        self.zoom = 1.0
        self.offset = pygame.Vector2()
        self.dirty = False
        self.notice = ""
        self.model = WorldModel(self.params,self.seed)
        if load_path:
            self.load(load_path)
        else:
            self.generate()

    def generate(self):
        self.model = WorldModel(self.params,self.seed)
        self.notice = "Generating world..."
        print(f"Generating {self.params.size}x{self.params.size} world; "
              f"{self.params.meters_per_tile:g} meters/tile...")
        self.model.generate()
        self.refresh_preview()
        self.dirty = False
        self.notice = f"Generated seed {self.seed}"

    def refresh_preview(self):
        n = self.model.params.size
        surface = pygame.Surface((n,n))
        surface.lock()
        try:
            for k,tile in enumerate(self.model.terrain):
                if self.layer == 1:
                    value = max(0,min(255,round((self.model.elevation[k]+1)*127)))
                    color = (value,value,value)
                elif self.layer == 2:
                    value = max(0,min(255,round((self.model.moisture[k]+1)*127)))
                    color = (45,value,180)
                elif self.layer == 4:
                    # Slope view: gentle = green, moderate = yellow,
                    # steep = red. The scale is in actual degrees.
                    slope = self.model.slope_degrees[k]
                    fraction = max(0,min(1,slope/45))
                    color = (round(60+195*fraction),
                             round(175-120*fraction),
                             round(65-45*fraction))
                else:
                    color = COLORS[tile]
                surface.set_at((k%n,k//n),color)
        finally:
            surface.unlock()
        self.preview = surface

    def save(self):
        filename = f"world_{self.seed}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.world.json.gz"
        path = SAVE_DIR / filename
        self.model.save(path)
        self.notice = f"Saved {filename}"
        print(f"Saved {path}")

    def load(self,path):
        try:
            self.model = WorldModel.load(path)
            self.params = self.model.params
            self.seed = self.model.seed
            self.layer = 0
            self.refresh_preview()
            self.zoom = 1.0
            self.offset.update(0,0)
            self.dirty = False
            self.notice = f"Loaded {Path(path).name}"
        except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
            self.notice = f"Load failed: {e}"

    def load_latest(self):
        files = sorted(SAVE_DIR.glob("*.world.json.gz"), key=lambda p:p.stat().st_mtime)
        if files:
            self.load(files[-1])
        else:
            self.notice = "No saved maps yet"

    def draw(self):
        s = self.screen
        s.fill((24,30,37))
        s.blit(self.title.render("World Workbench",True,(238,240,236)),(20,20))
        header = (f"Seed {self.seed}  •  {self.model.params.size}²  "
                  f"•  {self.model.params.meters_per_tile:g}m/tile  •  Layer {self.layer+1}/5")
        s.blit(self.font.render(header,True,(154,198,172)),(258,27))
        pygame.draw.rect(s,(10,19,22),MAP_RECT)
        # Fit the whole map at 1.0; zoom is relative to this fitted size.
        base = min(MAP_RECT.width,MAP_RECT.height)/self.model.params.size
        scale = max(.5,min(8,self.zoom))*base
        image_size = max(1,round(self.model.params.size*scale))
        image = pygame.transform.scale(self.preview,(image_size,image_size))
        center = pygame.Vector2(MAP_RECT.center)+self.offset
        pos = pygame.Vector2(center.x-image_size/2,center.y-image_size/2)
        old_clip = s.get_clip()
        s.set_clip(MAP_RECT)
        s.blit(image,(round(pos.x),round(pos.y)))
        if self.layer in (0,3):
            # Decorative resources are world data, not random UI pixels.
            # They therefore remain stable across zooming and save/load.
            for obj in self.model.objects:
                px = round(pos.x + (obj["x"] + .5)*scale)
                py = round(pos.y + (obj["y"] + .5)*scale)
                if obj["type"] == "tree":
                    color = (18, 63, 40)
                    radius = max(2, round(scale * 0.75))
                else:
                    color = (80, 84, 83)
                    radius = max(2, round(scale * 0.7))
                pygame.draw.circle(s, color, (px,py), radius)
            for site in self.model.settlements:
                x,y = site["center"]
                px,py = round(pos.x+x*scale),round(pos.y+y*scale)
                palette = {"story_hub":(255,226,108),"castle":(229,117,115),
                           "village":(244,244,233),"outpost":(212,163,235),"farm":(243,189,107)}
                pygame.draw.circle(s,palette.get(site["blueprint"],(255,255,255)),(px,py),5)
                if self.layer == 3:
                    s.blit(self.small.render(site["id"],True,(255,255,255)),(px+7,py-7))
            # Ruin markers: an X that shows the rough destination on the
            # workbench. The actual game map need not reveal these markers.
            for ruin in self.model.ruins:
                x,y = ruin["center"]
                px,py = round(pos.x+x*scale),round(pos.y+y*scale)
                pygame.draw.line(s,(255,211,137),(px-4,py-4),(px+4,py+4),2)
                pygame.draw.line(s,(255,211,137),(px-4,py+4),(px+4,py-4),2)
        s.set_clip(old_clip)
        pygame.draw.rect(s,(105,119,123),MAP_RECT,2)
        s.blit(self.font.render("Adjust settings and click Generate",True,(235,238,239)),(PANEL_X,69))
        for slider in self.sliders:
            slider.draw(s,self.font,self.params)
        for label,rect in self.buttons:
            pygame.draw.rect(s,(54,91,81),rect,border_radius=5)
            txt = self.small.render(label,True,(245,248,245))
            s.blit(txt,txt.get_rect(center=rect.center))
        counts,walkable = self.model.statistics()
        n = len(self.model.terrain)
        v = self.model.validation
        summary = (f"Forest {counts[FOREST]*100/n:.1f}%  | Walkable {v['walkable_percent']:.1f}%  "
                   f"| Connected {v['connected_percent_of_walkable']:.1f}%  "
                   f"| Buildable {v['buildable_percent']:.1f}%")
        s.blit(self.small.render(summary,True,(214,227,220)),(20,733))
        summary2 = (f"World {v['physical_width_km']:.2f}km wide  "
                    f"| Steep {v['steep_percent']:.1f}%  "
                    f"| [ ] tile meters  , . height  Z size  1–5 layers")
        s.blit(self.small.render(summary2,True,(172,191,188)),(20,748))
        status = self.notice + ("  [Unsaved settings]" if self.dirty else "")
        s.blit(self.small.render(status[:62],True,(214,185,124)),(790,729))
        pygame.display.flip()

    def run(self):
        running = True
        right_drag = False
        while running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_s:
                        self.save()
                    elif event.key == pygame.K_l:
                        self.load_latest()
                    elif event.key == pygame.K_f:
                        self.zoom = 1.0
                        self.offset.update(0,0)
                    elif pygame.K_1 <= event.key <= pygame.K_5:
                        self.layer = event.key-pygame.K_1
                        self.refresh_preview()
                    elif event.key == pygame.K_z:
                        # Adjust the planned world resolution without
                        # generating millions of tiles while a key is held.
                        sizes = (256,512,1024)
                        idx = sizes.index(self.params.size) if self.params.size in sizes else 0
                        self.params.size = sizes[(idx+1)%len(sizes)]
                        self.dirty = True
                        self.notice = f"Next world size: {self.params.size}; click Generate"
                    elif event.key in (pygame.K_LEFTBRACKET,pygame.K_RIGHTBRACKET):
                        delta = -2 if event.key == pygame.K_LEFTBRACKET else 2
                        self.params.meters_per_tile = max(2,min(64,self.params.meters_per_tile+delta))
                        self.dirty = True
                        self.notice = "Tile scale changed; click Generate"
                    elif event.key in (pygame.K_COMMA, pygame.K_PERIOD):
                        # This changes the vertical distance represented by
                        # one noise unit, not the horizontal tile spacing.
                        delta = -20 if event.key == pygame.K_COMMA else 20
                        self.params.vertical_span_meters = max(
                            20,min(600,self.params.vertical_span_meters+delta))
                        self.dirty = True
                        self.notice = (f"Elevation scale {self.params.vertical_span_meters:g}m; "
                                       "click Generate")
                elif event.type == pygame.MOUSEWHEEL and MAP_RECT.collidepoint(pygame.mouse.get_pos()):
                    self.zoom = max(.5,min(8,self.zoom * (1.2**event.y)))
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    right_drag = MAP_RECT.collidepoint(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                    right_drag = False
                elif event.type == pygame.MOUSEMOTION and right_drag:
                    self.offset += pygame.Vector2(event.rel)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for label,rect in self.buttons:
                        if rect.collidepoint(event.pos):
                            if label == "Generate":
                                self.generate()
                            elif label == "New seed":
                                self.seed = random.randint(0,2**31-1)
                                self.generate()
                            elif label == "Save map":
                                self.save()
                            elif label == "Load latest":
                                self.load_latest()
                for slider in self.sliders:
                    if slider.handle(event,self.params):
                        self.dirty = True
            self.draw()
        pygame.quit()


