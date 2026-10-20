import json
import numpy as np
from services.speech_normalization import prepare_speech_chunks, prepare_speech_plan, tamil_number
from services.generation import generate

def test_semicolon_is_a_boundary_without_changing_words():
    chunks, changes = prepare_speech_chunks(['கர்த்தர் என் மேய்ப்பர்; நான் தாழ்ச்சியடையேன்.'])
    assert chunks == ['கர்த்தர் என் மேய்ப்பர்', ' நான் தாழ்ச்சியடையேன்']
    assert changes == []
    # Without comma splitting, sentence ends still split but keep their punctuation.
    # A chunk-final semicolon is replaced by silence; the model would voice it.
    assert prepare_speech_chunks(['தமிழ்; அருள்'], False)[0] == ['தமிழ் ', 'அருள்']
    assert prepare_speech_chunks(['தமிழ், அருள்'], False)[0] == ['தமிழ், அருள்']

def test_numbers_require_explicit_mode():
    original = '1 தமிழ் 123.\n2 அருள் ௩.'
    assert ''.join(prepare_speech_chunks([original], False)[0]) == original
    digits, _ = prepare_speech_chunks([original], number_mode='Read each digit in Tamil')
    assert 'ஒன்று இரண்டு மூன்று' in digits[0]
    labels = prepare_speech_plan(original, input_format='Verse-numbered Bible text')
    assert labels['normalized_number_text'] == 'தமிழ் நூற்று இருபத்து மூன்று.\nஅருள் மூன்று.'
    assert prepare_speech_plan('யோவான் 3:16')['normalized_number_text'] == 'யோவான், மூன்றாம் அதிகாரம், பதினாறாம் வசனம்.'

def test_pcm_pause_and_original_metadata(tmp_path):
    original = 'தமிழ்; அருள் 12.'
    _, _, meta, record = generate(original, output_root=tmp_path, pause_ms=400,
        number_mode='Read each digit in Tamil', semicolon_pause=True)
    assert record['original_text'] == original
    assert len(record['spoken_chunks']) == 2
    bounds = record['chunk_sample_boundaries']
    assert bounds[1]['start_sample'] - bounds[0]['end_sample'] == 8400
    assert record['speech_text_changes']

def test_tamil_cardinals_and_numeric_punctuation():
    assert tamil_number('123') == 'நூற்று இருபத்து மூன்று'
    assert tamil_number('௧௨௩') == 'நூற்று இருபத்து மூன்று'
    assert tamil_number('3.14') == 'மூன்று புள்ளி ஒன்று நான்கு'
    assert tamil_number('-12') == 'மைனஸ் பன்னிரண்டு'
    assert tamil_number('1,000') == 'ஆயிரம்'
    assert tamil_number('012') == 'பூஜ்ஜியம் ஒன்று இரண்டு'
    plan = prepare_speech_plan('123 பேர், 3.14 அளவு; 1,000 பேர். முடிவு!')
    assert plan['pauses_ms'] == [180,350,450]
    assert 'மூன்று புள்ளி ஒன்று நான்கு' in plan['normalized_tts_text']

def test_leading_counts_not_removed_in_plain_text():
    plan = prepare_speech_plan('123 பேர் வந்தனர்.\n2 பேர் சென்றனர்.')
    assert plan['normalized_number_text'].startswith('நூற்று இருபத்து மூன்று பேர்')
    assert 'இரண்டு பேர்' in plan['normalized_number_text']
    assert not any(c['reason']=='explicit verse label' for c in plan['changes'])

def test_invalid_verse_layout_refused_and_unrecognized_forms_logged():
    import pytest
    for text in ['1 வசனம்\nதொடர்ச்சி', '2 வசனம்\n1 வசனம்', '0 வசனம்']:
        with pytest.raises(ValueError):
            prepare_speech_plan(text,input_format='Verse-numbered Bible text')
    plan = prepare_speech_plan('3ஆம் அதிகாரம்')
    assert plan['normalized_number_text'] == '3ஆம் அதிகாரம்'
    assert plan['warnings']

