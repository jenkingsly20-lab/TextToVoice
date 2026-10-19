import numpy as np
from engines.base import AudioResult, Capabilities

class MockEngine:
    id = 'mock'
    display_name = 'TEST ONLY — NOT SPEECH (test tone)'
    capabilities = Capabilities(voices=('440 Hz test tone',), speech=False)
    def is_available(self): return True
    def load(self): pass
    def unload(self): pass
    def synthesize(self, text, options):
        rate = 24000
        t = np.arange(rate // 2) / rate
        pcm = (0.1 * np.sin(2 * np.pi * 440 * t) * np.sin(np.pi * t / .5)**2).astype(np.float32)
        return AudioResult(pcm, rate, 'CPU', '1')
