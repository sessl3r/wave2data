from dataclasses import dataclass, field


@dataclass
class Sample:
    timestamp: int
    signals: list = field(default_factory=list)
    values: list = field(default_factpry=list)


@dataclass
class Signal:
    name: str


@dataclass
class Waveform:
    signals: [Signal] = field(default_factory=list)

    def __post_init__(self):
        self.samples = []

    def add(self, s: Sample):
        self.samples.append(s)



def main():
    s = Sample(123, names, data)

if __main__ == "__main__":
    main()
