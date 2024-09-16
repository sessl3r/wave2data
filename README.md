# wave2data

A package to read data from a waveform (eg. VCD, FST, CSV, ...) extract the data
in the protocol and write it out somewhere or use for further analysis.

## Usage

TODO

## wavedecoder.py

Simple example tool to retrieve some input and decode it or just see some signals.

Example calls:

./wavedecoder.py examples/quartus.csv --signals
./wavedecoder.py examples/quartus.csv --signals --filter core_inst.core_inst.rx
./wavedecoder.py examples/quartus.csv --decoder '{"rx_bus":{"cls":"AXIStream","filter":"core_inst.core_inst.rx","name_tlast":"tlast"}}'
./wavedecoder.py examples/quartus.csv --decoder '{"rx_bus":{"cls":"AXIStream","filter":"core_inst.core_inst.rx","name_tlast":"tlast"},"tx_bus":{"cls":"AXIStream","filter":"core_inst.core_inst.tx","name_tlast":"tlast"}}'
./wavedecoder.py example.vcd --decoder '{"rx":{"cls":"AXIStream","filter":"core_inst|core_inst|rx","name_tlast":"tlast","name_clk":"!pcie_a5e_if_instpcie_a4e_if_rx_inst.clk"},"tx":{"cls":"AXIStream","filter":"core_inst|core_inst|tx","name_tlast":"tlast","name_clk":"!pcie_a5e_if_instpcie_a4e_if_rx_inst.clk"}}' --protocol '{"rx":{"cls":"TLPAXIStreamAgilex5E"},"tx":{"cls":"TLPAXIStreamAgilex5E"}}'
