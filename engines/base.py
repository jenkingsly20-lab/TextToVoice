from dataclasses import dataclass
from typing import Protocol
import numpy as np

@dataclass(frozen=True)
class Capabilities:
    voices: tuple[str, ...] = ()
    reference_audio: bool = False
    speech: bool = True

@dataclass
class AudioResult:
    pcm: np.ndarray
    sample_rate: int
    device: str
    version: str

class TTSEngine(Protocol):
    id: str
    display_name: str
    capabilities: Capabilities
    def is_available(self) -> bool: ...
    def load(self) -> None: ...
    def synthesize(self, text: str, options: dict) -> AudioResult: ...
    def unload(self) -> None: ...
