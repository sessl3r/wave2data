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
from dataclasses import dataclass, fields
from enum import Enum
from .input import WaveInput
from .wave import Sample


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
    endtime: float = None

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name} " \
                f"@{self.starttime}:{self.endtime} {self.data.hex()})"

    def add(self, data: bytes, endtime: int = None):
        """ append data from a sample to this packet """
        self.data += data
        if endtime:
            self.endtime = endtime


@dataclass(repr=False)
class AXISPacket(Packet):
    """ wrapper for a AXI Stream packet """

    # TODO: shall implement masking / shifting for keep

    keep: bytes = None
    beats: int = 0
    backpreasure: int = 0
    tkeep_mode: KeepHandling = KeepHandling.NONE

    def __post_init__(self):
        # TODO: implement masking / shifting
        if self.tkeep_mode == KeepHandling.MASK:
            pass
        elif self.tkeep_mode == KeepHandling.SHIFT:
            pass

    def __repr__(self):
        ret = f"{self.__class__.__name__}({self.name}" \
                f"@{self.starttime}:{self.endtime} "\
                f"beats={self.beats} "\
                f"backpreasure={self.backpreasure})"
        if len(self.data) > 0:
            ret += f"\n    data: {self.data.hex(' ', 4)})"
        if hasattr(self, 'keep') and self.keep:
            ret += f"\n    keep: {self.keep.hex(' ', 4)})"
        return ret


    def add(self, data: bytes, keep: bytes = None, endtime: int = None):
        """ prepend data from a sample to this packet """
        self.data = data + self.data
        if keep and self.keep:
            self.keep = keep + self.keep
        if endtime:
            self.endtime = endtime


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
            ret += f"\n    data: {self.data.hex(' ', 4)})"
        if len(self.strb) > 0:
            ret += f"\n    strb: {self.strb.hex(' ', 4)})"
        return ret

    def add(self, data: bytes, strb: bytes = None, endtime: int = None):
        """ prepend data from a sample to this packet """
        self.data = data + self.data
        if strb and self.strb:
            self.strb = strb + self.strb
        if endtime:
            self.endtime = endtime


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

    """

    name: str
    waveinput: WaveInput

    def __post_init__(self):
        self.__create_signals()

    def __create_signals(self):
        """ create attributes for each signal """
        for field in fields(self):
            if "name_" in field.name:
                name = field.name.replace("name_", "")
                signals = self.waveinput.get(name)
                if not len(signals):
                    continue
                setattr(self, name, signals[0].name)

    def __iter__(self):
        lastsample = None
        for sample in self.waveinput:
            if not lastsample:
                lastsample = sample
            temp = self.decode(sample, lastsample)
            lastsample = sample
            if not temp:
                continue
            yield temp

    @abstractmethod
    def decode(self, sample: Sample):
        pass


class StreamDecoder(WaveDecoder):
    def __post_init__(self):
        super().__post_init__()
        self.packet = None
        self.backpreasure = 0
        self.beats = 0

    def handshake_decode(self, timestamp, valid, ready, lastvalid, lastready):
        # TODO: also should check for all other signals to not change when not
        # ready
        if lastvalid and not lastready and not valid:
            raise StreamError(f"@{timestamp} valid dropped while not ready")

        if valid and not ready:
            self.backpreasure += 1

        if valid and ready:
            return True

        return False


@dataclass
class AXIStream(StreamDecoder):
    """ decoder for AXIStream transfers """

    name_tvalid: str = "tvalid"
    name_tready: str = "tready"
    name_tlast: str = None
    name_tdata: str = "tdata"
    name_tkeep: str = None
    tkeep_mode: KeepHandling = KeepHandling.NONE

    def decode(self, sample: Sample, lastsample: Sample):
        valid = sample.signals[self.tvalid].value
        ready = sample.signals[self.tready].value
        last = None
        if self.tlast:
            last = sample.signals[self.tlast].value
        data = sample.signals[self.tdata].value
        keep = None
        if hasattr(self, 'tkeep'):
            keep = sample.signals[self.tkeep].value
        lastvalid = lastsample.signals[self.tvalid].value
        lastready = lastsample.signals[self.tready].value

        if not self.handshake_decode(sample.timestamp,
                                     valid, ready, lastvalid, lastready):
            return None

        self.beats += 1
        if not self.packet:
            self.packet = AXISPacket("name", starttime=sample.timestamp,
                                     tkeep_mode=self.tkeep_mode,
                                     data=data, keep=keep)
        else:
            self.packet.add(data=data, keep=keep, endtime=sample.timestamp)
        if not self.tlast or last:
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

        if not self.handshake_decode(sample.timestamp,
                                     valid, ready, lastvalid, lastready):
            return None

        self.beats += 1
        if not self.packet:
            self.packet = AVStreamPacket("name", sample.timestamp,
                                         data=data, strb=strb)
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
