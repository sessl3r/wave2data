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

from dataclasses import dataclass, field

TIMEMAP = {'s': 1, 'ms': 1e-3, 'us': 1e-6, 'ns': 1e-9, 'ps': 1e-12, 'fs': 1e-15}


@dataclass
class Signal:
    """ A digital signal or vector """
    name: str
    length: int
    handle: dict = field(default=None, repr=False)
    value: bytes = None

    def __post_init__(self):
        self.alias = self.name.split('.')[-1]

    def __repr__(self):
        if isinstance(self.value, bool):
            value = int(self.value)
        else:
            value = self.value.hex()
        return f"Signal({self.alias}={value} length={self.length})"

    def set(self, handle, value):
        """ set/update value of the signal or the subsignal """
        if handle not in self.handle.values():
            return False
        # we have one signal without subsignals
        if len(self.handle) == 1 and not self.length == 1:
            if self.length == 1:
                if isinstance(value, bool):
                    self.value = value
                elif isinstance(value, str):
                    self.value = bool("1" == value)
            else:
                if isinstance(value, str):
                    if len(value) % 2:
                        value = "0" + value
                    self.value = bytes.fromhex(value)
                else:
                    self.value = value
            return True
        # we have vector signal using bit subsignals
        for index, val in self.handle.items():
            if val == handle:
                if isinstance(self.value, bool):
                    self.value = value != 0
                elif value != 0:
                    self.value = self.set_bit(self.value, index)
                else:
                    self.value = self.clr_bit(self.value, index)
                return True
        return False

    def set_bit(self, a: bytes, index: int):
        """ set a bit in the values bytes """
        return (int.from_bytes(a, 'big') | int(1 << index)).to_bytes(
                len(a), 'big')

    def clr_bit(self, a: bytes, index: int):
        """ clr a bit in the values bytes """
        return (int.from_bytes(a, 'big') & ~int(1 << index)).to_bytes(
                len(a), 'big')


@dataclass(repr=False)
class Sample:
    """ Wrapper holding the values and timestamp of several signals """
    timestamp: int
    signals: dict = field(default_factory=list)

    def __post_init__(self):
        for signal in self.signals.values():
            setattr(self, signal.name, signal)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}"
            f"(@{self.timestamp} {list(self.signals.values())})"
        )

    @property
    def timestamp_str(self):
        for name, value in TIMEMAP.items():
            timestamp = self.timestamp * (1 / value)
            if timestamp > 10:
                return f"{timestamp:.3f}{name}"
        return f"{timestamp:.03f}{name}"
