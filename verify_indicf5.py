"""Explicit real-model smoke test using the publisher's documented demo prompt.

Not part of download-free pytest; runs entirely offline after artifacts are cached.
"""
from pathlib import Path
import json
import time
from engines.indicf5 import IndicF5Engine
from services.audio import write_wav, encode_mp3
from config import ROOT, OUTPUTS

def main():
    engine = IndicF5Engine()
    started = time.perf_counter()
    try:
        engine.load()
        result = engine.synthesize('தமிழ் வாழ்வு அறிவு அருள் பள்ளி நன்றி.', {
            'reference_audio': str(ROOT / 'engine_sources/IndicF5/prompts/PAN_F_HAPPY_00001.wav'),
            'reference_text': 'ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ  ਹਨ।',
            'reference_consent': True,
            'device': 'Auto'})
        import uuid
        folder = OUTPUTS / ('indicf5_smoke_' + uuid.uuid4().hex)
        folder.mkdir(parents=True)
        wav = folder / 'tamil.wav'
        write_wav(wav, result.pcm, result.sample_rate)
        mp3, warning = encode_mp3(wav)
        record = {'text': 'தமிழ் வாழ்வு அறிவு அருள் பள்ளி நன்றி.', 'model_revision': result.version,
            'source_revision': '13f7c4d627cc10111aea8fe9c0039462cacacdc7',
            'vocos_revision': '0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21',
            'reference': 'Publisher README inference example: PAN_F_HAPPY_00001.wav; internal demo only',
            'device': result.device, 'elapsed_seconds_including_load': time.perf_counter()-started,
            **engine.last_metrics, 'wav': str(wav), 'mp3': str(mp3) if mp3 else None,
            'warning': warning, 'human_pronunciation_review': 'pending'}
        (folder / 'metadata.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        (ROOT / 'model_cache/indicf5_verified.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(record, ensure_ascii=True, indent=2))
    finally:
        engine.unload()

if __name__ == '__main__':
    main()
