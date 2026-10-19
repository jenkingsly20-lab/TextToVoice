"""Load a locally configured, attributed default voice; never download at inference."""
import hashlib
import json
import os
from pathlib import Path
from config import ROOT, CACHE
from services.audio import prepare_reference

DEFAULT_CONFIG = ROOT / 'assets/voices/default_tamil/voice.json'

def installed_voice_configs():
    configs = {'default': Path(os.getenv('TAMIL_TTS_DEFAULT_VOICE_CONFIG', DEFAULT_CONFIG))}
    for path in sorted((ROOT / 'assets/voices').glob('*/voice.json')):
        if path == DEFAULT_CONFIG:
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        configs[data['id']] = path
    return configs

def voice_choices():
    return [(json.loads(path.read_text(encoding='utf-8')).get('display_name', key), key)
            for key, path in installed_voice_configs().items() if path.is_file()]

def selected_reference(selection=None):
    if selection in (None, '', 'Default Tamil narration'):
        selection = 'default'
    configs = installed_voice_configs()
    if selection not in configs:
        raise ValueError('Selected voice is not installed. Refresh the voice list.')
    return get_default_reference(configs[selection])

def voice_sample(selection):
    return selected_reference(selection)['voice_provenance']['source_audio']

def get_default_reference(config_path=None):
    path = Path(config_path or os.getenv('TAMIL_TTS_DEFAULT_VOICE_CONFIG', DEFAULT_CONFIG))
    if not path.is_file():
        raise ValueError('Default Tamil voice is not configured yet. A licensed Tamil reference and matching transcript must be installed once; no microphone recording is needed for normal use.')
    data = json.loads(path.read_text(encoding='utf-8'))
    required = ['id', 'audio', 'transcript_file', 'audio_sha256', 'transcript_sha256', 'license', 'license_url', 'source_url', 'attribution', 'permission_basis']
    if any(not data.get(field) for field in required):
        raise ValueError('Default Tamil voice configuration is missing its transcript or permission/provenance details.')
    audio = (path.parent / data['audio']).resolve()
    transcript_file = (path.parent / data['transcript_file']).resolve()
    if not audio.is_file() or not transcript_file.is_file():
        raise ValueError('Default Tamil voice assets are missing. Restore the configured audio and matching transcript.')
    transcript = transcript_file.read_text(encoding='utf-8')
    if not transcript.strip():
        raise ValueError('Default Tamil reference transcript is empty.')
    if hashlib.sha256(transcript.encode('utf-8')).hexdigest() != data['transcript_sha256']:
        raise ValueError('Default Tamil reference transcript changed. Restore the exact source transcript.')
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    if digest != data['audio_sha256']:
        raise ValueError('Default Tamil reference audio changed. Revalidate its matching transcript and attribution before use.')
    cached = CACHE / 'reference_pcm' / f'{digest}.wav'
    cached.parent.mkdir(parents=True, exist_ok=True)
    cache_hit = cached.is_file()
    if not cached.is_file():
        import tempfile
        with tempfile.TemporaryDirectory(prefix='prepare_', dir=cached.parent) as temporary:
            prepared = Path(temporary) / 'reference.wav'
            prepare_reference(audio, prepared)
            prepared.replace(cached)
    provenance = {key: value for key, value in data.items() if key not in ('audio', 'transcript_file')}
    provenance['source_audio'] = str(audio)
    return {'reference_audio': str(cached), 'reference_text': transcript,
            'preprocessing_cache_hit':cache_hit,
            'reference_consent': True, 'voice': data.get('display_name', data['id']),
            'voice_provenance': provenance}

def default_voice_status():
    try:
        reference = get_default_reference()
        return 'Ready — ' + reference['voice'] + '. Paste Tamil text and click Generate Speech.'
    except (ValueError, OSError) as exc:
        return 'Default voice setup pending: ' + str(exc)
