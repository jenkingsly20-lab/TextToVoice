import shutil
import subprocess
import wave
import numpy as np
import pytest
from services.audio import prepare_reference, write_wav

@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg is required for M4A decoding')
def test_m4a_reference_decodes_without_trimming(tmp_path):
    wav = tmp_path / 'original.wav'
    samples = np.sin(2*np.pi*440*np.arange(48000)/24000).astype(np.float32)*.1
    write_wav(wav, samples, 24000)
    m4a = tmp_path / 'Recording 6.m4a'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(wav), '-c:a', 'aac', str(m4a)], check=True)
    original = m4a.read_bytes()
    converted = prepare_reference(m4a, tmp_path / 'reference.wav')
    with wave.open(converted) as f:
        assert f.getnchannels() == 1
        assert f.getframerate() == 24000
        assert abs(f.getnframes()/24000 - 2) < .1
    assert m4a.read_bytes() == original

@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg is required')
def test_corrupt_reference_is_actionable(tmp_path):
    broken = tmp_path / 'broken.m4a'
    broken.write_bytes(b'not audio')
    with pytest.raises(ValueError, match='audio file'):
        prepare_reference(broken, tmp_path / 'decoded.wav')
