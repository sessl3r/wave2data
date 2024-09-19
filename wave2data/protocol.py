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

from .decoder import AXISPacket
from .tlp import Tlp

class Protocol:
    pass


class TLPAXIStreamAgilex5E(Protocol):
    """ generate TLP from AXIStream decoded data as on Agilex 5E """

    def __init__(self, packet: AXISPacket):
        dw = packet.datawidth // 8
        firstbeat = packet.normdata[0:dw]
        temphdr = firstbeat[16:dw]
        data = packet.normdata[dw:]
        hdr = bytes()
        # double word swap the header
        for i in range(16, 0, -4):
            hdr += temphdr[i-4:i]
        try:
            self.tlp = Tlp().unpack_header(hdr)
            self.tlp.set_data(data)
        except:
            self.tlp = None

    def __repr__(self):
        if self.tlp:
            return self.tlp.__repr__()
        return "Tlp(Invalid)"
