import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import numpy as np
from config import ROOT
from engines.base import AudioResult, Capabilities

MODEL_REVISION = 'fb652a96e508091045890dae5bb99fe511facbcf'
VOCOS_REVISION = '0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21'

class IndicF5Engine:
    id = 'indicf5'
    display_name = 'IndicF5 — Tamil reference voice (local)'
    capabilities = Capabilities(reference_audio=True)
    def __init__(self):
        self.process = None
        self.temp = None
        self.device = 'Auto'
        self.last_metrics = {}
        self.log = None
        self.reference_cache_key = None

    def is_available(self):
        return all(p.exists() for p in [
            ROOT / '.venv-indicf5/Scripts/python.exe',
            ROOT / f'model_cache/models--ai4bharat--IndicF5/snapshots/{MODEL_REVISION}/model.safetensors',
            ROOT / f'model_cache/models--charactr--vocos-mel-24khz/snapshots/{VOCOS_REVISION}/config.yaml',
            ROOT / 'model_cache/indicf5_verified.json'])

    def _read(self, timeout=300):
        try:
            line = self.responses.get(timeout=timeout)
        except queue.Empty:
            self.unload()
            raise RuntimeError('IndicF5 timed out. Try a shorter line or restart the engine.')
        if not line:
            raise RuntimeError('IndicF5 worker exited. Inspect outputs/.engine_logs/indicf5.log.')
        response = json.loads(line)
        if response.get('error'):
            raise RuntimeError(response['error'])
        return response

    def load(self):
        if self.process and self.process.poll() is None:
            return
        from config import OUTPUTS
        folder = OUTPUTS / '.engine_logs'
        folder.mkdir(parents=True, exist_ok=True)
        self.log = (folder / 'indicf5.log').open('a', encoding='utf-8')
        self.temp = tempfile.TemporaryDirectory(prefix='indicf5_')
        self.responses = queue.Queue()
        env = os.environ.copy()
        env.update(PYTHONIOENCODING='utf-8', HF_HUB_OFFLINE='1', WANDB_MODE='disabled', HF_HUB_DISABLE_TELEMETRY='1')
        self.process = subprocess.Popen([str(ROOT / '.venv-indicf5/Scripts/python.exe'), '-u',
            str(ROOT / 'engines/indicf5_worker.py'), self.device], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True,
            encoding='utf-8', env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        stream = self.process.stdout
        responses = self.responses
        def collect():
            for line in stream:
                responses.put(line)
            responses.put('')
        threading.Thread(target=collect, daemon=True).start()
        try:
            self._read()
        except Exception:
            self.unload()
            raise

    def synthesize(self, text, options):
        return self.synthesize_batch([text], options)[0]

    def synthesize_batch(self, texts, options):
        """Synthesize several chunks in one worker request; the worker batches them on the GPU."""
        ref = options.get('reference_audio')
        transcript = options.get('reference_text', '')
        if not options.get('reference_consent'):
            raise ValueError('Confirm permission to use the reference voice.')
        if not ref or not transcript.strip():
            raise ValueError('Provide a 1–15 second reference recording and its exact transcript.')
        device = options.get('device', 'Auto')
        measured = time.perf_counter()
        if self.device != device:
            self.unload()
            self.device = device
        self.load()
        model_load_ms = (time.perf_counter()-measured)*1000
        from services.audio import prepare_reference
        measured = time.perf_counter()
        source = Path(ref)
        cache_key = (str(source.resolve()), source.stat().st_mtime_ns, source.stat().st_size)
        reference = str(Path(self.temp.name) / 'reference.wav')
        reference_cache_hit = self.reference_cache_key == cache_key
        if not reference_cache_hit:
            prepare_reference(ref, reference)
            self.reference_cache_key = cache_key
        reference_prepare_ms = (time.perf_counter()-measured)*1000
        outputs = [str(Path(self.temp.name) / f'chunk_{i}.npy') for i in range(len(texts))]
        measured = time.perf_counter()
        self.process.stdin.write(json.dumps({'texts': list(texts), 'reference_audio': reference,
            'reference_text': transcript, 'outputs': outputs, 'steps': options.get('steps', 32),
            'precision': options.get('precision', 'fp32'), 'cfg_strength': options.get('cfg_strength', 2.0),
            'seed': options.get('seed', 1234), 'paces': options.get('paces')}, ensure_ascii=True) + '\n')
        self.process.stdin.flush()
        per_chunk = 120 if device == 'CPU' else 30
        result = self._read(timeout=(900 if device == 'CPU' else 300) + per_chunk*len(texts))
        worker_roundtrip_ms = (time.perf_counter()-measured)*1000
        audio = []
        for output in outputs:
            audio.append(AudioResult(np.load(output), 24000, result['device'], MODEL_REVISION))
            Path(output).unlink(missing_ok=True)
        result.update(adapter_model_load_ms=model_load_ms,reference_prepare_ms=reference_prepare_ms,
            reference_cache_hit=reference_cache_hit,worker_roundtrip_ms=worker_roundtrip_ms)
        self.last_metrics = result
        return audio

    def unload(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            for stream in [self.process.stdin, self.process.stdout]:
                if stream:
                    stream.close()
            self.process = None
        if self.temp:
            self.temp.cleanup()
            self.temp = None
        self.reference_cache_key = None
        if self.log:
            self.log.close()
            self.log = None