def test_numbered_bible_words_and_original_are_auditable(tmp_path):
    source = '1 கர்த்தர் என் மேய்ப்பர்; நான் தாழ்ச்சியடையேன்.\n2 அவர் 123 பேரை அழைத்தார், அவர்கள் வந்தார்கள்.'
    *_, record = generate(source, output_root=tmp_path,input_format='Verse-numbered Bible text',semicolon_pause=True)
    assert record['original_text'] == source
    assert 'நூற்று இருபத்து மூன்று பேரை' in record['normalized_tts_text']
    assert [c['verse_number'] for c in record['speech_text_changes'] if c['reason']=='explicit verse label'] == [1,2]
    for change in record['speech_text_changes']:
        assert source[change['start']:change['end']] == change['original']
    assert ';' not in record['normalized_tts_text']

def test_default_keeps_one_chunk_per_verse_with_punctuation(tmp_path):
    source = 'யோவான் 1\n1 கர்த்தர் என் மேய்ப்பர்; நான் தாழ்ச்சியடையேன்.\n2 அவர் அழைத்தார், அவர்கள் வந்தார்கள்.'
    *_, record = generate(source, output_root=tmp_path)
    # Heading, verse 1 split at its semicolon (sentence end, real silence), verse 2 kept
    # whole with its comma inline for natural phrasing.
    assert record['spoken_chunks'][1:] == ['கர்த்தர் என் மேய்ப்பர் ','நான் தாழ்ச்சியடையேன்.\n',
                                         'அவர் அழைத்தார், அவர்கள் வந்தார்கள்.']
    assert record['pauses_ms'][1] == 350
    assert [v['verse_number'] for v in record['verse_pcm_segments']] == [1,2]

def test_long_lines_split_at_sentence_then_clause_boundaries():
    from services.speech_normalization import split_long
    sentence = 'அவர் ' * 30 + 'வந்தார். '
    parts = split_long(sentence * 3, limit=220)
    assert len(parts) > 1 and all(len(p.strip()) <= 220 for p, _ in parts)
    assert ''.join(p for p, _ in parts) == sentence * 3
    assert parts[0][0].rstrip().endswith('.') and parts[0][1] == 450 and parts[-1][1] == 0
    clause = ('அவர் ' * 30 + 'வந்தார், ') * 3
    parts = split_long(clause, limit=220)
    assert all(len(p.strip()) <= 220 for p, _ in parts) and ''.join(p for p, _ in parts) == clause
    words = 'அவர்வந்தார் ' * 40
    assert all(len(p.strip()) <= 220 for p, _ in split_long(words, limit=220))
    assert split_long('குறுகிய வரி.') == [('குறுகிய வரி.', 0)]

def test_numbered_lines_without_heading_are_detected_as_verses():
    from services.chapter_plan import build_chapter_plan
    plan = build_chapter_plan('1 முதல் வசனம்.\n2 இரண்டாம் வசனம்.\n3 மூன்றாம் வசனம்.', 'Lines', 400, False,
                              'Tamil number words', 'Plain text')
    assert plan['chunk_verse_numbers'] == [1,2,3]
    assert not plan['spoken_chunks'][0].lstrip().startswith(('1','ஒன்று'))
    assert any('detected automatically' in w for w in plan['warnings'])
    two = build_chapter_plan('1 முதல்.\n2 இரண்டு.', 'Lines', 400, False, 'Tamil number words', 'Plain text')
    assert two['chunk_verse_numbers'] == [None,None]

def test_chunk_cache_resumes_and_is_cleared(tmp_path):
    import numpy as np
    from engines.base import AudioResult, Capabilities
    from services.chapter_generation import synthesize_all
    class Engine:
        capabilities = Capabilities()
        def __init__(self): self.calls = []
        def synthesize_batch(self, texts, options):
            self.calls.append(list(texts))
            return [AudioResult(np.full(10*len(t), .1, np.float32), 24000, 'cuda', '1') for t in texts]
    engine = Engine()
    options = dict(steps=16, precision='bf16', seed=1, reference_text='x')
    chunks = ['மூன்று', 'ஒன்று இரண்டு', 'அ']
    results, records, _, files = synthesize_all(engine, chunks, options, tmp_path)
    assert engine.calls == [['அ', 'மூன்று', 'ஒன்று இரண்டு']]  # sorted by length into one batch
    assert [len(r.pcm) for r in results] == [60, 120, 10]
    assert all(f.is_file() for f in files)
    again, records, _, _ = synthesize_all(engine, chunks, options, tmp_path)
    assert len(engine.calls) == 1 and all(r['cache_hit'] for r in records)
    assert [len(r.pcm) for r in again] == [60, 120, 10]
