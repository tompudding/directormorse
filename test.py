import numpy as np
import time
import threading
import pygame
import pygame.locals
import multiprocessing

parent_conn, child_conn = multiprocessing.Pipe()

class Player(object):
    def callback(self, outdata, frames, time, status):
        if not self.playing:
            outdata.fill(0)
            return
        if self.pos + frames > len(self.tone):
            #wrapping
            start = self.tone[self.pos:self.pos+frames]
            self.pos = frames-len(start)
            end = self.tone[:self.pos]
            new = np.append(start,end)
        else:
            new = self.tone[self.pos:self.pos+frames]
            self.pos += frames
        outdata[:, 0] = new

    def input_thread(self, conn):
        while self.running:
            command = conn.recv()
            if command == 'd':
                self.running = False
            else:
                self.playing = True if command == '1' else False


    def run(self, conn):
        import sounddevice as sd
        import generate
        self.tone = generate.GenerateTone(freq=700, vol=1.0/100000)
        self.playing = False
        self.running = True
        self.pos = 0
        self.thread = threading.Thread(target=self.input_thread, args=(conn, ))
        self.thread.start()

        with sd.OutputStream(channels=1, callback=self.callback, samplerate=48000, latency='low') as stream:
            while self.running:
                sd.sleep(100)
        self.thread.join()

player = Player()
t = multiprocessing.Process(target=player.run, args=(child_conn, ))
t.start()
playing = False

#We musn't initialise pygame until after our sound generator has run, otherwise it can't see the audio device
width,height = (1280, 720)
pygame.init()
pygame.display.set_caption('Synapse')
pygame.mouse.set_visible(0)
pygame.key.set_repeat(500,50)
screen = pygame.display.set_mode((width, height))
import pygame.mixer


while 1:
    for event in pygame.event.get():
        if event.type == pygame.locals.KEYDOWN:
            if event.key == pygame.locals.K_SPACE and not playing:
                parent_conn.send('1')
                playing = True
            elif event.key == pygame.locals.K_q:
                parent_conn.send('d')
                t.join()
                raise SystemExit
        if event.type == pygame.locals.KEYUP and playing:
            if event.key == pygame.locals.K_SPACE:
                parent_conn.send('0')
                playing = False


