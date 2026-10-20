"""Generate chapter MP3 + JSON files for whole Bible books from the Tamil SQLite database.

Each chapter goes through the same pipeline as the app (heading, verse timing, MP3
verification) and is saved as <book>_<chapter>.mp3 + .json in outputs/batch/<book>/,
with an index.json per book.

Stopping and resuming:
  * Ctrl+C once  -> finishes the current chapter, then stops.
  * Ctrl+C twice -> stops immediately; the pieces already generated are kept.
  * Run the same command again -> finished chapters are skipped and a half-done
    chapter continues from its saved pieces.

Examples:
    .\\.venv\\Scripts\\python.exe batch_generate.py --books john,matthew
    .\\.venv\\Scripts\\python.exe batch_generate.py --books nt --voices male,female
    .\\.venv\\Scripts\\python.exe batch_generate.py --books john --chapters 1-5
    .\\.venv\\Scripts\\python.exe batch_generate.py --list-books
"""
import argparse
import html
import json
import os
import shutil
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import config
from services.chapter_generation import generate, registry, replace_with_retry, QUALITY_PRESETS, DEFAULT_QUALITY
from services.chapter_plan import BOOK_IDS

DEFAULT_DB = config.ROOT / '.venv-indicf5' / 'BibleDB' / 'tamil.db'
DEFAULT_OUT = config.OUTPUTS / 'batch'
SECONDS_PER_VERSE_GUESS = 3.0
VOICE_ALIASES = {'female': 'default', 'male': 'rasa_tam_m_book_00072'}
GROUPS = {'nt': range(40, 67), 'ot': range(1, 40), 'all': range(1, 67)}

def open_db(path):
    if not Path(path).is_file():
        sys.exit(f'Bible database not found: {path}')
    return sqlite3.connect(f'file:{Path(path).as_posix()}?mode=ro', uri=True)

def book_names(db):
    raw = db.execute('select booknames from configuration').fetchone()[0]
    return [name.strip().strip("'") for name in raw.split(',')]

def book_id(name):
    prefix, _, base = name.partition(' ') if name[:1].isdigit() else ('', '', name)
    return prefix + BOOK_IDS[base]

def resolve_books(db, value):
    names = book_names(db)
    ids = [book_id(name) for name in names]
    numbers = []
    for item in (part.strip() for part in value.split(',') if part.strip()):
        key = item.lower().replace(' ', '')
        if key in GROUPS:
            numbers.extend(GROUPS[key])
        elif item.isdigit() and 1 <= int(item) <= len(names):
            numbers.append(int(item))
        elif item in names:
            numbers.append(names.index(item) + 1)
        elif key in ids:
            numbers.append(ids.index(key) + 1)
        else:
            sys.exit(f'Unknown book {item!r}. Use --list-books to see names and numbers.')
    return [(n, names[n - 1], ids[n - 1]) for n in dict.fromkeys(numbers)]

def parse_chapters(value, available):
    if not value:
        return available
    chosen = set()
    for part in value.split(','):
        start, _, end = part.partition('-')
        chosen.update(range(int(start), int(end or start) + 1))
    return [c for c in available if c in chosen]

def chapter_text(db, number, name, chapter):
    verses = db.execute('select verseNum, word from words where bookNum=? and chNum=? order by verseNum',
                        (number, chapter)).fetchall()
    # The database contains HTML entities such as &quot; and &#39; in some verses.
    return f'{name} {chapter}\n' + '\n'.join(f'{verse} {html.unescape(text).strip()}' for verse, text in verses), len(verses)

