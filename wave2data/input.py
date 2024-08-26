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
import pylibfst
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
        """ get list of signals by matching against regex """

        ret = []
        for signal in self.signals.values():
            if regex in signal.name:
                ret.append(signal)
        return ret

    def get_dict(self, regex: str):
        """ get dict {name: signal} of signals by matching against regex """
        temp = self.get(regex)
        ret = {}
        for x in temp:
            ret[x.name] = x
        return ret

#    def cast_value(self, signal, value: str, default: int = None):
#        """ try to cast and default some values from signal levels """
#
#        # TODO: handle all x/z in nets and buses
#
#        if isinstance(value, int):
#            return bytes(value)
#
#        if signal.length > 1:
#            return bytes(int(value[i:i+8], 2)
#                         for i in range(0, len(value), 8))
#        if value in ['0', '1']:
#            return int(value)
#        if default is not None:
#            return default
#
#        raise ValueError(f"value {value} can not be decoded")


class FSTWaveInput(WaveInput):
    """ FST waveform input """

    def __init__(self, filename):
        super().__init__(filename)
        self._fst = pylibfst.lib.fstReaderOpen(self._filename.encode("UTF-8"))
        (unused, self._fstsignals) = pylibfst.get_scopes_signals2(self.fst)
        for s in self._fstsignals.by_name.values():
            if '[' in s.name and s.name.endswith(']'):
                temp = s.name.split('[')
                name = temp[0]
                offset = int(temp[1][:-1])
                subsignal = Signal(name, s.length, s.handle)
                # check if name already exists
# TODO: as in VCD part...
#                match = [n for n in self.signals if n.name == name]
#                if len(match):
#                    signal = match[0]
#                    signal.length += s.length
#                    signal.handle[offset] = subsignal
#                else:
#                    self._signals.append(Signal(name, s.length,
#                                                handle={offset: subsignal}))
#            else:
#                self._signals.append(Signal(s.name, s.length, handle=s.handle))

    def __repr__(self):
        ret = "<FSTWaveInput with signals: "
        for s in self.signals.values():
            ret += f"{s} "
        return f"{ret}>"

    def __iter__(self):
        self._timestamps = pylibfst.lib.fstReaderGetTimestamps(self.fst)
        self._timestamp_idx = 0
        return self

    def __next__(self):
        timestamp = self._timestamps.val[self._timestamp_idx]
        self._timestamp_idx += 1
        cbuf = pylibfst.ffi.new("char[4096]")
        ret = self.signals.copy()
        for signal in ret:
            if isinstance(signal.handle, dict):
                for offset, sub in signal.handle.items():
                    value = pylibfst.helpers.string(
                        pylibfst.lib.fstReaderGetValueFromHandleAtTime(
                            self.fst, timestamp, sub.handle, cbuf
                        )
                    )
                    value = self.cast_value(sub, value, default=0)
                    sub.value = value

            else:
                value = pylibfst.helpers.string(
                    pylibfst.lib.fstReaderGetValueFromHandleAtTime(
                        self.fst, timestamp, signal.handle, cbuf
                    )
                )
                value = self.cast_value(signal, value, default=0)
                signal.value = value

        return Sample(timestamp, ret)

    @property
    def fst(self):
        return self._fst

    def filter(self, data):
        if isinstance(data, str):
            signals = self.get(data)
        else:
            signals = data
        pylibfst.lib.fstReaderClrFacProcessMaskAll(self.fst)
        for signal in signals.values():
            if isinstance(signal.handle, dict):
                for h in signal.handle:
                    pylibfst.lib.fstReaderSetFacProcessMask(self.fst, h)
            else:
                pylibfst.lib.fstReaderSetFacProcessMask(self.fst, signal.handle)

        self._filter = signals


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
        """ TODO """
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
