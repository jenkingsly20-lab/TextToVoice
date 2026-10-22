"""Offline Kokoro-82M (ONNX) English inference in the isolated .venv-english environment.

stdout is JSON protocol only; library logs go to stderr. Each request synthesizes a
list of texts with one voice and writes one float32 .npy per text (24 kHz mono).
"""
import json
import sys
import time
from pathlib import Path

protocol_out = sys.stdout
sys.stdout = sys.stderr
ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'model_cache' / 'kokoro' / 'kokoro-v1.0.onnx'
VOICES = ROOT / 'model_cache' / 'kokoro' / 'voices-v1.0.bin'

def respond(data):
    protocol_out.write(json.dumps(data, ensure_ascii=True) + '\n')
    protocol_out.flush()

def disable_power_throttling():
    """Opt out of Windows 11 EcoQoS: a window-less background process can otherwise be
    held at low clock speeds / efficiency cores, which made CPU inference ~3x slower."""
    if sys.platform != 'win32':
        return
    import ctypes
    from ctypes import wintypes
    class PowerThrottlingState(ctypes.Structure):
        _fields_ = [('Version', wintypes.ULONG), ('ControlMask', wintypes.ULONG), ('StateMask', wintypes.ULONG)]
    PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
    state = PowerThrottlingState(1, PROCESS_POWER_THROTTLING_EXECUTION_SPEED, 0)  # control speed, never throttle
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE  # a 64-bit pseudo-handle; the int default truncates it
    kernel32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    process = kernel32.GetCurrentProcess()
    kernel32.SetProcessInformation(process, 4, ctypes.byref(state), ctypes.sizeof(state))  # ProcessPowerThrottling
    kernel32.SetPriorityClass(process, 0x8000)  # ABOVE_NORMAL_PRIORITY_CLASS

def main():
    disable_power_throttling()
    import numpy as np
    from kokoro_onnx import Kokoro
    kokoro = Kokoro(str(MODEL), str(VOICES))
    available = set(kokoro.get_voices())
    respond({'ready': True, 'device': 'cpu'})
    for line in sys.stdin:
        try:
            request = json.loads(line)
            texts, voice = request['texts'], request['voice']
            if voice not in available:
                raise ValueError(f'Unknown Kokoro voice {voice!r}.')
            if not texts or any(not t.strip() for t in texts):
                raise ValueError('Text is required.')
            speed = float(request.get('speed', 1.0))
            paces = request.get('paces') or [1.0] * len(texts)
            lang = 'en-gb' if voice.startswith('b') else 'en-us'
            started = time.perf_counter()
            durations = []
            for text, pace, output in zip(texts, paces, request['outputs']):
                # pace > 1 means "take longer", i.e. a lower speaking speed.
                pcm, rate = kokoro.create(text, voice=voice, speed=speed / pace, lang=lang)
                if rate != 24000:
                    raise ValueError(f'Unexpected Kokoro sample rate {rate}.')
                np.save(output, pcm.astype(np.float32))
                durations.append(len(pcm) / rate)
            respond({'ok': True, 'device': 'cpu', 'sample_rate': 24000, 'voice': voice, 'speed': speed,
                     'batch_size': len(texts), 'synthesis_wall_ms': (time.perf_counter() - started) * 1000,
                     'duration_seconds': durations})
        except Exception as exc:
            respond({'ok': False, 'error': str(exc)})

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        respond({'ready': False, 'error': str(exc)})
        raise
