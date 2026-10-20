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
SENTENCE_END = re.compile(r'[;；.!?。！？…।]+\s*')
# Symbols the model would try to pronounce. A bracketed bare number such as "(43)" is
# a merged verse label in the source text, so it is removed rather than read; words
# inside brackets (e.g. "(சேலா)") are kept and only the brackets go.
SPEECH_CLEANUP = re.compile(r'\(\s*' + D + r'+\s*\)|[()\[\]"“”‘’\']|(?<=\S)-(?=\S)')  # \w misses Tamil virama (்)
TRAILING_SEMICOLON = re.compile(r'[;；]+(\s*)$')
CLAUSE_END = re.compile(r'[,:：，]+\s*')
# One model call per sentence keeps commas inline for natural prosody; sentences
# longer than this are split further, so each call stays well under IndicF5's 30 s window.
MAX_CHUNK_CHARS = 220
PAUSES = {',':180,'，':180,':':250,'：':250,';':350,'；':350,'.':450,'。':450,'।':450,'?':500,'？':500,'!':450,'！':450,'…':600}

def split_long(source, limit=MAX_CHUNK_CHARS):
    """Split a verse/line at every sentence end, then split any sentence longer than limit.

    The model does not pause reliably at full stops inside one call, so each sentence
    is its own chunk followed by real silence. Commas stay inside the sentence for
    natural phrasing; clause and word splits are used only for over-long sentences.
    Returns (part, pause_ms_after) pairs; punctuation stays with its part."""
    def pieces(text, pattern):
        result, cursor = [], 0
        for match in pattern.finditer(text):
            result.append((text[cursor:match.end()], max(PAUSES[c] for c in match[0].strip())))
            cursor = match.end()
        if text[cursor:]:
            result.append((text[cursor:], 0))
        return result
    def words(text):
        return [(word, 120) for word in re.findall(r'\S+\s*', text)]
    parts = []
    for sentence, pause in pieces(source, SENTENCE_END):
        if not sentence.strip():
            if parts:
                parts[-1] = (parts[-1][0] + sentence, parts[-1][1])
            continue
        if len(sentence.strip()) <= limit:
            parts.append((sentence, pause))
            continue
        sub = []
        for clause, clause_pause in pieces(sentence, CLAUSE_END):
            sub.extend([(clause, clause_pause)] if len(clause.strip()) <= limit else words(clause))
            sub[-1] = (sub[-1][0], max(sub[-1][1], clause_pause))
        merged = []
        for part, part_pause in sub:
            if merged and len((merged[-1][0] + part).strip()) <= limit:
                merged[-1] = (merged[-1][0] + part, part_pause)
            else:
                merged.append((part, part_pause))
        merged[-1] = (merged[-1][0], pause)
        parts.extend(merged)
    if not parts:
        return [(source, 0)]
    parts[-1] = (parts[-1][0], 0)
    # IndicF5 voices a chunk-final semicolon as an extra syllable; the silence after
    # the chunk already marks it, so the model never sees it.
    return [(TRAILING_SEMICOLON.sub(r'\1', part), pause) for part, pause in parts]

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
    for match in SPEECH_CLEANUP.finditer(text):
        if not any(a <= match.start() < b for a,b in labels):
            # Hyphens inside words become a space; everything else is dropped.
            replacement = ' ' if match[0] == '-' else ''
            labels.append((match.start(),match.end()))
            changes.append(dict(start=match.start(),end=match.end(),original=match[0],
                replacement=replacement,reason='speech cleanup: symbol or embedded verse number not read aloud'))
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
        for part, pause in (split_long(tail) if not punctuation_pauses else [(tail, 0)]):
            if part.strip():
                if chunks: gaps.append(pending)
                chunks.append(part)
                pending = pause
        pending = max(pending,pause_ms)
    if not chunks: raise ValueError('No speakable text remains after selected speech settings.')
    timing['text_preprocessing_ms'] += (time.perf_counter()-measured)*1000
    return dict(spoken_chunks=chunks,pauses_ms=gaps,normalized_number_text=normalized,
        normalized_tts_text='\n'.join(chunks),changes=changes,punctuation_events=events,warnings=warnings,trailing_pause_ms=pending)

def prepare_speech_chunks(chunks, semicolon_pause=True, number_mode='Keep numbers unchanged', input_format='Plain text'):
    plan = prepare_speech_plan(''.join(chunks),'Whole text',400,semicolon_pause,number_mode,input_format)
    return plan['spoken_chunks'],plan['changes']

def preview_speech(text, punctuation_pauses=False, number_mode='Tamil number words', input_format='Plain text', mode='Lines', pause_ms=400):
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
