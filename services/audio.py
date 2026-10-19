import shutil
import subprocess
import wave
import json
from pathlib import Path
import numpy as np

def prepare_reference(source, destination):
    """Decode browser/phone formats to mono PCM WAV without trimming the clip."""
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError('Reference recording is missing. Upload it again.')
    binary = shutil.which('ffmpeg')
    if not binary:
        raise ValueError('FFmpeg is required to read M4A/MP3/browser recordings. Restart after installing FFmpeg.')
    try:
        subprocess.run([binary, '-nostdin', '-v', 'error', '-y', '-i', str(source),
            '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', str(destination)],
            capture_output=True, check=True, timeout=60,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.CalledProcessError:
        raise ValueError('இந்த audio file-ஐ வாசிக்க முடியவில்லை. வேறு recording அல்லது WAV/M4A/MP3 file upload செய்யுங்கள்.') from None
    except subprocess.TimeoutExpired:
        raise ValueError('Audio conversion timed out. Use a short 1–15 second recording.') from None
    with wave.open(str(destination), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate()
    if not 1 <= duration <= 15:
        raise ValueError(f'Reference recording is {duration:.1f} seconds. Use 1–15 seconds and update its exact transcript; no audio is trimmed automatically.')
    return str(destination)

def combine(chunks, rate, pause_ms, pauses_ms=None):
    if not chunks or not 0 <= pause_ms <= 2000:
        raise ValueError('Invalid chunks or pause.')
    pauses_ms = [pause_ms] * (len(chunks)-1) if pauses_ms is None else pauses_ms
    if len(pauses_ms) != len(chunks)-1 or any(not 0 <= ms <= 2000 for ms in pauses_ms):
        raise ValueError('Invalid per-boundary audio pauses.')
    parts, boundaries, offset = [], [], 0
    for i, chunk in enumerate(chunks):
        chunk = np.asarray(chunk, dtype=np.float32)
        if chunk.ndim != 1 or not len(chunk) or not np.isfinite(chunk).all():
            raise ValueError('Engine returned invalid mono PCM audio.')
        if i:
            pause = np.zeros(round(rate * pauses_ms[i-1] / 1000), dtype=np.float32)
            parts.append(pause)
            offset += len(pause)
        boundaries.append({'start_sample': offset, 'end_sample': offset + len(chunk)})
        parts.append(chunk)
        offset += len(chunk)
    return np.concatenate(parts), boundaries

def write_wav(path, pcm, rate):
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((np.clip(pcm, -1, 1) * 32767).astype('<i2').tobytes())

def encode_mp3(wav, output=None, bitrate_kbps=None):
    from config import MP3_BITRATE_KBPS
    bitrate_kbps = MP3_BITRATE_KBPS if bitrate_kbps is None else int(bitrate_kbps)
    if bitrate_kbps not in (32,40,48,56,64,80,96,112,128,160,192,224,256,320):
        raise ValueError('Unsupported MP3 bitrate. Choose a standard MPEG-1 bitrate (default 192 kbps).')
    binary = shutil.which('ffmpeg')
    if not binary:
        return None, 'FFmpeg is required for permanent MP3 output. See WINDOWS_SETUP.md.'
    mp3 = Path(output) if output else Path(wav).with_suffix('.mp3')
    try:
        subprocess.run([binary, '-nostdin', '-v', 'error', '-n', '-i', str(wav),
                        '-codec:a', 'libmp3lame', '-ar', '48000', '-b:a', f'{bitrate_kbps}k',
                        '-write_xing', '1', str(mp3)],
                       capture_output=True, check=True, timeout=180,
                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return mp3, None
    except (subprocess.SubprocessError, OSError) as exc:
        return None, f'MP3 encoding failed: {exc}'

def inspect_mp3_timeline(path, source_samples, source_rate):
    """Verify the standard gapless decoded timeline, never infer alignment from text."""
    result = dict(verified=False,playback_sample_rate=48000,requires_gapless_player=True,
        flutter_player_verification_required=True,
        basis='PCM segment positions on an encoder-delay/padding-compensated MP3 playback timeline')
    ffprobe, ffmpeg = shutil.which('ffprobe'),shutil.which('ffmpeg')
    if not ffprobe or not ffmpeg:
        result['limitation'] = 'FFmpeg/FFprobe unavailable; final MP3 timing could not be verified.'
        return result
    flags = getattr(subprocess,'CREATE_NO_WINDOW',0)
    try:
        stream_info = subprocess.run([ffprobe,'-v','error','-select_streams','a:0','-show_streams',
            '-of','json',str(path)],capture_output=True,check=True,timeout=30,creationflags=flags)
        stream = json.loads(stream_info.stdout)['streams'][0]
        rate = int(stream['sample_rate'])
        packet_info = subprocess.run([ffprobe,'-v','error','-select_streams','a:0',
            '-show_packets','-read_intervals','%+#1','-of','json',str(path)],
            capture_output=True,check=True,timeout=30,creationflags=flags)
        packets = json.loads(packet_info.stdout).get('packets',[])
        side = packets[0].get('side_data_list',[]) if packets else []
        skip = next((int(item.get('skip_samples',0)) for item in side if item.get('side_data_type')=='Skip Samples'),0)
        decoded = subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(path),'-map','0:a:0',
            '-ac','1','-c:a','pcm_f32le','-f','f32le','pipe:1'],
            capture_output=True,check=True,timeout=180,creationflags=flags)
        if len(decoded.stdout)%4:
            raise ValueError('Invalid decoded PCM size.')
        count = len(decoded.stdout)//4
        expected = round(source_samples*rate/source_rate)
        result.update(playback_sample_rate=rate,decoded_samples=count,expected_decoded_samples=expected,
            decoded_duration_ms=round(count*1000/rate),encoder_skip_samples=skip,
            encoder_skip_ms=skip*1000/rate,container_start_time_seconds=float(stream.get('start_time',0)),
            measured_bitrate_bps=int(stream.get('bit_rate',0)),decoder='FFmpeg',
            verified=(count==expected and skip>0 and stream.get('codec_name')=='mp3'))
        if not result['verified']:
            result['limitation'] = 'Decoded length or encoder-delay metadata did not match the PCM timeline; verse highlighting is withheld.'
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as exc:
        result['limitation'] = f'MP3 timeline verification failed: {exc}'
    return result
