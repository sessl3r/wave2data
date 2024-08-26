#!/usr/bin/env python3

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

import argparse
import sys
import wave2data

parser = argparse.ArgumentParser(
        prog="test script for wave2data")
parser.add_argument("wavefile", help="Waveform file to analyze")
parser.add_argument("--signals", action="store_true",
                    help="Print all signals in file")
parser.add_argument("--filter", help="Regex to filter signals by")
parser.add_argument("--decoder", nargs='*',
                    help="Decoder class to use (can be multiple)")

args = parser.parse_args()
if args.wavefile.endswith(".fst"):
    wave = wave2data.input.FSTWaveInput(args.wavefile, args.timeval)
else:
    wave = wave2data.input.VCDWaveInput(args.wavefile)
print(f"Opened {args.wavefile}")

if args.filter:
    wave.filter(args.filter)

if args.signals:
    for signal in wave.signals:
        print(signal)
    sys.exit(0)

if args.decoder:
    for decodername in args.decoder:
        decoder_class = getattr(sys.modules["wave2data.decoder"], decodername)
        decoder = decoder_class("rx", wave,
                                name_tlast="tlast", name_tkeep="tkeep")

    for packet in decoder:
        print(packet)
else:
    for sample in wave:
        print(sample)
