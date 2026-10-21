"""Keep explicit verse identity attached to every synthesized speech segment."""
import time
from services.bible_heading import extract_heading
from services.speech_normalization import LABEL, prepare_speech_plan

BOOK_IDS = dict(zip(
    'ஆதியாகமம்|யாத்திராகமம்|லேவியராகமம்|எண்ணாகமம்|உபாகமம்|யோசுவா|நியாயாதிபதிகள்|ரூத்|சாமுவேல்|இராஜாக்கள்|ராஜாக்கள்|நாளாகமம்|எஸ்றா|நெகேமியா|எஸ்தர்|யோபு|சங்கீதம்|சங்கீதங்கள்|நீதிமொழிகள்|பிரசங்கி|உன்னதப்பாட்டு|ஏசாயா|எரேமியா|புலம்பல்|புலம்பல்கள்|எசேக்கியேல்|தானியேல்|ஓசியா|யோவேல்|ஆமோஸ்|ஒபதியா|யோனா|மீகா|நாகூம்|ஆபகூக்|செப்பனியா|ஆகாய்|சகரியா|மல்கியா|மத்தேயு|மாற்கு|லூக்கா|யோவான்|அப்போஸ்தலர்|அப்போஸ்தலருடைய நடபடிகள்|ரோமர்|கொரிந்தியர்|கலாத்தியர்|எபேசியர்|பிலிப்பியர்|கொலோசெயர்|தெசலோனிக்கேயர்|தீமோத்தேயு|தீத்து|பிலேமோன்|எபிரெயர்|யாக்கோபு|பேதுரு|யூதா|வெளிப்படுத்தல்|வெளிப்படுத்தின விசேஷம்'.split('|'),
    'genesis|exodus|leviticus|numbers|deuteronomy|joshua|judges|ruth|samuel|kings|kings|chronicles|ezra|nehemiah|esther|job|psalms|psalms|proverbs|ecclesiastes|songofsolomon|isaiah|jeremiah|lamentations|lamentations|ezekiel|daniel|hosea|joel|amos|obadiah|jonah|micah|nahum|habakkuk|zephaniah|haggai|zechariah|malachi|matthew|mark|luke|john|acts|acts|romans|corinthians|galatians|ephesians|philippians|colossians|thessalonians|timothy|titus|philemon|hebrews|james|peter|jude|revelation|revelation'.split('|')))
NUMBERED_ONLY = {'samuel','kings','chronicles','corinthians','thessalonians','timothy','peter'}

