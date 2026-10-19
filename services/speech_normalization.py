"""Speech-only transformations with an audit trail; never overwrite input text."""
import re
import time
from indic_numtowords import num2words
from services.text_chunks import chunk_text

NUMBER_MODES = ['Tamil number words', 'Keep numbers unchanged', 'Read each digit in Tamil']
INPUT_FORMATS = ['Plain text', 'Verse-numbered Bible text']
DIGITS = ('பூஜ்ஜியம்', 'ஒன்று', 'இரண்டு', 'மூன்று', 'நான்கு', 'ஐந்து', 'ஆறு', 'ஏழு', 'எட்டு', 'ஒன்பது')
D = r'[0-9௦-௯]'
LABEL = re.compile(r'^[ \t]*(?P<number>' + D + r'+)(?:[.)])?[ \t]+')
TOKEN = re.compile(r'(?<!\w)[+-]?(?:' + D + r'{1,2}(?:,' + D + r'{2})+,' + D + r'{3}|' + D + r'{1,3}(?:,' + D + r'{3})+|' + D + r'+)(?:\.' + D + r'+)?(?!\w)')
PUNCTUATION = re.compile(r'[;；,:：，.!?。！？…।]+')
PAUSES = {',':180,'，':180,':':250,'：':250,';':350,'；':350,'.':450,'。':450,'।':450,'?':500,'？':500,'!':450,'！':450,'…':600}

def tamil_number(token, digits=False):
    value = ''.join(str(int(c)) if c.isdecimal() else c for c in token).replace(',', '')
    sign = ''
    if value.startswith(('-', '+')):
        sign, value = ('மைனஸ் ' if value[0] == '-' else 'பிளஸ் '), value[1:]
    whole, dot, fraction = value.partition('.')
    if len(whole) > 15:
        raise ValueError('Numbers above 15 digits need a reviewed spoken form.')
    if digits or (len(whole) > 1 and whole.startswith('0')):
        words = ' '.join(DIGITS[int(c)] for c in whole)
    else:
        words = num2words(int(whole), lang='ta').replace('\u200c', '').strip()
    if not words:
        raise ValueError('Unable to normalize this Tamil number: ' + token)
    if dot:
        words += ' புள்ளி ' + ' '.join(DIGITS[int(c)] for c in fraction)
    return sign + words

def normalize_text(text, number_mode, input_format):
    if number_mode not in NUMBER_MODES or input_format not in INPUT_FORMATS:
        raise ValueError('Unknown number reading mode or Bible input format.')
    changes, labels, last, offset = [], [], 0, 0
    if input_format == INPUT_FORMATS[1]:
        for line in text.splitlines(keepends=True):
            if line.strip():
                match = LABEL.match(line)
                if not match or not line[match.end():].strip():
                    raise ValueError('Verse-numbered format requires one verse per line: number, space, verse text. Select Plain text for other layouts.')
                verse = int(match['number'])
                if verse <= last:
                    raise ValueError('Verse numbers must be positive and strictly increasing within one chapter.')
                last = verse
                a,b = offset, offset+match.end()
                labels.append((a,b))
                changes.append(dict(start=a,end=b,original=text[a:b],replacement='',reason='explicit verse label',verse_number=verse))
            offset += len(line)
    if number_mode != 'Keep numbers unchanged':
        for match in TOKEN.finditer(text):
            if not any(a <= match.start() < b for a,b in labels):
                changes.append(dict(start=match.start(),end=match.end(),original=match[0],
                    replacement=tamil_number(match[0], number_mode=='Read each digit in Tamil'),reason=number_mode))
    changes.sort(key=lambda change:change['start'])
    parts, cursor = [], 0
    for change in changes:
        parts.extend([text[cursor:change['start']],change['replacement']])
        cursor = change['end']
    parts.append(text[cursor:])
    normalized = ''.join(parts)
    warnings = []
    if number_mode != 'Keep numbers unchanged' and re.search(D, normalized):
        warnings.append('Attached numeric forms (ordinals/IDs) remain unchanged; review preview. No Bible words or suffixes were guessed or removed.')
    return normalized, changes, warnings

