import json
import numpy as np
from services.speech_normalization import prepare_speech_chunks, prepare_speech_plan, tamil_number
from services.generation import generate

def test_semicolon_is_a_boundary_without_changing_words():
    chunks, changes = prepare_speech_chunks(['கர்த்தர் என் மேய்ப்பர்; நான் தாழ்ச்சியடையேன்.'])
    assert chunks == ['கர்த்தர் என் மேய்ப்பர்', ' நான் தாழ்ச்சியடையேன்']
    assert changes == []
    assert prepare_speech_chunks(['தமிழ்; அருள்'], False)[0] == ['தமிழ்; அருள்']

def test_numbers_require_explicit_mode():
    original = '1 தமிழ் 123.\n2 அருள் ௩.'
    assert prepare_speech_chunks([original], False)[0] == [original]
    digits, _ = prepare_speech_chunks([original], number_mode='Read each digit in Tamil')
    assert 'ஒன்று இரண்டு மூன்று' in digits[0]
    labels = prepare_speech_plan(original, input_format='Verse-numbered Bible text')
    assert labels['normalized_number_text'] == 'தமிழ் நூற்று இருபத்து மூன்று.\nஅருள் மூன்று.'
    assert prepare_speech_plan('யோவான் 3:16')['normalized_number_text'] == 'யோவான், மூன்றாம் அதிகாரம், பதினாறாம் வசனம்.'

def test_pcm_pause_and_original_metadata(tmp_path):
    original = 'தமிழ்; அருள் 12.'
    _, _, meta, record = generate(original, output_root=tmp_path, pause_ms=400,
        number_mode='Read each digit in Tamil')
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
    *_, record = generate(source, output_root=tmp_path,input_format='Verse-numbered Bible text')
    assert record['original_text'] == source
    assert 'நூற்று இருபத்து மூன்று பேரை' in record['normalized_tts_text']
    assert [c['verse_number'] for c in record['speech_text_changes'] if c['reason']=='explicit verse label'] == [1,2]
    for change in record['speech_text_changes']:
        assert source[change['start']:change['end']] == change['original']
    assert ';' not in record['normalized_tts_text']
