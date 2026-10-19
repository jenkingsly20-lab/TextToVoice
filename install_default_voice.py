"""One-time installation of a single attributed Tamil narration clip from Rasa.

Requires user-accepted dataset access. Downloads one ~5-second clip, never a shard.
"""
import hashlib
import json
from pathlib import Path
import httpx
from huggingface_hub import HfApi, get_token

ROOT = Path(__file__).resolve().parent
REVISION = '632f55c7ac590219d41cd7adffce5b440e4604f5'
SAMPLE = 'TAM_F_BOOK_00014'

def main():
    token = get_token()
    if not token:
        raise SystemExit('Run .\\.venv\\Scripts\\hf.exe auth login after accepting Rasa access.')
    if HfApi(token=token).dataset_info('ai4bharat/Rasa').sha != REVISION:
        raise SystemExit('Rasa revision changed. Recheck the selected row and license before installing.')
    response = httpx.get('https://datasets-server.huggingface.co/rows',
        params={'dataset':'ai4bharat/Rasa','config':'Tamil','split':'test','offset':16,'length':1},
        headers={'Authorization': 'Bearer ' + token}, timeout=30)
    response.raise_for_status()
    row = response.json()['rows'][0]['row']
    if row['filename'] != SAMPLE or row['language'] != 'Tamil' or row['style'] != 'BOOK':
        raise SystemExit('Selected dataset row changed; refusing to guess a voice/transcript.')
    # Dataset viewer supplies a short-lived signed media URL; do not persist it.
    audio_response = httpx.get(row['audio'][0]['src'], follow_redirects=True, timeout=60)
    audio_response.raise_for_status()
    folder = ROOT / 'assets/voices/default_tamil'
    folder.mkdir(parents=True, exist_ok=True)
    audio = folder / 'reference.wav'
    audio.write_bytes(audio_response.content)
    transcript = row['text']
    (folder / 'transcript.txt').write_text(transcript, encoding='utf-8')
    metadata = {
        'id': 'rasa_tamil_female_book_00014',
        'display_name': 'Tamil narration — Rasa (female)',
        'audio': 'reference.wav', 'transcript_file': 'transcript.txt',
        'audio_sha256': hashlib.sha256(audio_response.content).hexdigest(),
        'transcript_sha256': hashlib.sha256(transcript.encode('utf-8')).hexdigest(),
        'license': 'CC-BY-4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'source_url': 'https://huggingface.co/datasets/ai4bharat/Rasa',
        'source_revision': REVISION, 'source_config': 'Tamil', 'source_split': 'test',
        'source_row_index': 16, 'source_sample_id': SAMPLE,
        'duration_seconds': float(row['duration']),
        'attribution': 'Rasa: Building Expressive Speech Synthesis Systems for Indian Languages in Low-resource Settings. Praveen Srinivasa Varadhan, Ashwin Sankar, Giri Raju, Mitesh M. Khapra / AI4Bharat, INTERSPEECH 2024.',
        'permission_basis': 'Publisher releases this expressive TTS dataset under CC-BY-4.0; user accepted gated access. Used for its documented speech-synthesis purpose with attribution. No endorsement is implied.',
        'changes': 'One complete source clip retrieved through the official dataset viewer; no trimming, transcript editing or voice training. Runtime cache decodes to mono 24 kHz PCM.',
        'quality_review': 'Narration-style dataset sample; human review of pronunciation and suitability remains required.'}
    (folder / 'voice.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    from services.default_voice import get_default_reference
    reference = get_default_reference()
    print(json.dumps({'installed':reference['voice'], 'sample':SAMPLE,
        'duration_seconds':metadata['duration_seconds'], 'bytes':audio.stat().st_size,
        'audio_sha256':metadata['audio_sha256']}, indent=2))

if __name__ == '__main__':
    main()
