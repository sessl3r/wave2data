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
from dataclasses import dataclass, fields, field
from enum import Enum
import re
from .input import WaveInput
from .wave import Sample, TIMEMAP


class StreamError(Exception):
    pass


class KeepHandling(Enum):
    NONE = 0,
    MASK = 1,
    SHIFT = 2


@dataclass
class Packet:
    """ wrapper for a generic packet """

    name: str
    starttime: float
    data: bytes
    datawidth: int
    endtime: float = None

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name} " \
                f"{self.starttime_str}:{self.endtime_str})"

    def add(self, data: bytes, endtime: int = None):
        """ append data from a sample to this packet """
        assert isinstance(data, bytes), f"data of invalid class {type(data)}"
        self.data += data
        if endtime:
            self.endtime = endtime

    @property
    def starttime_str(self):
        return self._timestamp_str(self.starttime)

    @property
    def endtime_str(self):
        return self._timestamp_str(self.endtime)

    def _timestamp_str(self, timestamp: float):
        if not timestamp:
            return "NaN"
        for name, value in TIMEMAP.items():
            t = timestamp * (1 / value)
            if t > 10:
                return f"{t:.3f}{name}"
        return f"{t:.03f}{name}"


@dataclass(repr=False)
class AXISPacket(Packet):
    """ wrapper for a AXI Stream packet """

    # TODO: shall implement masking / shifting for keep

    keep: bytes = None
    beats: int = 0
    backpreasure: int = 0
    keep_mode: KeepHandling = KeepHandling.NONE

    def __post_init__(self):
        self.normdata = self._normalize_keep(self.data, self.keep)

    def _normalize_keep(self, data: bytes, keep: bytes):
        if not keep:
            return data
        if self.keep_mode == KeepHandling.MASK:
            raise NotImplementedError
        elif self.keep_mode == KeepHandling.SHIFT:
            assert len(keep) * 8 == len(data)
            for bidx in range(len(keep))[::-1]:
                for x in range(8):
                    idx = bidx * 8 + (7-x)
                    val = keep[bidx] & (1 << x) != 0
                    if not val:
                        data = data[:idx] + data[idx+1:]
        return data

    def __repr__(self):
        ret = super().__repr__()[:-1]
        ret += f" beats={self.beats} backpreasure={self.backpreasure}"
        if len(self.data) > 0:
            ret += f" data={self.data.hex(' ', 4)}"
        if hasattr(self, 'keep') and self.keep:
            ret += f" keep={self.keep.hex(' ', 4)}"
        return ret + ")"

    def add(self, data: bytes, keep: bytes = None, endtime: int = None):
        """ prepend data from a sample to this packet """
        self.normdata += self._normalize_keep(data, keep)
        super().add(data, endtime)
        if keep and self.keep:
            self.keep += keep


@dataclass
class AVStreamPacket(Packet):
    """ wrapper for Avalon Stream packet """

    strb: bytes = None
    beats: int = 0
    backpreasure: int = 0

    def __repr__(self):
        ret = f"{self.__class__.__name__}({self.name}" \
                f"@{self.starttime}:{self.endtime} "\
                f"beats={self.beats} "\
                f"backpreasure={self.backpreasure})"
        if len(self.data) > 0:
            ret += f" data={self.data.hex(' ', 4)})"
        if len(self.strb) > 0:
            ret += f" strb={self.strb.hex(' ', 4)})"
        return ret

    def add(self, data: bytes, strb: bytes = None, endtime: int = None):
        """ prepend data from a sample to this packet """
        super().add(data, endtime)
        if strb and self.strb:
            self.strb += self.strb


class CorundumTLP(AVStreamPacket):
    """ wrapper for corundums TLP packet format """

    hdr: bytes
    func_num: bytes
    bar_id: bytes


@dataclass
class WaveDecoder(ABC):
    """ common decoder class for WaveInput

    :param name: the name of the decoder
    :param waveinput: subclass of WaveInput to retrieve the samples from

    TODO: really need to find a cleaner way to get sample values etc.

    """

    name: str
    waveinput: WaveInput = field(repr=False)
    filter: str

    def __post_init__(self):
        self.signals = self.waveinput.get_dict(self.filter)
        self.allsignals = self.waveinput.signals
        self.__create_signals()

    def __create_signals(self):
        """ create attributes for each signal """
        self.names = {}
        for f in fields(self):
            if "name_" in f.name:
                name = f.name.replace("name_", "")
                regex = getattr(self, f.name)
                self.names[name] = None
                if not regex:
                    continue
                if regex.startswith('!'):
                    signals = self.allsignals
                    regex = regex[1:]
                else:
                    signals = self.signals
                for signal in signals.values():
                    if regex in signal.name or re.match(regex, signal.name):
                        setattr(self, name, signal.name)
                        self.names[name] = signal.name

    def __iter__(self):
        for sample in self.waveinput:
            temp = self.decode(sample)
            if not temp:
                continue
            yield temp

    @abstractmethod
    def decode(self, sample: Sample):
        pass


