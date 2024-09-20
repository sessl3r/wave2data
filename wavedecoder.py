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
import copy
import json
import sys
import wave2data
from wave2data.decoder import *
from wave2data.protocol import *

parser = argparse.ArgumentParser(
        description="Parse a given wavefile with specified decoder(s)")
parser.add_argument("wavefile", type=str, help="Waveform file to analyze")
parser.add_argument("--decoder", help="A JSON formatted string to configure one or multiple decoders")
parser.add_argument("--protocol", help="A JSON formatted string to configure protocols onto decoders") 
parser.add_argument("--filter", help="Filter signals in waveinput")
parser.add_argument("--debug", action="store_true",
        help="Print samples if decoder, or packets of protocol")
parser.add_argument("--signals", action="store_true",
                    help="Print all signals in file and exit")

args = parser.parse_args()
if args.wavefile.endswith('.vcd'):
    wave = wave2data.input.VCDWaveInput(args.wavefile)
elif args.wavefile.endswith('.csv'):
    wave = wave2data.input.QuartusCSVInput(args.wavefile)

if args.filter:
    wave.filter(args.filter)

if args.signals:
    for signal in wave.signals:
        print(signal)
    sys.exit(0)

if not args.decoder:
    for sample in wave:
        print(sample)
    sys.exit(0)


arg = json.loads(args.decoder)

decoder_settings = {}
for key, value in arg.items():
    decoder_settings[key] = {}
    d = decoder_settings[key]
    if not 'cls' in value:
        raise KeyError(f"Decoder is missing a 'cls' entry ({key}: {value})")
    d['cls'] = globals()[value['cls']]
    value.pop('cls')
    d['args'] = {}
    for sk, sv in value.items():
        if 'decoder' == sk:
            continue  # TODO: subdecoder
        d['args'][sk] = sv

decoders = {}
for name, decoder in decoder_settings.items():
    decoders[name] = decoder['cls'](name, wave, **decoder['args'])

print("Running decoders on samples:")
for decoder in decoders.values():
    print(decoder)

protocols = {}
if args.protocol:
    arg = json.loads(args.protocol)
    for bus, value in arg.items():
        if bus not in decoders.keys():
            raise ValueError(f"unable to find decoder '{bus}' in decoders")
        protocols[bus] = {}
        protocols[bus]['cls'] = globals()[value['cls']]
    print("Running Protocols on decoders:")
    for bus, protocol in protocols.items():
        print(f"Bus {bus} : {protocol}")

lastsample = None
nlen = max([len(n) for n in decoders.keys()])
decoder_errors = 0
protocol_errors = 0

for sample in wave:
    if not isinstance(sample, wave2data.wave.Sample):
        print(sample)
        continue
    if not lastsample:
        lastsample = sample
    for decoder in decoders.values():
        try:
            packet = decoder.decode(sample, lastsample)
        except Exception as e:
            print(f"ERROR while decoding: {e}")
            print(f"  Decoder: {decoder}")
            decoder_errors += 1
            continue
        if packet:
            if packet.name in protocols:
                protocol = protocols[packet.name]
                try:
                    pp = protocol['cls'](packet)
                except Exception as e:
                    print(f"ERROR while handling protocol: {e}")
                    print(f"  Protocol: {protocol}")
                    print(f"  Packet: {packet}")
                    protocol_errors += 1
                    continue
                info = f"{sample.timestamp_str:>010} {packet.name:{nlen}s} {pp}"
                if args.debug:
                    info += f"\n  from {packet}"
                print(info)
            else:
                print(packet)
    lastsample = copy.deepcopy(sample)

if decoder_errors > 0:
    print(f"ERROR: Found {decoder_errors} decoder errors while scanning! Check the output!")
if protocol_errors > 0:
    print(f"ERROR: Found {protocol_errors} protocol errors while scanning! Check the output!")

