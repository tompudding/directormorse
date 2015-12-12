import os, sys
import morse


def main(m):
    import pygame
    import pygame.locals
    #We musn't initialise pygame until after our sound generator has run, otherwise it can't see the audio device
    width,height = (1280, 720)
    pygame.init()
    pygame.display.set_caption('Synapse')
    pygame.mouse.set_visible(0)
    pygame.key.set_repeat(500,50)
    screen = pygame.display.set_mode((width, height))
    import pygame.mixer
    clock = pygame.time.Clock()
    clock.tick(60)

    playing = False
    while True:
        t = pygame.time.get_ticks()
        m.update(t)
        for event in pygame.event.get():
            if event.type == pygame.locals.QUIT:
                done = True
                break

            if event.type == pygame.locals.KEYDOWN:
                if event.key == pygame.locals.K_SPACE and not playing:
                    m.key_down(t)
                    playing = True
                elif event.key == pygame.locals.K_q:
                    raise SystemExit
            if event.type == pygame.locals.KEYUP and playing:
                if event.key == pygame.locals.K_SPACE:
                    m.key_up(t)
                    playing = False

with morse.SoundMorse() as m:
    main(m)
