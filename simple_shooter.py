import pygame
import sys
from pygame.locals import *

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
PLAYER_SIZE = 50
PLAYER_COLOR = (0, 128, 255)
BULLET_COLOR = (255, 0, 0)
BACKGROUND_COLOR = (0, 0, 0)
BULLET_SPEED = 10
FPS = 60

# Set up the display
window = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Simple 2D Shooter')

# Player class
def create_player():
    player = pygame.Rect(WIDTH // 2, HEIGHT - PLAYER_SIZE, PLAYER_SIZE, PLAYER_SIZE)
    return player

def move_player(player, key):
    if key[pygame.K_LEFT] and player.left > 0:
        player.move_ip(-5, 0)
    if key[pygame.K_RIGHT] and player.right < WIDTH:
        player.move_ip(5, 0)
    return player

# Bullet class
def create_bullet(player):
    bullet = pygame.Rect(player.centerx, player.top, 5, 10)
    return bullet

def move_bullet(bullets):
    for bullet in bullets[:]:  # Copy the list
        bullet.move_ip(0, -BULLET_SPEED)
        if bullet.bottom < 0:
            bullets.remove(bullet)
    return bullets

# Main loop
def main():
    player = create_player()
    bullets = []
    clock = pygame.time.Clock()
    
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_SPACE:
                    bullets.append(create_bullet(player))

        key = pygame.key.get_pressed()
        player = move_player(player, key)
        bullets = move_bullet(bullets)
        
        # Drawing
        window.fill(BACKGROUND_COLOR)
        pygame.draw.rect(window, PLAYER_COLOR, player)
        for bullet in bullets:
            pygame.draw.rect(window, BULLET_COLOR, bullet)
        pygame.display.flip()

        clock.tick(FPS)

if __name__ == '__main__':
    main()
