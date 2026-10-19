"""Install three small attributed reference clips; no model download/inference."""
import hashlib
import json
from pathlib import Path
import httpx
from huggingface_hub import HfApi, get_token
from install_default_voice import REVISION, ROOT

SAMPLES = [
    (77, 'TAM_F_NEWS_00621', 'Female', 'NEWS', 'Tamil female — news style'),
    (24, 'TAM_F_CONV_02748', 'Female', 'CONV', 'Tamil female — conversational style'),
    (2236, 'TAM_M_BOOK_00072', 'Male', 'BOOK', 'Tamil male — narration'),
]

def main():
    token = get_token()
    if not token:
        raise SystemExit('Local Hugging Face login is required.')
    if HfApi(token=token).dataset_info('ai4bharat/Rasa').sha != REVISION:
        raise SystemExit('Dataset revision changed; recheck sample provenance.')
    template = json.loads((ROOT/'assets/voices/default_tamil/voice.json').read_text(encoding='utf-8'))
    for index, sample_id, gender, style, label in SAMPLES:
        response = httpx.get('https://datasets-server.huggingface.co/rows',
            params=dict(dataset='ai4bharat/Rasa', config='Tamil', split='test', offset=index, length=1),
            headers={'Authorization':'Bearer '+token}, timeout=30)
        response.raise_for_status()
        row = response.json()['rows'][0]['row']
        if (row['filename'], row['language'], row['gender'], row['style']) != (sample_id, 'Tamil', gender, style):
            raise ValueError('Dataset sample metadata changed.')
        if not 1 <= float(row['duration']) <= 15 or not row['text'].strip():
            raise ValueError('Reference duration or transcript is unsuitable.')
        audio = httpx.get(row['audio'][0]['src'], follow_redirects=True, timeout=60)
        audio.raise_for_status()
        folder = ROOT/'assets/voices'/sample_id.lower()
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'reference.wav').write_bytes(audio.content)
        (folder/'transcript.txt').write_text(row['text'], encoding='utf-8')
        metadata = dict(template, id='rasa_'+sample_id.lower(), display_name=label,
            audio_sha256=hashlib.sha256(audio.content).hexdigest(),
            transcript_sha256=hashlib.sha256(row['text'].encode('utf-8')).hexdigest(),
            source_row_index=index, source_sample_id=sample_id, duration_seconds=float(row['duration']),
            gender=gender, style=style, quality_review='Source reference only; generated voice quality awaits user review.')
        (folder/'voice.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        (folder/'ATTRIBUTION.md').write_text(label+'\n\n'+metadata['attribution']+'\n\n'+metadata['source_url']+'\n'+metadata['license_url']+'\n\n'+metadata['changes']+'\n', encoding='utf-8')
        print('Installed:', label, sample_id, len(audio.content), 'bytes')

if __name__ == '__main__':
    main()
