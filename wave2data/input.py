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
import csv
# import pylibfst
import re
from vcd.reader import TokenKind, tokenize
from .wave import Sample, Signal, TIMEMAP


class WaveInput(ABC):
    """ Baseclass for waveform input """

    def __init__(self, filename: str):
        self._filename = filename
        self._signals = {}
        self._filter = self._signals

    def __repr__(self):
        ret = f"<{self.__class__.__name__} with signals: "
        for s in self.signals.values():
            ret += f"{s} "
        return f"{ret}>"

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

    def get(self, compare: str, regex=False):
        """ get list of signals by matching against regex or substr """
        ret = []
        for signal in self.signals.values():
            if regex and re.match(compare, signal.name):
                ret.append(signal)
            elif not regex and compare in signal.name:
                ret.append(signal)
        return ret

    def get_dict(self, compare: str, regex=False):
        """ get dict {name: signal} of signals by matching against regex """
        temp = self.get(compare, regex=False)
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

    def __init__(self, filename: str):
        super().__init__(filename)
        self._vcd = tokenize(open(filename, "rb"))
        self._create_signals()
        self._set_init_values()
        self.timestamp = 0

    def _create_signals(self):
        """ find and add defined signals and subsignals """
        scope = ""
        for token in self._vcd:
            if token.kind is TokenKind.SCOPE:
                scope += token.data.ident
            elif token.kind is TokenKind.UPSCOPE:
                scope = '.'.join(scope.split('.')[:-2])
            elif token.kind is TokenKind.VAR:
                if len(scope):
                    name = f"{scope}.{token.data.reference}"
                else:
                    name = token.data.reference
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
                self.timeval = magnitude * TIMEMAP[unit]
            elif token.kind is TokenKind.ENDDEFINITIONS:
                return

    def _set_init_values(self):
        """ set all values initially to zero """
        for s in self.signals.values():
            if s.length > 1:
                s.value = bytes((s.length+8-1)//8)
            else:
                s.value = False

    def __iter__(self):
        """ iterate through VCD file

        reads tokens from the VCD file and if time changes and values changed
        yields the next value.

        """
        updated = False
        for token in self._vcd:
            # On next timestamp we yield samples if anything changed
            if token.kind is TokenKind.CHANGE_TIME:
                if updated:
                    yield Sample(self.timestamp, self.signals)
                    updated = False
                self.timestamp = token.data * self.timeval
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
                yield token
            # Print all unhandled tokens
            elif token.kind not in [TokenKind.END, TokenKind.DUMPVARS]:
                yield token


class QuartusCSVInput(WaveInput):
    """ Quartus CSV wavefrom input:

    Reads CSV files generated by Quartus SignalTap

    """

    def __init__(self, filename: str):
        super().__init__(filename)
        self._csv = csv.reader(open(filename, "r"))
        self._create_signals()

    def _create_signals(self):
        parser_state = None
        signals = []
        for line in self._csv:
            if not len(line):
                continue
            if line[0] == 'Groups:':
                parser_state = 'groups'
                continue
            elif line[0] == 'Data:':
                parser_state = 'data'
                continue
            if parser_state == 'data':
                for idx in range(len(line)):
                    if 'time unit' in line[idx]:
                        continue
                    if len(line[idx]) < 2:
                        continue
                    ret = self._signalname_parse(line[idx], signals)
                    if not ret:
                        continue
                    signals.append(ret['name'])
                    if ret['length'] > 1:
                        initval = bytes((ret['length']+8-1)//8)
                    else:
                        initval = False
                    self.signals[ret['name']] = Signal(ret['name'],
                                                       ret['length'],
                                                       {0: idx}, initval)
                break

    def _signalname_parse(self, text: str, known: []):
        splittext = text.replace(" =", "").replace('|', '.')
        splittext = splittext.replace(' ', '').split('[')
        name = splittext[0]
        length = 1
        if len(splittext) > 1:
            rangestr = splittext[1][:-1]
            if '..' in rangestr:
                rangestr = rangestr.split('..')
                length = int(rangestr[0]) + 1
            else:
                length = 1
        if name in known:
            return None
        return {'name': name, 'length': length}

    def __iter__(self):
        for line in self._csv:
            for idx in range(len(line))[1:]:
                value = line[idx].replace(' ', '')
                if 'X' in value:
                    continue  # TODO: do this correct....
                for signal in self.signals.values():
                    if signal.set(idx, value):
                        continue
            yield Sample(int(line[0]), self.signals)
