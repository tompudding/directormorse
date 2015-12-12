import numpy as np
import threading
import multiprocessing
import sys

english_to_morse = {
        'A': '.-',              'a': '.-',
        'B': '-...',            'b': '-...',
        'C': '-.-.',            'c': '-.-.',
        'D': '-..',             'd': '-..',
        'E': '.',               'e': '.',
        'F': '..-.',            'f': '..-.',
        'G': '--.',             'g': '--.',
        'H': '....',            'h': '....',
        'I': '..',              'i': '..',
        'J': '.---',            'j': '.---',
        'K': '-.-',             'k': '-.-',
        'L': '.-..',            'l': '.-..',
        'M': '--',              'm': '--',
        'N': '-.',              'n': '-.',
        'O': '---',             'o': '---',
        'P': '.--.',            'p': '.--.',
        'Q': '--.-',            'q': '--.-',
        'R': '.-.',             'r': '.-.',
        'S': '...',             's': '...',
        'T': '-',               't': '-',
        'U': '..-',             'u': '..-',
        'V': '...-',            'v': '...-',
        'W': '.--',             'w': '.--',
        'X': '-..-',            'x': '-..-',
        'Y': '-.--',            'y': '-.--',
        'Z': '--..',            'z': '--..',
        '0': '-----',           ',': '--..--',
        '1': '.----',           '.': '.-.-.-',
        '2': '..---',           '?': '..--..',
        '3': '...--',           ';': '-.-.-.',
        '4': '....-',           ':': '---...',
        '5': '.....',           "'": '.----.',
        '6': '-....',           '-': '-....-',
        '7': '--...',           '/': '-..-.',
        '8': '---..',           '(': '-.--.-',
        '9': '----.',           ')': '-.--.-',
        ' ': ' ',               '_': '..--.-',
}

morse_to_english = {morse:english for english,morse in english_to_morse.iteritems()}

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
    LETTER_THRESHOLD = 400
    DOT_TIME = 180
    def __init__(self):
        self.on_times = []
        self.guess = []
        self.last_on = None

    def key_down(self, t):
        self.last_on = t

    def key_up(self, t):
        duration = t - self.last_on
        self.on_times.append( (self.last_on, duration) )
        if duration < self.DOT_TIME:
            self.guess.append('.')
        else:
            self.guess.append('-')
        sys.stdout.flush()
        self.last_on = None

    def process(self):
        try:
            out = morse_to_english[''.join(self.guess)]
        except KeyError:
            out = '?'
        print ''.join(self.guess) + ':' + out
        self.on_times = []
        self.guess = []


    def update(self, t):
        if self.last_on is None and self.on_times:
            #It's off and we've got some in the bank
            last_on,duration = self.on_times[-1]
            last_off = last_on + duration
            duration = t - last_off
            if duration > self.LETTER_THRESHOLD:
                self.process()


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