def write_index(folder, number, name, identifier, quality):
    chapters = []
    for manifest in sorted(folder.glob(f'{identifier}_*.json')):
        data = json.loads(manifest.read_text(encoding='utf-8'))
        chapters.append(dict(chapter=data['chapter'], audio_filename=data['audio_filename'],
            metadata_filename=manifest.name, verse_count=len(data['verses']), voice=data['settings'].get('voice'),
            duration_ms=data['total_duration_ms'], generation_seconds=round(data['elapsed_seconds'], 1)))
    index = dict(book_number=number, book_name=name, book_id=identifier, quality=quality,
                 updated_utc=datetime.now(timezone.utc).isoformat(), chapters=chapters)
    (folder / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')

def clock(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600}h {seconds % 3600 // 60:02d}m' if seconds >= 3600 else f'{seconds // 60}m {seconds % 60:02d}s'

def bar(fraction, width=24):
    filled = int(round(fraction * width))
    return '[' + '#' * filled + '.' * (width - filled) + ']'

class Display:
    """One status line rewritten in place; finished chapters print a permanent line."""
    def __init__(self):
        self.width = 0
    def status(self, text):
        text = text[:shutil.get_terminal_size((120, 20)).columns - 1]
        sys.stdout.write('\r' + text.ljust(self.width))
        sys.stdout.flush()
        self.width = len(text)
    def line(self, text):
        sys.stdout.write('\r' + ' ' * self.width + '\r' + text + '\n')
        sys.stdout.flush()
        self.width = 0

def keep_awake(enabled):
    """Stop Windows sleeping or entering Modern Standby while the batch runs.

    On Modern Standby laptops, sleep set to Never does not prevent standby when the
    screen turns off, so the display is kept on too (it can be dimmed). The request
    ends automatically when this program exits."""
    if os.name != 'nt':
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if enabled else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--books', help='Comma-separated: john,matthew or 43,40 or Tamil names; nt / ot / all')
    parser.add_argument('--chapters', help='Only these chapters, e.g. 3, 1-5 or 1,4,7-9 (default: all)')
    parser.add_argument('--db', default=str(DEFAULT_DB), help='Path to tamil.db')
    parser.add_argument('--out', default=str(DEFAULT_OUT), help='Output folder (a sub-folder per book)')
    parser.add_argument('--quality', default=DEFAULT_QUALITY, choices=list(QUALITY_PRESETS))
    parser.add_argument('--voice', default='default', help='Voice for every book: female, male or an installed voice id')
    parser.add_argument('--voices', help='Alternate voices book by book, e.g. male,female (Matthew male, Mark female, …)')
    parser.add_argument('--voice-for', help='Fix the voice for particular books, e.g. psalms=male,proverbs=female')
    parser.add_argument('--force', action='store_true', help='Regenerate chapters that already exist')
    parser.add_argument('--retries', type=int, default=2, help='Extra immediate attempts for a failed chapter (default 2)')
    parser.add_argument('--allow-sleep', action='store_true', help='Let Windows sleep/turn off the screen during the run')
    parser.add_argument('--list-books', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')  # Tamil names on the Windows console
    db = open_db(args.db)
    if args.list_books:
        for i, name in enumerate(book_names(db), 1):
            count = db.execute('select count(distinct chNum) from words where bookNum=?', (i,)).fetchone()[0]
            print(f'{i:2d}  {book_id(name):16s} {name}  ({count} chapters)')
        return
    if not args.books:
        parser.error('--books is required, e.g. --books john,matthew')

    # Plan every chapter up front so progress and time left cover the whole run.
    out = Path(args.out)
    voices = [VOICE_ALIASES.get(v.strip(), v.strip()) for v in (args.voices or args.voice).split(',') if v.strip()]
    from services.default_voice import installed_voice_configs
    overrides = {}
    for item in (args.voice_for or '').split(','):
        if item.strip():
            book, _, chosen = item.partition('=')
            for _, _, identifier in resolve_books(db, book.strip()):
                overrides[identifier] = VOICE_ALIASES.get(chosen.strip(), chosen.strip())
    unknown = [v for v in voices + list(overrides.values()) if v not in installed_voice_configs()]
    if unknown:
        sys.exit(f'Unknown voice(s) {unknown}. Use female, male or one of: {", ".join(installed_voice_configs())}')
    jobs, skipped = [], 0
    # Voices rotate by the book's position in --books, so a resumed run keeps the same assignment.
    for position, (number, name, identifier) in enumerate(resolve_books(db, args.books)):
        voice = overrides.get(identifier, voices[position % len(voices)])
        if len(voices) > 1 or overrides:
            print(f'{identifier:16s} {"male" if voice == VOICE_ALIASES["male"] else "female" if voice == "default" else voice}')
        available = [c for (c,) in db.execute('select distinct chNum from words where bookNum=? order by chNum', (number,))]
        for chapter in parse_chapters(args.chapters, available):
            stem = f'{identifier}_{chapter:02d}'
            folder = out / identifier
            finished = (folder / f'{stem}.mp3').is_file() and (folder / f'{stem}.json').is_file()
            if finished and not args.force:
                skipped += 1
                continue
            verses = db.execute('select count(*) from words where bookNum=? and chNum=?', (number, chapter)).fetchone()[0]
            jobs.append(dict(number=number, name=name, identifier=identifier, chapter=chapter, stem=stem,
                             folder=folder, verses=verses, voice=voice))
    total = len(jobs) + skipped
    print(f'{total} chapter(s) selected: {skipped} already done, {len(jobs)} to generate  [{args.quality}]')
    print(f'Output: {out.resolve()}')
    if not jobs:
        print('Nothing to do.')
        return
    print('Ctrl+C once = stop after this chapter · twice = stop now · run again to resume')
    if not args.allow_sleep:
        keep_awake(True)
        print('Keeping Windows awake (screen stays on; you may dim it). Closing the lid can still sleep.')
    print()

    stop = {'requests': 0}
    def on_interrupt(signum, frame):
        stop['requests'] += 1
        if stop['requests'] == 1:
            display.line('>> Stop requested: finishing the current chapter, then stopping. '
                         'Press Ctrl+C again to stop immediately.')
        else:
            raise KeyboardInterrupt
    display = Display()
    signal.signal(signal.SIGINT, on_interrupt)

    all_verses = sum(job['verses'] for job in jobs)
    verses_done, seconds_generating, done, failed = 0, 0.0, 0, []
    failure_log = out / 'failed_chapters.log'
    def log_failure(job, attempt, error):
        out.mkdir(parents=True, exist_ok=True)
        with failure_log.open('a', encoding='utf-8') as stream:
            stream.write(f'{datetime.now().isoformat(timespec="seconds")}  {job["stem"]}  attempt {attempt}  {error}\n')
    # Each chapter gets 1 + --retries attempts in a row; chapters that still fail get
    # one final attempt after all other chapters. Saved pieces make retries cheap.
    queue = [(job, 1) for job in jobs]
    deferred, final_pass = [], False
    started = time.perf_counter()
    try:
        while queue or (deferred and not final_pass):
            if stop['requests']:
                break
            if not queue:
                final_pass = True
                queue = [(job, args.retries + 2) for job in deferred]
                display.line(f'>> Final retry for {len(deferred)} failed chapter(s): {", ".join(j["stem"] for j in deferred)}')
                deferred = []
            job, attempt = queue.pop(0)
            job['folder'].mkdir(parents=True, exist_ok=True)
            text, verse_count = chapter_text(db, job['number'], job['name'], job['chapter'])
            state = dict(fraction=0.0, result=None, error=None)
            def progress(fraction, desc=''):
                state['fraction'] = fraction
            def work():
                try:
                    state['result'] = generate(text, 'indicf5', voice=job['voice'], output_root=out / '.work',
                        quality=args.quality, input_format='Verse-numbered Bible text', progress=progress)
                except Exception as exc:
                    state['error'] = exc
            measured = time.perf_counter()
            thread = threading.Thread(target=work, daemon=True)
            thread.start()
            label = job['stem'] + (f' (try {attempt})' if attempt > 1 else '')
            while thread.is_alive():
                thread.join(0.5)  # short waits keep Ctrl+C responsive on Windows
                rate = seconds_generating / verses_done if verses_done else SECONDS_PER_VERSE_GUESS
                current = verses_done + state['fraction'] * job['verses']
                left = max(0.0, (all_verses - current) * rate)
                overall = (skipped + done + state['fraction']) / total
                display.status(f'{bar(overall)} {overall*100:5.1f}%  {skipped + done}/{total} chapters  '
                               f'| {label} {state["fraction"]*100:3.0f}%  | elapsed {clock(time.perf_counter()-started)}'
                               f'  left ~{clock(left)}')
            elapsed = time.perf_counter() - measured
            error = state['error']
            if error is None:
                _, produced, _, record = state['result']
                if (record['book_id'] != job['identifier'] or record['chapter'] != job['chapter']
                        or len(record['verses']) != verse_count):
                    error = 'heading or verse timing did not match the database'
            if error is not None:
                log_failure(job, attempt, error)
                if attempt <= args.retries:
                    display.line(f'! {job["stem"]}  attempt {attempt} failed: {error}  -> retrying now')
                    if registry.current is not None:
                        registry.current.unload()  # start the retry with a fresh GPU worker
                    queue.insert(0, (job, attempt + 1))
                elif not final_pass:
                    display.line(f'! {job["stem"]}  failed {attempt} times: {error}  -> will retry once more at the end')
                    deferred.append(job)
                else:
                    failed.append(job['stem'])
                    display.line(f'x {job["stem"]}  FAILED after all retries: {error}')
                continue
            mp3, manifest = job['folder'] / f'{job["stem"]}.mp3', job['folder'] / f'{job["stem"]}.json'
            record['output_directory'] = str(job['folder'].resolve())
            temporary = manifest.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            shutil.copyfile(produced, mp3)
            replace_with_retry(temporary, manifest)  # JSON last: a chapter counts as done only when both files exist
            shutil.rmtree(Path(produced).parent, ignore_errors=True)
            write_index(job['folder'], job['number'], job['name'], job['identifier'], args.quality)
            done += 1
            verses_done += job['verses']
            seconds_generating += elapsed
            overall = (skipped + done) / total
            display.line(f'ok {label}  {verse_count} verses, {record["duration_seconds"]/60:.1f} min audio, '
                         f'made in {clock(elapsed)}   [{skipped + done}/{total} chapters, {overall*100:.1f}%]')
    except KeyboardInterrupt:
        display.line('>> Stopped immediately. Pieces already generated are kept; run the same command to resume.')
        engine = registry.current
        if engine is not None and getattr(engine, 'process', None) is not None:
            engine.process.kill()
        os._exit(130)
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler)
    if registry.current is not None:
        registry.current.unload()
    remaining = total - skipped - done
    print(f'\nGenerated {done} chapter(s) in {clock(time.perf_counter() - started)}. '
          f'Done {skipped + done}/{total}; {remaining} to go.')
    if stop['requests'] and remaining:
        print('Stopped on request. Run the same command again to continue.')
    if failed or deferred:
        print(f'Failed: {", ".join(failed + [j["stem"] for j in deferred])} '
              f'(details in {failure_log}; run the same command again to retry)')
        sys.exit(1)

if __name__ == '__main__':
    main()
