import numpy as np
import threading
import multiprocessing
import sys
import ui
import globals
from globals.types import Point

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
        '5': '.....',           ">": '.----.',
        '6': '-....',           '-': '-....-',
        '7': '--...',           '/': '-..-.',
        '8': '---..',           '(': '-.--.-',
        '9': '----.',           ')': '-.--.-',
        ' ': ' ',               '_': '..--.-',
        '\n' : ' ',
}

morse_to_english = {morse:english for english,morse in english_to_morse.iteritems()}

class Player(object):
    def callback(self, outdata, frames, time, status):
        if not self.playing or self.broken:
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

    def run(self, conn, freq):
        import sounddevice as sd
        import generate
        self.tone = generate.GenerateTone(freq=freq, vol=1.0/400000)
        self.playing = False
        self.running = True
        self.broken = False
        self.pos = 0
        self.thread = threading.Thread(target=self.input_thread, args=(conn, ))
        self.thread.start()
        print sd.query_devices()
        print sd.default.device
        #raise SystemExit()
        with sd.OutputStream(channels=1, callback=self.callback,samplerate=48000, blocksize=2048, latency='low') as stream:
            while self.running:
                sd.sleep(1000)

        self.thread.join()


class Morse(object):
    LETTER_THRESHOLD = 2000
    DOT_TIME = 180
    DASH_TIME = DOT_TIME*3
    WORD_THRESHOLD = DOT_TIME*7
    PLAY_DOT_TIME = 60
    PLAY_DASH_TIME = PLAY_DOT_TIME*3
    def __init__(self):
        self.morse_light = None
        self.reset()

    def register_bars(self, letter_bar, word_bar):
        self.letter_bar = letter_bar
        self.word_bar = word_bar

    def register_light(self, light):
        self.light = light

    def key_down(self, t):
        self.last_on = t
        self.set_letter_bar(1)
        self.light.TurnOn()
        if self.morse_light:
            self.morse_light.on = True

    def key_up(self, t):
        if self.last_on is None:
            return
        self.light.TurnOff()
        if self.morse_light:
            self.morse_light.on = False
        duration = t - self.last_on
        self.on_times.append( (self.last_on, duration) )
        if duration < self.DOT_TIME:
            self.guess.append('.')
        else:
            self.guess.append('-')
        sys.stdout.flush()
        self.last_on = None

    def process(self):
        t = globals.time
        try:
            out = morse_to_english[''.join(self.guess)]
        except KeyError:
            out = '?'
        #print ''.join(self.guess) + ':' + out
        self.on_times = []
        self.guess = []
        self.last_processed = t
        return out

    def reset(self):
        self.on_times = []
        self.guess = []
        self.last_on = None
        self.last_processed = None
        self.playing = None
        self.play_sequence = None
        self.letter_bar = None
        self.word_bar = None
        self.morse_light = None

    def playback(self, t):
        if self.play_sequence is None:
            return False
        if not self.play_sequence:
            self.reset()
            return None

        key,start,duration = self.play_sequence[0]
        #print start,duration,t,self.playing
        if t < start:
            return True

        elif t < start + duration:
            if self.playing is None:
                self.key_down(t)
                self.playing = (key, start, duration)
            return True

        else:
            #We've done this one
            self.playing = None
            self.key_up(t)
            self.play_sequence.pop(0)
            return key if key is not None else False

    def set_word_bar(self,level):
        if self.word_bar:
            self.word_bar.SetBarLevel(level)

    def set_letter_bar(self,level):
        if self.letter_bar:
            self.letter_bar.SetBarLevel(level)

    def forming_letter(self):
        if self.on_times:
            return True
        else:
            return False

    def finish_letter(self):
        self.set_letter_bar(0)
        return self.process()

    def update(self, t):
        r = self.playback(t)
        if r or r is None:
            if r is True:
                #True from playback means it's still going, True from this function means it's the end of a word.
                #Bloody hacky LD code
                return False
            if r is None:
                return 4
            self.set_letter_bar(0)
            self.set_word_bar(0)
            if r == '\n':
                return True
            return r

        if self.last_on is None and self.on_times:
            #It's off and we've got some in the bank
            last_on,duration = self.on_times[-1]
            last_off = last_on + duration
            duration = t - last_off

    def play(self, message, morse_light=None):
        self.morse_light = morse_light
        if not message.endswith('\n>'):
            message += '\n>'
        if self.play_sequence:
            #We're playing something already, let's terminate it
            message = '\n>' + message
        self.play_sequence = []
        pos = globals.time
        for letter in message:
            for i,key in enumerate(english_to_morse[letter]):
                duration = self.PLAY_DOT_TIME if key == '.' else self.PLAY_DASH_TIME
                #This is the hackiest shit
                self.play_sequence.append( (letter if i == len(english_to_morse[letter])-1 else None, pos, duration) )
                pos += duration
                pos += self.PLAY_DOT_TIME
            pos += self.PLAY_DASH_TIME

    def create_key(self, elem, colour):
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        alpha_0 = alphabet[:18][::-1]
        alpha_1 = alphabet[18:][::-1]
        elem.text_items = []
        margin_height = 0.02
        margin_width  = 0.01
        height = (1.0-2*margin_height)/18
        width  = (1.0-2*margin_width)/3.4
        elem.border = ui.Border(elem,Point(0,0),Point(1,1),colour=colour,line_width=2)
        for i,alpha in enumerate((alpha_0,alpha_1)):
            for j in xrange(18):
                x = margin_width+i*width
                y = margin_height+j*height
                item = ui.TextBox(parent = elem,
                                  bl = Point(x,y),
                                  tr = Point(x+width*2,y+height),
                                  scale = 6,
                                  text = '%s : %s' % (alpha[j], english_to_morse[alpha[j]]),
                                  colour=colour)
                elem.text_items.append(item)

        #Now add the output information on the right
        info = [('UC','Unknown'),
                ('','Command'),
                ('BC','Bad'),
                ('','Command'),
                ('IN','Invalid'),
                ('','Number'),
                ('SR','Scan'),
                ('','Results:'),
                ('RB','Robot'),
                ('DS','Dstance'),
                ('BR','Bearing'),
                ('CC','Candy'),
                ('','Cane'),
                ('AX','Axe')]

        for i,(code,meaning) in enumerate(info):
            text = '%3s: %s' % (code,meaning)
            y = 17 - i
            item = ui.TextBox(parent=elem,
                              bl = Point(width*2,
                                         margin_height+y*height),
                              tr = Point(width*4,
                                         margin_height+(y+1)*height),
                              scale=6,
                              text=text,
                              colour=colour)
            elem.text_items.append(item)


class SoundMorse(Morse):

    def __init__(self, freq=700):
        super(SoundMorse,self).__init__()
        self.freq = freq

    def __enter__(self):
        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        self.player = Player()
        self.t = multiprocessing.Process(target=self.player.run, args=(self.child_conn, self.freq))
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

