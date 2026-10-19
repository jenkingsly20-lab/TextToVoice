import json
import shutil
import subprocess
import wave
import numpy as np
import pytest
from engines.registry import Registry
from services.text_chunks import chunk_text
from services.audio import combine
from services.generation import generate
from services.ratings import save_rating

TEXT = 'தமிழ் வாழ்வு; பள்ளி.\r\nஇயேசு கிறிஸ்து!\nஅறிவு அருள் நன்றி'

@pytest.mark.parametrize('mode', ['Whole text', 'Lines', 'Sentences'])
def test_lossless_tamil(mode):
    assert ''.join(chunk_text(TEXT, mode)) == TEXT

def test_empty_and_unknown():
    with pytest.raises(ValueError): chunk_text('   ')
    with pytest.raises(ValueError): Registry().select('not-installed-engine')
    assert Registry().choices()[0][1] == 'mock'

def test_pcm_pause_boundaries():
    pcm, bounds = combine([np.ones(10), np.ones(20)], 1000, 400)
    assert len(pcm) == 430
    assert bounds == [{'start_sample': 0, 'end_sample': 10}, {'start_sample': 410, 'end_sample': 430}]
    assert not np.any(pcm[10:410])

def test_end_to_end(tmp_path):
    wav, mp3, meta, record = generate(TEXT, output_root=tmp_path)
    assert json.loads(open(meta, encoding='utf-8').read())['original_text'] == TEXT
    assert record['is_speech'] is False
    with wave.open(wav) as f:
        assert f.getframerate() == 24000
        assert f.getnframes() / f.getframerate() == record['duration_seconds']
    if shutil.which('ffmpeg'):
        assert mp3
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-f', 'null', '-'], capture_output=True)
        assert decoded.returncode == 0
    with pytest.raises(ValueError): save_rating(record, None, 'A', 'tone', output_root=tmp_path)
    second = generate(TEXT, output_root=tmp_path)
    assert wav != second[0]

def test_assessment_and_identical_input(tmp_path):
    a = {'id': 'a', 'is_speech': True, 'original_text': TEXT}
    b = {'id': 'b', 'is_speech': True, 'original_text': 'different'}
    with pytest.raises(ValueError): save_rating(a, b, 'A', '', output_root=tmp_path)
    jp, cp = save_rating(a, None, 'Single output', 'தமிழ்', 4, 4, 4, 4, 4, output_root=tmp_path)
    assert json.loads(open(jp, encoding='utf-8').read())['notes'] == 'தமிழ்'

def test_ui_build_and_tamil_upload(tmp_path):
    from app import build_ui, read_upload
    path = tmp_path / 'tamil.txt'
    path.write_bytes(TEXT.encode('utf-8'))
    assert read_upload(str(path)) == TEXT
    ui = build_ui()
    assert ui.config['analytics_enabled'] is False
    assert 'Tamil Bible Voice Lab' == ui.title
