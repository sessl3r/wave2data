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


@dataclass
class Sample:
    """ Wrapper holding the values and timestamp of several signals """
    timestamp: int
    signals: dict = field(default_factory=list)

    def __post_init__(self):
        for signal in self.signals.values():
            setattr(self, signal.name, signal)