def build_chapter_plan(text, mode, pause_ms, punctuation_pauses, number_mode, input_format,
                       language='ta', sentence_pauses=True):
    started = time.perf_counter()
    heading = extract_heading(text, language)
    body_start = heading['body_start'] if heading else 0
    body = text[body_start:]
    lines = body.splitlines(keepends=True)
    content_lines = [line for line in lines if line.strip()]
    numbered = bool(content_lines) and all(LABEL.match(line) for line in content_lines)
    if heading and any(LABEL.match(line) for line in content_lines) and not numbered:
        raise ValueError('This chapter mixes numbered verses and unnumbered/wrapped lines. Put each complete verse on one numbered line; reliable verse timing cannot be inferred from this layout.')
    # A recognized reference + consistently numbered lines is a verified format;
    # arbitrary plain text without that heading is never stripped automatically.
    use_verses = input_format == 'Verse-numbered Bible text' or bool(heading and numbered)
    # Without a heading, three or more lines numbered 1, 2, 3… (strictly increasing)
    # are treated as verses so their labels are not read aloud.
    auto_verses = False
    if not use_verses and not heading and numbered and len(content_lines) >= 3:
        numbers = [int(LABEL.match(line)['number']) for line in content_lines]
        auto_verses = all(a < b for a,b in zip(numbers,numbers[1:])) and all(line[LABEL.match(line).end():].strip() for line in content_lines)
        use_verses = auto_verses
    book_id = None
    if heading and heading.get('book_id'):
        book_id = heading['book_id']
    elif heading:
        base = BOOK_IDS[heading['book']]
        prefix = heading['book_prefix']
        book_id = str(prefix)+base if prefix else (None if base in NUMBERED_ONLY else base)
    parse_ms = (time.perf_counter()-started)*1000
    timings = {'reference_parsing_ms':parse_ms,'text_preprocessing_ms':0.0,'text_chunking_ms':0.0}
    settings = dict(mode=mode,pause_ms=pause_ms,punctuation_pauses=punctuation_pauses,
                    number_mode=number_mode,_allow_heading=False,_timings=timings,
                    language=language,sentence_pauses=sentence_pauses)
    if not use_verses or not content_lines:
        plan = prepare_speech_plan(text,mode,pause_ms,punctuation_pauses,number_mode,input_format,_timings=timings,
                                   language=language,sentence_pauses=sentence_pauses)
        plan.update(chunk_verse_numbers=[None]*len(plan['spoken_chunks']),verse_sources=[],
            book_id=book_id,chapter=heading['chapter'] if heading else None,stage_timings=timings,
            verse_layout_verified=False,heading=heading)
        return plan
    combined = dict(spoken_chunks=[],pauses_ms=[],changes=[],punctuation_events=[],warnings=[],
        normalized_number_text='',chunk_verse_numbers=[],verse_sources=[])
    pending, offset, last_verse = 0, body_start, 0
    def append(plan, verse):
        nonlocal pending
        if combined['spoken_chunks']:
            combined['pauses_ms'].append(pending)
        combined['spoken_chunks'].extend(plan['spoken_chunks'])
        combined['pauses_ms'].extend(plan['pauses_ms'])
        combined['chunk_verse_numbers'].extend([verse]*len(plan['spoken_chunks']))
        combined['punctuation_events'].extend(plan['punctuation_events'])
        combined['warnings'].extend(plan['warnings'])
        pending = plan['trailing_pause_ms']
    if heading:
        hp = prepare_speech_plan(heading['spoken'],input_format='Plain text',**settings)
        append(hp,None)
        pending = max(450,pause_ms)
        combined['changes'].append(dict(start=heading['start'],end=heading['end'],original=heading['original'],
            replacement=heading['spoken'],reason='Bible reference heading'))
        combined['normalized_number_text'] = text[:heading['start']]+heading['spoken']+'\n'
    for line in lines:
        if line.strip():
            match = LABEL.match(line)
            if not match or not line[match.end():].strip() or int(match['number']) <= last_verse:
                raise ValueError('For verse timing, use one complete numbered verse per line with positive, increasing verse numbers. Wrapped or mixed layouts must be corrected explicitly.')
            verse = int(match['number'])
            last_verse = verse
            vp = prepare_speech_plan(line,input_format='Verse-numbered Bible text',**settings)
            combined['verse_sources'].append(dict(verse_number=verse,original_text=line,
                first_chunk=len(combined['spoken_chunks']),chunk_count=len(vp['spoken_chunks'])))
            append(vp,verse)
            combined['changes'].extend(dict(change,start=change['start']+offset,end=change['end']+offset) for change in vp['changes'])
            combined['normalized_number_text'] += vp['normalized_number_text']
        else:
            combined['normalized_number_text'] += line
        offset += len(line)
    combined.update(normalized_tts_text='\n'.join(combined['spoken_chunks']),
        book_id=book_id,chapter=heading['chapter'] if heading else None,stage_timings=timings,
        verse_layout_verified=True,heading=heading,trailing_pause_ms=pending)
    if auto_verses:
        combined['warnings'].append('Numbered verse lines detected automatically: verse numbers are not read aloud. If the numbers should be spoken, add a word before each number.')
    return combined

def verse_pcm_boundaries(plan, boundaries, total_samples, rate):
    result = []
    for source in plan['verse_sources']:
        first = source['first_chunk']
        last = first+source['chunk_count']-1
        result.append(dict(verse_number=source['verse_number'],start_sample=boundaries[first]['start_sample'],
            speech_end_sample=boundaries[last]['end_sample'],original_text=source['original_text']))
    for i,verse in enumerate(result):
        # Assign the following inter-verse pause to the preceding verse. End is exclusive.
        verse['end_sample'] = result[i+1]['start_sample'] if i+1<len(result) else total_samples
        for key in ('start','end','speech_end'):
            verse[key+'_ms'] = round(verse[key+'_sample']*1000/rate)
    return result
