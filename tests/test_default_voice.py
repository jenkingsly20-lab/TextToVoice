import hashlib
import json
import wave
import pytest
from services.default_voice import get_default_reference

def make_config(tmp_path):
    audio = tmp_path / 'audio.wav'
    with wave.open(str(audio), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b'\x01\x00' * 48000)
    (tmp_path / 'text.txt').write_text('தமிழ் உரை.', encoding='utf-8')
    data = dict(id='test', audio='audio.wav', transcript_file='text.txt',
                audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),
                transcript_sha256=hashlib.sha256('தமிழ் உரை.'.encode('utf-8')).hexdigest(),
                license='test fixture', license_url='https://example.com/license',
                source_url='https://example.com/voice', attribution='test fixture', permission_basis='synthetic fixture')
    path = tmp_path / 'voice.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path

def test_default_assets_validate_and_preprocessing_is_cached(tmp_path, monkeypatch):
    import services.default_voice as module
    path = make_config(tmp_path)
    monkeypatch.setattr(module, 'CACHE', tmp_path / 'cache')
    calls = []
    original = module.prepare_reference
    def tracked(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(module, 'prepare_reference', tracked)
    a = get_default_reference(path)
    b = get_default_reference(path)
    assert a == b
    assert a['reference_text'] == 'தமிழ் உரை.'
    assert a['reference_consent'] is True
    assert len(calls) == 1

def test_missing_or_changed_default_fails_clearly(tmp_path):
    with pytest.raises(ValueError, match='not configured'):
        get_default_reference(tmp_path/'missing.json')
    path = make_config(tmp_path)
    (tmp_path/'audio.wav').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        get_default_reference(path)
