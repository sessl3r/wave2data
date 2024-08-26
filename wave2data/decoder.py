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
from .input import WaveInput
from .wave import Sample


class AXIStreamError(Exception):
    pass


class AVSFramingError(Exception):
    pass


@dataclass
class Packet:
    """ wrapper for a generic packet """

    name: str
    starttime: int
    data: bytes

    def __post_init__(self):
        self.endtime = self.starttime

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

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}" \
                f"@{self.starttime}:{self.endtime} "\
                f"beats={self.beats} "\
                f"backpreasure={self.backpreasure})" \
                f"\n    data: {self.data.hex()})"


    def add(self, data: bytes, keep: bytes = None, endtime: int = None):
        """ append data from a sample to this packet """
        self.data += data
        if keep and self.keep:
            self.keep += keep
        if endtime:
            self.endtime = endtime


class AvalonStreamPacket(Packet):
    """ wrapper for Avalon Stream packet """


#class AVSTLPPacket(AVSPacket):
#
#    def __init__(self, name: str, starttime: int, endtime: int = None,
#                 has_func_num: bool = False, has_bar_id: bool = False):
#        super().__init__(name, starttime, endtime)
#        self.hdr = bytes()
#        if has_func_num:
#            self.func_num = bytes()
#        if has_bar_id:
#            self.bar_id = bytes()
#
#    def __repr__(self):
#        return f"<AVSTLPPacket[{self.name}] @{self.starttime}:{self.endtime} {self.hdr.hex()} {self.data.hex()}>"
#
#    def add(self, data: bytes, starttime: int = None, endtime: int = None,
#            hdr: bytes = None, func_num: bytes = None, bar_id: bytes = None):
#        super().add(data, starttime, endtime)
#        if hdr:
#            self.hdr += hdr
#        if func_num:
#            self.func_num += func_num
#        if bar_id:
#            self.bar_id += bar_id


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
                setattr(self, name, self.waveinput.get(name)[0].name)

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


@dataclass
class AXIStream(WaveDecoder):
    """ decoder for AXIStream transfers """
    name_tvalid: str = "valid"
    name_tready: str = "ready"
    name_tlast: str = None
    name_tdata: str = "data"
    name_tkeep: str = None

    def __post_init__(self):
        super().__post_init__()
        self.packet = None
        self.backpreasure = 0
        self.beats = 0

    def decode(self, sample: Sample, lastsample: Sample):
        valid = sample.signals[self.tvalid].value
        ready = sample.signals[self.tready].value
        if self.tlast:
            last = sample.signals[self.tlast].value
        data = sample.signals[self.tdata].value
        lastvalid = lastsample.signals[self.tvalid].value
        lastready = lastsample.signals[self.tready].value

        if lastvalid and not lastready and not valid:
            raise AXIStreamError(f"@{sample.timestamp}\
                    AXI-Stream valid dropped while not ready")

        if valid and not ready:
            self.backpreasure += 1

        if not (valid and ready):
            return None

        self.beats += 1
        if not self.packet:
            self.packet = AXISPacket("name", sample.timestamp, data=data)
        else:
            self.packet.add(data, sample.timestamp)
        if not self.tlast or last:
            self.packet.beats = self.beats
            self.packet.backpreasure = self.backpreasure
            temp = self.packet
            self.packet = None
            return temp


#@dataclass
#class AvalonStream(WaveDecoder):
#    sig_name_valid: str = "valid"
#    sig_name_ready: str = "ready"
#    sig_name_sop: str = "sop"
#    sig_name_eop: str = "eop"
#    sig_name_data: str = "data"
#    sig_name_strb: str = None
#
#    def decode_valid_ready(self, sample, last):
#        """ check if sample contains valid data """
#        # TODO: add avalon violation checks
#        if sample.valid and sample.ready:
#            return True
#        return False
#
#    def decode(self, sample: Sample, lastsample: Sample):
#        if not self.decode_valid_ready(sample, lastsample):
#            return
#        else:
#            pass
#
#
#
#    def decode(self):
#        waveform = self.filter_valid_ready_only()
#        packets = []
#        for sample in waveform.samples:
#            sop = sample.values[self.s_sop]
#            eop = sample.values[self.s_eop]
#
#            # TODO: implement strb
#            if sop:
#                p = AVSPacket(self.name, sample.timestamp)
#            assert p is not None, "AVS: got eop with no packet (no sop?)"
#            p.add(sample.values[self.s_data])
#            if eop:
#                p.endtime = sample.timestamp
#                packets.append(p)
#                p = None
#
#        return packets
#
#
#@dataclass
#class AVSTLP(AvalonStream):
#    sig_name_hdr: str = "hdr"
#
#    def __repr__(self):
#        return f"<AVSTLP {self.waveform.signals}>"
#
#    def decode(self):
#        waveform = self.filter_valid_ready_only()
#        packets = []
#        p = None
#        for sample in waveform.samples:
#            sop = sample.values[self.sig_sop]
#            eop = sample.values[self.sig_eop]
#
#            # TODO: implement strb
#            if sop:
#                p = AVSTLPPacket(self.name, sample.timestamp)
#            assert p is not None, "AVSTLP: got eop with no packet (no sop?)"
#            p.add(sample.values[self.sig_data], hdr=sample.values[self.sig_hdr])
#            if eop:
#                p.endtime = sample.timestamp
#                packets.append(p)
#                p = None
#
#        return packets
#
