from engines.mock import MockEngine
from engines.indicf5 import IndicF5Engine

RESEARCHED = '''### Engine availability
* **Test tone — installed. TEST ONLY, NOT SPEECH.** No pronunciation evaluation is possible with a tone.
* **IndicF5 — Not installed.** Tamil supported; gated weights require your Hugging Face acceptance and an authorized reference recording plus transcript. Native Windows and 8 GB feasibility remain unverified.
* **Indic-Speak — Not installed.** Tamil stock voices documented; gated custom license. Native Windows and available VRAM remain unverified.

See `docs/MODEL_RESEARCH.md` and `docs/WINDOWS_SETUP.md`. No real model downloads happen at launch.
'''

class Registry:
    def __init__(self):
        self.engines = {'mock': MockEngine()}
        self.engines['indicf5'] = IndicF5Engine()
        self.current = None
    def choices(self):
        return [(e.display_name, e.id) for e in self.engines.values() if e.is_available()]
    def select(self, engine_id):
        engine = self.engines.get(engine_id)
        if engine is None or not engine.is_available():
            raise ValueError('Engine is not installed and usable. See setup guidance.')
        if self.current is not engine:
            if self.current:
                self.current.unload()
            self.current = None
            engine.load()
            self.current = engine
        return engine
