# English audio update: instructions for the Flutter/backend agent

**From:** the TextToVoice generation project (`C:\John\TextToVoice`, branch `perf-improvements`, commit `5f8bb08`)
**Date:** 2026-10-22
**Scope:** English (WEB) New Testament audio. **Only JSON metadata changed in 8 files; no MP3 changed.**

## 1. What changed and why

Your report found that **Romans 16 and Acts 8 are "not full"**, because of verse gaps in the English WEB database. The World English Bible leaves 5 verses empty; modern texts move them to footnotes:

| Chapter | Empty verse |
|---|---|
| Luke 17 | 36 |
| Acts 8 | 37 |
| Acts 15 | 34 |
| Acts 24 | 7 |
| Romans 16 | 25 |

These verses have **no audio** (there is nothing to read). Previously their verse numbers were missing from the chapter JSON. **Now every chapter lists every verse number:**

- Each empty verse appears in `verses` as a **zero-length entry**, placed where the next verse starts (or at the end of the chapter for Romans 16:25):

  ```json
  {"verse_number": 37, "start_ms": 290157, "end_ms": 290157, "speech_end_ms": 290157, "omitted_in_source": true}
  ```

- `verse_timing.omitted_verses` lists them, e.g. `[37]`, with an explanatory `verse_timing.omitted_note`.
- The timeline stays contiguous: the previous verse's `end_ms` equals the placeholder's `start_ms`, which equals the next verse's `start_ms`.
- Those 5 chapters should now report as **full chapters** against the WEB verse counts.

## 2. Changed files

Paths are relative to the English audio root (the folder you deploy as `english/`, i.e. the generator's `outputs/batch_en/`). The checksums are in `changed_files_english_nt.sha256`, next to this file.

| File | Change |
|---|---|
| `luke/luke_17.json` | + verse 36 placeholder (36 → 37 entries) |
| `acts/acts_08.json` | + verse 37 placeholder (39 → 40) |
| `acts/acts_15.json` | + verse 34 placeholder (40 → 41) |
| `acts/acts_24.json` | + verse 7 placeholder (26 → 27) |
| `romans/romans_16.json` | + verse 25 placeholder (24 → 25) |
| `luke/index.json`, `acts/index.json`, `romans/index.json` | `verse_count` for those chapters increased by 1 |

**All 260 MP3 files and the other 252 chapter JSON files are unchanged.**

## 3. What you need to do

1. **Copy the 8 changed JSON files** from the generator's `outputs/batch_en/` into your `english/` audio folder, then check them against `changed_files_english_nt.sha256`.
2. **Regenerate `audio-expected-english-nt.csv` and `audio-manifest-english-nt-json.sha256`**, because these 8 JSON files changed. Expected verse counts for the 5 chapters are now: Luke 17 = 37, Acts 8 = 40, Acts 15 = 41, Acts 24 = 27, Romans 16 = 25.
3. **App/player:** when highlighting, **skip verse entries that have `omitted_in_source: true`** (or `start_ms == end_ms`). If the reader shows those verse numbers at all, show them without audio highlighting.
4. **The 48 kbps conversion** in your deployment prompt is unaffected (the MP3s didn't change). Copy the JSON from the generator, not from an older copy.
5. **Re-run your API check of all 260 chapters.** Expect 260 full chapters.

## 4. Things that stay as they are (by decision)

- **Highlighting detail in English:**
  - **Michael (male) books are verse-level only.** Each verse is read as one passage, so there are no clause or sentence timings. This was chosen deliberately to keep Michael's natural reading style.
  - **Heart (female) books** also have sentence-level timings in `chunk_sample_boundaries` and `chunk_verse_numbers`, like the Tamil audio.

  | Voice | Books (NT) |
  |---|---|
  | Michael (`am_michael`), verse-level | Matthew, Luke, Acts, 1 Corinthians, Galatians, Philippians, 1 Thessalonians, 1 Timothy, Titus, Hebrews, 1 Peter, 1 John, 3 John, Revelation |
  | Heart (`af_heart`), verse + sentence | Mark, John, Romans, 2 Corinthians, Ephesians, Colossians, 2 Thessalonians, 2 Timothy, Philemon, James, 2 Peter, 2 John, Jude |

- **Romans 14 and 16 numbering:** the WEB places the closing doxology at Romans 14:24–26, while the Tamil Bible has it at 16:25–27. Each language follows its own text, so verse numbers in those two chapters differ between Tamil and English.
- **MP3 timing:** verse times are on the gapless MP3 playback timeline, compensated for encoder delay and padding. Players must honour the LAME/Xing gapless metadata, so check highlighting alignment on a real device (see `timing_note` in each JSON). Also re-check alignment after your 48 kbps conversion, since re-encoding changes encoder delay.

## 5. Coming next: English Old Testament

- **Status:** being generated now: 929 chapters, ~59 h of audio, output in `outputs/batch_en/<book>/`.
- **Voices:** Genesis Michael, Psalms Michael, then alternating in Bible order starting with Exodus Michael, Leviticus Heart, Numbers Michael, …
- **Format:** same as the NT. The English OT has no empty verses, so it has no `omitted_in_source` entries.
- A separate note will follow once it has been verified.

## 6. JSON fields the app uses (reference)

| Field | Meaning |
|---|---|
| `book_id`, `chapter`, `audio_filename` | e.g. `john`, `3`, `john_03.mp3` |
| `total_duration_ms` | decoded playback length |
| `verses[]` | `verse_number`, `start_ms`, `end_ms` (exclusive; the following pause belongs to the verse), `speech_end_ms`, and optionally `omitted_in_source` |
| `verse_timing.intro_end_ms` | end of the spoken heading ("John, chapter 3.") |
| `verse_timing.playback.verified` | always `true` for delivered files (MP3 timeline verified) |
| `chunk_sample_boundaries`, `chunk_verse_numbers` | sub-verse pieces in 24 kHz PCM samples (sentence-level in Heart and Tamil files) |
| `settings.voice` | `am_michael` / `af_heart` (English) |
