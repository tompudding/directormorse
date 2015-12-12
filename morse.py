import numpy as np
import threading
import multiprocessing

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
        self.tone = generate.GenerateTone(freq=700, vol=1.0/400000)
        self.playing = False
        self.running = True
        self.pos = 0
        self.thread = threading.Thread(target=self.input_thread, args=(conn, ))
        self.thread.start()

        with sd.OutputStream(channels=1, callback=self.callback, samplerate=48000, latency='low') as stream:
            while self.running:
                sd.sleep(100)
        self.thread.join()


class Morse(object):
    def __init__(self):
        self.on_times = []

    def key_down(self, t):
        pass

    def key_up(self, t):
        pass


class SoundMorse(Morse):
    def __enter__(self):
        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        self.player = Player()
        self.t = multiprocessing.Process(target=self.player.run, args=(self.child_conn, ))
        self.t.start()
        return self

    def key_down(self, t):
        self.parent_conn.send('1')
        super(SoundMorse, self).key_down(t)

    def key_up(self, t):
        self.parent_conn.send('0')
        super(SoundMorse, self).key_up(t)

    def __exit__(self, type, value, traceback):
        self.parent_conn.send('d')
        self.t.join()

