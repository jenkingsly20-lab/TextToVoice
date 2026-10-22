"""Verify batch output against the Bible database (read-only): every chapter, verse, timing and voice.

Use the same --language, --books, --voices and --voice-for as the batch run, so the voice
assignment can be checked too.

Examples:
    .\\.venv\\Scripts\\python.exe tools\\verify_batch.py --books nt --voices male,female
    .\\.venv\\Scripts\\python.exe tools\\verify_batch.py --books genesis,psalms,ot --voices male,female --voice-for psalms=male
    .\\.venv\\Scripts\\python.exe tools\\verify_batch.py --language en --books nt --voices male,female
    .\\.venv\\Scripts\\python.exe tools\\verify_batch.py --language en --books all --mp3   (also re-decodes every MP3)
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch_generate as b
from services.audio import inspect_mp3_timeline

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--language', choices=['ta', 'en'], default='ta')
    parser.add_argument('--books', default='all', help='Same value as the batch run (order matters for --voices)')
    parser.add_argument('--voices', help='Expected rotation, e.g. male,female (omit to only check one voice per book)')
    parser.add_argument('--voice-for', help='Expected per-book overrides, e.g. psalms=male')
    parser.add_argument('--db')
    parser.add_argument('--out')
    parser.add_argument('--mp3', action='store_true', help='Also decode every MP3 and re-check its timeline (slow)')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    english = args.language == 'en'
    db = b.open_db(args.db or (b.ENGLISH_DB if english else b.DEFAULT_DB))
    out = Path(args.out or (b.ENGLISH_OUT if english else b.DEFAULT_OUT))

    # Expected voice per book, mirroring batch_generate's rotation and overrides.
    if english:
        names = {key: value['voice'] for key, value in b.ENGLISH_VOICES.items()}
    else:
        from services.default_voice import selected_reference
        names = {alias: selected_reference(voice_id)['voice'] for alias, voice_id in b.VOICE_ALIASES.items()}
    rotation = [v.strip() for v in args.voices.split(',')] if args.voices else []
    overrides = {}
    for item in (args.voice_for or '').split(','):
        if item.strip():
            book, _, voice = item.partition('=')
            for _, _, identifier in b.resolve_books(db, book.strip()):
                overrides[identifier] = voice.strip()

    problems, chapters, verses_total, audio_ms = [], 0, 0, 0
    devices, voices_used = collections.Counter(), {}
    for position, (number, name, identifier) in enumerate(b.resolve_books(db, args.books)):
        folder = out / identifier
        db_chapters = b.chapters_of(db, number)
        index_path = folder / 'index.json'
        if not index_path.is_file():
            problems.append(f'{identifier}: index.json missing')
        elif [c['chapter'] for c in json.loads(index_path.read_text(encoding='utf-8'))['chapters']] != db_chapters:
            problems.append(f'{identifier}: index.json chapters do not match the database (missing or out of order)')
        voices = set()
        for chapter in db_chapters:
            stem = f'{identifier}_{chapter:02d}'
            mp3, manifest = folder / f'{stem}.mp3', folder / f'{stem}.json'
            if not mp3.is_file() or not manifest.is_file():
                problems.append(f'{stem}: missing ' + ' and '.join(x for x, ok in (('MP3', mp3.is_file()), ('JSON', manifest.is_file())) if not ok))
                continue
            record = json.loads(manifest.read_text(encoding='utf-8'))
            # Every verse number in the database, including source-empty ones (listed as omitted_in_source).
            expected = [verse for verse, _ in b.verses_of(db, number, chapter)]
            got = [v['verse_number'] for v in record['verses']]
            if got != expected:
                problems.append(f'{stem}: verse numbers differ from the database ({len(got)} vs {len(expected)})')
            spoken = [v for v in record['verses'] if not v.get('omitted_in_source')]
            times = [(v['start_ms'], v['end_ms']) for v in record['verses']]
            if (any(v['start_ms'] >= v['end_ms'] for v in spoken)
                    or any(times[i][1] != times[i + 1][0] for i in range(len(times) - 1))
                    or (times and times[-1][1] != record['total_duration_ms'])):
                problems.append(f'{stem}: verse timings are not contiguous')
            short = [v['verse_number'] for v in spoken if v['speech_end_ms'] - v['start_ms'] < 600]
            if short:
                problems.append(f'{stem}: suspiciously short verse audio {short}')
            if not record['verse_timing']['playback']['verified']:
                problems.append(f'{stem}: MP3 timeline not verified')
            if args.mp3:
                playback = record['verse_timing']['playback']
                check = inspect_mp3_timeline(mp3, round(playback['expected_decoded_samples'] * record['sample_rate']
                                                        / playback['playback_sample_rate']), record['sample_rate'])
                if not check['verified']:
                    problems.append(f'{stem}: MP3 re-check failed ({check.get("limitation")})')
            if record['book_id'] != identifier or record['chapter'] != chapter or not record['is_speech']:
                problems.append(f'{stem}: wrong book/chapter metadata')
            if mp3.stat().st_size < 50_000:
                problems.append(f'{stem}: MP3 only {mp3.stat().st_size} bytes')
            voices.add(record['settings']['voice'])
            devices[record.get('device')] += 1
            chapters += 1
            verses_total += len(spoken)
            audio_ms += record['total_duration_ms']
        voices_used[identifier] = voices
        if len(voices) > 1:
            problems.append(f'{identifier}: mixed voices {sorted(voices)}')
        if rotation and voices:
            alias = overrides.get(identifier, rotation[position % len(rotation)])
            if voices != {names.get(alias, alias)}:
                problems.append(f'{identifier}: voice {sorted(voices)}, expected {names.get(alias, alias)}')

    total_chapters = sum(len(b.chapters_of(db, n)) for n, _, _ in b.resolve_books(db, args.books))
    print(f'Output: {out.resolve()}')
    print(f'Chapters: {chapters} of {total_chapters}   spoken verses: {verses_total}   audio: {audio_ms / 3600000:.1f} h')
    print(f'Made on: {dict(devices)}')
    print('Voices: ' + ', '.join(f'{k}={"/".join(sorted(v))}' for k, v in voices_used.items()))
    print(f'Problems: {len(problems)}')
    for problem in problems:
        print('  -', problem)
    sys.exit(1 if problems else 0)

if __name__ == '__main__':
    main()