def prepare_speech_plan(text, mode='Lines', pause_ms=400, punctuation_pauses=True,
                        number_mode='Tamil number words', input_format='Plain text', _allow_heading=True, _timings=None):
    timing = _timings if _timings is not None else {'text_preprocessing_ms':0.0,'text_chunking_ms':0.0}
    measured = time.perf_counter()
    chunk_text(text, mode)
    timing['text_chunking_ms'] += (time.perf_counter()-measured)*1000
    if _allow_heading:
        from services.bible_heading import extract_heading
        heading = extract_heading(text)
        if heading:
            head = prepare_speech_plan(heading['spoken'],mode,pause_ms,punctuation_pauses,
                'Keep numbers unchanged','Plain text',_allow_heading=False,_timings=timing)
            body_text = text[heading['body_start']:]
            body = prepare_speech_plan(body_text,mode,pause_ms,punctuation_pauses,
                number_mode,input_format,_allow_heading=False,_timings=timing) if body_text.strip() else None
            head['changes'] = [dict(start=heading['start'],end=heading['end'],
                original=heading['original'],replacement=heading['spoken'],reason='Bible reference heading')]
            if body:
                head['spoken_chunks'] += body['spoken_chunks']
                head['pauses_ms'] += [max(450,pause_ms)]+body['pauses_ms']
                head['punctuation_events'] += body['punctuation_events']
                head['warnings'] += body['warnings']
                head['changes'] += [dict(change,start=change['start']+heading['body_start'],
                    end=change['end']+heading['body_start']) for change in body['changes']]
            head['normalized_number_text'] = (text[:heading['start']]+heading['spoken']+
                ('\n'+body['normalized_number_text'] if body else ''))
            head['normalized_tts_text'] = '\n'.join(head['spoken_chunks'])
            head['trailing_pause_ms'] = body['trailing_pause_ms'] if body else head['trailing_pause_ms']
            return head
    measured = time.perf_counter()
    normalized, changes, warnings = normalize_text(text, number_mode, input_format)
    timing['text_preprocessing_ms'] += (time.perf_counter()-measured)*1000
    measured = time.perf_counter()
    source_chunks = chunk_text(normalized, mode)
    timing['text_chunking_ms'] += (time.perf_counter()-measured)*1000
    measured = time.perf_counter()
    chunks, gaps, events, pending = [], [], [], 0
    for source in source_chunks:
        cursor = 0
        for match in list(PUNCTUATION.finditer(source)) if punctuation_pauses else []:
            part = source[cursor:match.start()]
            if part.strip():
                if chunks: gaps.append(pending)
                chunks.append(part)
                pending = 0
            duration = max(PAUSES[c] for c in match[0])
            if len(match[0]) >= 3 and set(match[0]) == {'.'}: duration = 600
            pending = max(pending,duration)
            events.append(dict(punctuation=match[0],pause_ms=duration,source_chunk=source,start=match.start(),end=match.end()))
            cursor = match.end()
        tail = source[cursor:]
        if tail.strip():
            if chunks: gaps.append(pending)
            chunks.append(tail)
            pending = 0
        pending = max(pending,pause_ms)
    if not chunks: raise ValueError('No speakable text remains after selected speech settings.')
    timing['text_preprocessing_ms'] += (time.perf_counter()-measured)*1000
    return dict(spoken_chunks=chunks,pauses_ms=gaps,normalized_number_text=normalized,
        normalized_tts_text='\n'.join(chunks),changes=changes,punctuation_events=events,warnings=warnings,trailing_pause_ms=pending)

def prepare_speech_chunks(chunks, semicolon_pause=True, number_mode='Keep numbers unchanged', input_format='Plain text'):
    plan = prepare_speech_plan(''.join(chunks),'Whole text',400,semicolon_pause,number_mode,input_format)
    return plan['spoken_chunks'],plan['changes']

def preview_speech(text, punctuation_pauses=True, number_mode='Tamil number words', input_format='Plain text', mode='Lines', pause_ms=400):
    if not text or not text.strip(): return ''
    try:
        from services.chapter_plan import build_chapter_plan
        plan = build_chapter_plan(text,mode,pause_ms,punctuation_pauses,number_mode,input_format)
        parts = []
        for i,chunk in enumerate(plan['spoken_chunks']):
            if i: parts.append(f"[இடைவெளி {plan['pauses_ms'][i-1]} ms]")
            parts.append(chunk)
        return '\n'.join(parts+plan['warnings'])
    except ValueError as exc: return 'Error — '+str(exc)
