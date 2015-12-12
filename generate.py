# generate.py : contains tone-generating function
#
# Copyright (C) 2010  Sean McKean
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Taken from http://www.pygame.org/project-pitch+perfect-1689-2941.html, thanks Sean!

import sys
import os
import numpy as np


__all__ = [ 'GenerateTone' ]


notes_dct = {
        'a': 0.0, 'a#': 1.0, 'bb': 1.0, 'b': 2.0, 'c': 3.0, 'c#': 4.0,
        'db': 4.0, 'd': 5.0, 'd#': 6.0, 'eb': 6.0, 'e': 7.0, 'f': 8.0,
        'f#': 9.0, 'gb': 9.0, 'g': 10.0, 'g#': 11.0, 'ab': 11.0,
        }
def_length = 1.0 / 24.0
log440 = np.log2(440.0)


def GenerateTone( freq=480.0, vol=1.0, wave='sine', random=False,
                  length=def_length ):
    """ GenerateTone( freq=440.0, vol=1.0, wave='sine', random=False,
                      length=(1.0 / 24.0) ) -> pygame.mixer.Sound

        freq:  frequency in Hz; can be passed in as an int, float,
               or string (with optional trailing octave, defaulting to 4):
               'A4' (440 Hz), 'B#', 'Gb-1'
        vol:  relative volume of returned sound; will be clipped
              into range 0.0 -> 1.0
        wave:  int designating waveform returned;
               one of 'sine', 'saw', or 'square'
        random:  boolean value; if True will modulate frequency randomly
        length:  relative length of the Sound returned;
                 bigger values will result in more longer and more accurate
                 waveforms, but will also take longer to create;
                 the default value should be adequate for most uses
    """

    if type(freq) == str:
        i = 0
        while i < len(freq) and freq[i] not in '1234567890-':
            i += 1
        if i == 0:
            note = 'a'
        else:
            note = freq[: i].lower()
        if i == len(freq):
            octave = 4
        else:
            octave = int(freq[i: ])
        freq = 2.0 ** (log440 + notes_dct[note] / 12.0 + octave - 4)
    #vol = np.clip(vol, 0.0, 1.0)

    if random:
        # Modulate frequency randomly, playing in previous mode selected.
        freq += (np.random.rand() * 2.0 - 1.0) * freq / 8.0
    multiplier = int(freq * length)
    pb_freq = 48000
    length = max(1, int(float(pb_freq) / freq * multiplier))
    lin = np.linspace(0.0, multiplier, length, endpoint=False)

    if wave == 'sine':
        ary = np.sin(lin * 2.0 * np.pi)
    elif wave == 'saw':
        ary = 2.0 * ((lin + 0.5) % 1.0) - 1.0
    elif wave == 'square':
        ary = np.zeros(length)
        ary[lin % 1.0 < 0.5] = 1.0
        ary[lin % 1.0 >= 0.5] = -1.0
    else:
        print "wave parameter should be one of 'sine', 'saw', or 'square'."
        return None

    # If mixer is in stereo mode, double up the array information for
    # each channel.
    snd_ary = (ary * vol * float((1 << 15) - 1))
    #snd_ary = (snd_ary * vol).astype(np.int16)
    snd_ary = np.tile(snd_ary, 40)
    return snd_ary.astype(np.float16)
