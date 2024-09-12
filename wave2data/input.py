"""

Copyright (c)  Tobias Binkowski <sessl3r@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

from abc import ABC, abstractmethod
# import pylibfst
import re
from vcd.reader import TokenKind, tokenize
from .wave import Sample, Signal


class WaveInput(ABC):
    """ Baseclass for waveform input """

    def __init__(self, filename: str):
        self._filename = filename
        self._signals = {}
        self._filter = self._signals

    @abstractmethod
    def __iter__(self):
        pass

    def filter(self, data: [str, list]):
        """ set signals filter to given signals """
        if isinstance(data, str):
            self._filter = self.get_dict(data)
        else:
            self._filter = data

    @property
    def signals(self):
        return self._filter

    def get(self, regex: str):
        """ get list of signals by matching against regex or substr """
        ret = []
        for signal in self.signals.values():
            if regex in signal.name or re.match(regex, signal.name):
                ret.append(signal)
        return ret

    def get_dict(self, regex: str):
        """ get dict {name: signal} of signals by matching against regex """
        temp = self.get(regex)
        ret = {}
        for x in temp:
            ret[x.name] = x
        return ret


class VCDWaveInput(WaveInput):
    """ VCD waveform input:

    Creates signals with name [scope.]signal.
    The handle is a dict of sub-signals which together form the total signal.
    The dict-index is the bitoffset in the vector.

    """

    TIMEMAP = {
        's': 1, 'ms': 1e-3, 'us': 1e-6, 'ns': 1e-9, 'ps': 1e-12, 'fs': 1e-15
    }

    def __init__(self, filename: str):
        super().__init__(filename)
        self._vcd = tokenize(open(filename, "rb"))
        self._create_signals()
        self._set_init_values()

    def _create_signals(self):
        """ find and add defined signals and subsignals """
        scope = ""
        for token in self._vcd:
            if token.kind is TokenKind.SCOPE:
                scope += token.data.ident + '.'
            elif token.kind is TokenKind.UPSCOPE:
                scope = '.'.join(scope.split('.')[:-2]) + '.'
            elif token.kind is TokenKind.VAR:
                name = scope + token.data.reference
                handle = token.data.id_code
                length = token.data.size
                index = token.data.bit_index
                if not index:
                    index = 0
                if name in self.signals:
                    s = self.signals[name]
                    s.length += length
                    s.handle[index] = handle
                else:
                    self.signals[name] = Signal(name, length, {index: handle})
            elif token.kind is TokenKind.TIMESCALE:
                magnitude = token.timescale.magnitude.value
                unit = token.timescale.unit.value
                self.timeval = magnitude * self.TIMEMAP[unit]
            elif token.kind is TokenKind.ENDDEFINITIONS:
                return

    def _set_init_values(self):
        """ set all values initially to zero """
        for s in self.signals.values():
            if s.length > 1:
                s.value = bytes((s.length+8-1)//8)
            else:
                s.value = False

    def __repr__(self):
        ret = "<VCDWaveInput with signals: "
        for s in self.signals.values():
            ret += f"{s} "
        return f"{ret}>"

    def __iter__(self):
        """ iterate through VCD file

        reads tokens from the VCD file and if time changes and values changed
        yields the next value.

        """
        updated = False
        for token in self._vcd:
            # On next timestamp we yield samples if anything changed
            if token.kind is TokenKind.CHANGE_TIME:
                timestamp = token.data * self.timeval
                if updated:
                    yield Sample(timestamp, self.signals)
                    updated = False
                continue
            # Capture all changes which are relevant
            elif token.kind is TokenKind.CHANGE_SCALAR:
                handle = token.data.id_code
                value = token.data.value
                if value not in ['0', '1']:
                    value = '0'
                for signal in self.signals.values():
                    if signal.set(handle, int(value)):
                        updated = True
                        break
            # Print all comments
            elif token.kind is TokenKind.COMMENT:
                print(f"Comment: {token.data}")
            # Print all unhandled tokens
            elif token.kind not in [TokenKind.END, TokenKind.DUMPVARS]:
                print(token)
