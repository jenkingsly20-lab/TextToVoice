"""Offline, eager-mode IndicF5 inference in the isolated Python environment.

Uses the official architecture at Git revision 13f7c4d... and strict checkpoint
loading. Avoids torch.compile on Windows and upstream punctuation replacement.
stdout is JSON protocol only; library logs go to stderr.
"""
import sys
import json
import os
import time
from pathlib import Path

protocol_out = sys.stdout
sys.stdout = sys.stderr
ROOT = Path(__file__).resolve().parents[1]
os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', WANDB_MODE='disabled',
                  DO_NOT_TRACK='1', TOKENIZERS_PARALLELISM='false')
MODEL_REVISION = 'fb652a96e508091045890dae5bb99fe511facbcf'
VOCOS_REVISION = '0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21'

def respond(data):
    protocol_out.write(json.dumps(data, ensure_ascii=True) + '\n')
    protocol_out.flush()

def main():
    import torch
    import numpy as np
    import soundfile as sf
    import torchaudio
    from safetensors.torch import load_file
    from vocos import Vocos
    from f5_tts.model import DiT
    from f5_tts.infer.utils_infer import load_model
    torch.set_num_threads(8)
    requested = sys.argv[1] if len(sys.argv) > 1 else 'Auto'
    device = 'cpu' if requested == 'CPU' else ('cuda' if torch.cuda.is_available() else 'cpu')
    model_dir = ROOT / 'model_cache' / 'models--ai4bharat--IndicF5' / 'snapshots' / MODEL_REVISION
    vocos_dir = ROOT / 'model_cache' / 'models--charactr--vocos-mel-24khz' / 'snapshots' / VOCOS_REVISION
    vocoder = Vocos.from_hparams(str(vocos_dir / 'config.yaml'))
    state = load_file(str(model_dir / 'model.safetensors'), device='cpu')
    model = load_model(DiT, dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
                       vocab_file=str(model_dir / 'checkpoints/vocab.txt'), device='cpu')
    # The saved wrapper used torch.compile; eager modules have no _orig_mod prefix.
    model_state = {k.removeprefix('ema_model._orig_mod.'): v for k,v in state.items() if k.startswith('ema_model._orig_mod.')}
    vocos_state = {k.removeprefix('vocoder._orig_mod.'): v for k,v in state.items() if k.startswith('vocoder._orig_mod.')}
    model.load_state_dict(model_state, strict=True)
    vocoder.load_state_dict(vocos_state, strict=True)
    del state, model_state, vocos_state
    model = model.eval().to(device)
    vocoder = vocoder.eval().to(device)
    respond({'ready': True, 'device': device})
    for line in sys.stdin:
        try:
            request = json.loads(line)
            text, ref_text = request['text'], request['reference_text']
            if not text.strip() or not ref_text.strip():
                raise ValueError('Both text and the exact reference transcript are required.')
            prepared_at = time.perf_counter()
            waveform, sr = sf.read(request['reference_audio'], dtype='float32', always_2d=True)
            waveform = waveform.mean(axis=1)
            seconds = len(waveform) / sr
            if not 1 <= seconds <= 15:
                raise ValueError('Reference recording must be 1–15 seconds; no automatic trimming is performed.')
            if not np.isfinite(waveform).all() or np.sqrt(np.mean(waveform**2)) < 0.0001:
                raise ValueError('Reference recording is silent or invalid.')
            audio = torch.from_numpy(waveform).unsqueeze(0)
            if sr != 24000:
                audio = torchaudio.functional.resample(audio, sr, 24000)
            rms = audio.square().mean().sqrt()
            if rms < .1:
                audio = audio * .1 / rms
            audio = audio.to(device)
            ref_frames = audio.shape[-1] // 256
            duration = ref_frames + int(ref_frames / len(ref_text.encode('utf-8')) * len(text.encode('utf-8')))
            if duration * 256 / 24000 > 30:
                raise ValueError('Estimated chunk is longer than 30 seconds. Use shorter lines to conserve memory.')
            if device == 'cuda':
                torch.cuda.reset_peak_memory_stats()
            audio_prepare_ms = (time.perf_counter()-prepared_at)*1000
            synthesis_at = time.perf_counter()
            gpu_start,gpu_end = None,None
            if device == 'cuda':
                gpu_start = torch.cuda.Event(enable_timing=True)
                gpu_end = torch.cuda.Event(enable_timing=True)
                gpu_start.record()
            # Character lists preserve all original Tamil characters and punctuation.
            with torch.inference_mode():
                generated, _ = model.sample(cond=audio, text=[list(ref_text + ' ' + text)], duration=duration,
                    steps=32, cfg_strength=2.0, sway_sampling_coef=-1.0)
                mel = generated[:, ref_frames:, :].float().permute(0, 2, 1)
                out = vocoder.decode(mel)
                if rms < .1:
                    out = out * rms.to(device) / .1
                if gpu_end is not None:
                    gpu_end.record()
                pcm = out.squeeze().cpu().numpy().astype(np.float32)
            gpu_elapsed_ms = None
            if gpu_end is not None:
                gpu_end.synchronize()
                gpu_elapsed_ms = gpu_start.elapsed_time(gpu_end)
            synthesis_wall_ms = (time.perf_counter()-synthesis_at)*1000
            written_at = time.perf_counter()
            sf.write(request['output'], pcm, 24000, subtype='FLOAT')
            respond({'ok': True, 'device': device, 'sample_rate': 24000,
                     'reference_audio_prepare_ms':audio_prepare_ms,'synthesis_wall_ms':synthesis_wall_ms,
                     'gpu_elapsed_ms':gpu_elapsed_ms,'temporary_chunk_write_ms':(time.perf_counter()-written_at)*1000,
                     'peak_vram_bytes': torch.cuda.max_memory_allocated() if device == 'cuda' else 0,
                     'duration_seconds': len(pcm) / 24000})
        except Exception as exc:
            if device == 'cuda':
                torch.cuda.empty_cache()
            respond({'ok': False, 'error': str(exc)})

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        respond({'ready': False, 'error': str(exc)})
        raise
