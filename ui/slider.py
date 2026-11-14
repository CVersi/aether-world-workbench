"""A minimal Pygame slider; UI only, no generation logic."""
import pygame
from config import PANEL_X

class Slider:
    def __init__(self, label, key, y, low, high, step):
        self.label, self.key = label, key
        self.y, self.low, self.high, self.step = y, low, high, step
        self.rect = pygame.Rect(PANEL_X, y + 22, 325, 13)
        self.dragging = False

    def handle(self, event, params):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = self.rect.inflate(10, 20).collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        if self.dragging and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            ratio = max(0, min(1, (event.pos[0] - self.rect.left) / self.rect.width))
            value = round((self.low + ratio * (self.high - self.low)) / self.step) * self.step
            if isinstance(getattr(params, self.key), int):
                value = int(round(value))
            else:
                value = round(value, 3)
            if getattr(params, self.key) != value:
                setattr(params, self.key, value)
                return True
        return False

    def draw(self, surface, font, params):
        value = getattr(params, self.key)
        text = font.render(f"{self.label}: {value}", True, (225, 231, 232))
        surface.blit(text, (PANEL_X, self.y))
        pygame.draw.line(surface, (86, 100, 111), self.rect.midleft, self.rect.midright, 4)
        ratio = (value - self.low) / (self.high - self.low)
        x = int(self.rect.left + ratio * self.rect.width)
        pygame.draw.circle(surface, (112, 204, 165), (x, self.rect.centery), 8)


