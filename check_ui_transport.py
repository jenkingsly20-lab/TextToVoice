"""Explicit localhost upload + queued generation smoke check (uses model/demo audio)."""
import json
import uuid
import sys
import tempfile
import subprocess
from pathlib import Path
import httpx

def main():
    base = 'http://127.0.0.1:7860'
    with httpx.Client(base_url=base, timeout=180) as client:
        config = client.get('/config').json()
        components = {c['id']: c for c in config['components']}
        dependency = next(d for d in config['dependencies'] if any(
            components.get(t[0], {}).get('props', {}).get('value') == 'Generate Speech' for t in d['targets']))
        if not dependency['inputs']:
            dependency = next(d for d in config['dependencies'] if d.get('trigger_after') == dependency['id'] and len(d['inputs']) >= 10)
        default_mode = '--default' in sys.argv
        sample = Path(__file__).parent / 'engine_sources/IndicF5/prompts/PAN_F_HAPPY_00001.wav'
        temporary = tempfile.TemporaryDirectory(prefix='tts_transport_')
        if '--m4a' in sys.argv:
            m4a = Path(temporary.name) / 'Recording 6.m4a'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(sample), '-c:a', 'aac', str(m4a)], check=True)
            sample = m4a
        path = None
        if not default_mode:
            with sample.open('rb') as source:
                upload = client.post('/gradio_api/upload', files={'files': (sample.name, source, 'audio/mp4' if sample.suffix == '.m4a' else 'audio/wav')})
            upload.raise_for_status()
            path = upload.json()[0]
            print('Upload OK', flush=True)
        samples = ['கர்த்தர் என் மேய்ப்பராயிருக்கிறார்; நான் தாழ்ச்சியடையேன்.',
            'ஆதியிலே வார்த்தை இருந்தது, அந்த வார்த்தை தேவனிடத்திலிருந்தது, அந்த வார்த்தை தேவனாயிருந்தது.',
            'தேவன் தம்முடைய ஒரேபேறான குமாரனை விசுவாசிக்கிறவன் எவனோ அவன் கெட்டுப்போகாமல் நித்தியஜீவனை அடையும்படிக்கு, அவரைத் தந்தருளி, இவ்வளவாய் உலகத்தில் அன்புகூர்ந்தார்.']
        sample_index = int(sys.argv[sys.argv.index('--sample')+1])-1 if '--sample' in sys.argv else 0
        verse_test = '--verse-test' in sys.argv
        number_test = '--number-test' in sys.argv
        if verse_test:
            samples[sample_index] = '1 '+samples[0]+'\n2 '+samples[1]
        if number_test:
            samples[sample_index] = '123 பேர் வந்தார்கள்; 12 பேர் பேசினார்கள், 3 பேர் கேட்டார்கள். எல்லோரும் சென்றார்கள்.'
        session = uuid.uuid4().hex
        request = {'fn_index': dependency['id'], 'session_hash': session, 'data': [
            samples[sample_index], 'indicf5', 'Lines', 400, 'Reference recording',
            {'path': path, 'meta': {'_type': 'gradio.FileData'}},
            'ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ  ਹਨ।',
            True, 'Auto']}
        if len(dependency['inputs']) >= 10:
            request['data'].insert(5, not default_mode)
        if default_mode:
            request['data'][6:9] = [None, '', False]
        if len(dependency['inputs']) >= 12:
            request['data'].extend([True, 'Tamil number words'])
        if len(dependency['inputs']) >= 13:
            request['data'].append('Verse-numbered Bible text' if verse_test else 'Plain text')
        joined = client.post('/gradio_api/queue/join', json=request)
        joined.raise_for_status()
        print('Queue joined:', joined.text, flush=True)
        with client.stream('GET', '/gradio_api/queue/data', params={'session_hash': session}) as stream:
            for line in stream.iter_lines():
                if not line.startswith('data: '):
                    continue
                message = json.loads(line[6:])
                if message.get('msg') != 'process_completed':
                    print(json.dumps(message, ensure_ascii=True)[:600], flush=True)
                if message.get('msg') == 'process_completed':
                    assert message.get('success'), message
                    data = message['output']['data']
                    assert data[0] and data[1], data
                    record = data[4]
                    assert record['original_text'] == samples[sample_index]
                    if default_mode:
                        assert record['settings']['voice_provenance']['id'] == 'rasa_tamil_female_book_00014'
                    if verse_test:
                        assert [x['verse_number'] for x in record['speech_text_changes'] if x['reason']=='explicit verse label'] == [1,2]
                    if number_test:
                        assert 'நூற்று இருபத்து மூன்று' in record['normalized_tts_text']
                    if verse_test or number_test:
                        assert ';' not in record['normalized_tts_text']
                        assert 350 in record['pauses_ms']
                    wav = client.get(data[0]['url'])
                    mp3 = client.get(data[1]['url'])
                    assert wav.status_code == 200 and wav.content[:4] == b'RIFF'
                    assert mp3.status_code == 200 and len(mp3.content) > 1000
                    print(json.dumps({'sample':sample_index+1,'output_id':record['id'],'duration_seconds':record['duration_seconds'],'elapsed_seconds':record['elapsed_seconds'],'device':record['device'],'mp3_download_bytes':len(mp3.content),'text_preserved':True,'default_voice':default_mode},ensure_ascii=True), flush=True)
                    return
        raise RuntimeError('Queue ended without completed output.')

if __name__ == '__main__':
    main()
