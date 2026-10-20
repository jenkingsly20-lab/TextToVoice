"""Offline, eager-mode IndicF5 inference in the isolated Python environment.

Uses the official architecture at Git revision 13f7c4d... and strict checkpoint
loading. Avoids torch.compile on Windows and upstream punctuation replacement.
stdout is JSON protocol only; library logs go to stderr.

Speed: several chunks are sampled per GPU batch, the conditional and
unconditional classifier-free-guidance passes share one forward call, matmuls
use TF32 and the transformer runs under bf16 autocast (vocoder stays fp32).
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
# Sub-batch size limits: rows x frames, where CFG doubles the rows. 12000 frames
# keeps peak VRAM well under 8 GB; out-of-memory halves the sub-batch and retries.
FRAME_BUDGET = int(os.getenv('TAMIL_TTS_FRAME_BUDGET', '12000'))
MAX_BATCH = int(os.getenv('TAMIL_TTS_MAX_BATCH', '8'))
MAX_SECONDS = 30
GPU_MEMORY_FRACTION = float(os.getenv('TAMIL_TTS_GPU_MEMORY_FRACTION', '0.8'))

def respond(data):
    protocol_out.write(json.dumps(data, ensure_ascii=True) + '\n')
    protocol_out.flush()

def main():
    import contextlib
    import torch
    import numpy as np
    import soundfile as sf
    import torchaudio
    from torch.nn.utils.rnn import pad_sequence
    from safetensors.torch import load_file
    from vocos import Vocos
    from f5_tts.model import DiT
    from f5_tts.model.utils import lens_to_mask, list_str_to_idx
    from f5_tts.infer.utils_infer import load_model
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    requested = sys.argv[1] if len(sys.argv) > 1 else 'Auto'
    device = 'cpu' if requested == 'CPU' else ('cuda' if torch.cuda.is_available() else 'cpu')
    if device == 'cuda':
        # Near the VRAM limit the Windows driver silently spills into much slower shared
        # system memory instead of failing. Capping PyTorch's share turns that into an
        # out-of-memory error, which run() handles by halving the sub-batch.
        torch.cuda.set_per_process_memory_fraction(GPU_MEMORY_FRACTION)
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
    references = {}
    # The text ConvNeXt and the position conv ignore the padding mask, so in a batch
    # a short row would see its padded tail. Running these two cheap layers per row
    # at the row's own length keeps every row identical to unbatched inference.
    row_lengths = {'value': None}
    text_embed_forward = model.transformer.text_embed.forward
    conv_forward = model.transformer.input_embed.conv_pos_embed.forward
    def text_embed_rows(text, seq_len, drop_text=False):
        lengths = row_lengths['value']
        if lengths is None:
            return text_embed_forward(text, seq_len, drop_text=drop_text)
        rows = [text_embed_forward(text[i:i+1], n, drop_text=drop_text)[0] for i, n in enumerate(lengths)]
        return pad_sequence(rows, padding_value=0, batch_first=True)
    def conv_rows(x, mask=None):
        lengths = row_lengths['value']
        if lengths is None:
            return conv_forward(x, mask)
        out = torch.zeros_like(x)
        for i, n in enumerate(lengths):
            out[i:i+1, :n] = conv_forward(x[i:i+1, :n])
        return out
    model.transformer.text_embed.forward = text_embed_rows
    model.transformer.input_embed.conv_pos_embed.forward = conv_rows

    def load_reference(path):
        source = Path(path)
        key = (str(source.resolve()), source.stat().st_mtime_ns, source.stat().st_size)
        if key in references:
            return references[key]
        waveform, sr = sf.read(path, dtype='float32', always_2d=True)
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
        with torch.inference_mode():
            mel = model.mel_spec(audio).permute(0, 2, 1)  # 1 n d, fp32
        references.clear()
        references[key] = dict(mel=mel, ref_frames=audio.shape[-1] // 256, rms=rms.to(device))
        return references[key]

    def sample(ref, ref_text, texts, durations, steps, cfg_strength, seed, autocast):
        """Batched CFM Euler sampling equivalent to CFM.sample, one forward per step for CFG."""
        batch = len(texts)
        cond = ref['mel'].expand(batch, -1, -1)
        cond_len = cond.shape[1]
        text = list_str_to_idx([list(ref_text + ' ' + t) for t in texts], model.vocab_char_map).to(device)
        lens = torch.maximum((text != -1).sum(dim=-1), torch.full((batch,), cond_len, device=device, dtype=torch.long))
        duration = torch.tensor(durations, device=device, dtype=torch.long)
        duration = torch.maximum(lens + 1, duration).clamp(max=4096)
        longest = int(duration.amax())
        cond = torch.nn.functional.pad(cond, (0, 0, 0, longest - cond_len), value=0.0)
        cond_mask = torch.nn.functional.pad(lens_to_mask(lens), (0, longest - int(lens.amax())), value=False).unsqueeze(-1)
        step_cond = torch.where(cond_mask, cond, torch.zeros_like(cond))
        mask = lens_to_mask(duration) if int(duration.amin()) != longest else None
        if cfg_strength > 1e-5:
            # Dropped text (all -1 -> filler 0) and zeroed audio match drop_text/drop_audio_cond.
            step_cond_all = torch.cat([step_cond, torch.zeros_like(step_cond)])
            text_all = torch.cat([text, torch.full_like(text, -1)])
            mask_all = torch.cat([mask, mask]) if mask is not None else None
        noise = []
        for dur in duration.tolist():
            generator = torch.Generator(device=device).manual_seed(seed)
            noise.append(torch.randn(dur, model.num_channels, device=device, generator=generator))
        x = pad_sequence(noise, padding_value=0, batch_first=True)
        t = torch.linspace(0, 1, steps + 1, device=device)
        t = t + -1.0 * (torch.cos(torch.pi / 2 * t) - 1 + t)  # sway sampling, coef -1
        lengths = duration.tolist() if mask is not None else None
        row_lengths['value'] = lengths * 2 if lengths and cfg_strength > 1e-5 else lengths
        for i in range(steps):
            with autocast():
                if cfg_strength > 1e-5:
                    both = model.transformer(x=torch.cat([x, x]), cond=step_cond_all, text=text_all, time=t[i],
                                             mask=mask_all, drop_audio_cond=False, drop_text=False).float()
                    pred, null = both.chunk(2)
                    flow = pred + (pred - null) * cfg_strength
                else:
                    flow = model.transformer(x=x, cond=step_cond, text=text, time=t[i], mask=mask,
                                             drop_audio_cond=False, drop_text=False).float()
            x = x + (t[i + 1] - t[i]) * flow
        row_lengths['value'] = None
        out = torch.where(cond_mask, cond, x)
        results = []
        for row, dur in enumerate(duration.tolist()):
            mel = out[row:row+1, ref['ref_frames']:dur, :].float().permute(0, 2, 1)
            audio = vocoder.decode(mel)
            if ref['rms'] < .1:
                audio = audio * ref['rms'] / .1
            results.append(audio.squeeze().cpu().numpy().astype(np.float32))
        return results

    def run(ref, ref_text, texts, durations, steps, cfg_strength, seed, autocast):
        """Split into sub-batches by frame budget; halve a sub-batch on out-of-memory."""
        order = sorted(range(len(texts)), key=lambda i: durations[i])
        groups, current = [], []
        for i in order:
            rows = (2 if cfg_strength > 1e-5 else 1) * (len(current) + 1)
            if current and (len(current) >= MAX_BATCH or rows * durations[i] > FRAME_BUDGET):
                groups.append(current)
                current = []
            current.append(i)
        if current:
            groups.append(current)
        pcm, sub_batches = [None] * len(texts), 0
        while groups:
            group = groups.pop(0)
            try:
                with torch.inference_mode():
                    outputs = sample(ref, ref_text, [texts[i] for i in group], [durations[i] for i in group],
                                     steps, cfg_strength, seed, autocast)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if len(group) == 1:
                    raise
                half = len(group) // 2
                groups[:0] = [group[:half], group[half:]]
                continue
            sub_batches += 1
            for i, audio in zip(group, outputs):
                pcm[i] = audio
        return pcm, sub_batches

    respond({'ready': True, 'device': device})
    for line in sys.stdin:
        try:
            request = json.loads(line)
            texts, ref_text = request['texts'], request['reference_text']
            if not texts or any(not t.strip() for t in texts) or not ref_text.strip():
                raise ValueError('Both text and the exact reference transcript are required.')
            steps = int(request.get('steps', 32))
            cfg_strength = float(request.get('cfg_strength', 2.0))
            seed = int(request.get('seed', 1234))
            precision = request.get('precision', 'fp32')
            if not 4 <= steps <= 64:
                raise ValueError('Steps must be between 4 and 64.')
            if precision == 'bf16' and device == 'cuda' and torch.cuda.is_bf16_supported():
                autocast = lambda: torch.autocast('cuda', dtype=torch.bfloat16)
            else:
                precision = 'fp32'
                autocast = contextlib.nullcontext
            prepared_at = time.perf_counter()
            ref = load_reference(request['reference_audio'])
            ref_frames = ref['ref_frames']
            ref_bytes = len(ref_text.encode('utf-8'))
            durations = [ref_frames + int(ref_frames / ref_bytes * len(t.encode('utf-8'))) for t in texts]
            for t, duration in zip(texts, durations):
                if duration * 256 / 24000 > MAX_SECONDS:
                    raise ValueError(f'Estimated chunk is longer than {MAX_SECONDS} seconds including the reference: '
                                     + t[:60] + '… Use shorter lines.')
            if device == 'cuda':
                torch.cuda.reset_peak_memory_stats()
            audio_prepare_ms = (time.perf_counter()-prepared_at)*1000
            synthesis_at = time.perf_counter()
            gpu_start,gpu_end = None,None
            if device == 'cuda':
                gpu_start = torch.cuda.Event(enable_timing=True)
                gpu_end = torch.cuda.Event(enable_timing=True)
                gpu_start.record()
            pcm, sub_batches = run(ref, ref_text, texts, durations, steps, cfg_strength, seed, autocast)
            gpu_elapsed_ms = None
            if gpu_end is not None:
                gpu_end.record()
                gpu_end.synchronize()
                gpu_elapsed_ms = gpu_start.elapsed_time(gpu_end)
            synthesis_wall_ms = (time.perf_counter()-synthesis_at)*1000
            written_at = time.perf_counter()
            for audio, output in zip(pcm, request['outputs']):
                np.save(output, audio)
            peak_vram_bytes = torch.cuda.max_memory_allocated() if device == 'cuda' else 0
            if device == 'cuda':
                torch.cuda.empty_cache()  # release cached blocks so varied batch shapes do not hoard VRAM
            respond({'ok': True, 'device': device, 'sample_rate': 24000, 'steps': steps, 'precision': precision,
                     'cfg_strength': cfg_strength, 'seed': seed, 'batch_size': len(texts), 'sub_batches': sub_batches,
                     'reference_audio_prepare_ms':audio_prepare_ms,'synthesis_wall_ms':synthesis_wall_ms,
                     'gpu_elapsed_ms':gpu_elapsed_ms,'temporary_chunk_write_ms':(time.perf_counter()-written_at)*1000,
                     'peak_vram_bytes': peak_vram_bytes,
                     'duration_seconds': [len(audio) / 24000 for audio in pcm]})
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
