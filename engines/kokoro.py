"""Kokoro-82M English engine adapter: a persistent worker process in .venv-english."""
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
import numpy as np
from config import ROOT
from engines.base import AudioResult, Capabilities

MODEL_VERSION = 'kokoro-v1.0.onnx'

class KokoroEngine:
    id = 'kokoro'
    display_name = 'Kokoro-82M — English (local)'
    capabilities = Capabilities()

    def __init__(self):
        self.process = None
        self.temp = None
        self.log = None
        self.last_metrics = {}

    def is_available(self):
        return all(p.exists() for p in [ROOT / '.venv-english/Scripts/python.exe',
            ROOT / 'model_cache/kokoro/kokoro-v1.0.onnx', ROOT / 'model_cache/kokoro/voices-v1.0.bin'])

    def _read(self, timeout=300):
        try:
            line = self.responses.get(timeout=timeout)
        except queue.Empty:
            self.unload()
            raise RuntimeError('Kokoro timed out. Restart the engine.')
        if not line:
            raise RuntimeError('Kokoro worker exited. Inspect outputs/.engine_logs/kokoro.log.')
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
        self.log = (folder / 'kokoro.log').open('a', encoding='utf-8')
        self.temp = tempfile.TemporaryDirectory(prefix='kokoro_')
        self.responses = queue.Queue()
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        self.process = subprocess.Popen([str(ROOT / '.venv-english/Scripts/python.exe'), '-u',
            str(ROOT / 'engines/kokoro_worker.py')], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, text=True, encoding='utf-8', env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        stream, responses = self.process.stdout, self.responses
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
        voice = options.get('voice')
        if not voice:
            raise ValueError('Choose a Kokoro voice, e.g. am_michael or af_heart.')
        self.load()
        outputs = [str(Path(self.temp.name) / f'chunk_{i}.npy') for i in range(len(texts))]
        measured = time.perf_counter()
        self.process.stdin.write(json.dumps({'texts': list(texts), 'voice': voice, 'speed': options.get('speed', 1.0),
            'paces': options.get('paces'), 'outputs': outputs}, ensure_ascii=True) + '\n')
        self.process.stdin.flush()
        result = self._read(timeout=120 + 60 * len(texts))
        result['worker_roundtrip_ms'] = (time.perf_counter() - measured) * 1000
        audio = []
        for output in outputs:
            audio.append(AudioResult(np.load(output), 24000, 'cpu', MODEL_VERSION))
            Path(output).unlink(missing_ok=True)
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
        if self.log:
            self.log.close()
            self.log = None