@dataclass
class StreamDecoder(WaveDecoder):

    def __post_init__(self):
        super().__post_init__()
        self.packet = None
        self.backpreasure = 0
        self.beats = 0
        self.lastvalues = None

    def handshake_decode(self, timestamp: float, values: dict,
                         lastvalues: dict) -> bool:
        if lastvalues['valid'] and not lastvalues['ready']:
            if not values['valid']:
                raise StreamError(f"{timestamp} valid dropped while not ready")
            if lastvalues['data'] != values['data']:
                raise StreamError(f"{timestamp} data changed while valid but not ready")
            if (lastvalues['keep'] is not None and values['keep'] is not None) and \
                    (lastvalues['keep'] != values['keep']):
                raise StreamError(f"{timestamp} keep changed while valid but not ready")


        if values['valid'] and not values['ready']:
            self.backpreasure += 1

        if values['valid'] and values['ready']:
            return True

        return False


@dataclass
class AXIStream(StreamDecoder):
    """ decoder for AXIStream transfers """

    name_valid: str = "tvalid"
    name_ready: str = "tready"
    name_last: str = None
    name_data: str = "tdata"
    name_keep: str = None
    name_clk: str = None
    keep_mode: KeepHandling = KeepHandling.SHIFT

    def decode(self, sample: Sample):
        values = {}
        if not self.lastvalues:
            self.lastvalues = values
        lastvalues = self.lastvalues
        for name, key in self.names.items():
            if key:
                values[name] = sample.signals[key].value
            else:
                values[name] = None

        if values['clk'] is not None:
            if not values['clk'] or lastvalues['clk']:
                self.lastvalues['clk'] = values['clk']
                return None

        self.lastvalues = values


        if not self.handshake_decode(sample.timestamp_str, values, lastvalues):
            return None

        self.beats += 1
        if not self.packet:
            self.packet = AXISPacket(self.name, starttime=sample.timestamp,
                                     keep_mode=self.keep_mode,
                                     data=values['data'], keep=values['keep'],
                                     datawidth=sample.signals[self.data].length)
        else:
            self.packet.add(data=values['data'], keep=values['keep'],
                            endtime=sample.timestamp)
        if values['last'] is None or values['last']:
            self.packet.beats = self.beats
            self.packet.backpreasure = self.backpreasure
            self.beats = 0
            self.backpreasure = 0
            temp = self.packet
            self.packet = None
            return temp


@dataclass
class AvalonStream(StreamDecoder):
    name_valid: str = "valid"
    name_ready: str = "ready"
    name_sop: str = "sop"
    name_eop: str = "eop"
    name_data: str = "data"
    name_strb: str = None

    def decode(self, sample: Sample, lastsample: Sample):
        valid = sample.signals[self.valid].value
        ready = sample.signals[self.ready].value
        eop = sample.signals[self.eop].value
        data = sample.signals[self.data].value
        strb = None
        if hasattr(self, 'strb'):
            strb = sample.signals[self.strb].value
        lastvalid = lastsample.signals[self.valid].value
        lastready = lastsample.signals[self.ready].value
        lastdata = lastsample.signals[self.data].value

        if not self.handshake_decode(sample.timestamp,
                                     valid, ready, data,
                                     lastvalid, lastready, lastdata):
            return None

        self.beats += 1
        if not self.packet:
            self.packet = AVStreamPacket("name", sample.timestamp,
                                         keep_mode=self.keep_mode,
                                         data=data, strb=strb,
                                         datawidth=sample.signals[self.tdata].length)
        else:
            self.packet.add(data=data, strb=strb, endtime=sample.timestamp)
        if eop:
            self.packet.beats = self.beats
            self.packet.backpreasure = self.backpreasure
            self.beats = 0
            self.backpreasure = 0
            temp = self.packet
            self.packet = None
            return temp
