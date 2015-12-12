import numpy as np
import threading
import multiprocessing
import sys
import globals

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
        print sd.query_devices()
        print sd.default.device
        #raise SystemExit()
        with sd.OutputStream(channels=1, callback=self.callback,samplerate=48000, latency='low') as stream:
            while self.running:
                sd.sleep(1000)
        self.thread.join()


class Morse(object):
    LETTER_THRESHOLD = 400
    DOT_TIME = 180
    DASH_TIME = DOT_TIME*3
    WORD_THRESHOLD = DOT_TIME*7
    PLAY_DOT_TIME = 60
    PLAY_DASH_TIME = PLAY_DOT_TIME*3
    def __init__(self):
        self.on_times = []
        self.guess = []
        self.last_on = None
        self.last_processed = None
        self.playing = None
        self.play_sequence = []

    def key_down(self, t):
        self.last_on = t

    def key_up(self, t):
        if self.last_on is None:
            return
        duration = t - self.last_on
        self.on_times.append( (self.last_on, duration) )
        if duration < self.DOT_TIME:
            self.guess.append('.')
        else:
            self.guess.append('-')
        sys.stdout.flush()
        self.last_on = None

    def process(self, t):
        try:
            out = morse_to_english[''.join(self.guess)]
        except KeyError:
            out = '?'
        #print ''.join(self.guess) + ':' + out
        self.on_times = []
        self.guess = []
        self.last_processed = t
        return out

    def playback(self, t):
        if not self.play_sequence:
            return False

        while self.play_sequence:
            start,duration = self.play_sequence[0]
            #print start,duration,t,self.playing
            if t < start:
                return True

            elif t < start + duration:
                if self.playing is None:
                    self.key_down(t)
                    self.playing = (start, duration)
                return True

            else:
                #We've done this one
                self.playing = None
                self.key_up(t)
                self.play_sequence.pop(0)
        return False

    def update(self, t):
        if self.playback(t):
            return

        if self.last_on is None and self.on_times:
            #It's off and we've got some in the bank
            last_on,duration = self.on_times[-1]
            last_off = last_on + duration
            duration = t - last_off
            if duration > self.LETTER_THRESHOLD:
                return self.process(t)
        if self.last_on is None and not self.on_times and self.last_processed is not None:
            #It's off and there's nothing in the bank...
            duration = t - self.last_processed
            if duration > self.WORD_THRESHOLD:
                self.last_processed = None
                return True

    def play(self, message):
        self.play_sequence = []
        pos = globals.time
        for letter in message:
            for key in english_to_morse[letter]:
                duration = self.PLAY_DOT_TIME if key == '.' else self.PLAY_DASH_TIME
                self.play_sequence.append( (pos,duration) )
                pos += duration
                pos += self.PLAY_DOT_TIME
            pos += self.PLAY_DASH_TIME

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
        pass

