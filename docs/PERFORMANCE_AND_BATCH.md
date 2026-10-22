# Speed improvements and batch Bible generation

This document records what was changed on the `perf-improvements` branch, why each change was made, how it was verified, and how to use the batch generator for more books or other languages.

## Results at a glance

| | Before | After |
|---|---|---|
| John 14 (31 verses, ~5.3 min audio) | 783 s | ~106 s (incl. ~13 s model load) |
| Time per verse | ~25 s | ~3 s |
| Model calls for John 14 | 96 (one per comma/full stop) | 53 (one per sentence, batched 8 at a time) |
| Real-time factor (generation time / audio length) | 2.0–2.5 | ~0.3 |
| Whole New Testament (260 chapters, 7,957 verses) | ~55 h (estimate) | ~7–7.5 h (estimate) |

Measured on an ASUS ProArt laptop, RTX 4060 Laptop GPU (8 GB), Fast preset.

## What was slow

The GPU was always used correctly, and the model was loaded only once. The cost came from how work was cut up and sent to the GPU:

1. **Every comma, semicolon and full stop became a separate model call.** Each IndicF5 (F5-TTS) call re-processes the ~5 s reference voice clip at every one of its sampling steps, so tiny chunks (average 2.6 s of speech) spent about half their GPU time on the reference. A single-word chunk took 3.3 s.
2. **Calls ran one at a time** (batch size 1), leaving the GPU under-used.
3. **Full fp32 maths**, with TF32 disabled.
4. **Classifier-free guidance ran two separate transformer passes per step.**
5. **32 sampling steps.**

## Changes

### 1. Worker: batched, faster sampling (`engines/indicf5_worker.py`)

- **Custom batched sampler.** This replaces `CFM.sample` with an equivalent Euler loop that samples up to `MAX_BATCH` (8) chunks together, padded and attention-masked.
- **One forward pass for guidance.** The conditional and unconditional passes are stacked into one batch. The "dropped" inputs are built so they are identical to upstream `drop_text` / `drop_audio_cond`: text set to `-1`, which becomes filler token `0`, and the audio condition set to zeros.
- **Per-row padding fix (important).** The text ConvNeXt and the convolutional position embedding in F5's DiT ignore the padding mask. In a batch, a short row's real audio was influenced by its padded tail, and short verses sounded different (spectral similarity 0.29). These two cheap layers now run per row at each row's true length. Batched output is identical to unbatched output (similarity 1.000).
- **TF32 enabled; bf16 autocast for the transformer.** The vocoder stays in fp32.
- **Configurable steps and precision** come from the request (see presets below).
- **Fixed seed (1234)**, so a re-run produces the same audio and the resume cache stays consistent.
- **Reference cache.** The reference clip is decoded, resampled and converted to a mel spectrogram once, not on every request.
- **Memory safety.** Sub-batches are limited by a frame budget (`TAMIL_TTS_FRAME_BUDGET`, default 12000 rows×frames). On a CUDA out-of-memory error, the sub-batch is halved and retried automatically.
- **New protocol.** The worker accepts `texts` and `outputs` lists and returns one `.npy` per chunk. The adapter in `engines/indicf5.py` exposes `synthesize_batch()`; `synthesize()` still works for single texts.

### 2. Text: one chunk per sentence, with real pauses (`services/speech_normalization.py`)

- **Every verse is split at sentence ends** (`.` `?` `!` `;` `…` `।`), and real silence is inserted: 450 ms after `.`, 350 ms after `;`, 500 ms after `?`, and 600 ms after `…`.
  - *Tweak history:* first we sent one whole verse per call with punctuation kept. Listening showed the model does **not** pause reliably at full stops inside one call, so sentence splitting was added.
- **Commas stay inside the sentence,** where the model phrases them naturally. The old behaviour (split at every comma too) is still available as the "Also split at commas" option in the app.
- **Chunk-final semicolons are removed** from the text sent to the model, because IndicF5 voiced them as an extra syllable ("ஆகன"). The pause after them is kept, and the original text and the JSON audit trail are unchanged.
- **Long sentences** (over `MAX_CHUNK_CHARS` = 220 characters) are split further, at clause punctuation and then at word boundaries. This keeps every call inside IndicF5's 30-second window, which includes the reference clip.

### 3. Verse numbers (`services/chapter_plan.py`)

Three or more lines numbered in increasing order, with no chapter heading, are now detected as verses automatically. The verse numbers are no longer read aloud, and a warning is recorded in the JSON.

### 4. Orchestration: batches, resume cache, retry (`services/chapter_generation.py`)

- **Batching.** Chunks are sorted by length, so padding is minimal, and sent 8 per worker request (`BATCH_CHUNKS`). Results are put back in verse order.
- **Resume cache.** Each finished chunk is saved to `<output>/.cache/chunks/<sha256>.npz`. The key covers the text, voice, reference audio hash, transcript, steps, precision, seed and guidance strength. A failed or stopped chapter continues from its saved chunks. The cache is deleted once the chapter's MP3 and JSON are written.
- **Retry.** A failed batch is retried once; a dead or timed-out worker restarts automatically.
- **Speed/quality presets** (`QUALITY_PRESETS`):

  | Preset | Steps | Precision | Notes |
  |---|---|---|---|
  | Fast — 16 steps, bf16 (default) | 16 | bf16 | Spectral similarity to Original: 0.994 |
  | Balanced — 24 steps, bf16 | 24 | bf16 | |
  | Original — 32 steps, full precision | 32 | fp32 | Same settings as before the change |

### 5. App (`app.py`)

- New **Speed / quality** dropdown in Advanced Settings.
- **"Also split at commas"** checkbox (off by default).
- **Model warm-up at launch.** IndicF5 loads in the background, so the first generation skips the ~15–30 s load.

### 6. Install safety (`requirements-indicf5-lock.txt`)

The CUDA package index line (`--extra-index-url https://download.pytorch.org/whl/cu126`) was added. Without it, reinstalling from the lock file silently installs CPU-only PyTorch.

### 7. Batch generator (`batch_generate.py`)

Generates whole books from the Tamil SQLite Bible database. See the next section.

### 8. Fixes from the first overnight New Testament run

| Problem seen | Cause | Fix |
|---|---|---|
| No progress from 22:36 to 07:59 | The laptop entered **Modern Standby** when the screen turned off. Setting sleep to "Never" does not prevent this on Modern Standby laptops. | `batch_generate.py` now asks Windows to stay awake and keeps the screen on while it runs (`SetThreadExecutionState`). Use `--allow-sleep` to turn this off. Closing the lid can still sleep the laptop. |
| `matthew_08`, `matthew_15`: "heading or verse timing did not match" | The MP3 decoded 15 samples (0.3 ms) longer than the PCM, from encoder end padding. The timing check required an exact match. | Up to one MPEG frame (1152 samples, 24 ms) of extra tail is accepted. Missing samples are still rejected. (`services/audio.py`) |
| `mark_09`: `[WinError 5] Access is denied` on a cache rename | Windows (antivirus/indexer) briefly locked a newly written file. | Renames retry for up to 5 s (`replace_with_retry`). |
| Some chapters took 5–6 min instead of ~2; VRAM at 7.9 of 8 GB | Near the limit, the Windows driver silently moves data into slow shared system memory instead of failing. | The worker caps PyTorch at 80% of VRAM (`TAMIL_TTS_GPU_MEMORY_FRACTION`), so it gets a normal out-of-memory error and halves the batch instead. It also releases cached memory after each request. |

Failed chapters are not saved, so re-running the same command regenerates them automatically.

## How it was verified

- **Equivalence with upstream F5-TTS** (fp32, 32 steps, same seed): waveform correlation 0.9994 for the longest item.
- **Batched vs single-verse output:** log-mel correlation 1.000 after the padding fix. A different random seed gives 0.76, which shows the natural take-to-take variation.
- **Fast preset vs Original:** 0.994.
- **Listening tests by the user:** John 14 in the female voice, with sentence pauses and the semicolon fix; Exodus 1 in the male voice.
- **Unit tests:** 30 pass. New tests cover sentence splitting, long-line splitting, verse auto-detection and the resume cache.
  - Three tests (`test_end_to_end`, `test_default_assets_validate_and_preprocessing_is_cached`, `test_reference_consent_before_model_loading`) **were already failing on `main` before these changes**. They concern WAV/caching assumptions and are unrelated to speed.

## Batch generation

### Database

The batch generator reads `.venv-indicf5/BibleDB/tamil.db` (read-only; it is never modified), in SQLite format:

- `words(wordId, word, bookNum, chNum, verseNum)` holds one row per verse. `word` is the verse text, and `bookNum` runs 1–66.
- `configuration.booknames` holds the 66 Tamil book names in canonical order. Each chapter's spoken heading is built from these (e.g. `யோவான் 1` is spoken as "யோவான், முதலாம் அதிகாரம்").

The database is excluded from git (`.venv*/` is ignored). It is copyrighted by the Bible Society of India, so do not commit it.

### Commands

Run from `C:\John\TextToVoice` on the `perf-improvements` branch (or `main` once it is merged):

```powershell
# List all books with numbers and ids
.\.venv\Scripts\python.exe batch_generate.py --list-books

# New Testament, alternating voices book by book (Matthew male, Mark female, ...)
.\.venv\Scripts\python.exe batch_generate.py --books nt --voices male,female

# Old Testament
.\.venv\Scripts\python.exe batch_generate.py --books ot --voices male,female

# Specific books or chapters
.\.venv\Scripts\python.exe batch_generate.py --books john,matthew
.\.venv\Scripts\python.exe batch_generate.py --books genesis --chapters 1-10 --voice female
```

| Option | Meaning |
|---|---|
| `--books` | Comma-separated book ids (`john`), numbers (`43`) or Tamil names. Groups: `nt`, `ot`, `all`. |
| `--chapters` | `3`, `1-5` or `1,4,7-9`. Default: all chapters. |
| `--voice` | One voice for every book: `female` (default), `male`, or an installed voice id. |
| `--voices` | Rotate voices by book position, e.g. `male,female`. The rotation is based on the book's position in `--books`, so resuming keeps the same assignment. Use the same `--books` value when resuming. |
| `--voice-for` | Fix the voice for particular books, overriding the rotation, e.g. `psalms=male,proverbs=female`. |
| `--quality` | One of the presets above. Default: Fast. |
| `--out` | Output folder. Default: `outputs\batch`. |
| `--force` | Regenerate chapters that already exist. **This overwrites them.** |

### Stopping and resuming

- **Ctrl+C once:** finishes the current chapter, then stops.
- **Ctrl+C twice:** stops immediately and kills the GPU worker. Chunks already generated are kept.
- **Run the same command again:** finished chapters are skipped, and a half-done chapter resumes from its cached chunks.
- **Automatic retries:** a failed chapter is retried straight away, up to `--retries` more times (default 2), each time with a fresh GPU worker. Saved pieces make retries fast. A chapter that still fails gets one final try after all the other chapters. Every failure is logged, with time, attempt and error, in `outputs\batch\failed_chapters.log`.
- **A chapter counts as finished only when both its MP3 and JSON exist.** The JSON is written last, through a temporary file.
- Existing chapters are never overwritten unless you pass `--force`.

### Output (for Flutter)

```
outputs\batch\
  matthew\
    matthew_01.mp3
    matthew_01.json      # verse timings + full provenance
    ...
    index.json           # every chapter: files, verse count, duration, voice
  mark\ ...
  .work\                 # temporary working files and resume cache; safe to delete when nothing is running
```

Key fields in each chapter JSON:

- `book_id`, `chapter`, `audio_filename`, `total_duration_ms`.
- `verses[]`: `verse_number`, `start_ms`, `end_ms`, `speech_end_ms`.
  - The end is exclusive, and the pause after a verse belongs to that verse.
  - `verse_timing.intro_end_ms` marks the end of the spoken chapter heading.
- `original_text`, `spoken_chunks`, `pauses_ms`, `settings` (voice, quality, steps, precision, seed).

MP3 players differ in how they handle encoder delay. Check that verse highlighting lines up in your Flutter player before relying on it (see `timing_note` in the JSON).

### Time estimates (Fast preset, RTX 4060 Laptop GPU)

About **3 seconds per verse**, plus about 30 s of model load per run.

| Scope | Chapters | Verses | Estimate |
|---|---|---|---|
| One average chapter | — | ~30 | ~1.5–2 min |
| John + Matthew | 49 | 1,950 | ~1 h 40 min |
| New Testament | 260 | 7,957 | ~7–7.5 h |
| Old Testament | 929 | 23,145 | ~20–22 h (run it over several nights; it resumes) |

Tips for long runs on a laptop:

- Keep it plugged in, and set sleep to "Never" while plugged in.
- Use ProArt Creator Hub / MyASUS fan mode Standard or Performance, not Whisper.
- Up to about 85 °C GPU temperature is normal. To monitor it:

  ```powershell
  nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used --format=csv -l 10
  ```

### Old Testament notes

Text fixes made after scanning the whole database before the OT run:

| Found in the database | Where | Handling |
|---|---|---|
| HTML entities `&quot;` and `&#39;` | ~20 verses (Leviticus 13:45, 1 Kings 22:15, Psalms 2, 10, 11, 14, 29, 2 Chronicles 30:15) | Decoded when read (`html.unescape`), so the JSON text is clean too |
| Merged verse numbers `(43)`, `(6)` | 1 Samuel 20:42, Psalm 127:5 | Removed from speech (not read aloud) |
| Brackets and quotation marks, e.g. `(சேலா)` | ~80 verses, mostly Psalms | Symbols removed from speech; the words are still read |
| Hyphenated names, e.g. `மகேர்-சாலால்-அஷ்-பாஸ்` | Isaiah 8 | Hyphen read as a short space |
| Psalm heading crash for 91, 92 and 95–99 (`num2words` returns irregular single words, and misspells 98) | `services/bible_heading.py` | Correct ordinals spelled out explicitly, plus a fallback so no number can crash |

**"சேலா" (Selah) is drawn out.** On its own after a full stop, it was spoken in 0.3 s. `SLOW_WORDS` in `services/speech_normalization.py` gives a standalone word extra time: `சேலா` gets 2.4×, about 0.7 s, chosen by listening to 1.8× and 2.4×. Add other words there if they need a slower, longer reading.

All 1,189 chapters were dry-run through text planning, with no errors and no leftover symbols in the speech text.

- Psalms headings are spoken as "முதலாம் சங்கீதம்" (with no "அதிகாரம்"). Psalm 119 (176 verses) is within the supported range.
- Very long verses (e.g. Esther 8:9) are split automatically at sentence and clause boundaries.
- Numbers inside verse text are read as Tamil number words.
- Listen to one chapter from a few different books before committing to a whole-OT run, e.g. `--books genesis,psalms,esther --chapters 1`.

## Voices

Installed voices (folder `assets/voices/`):

| Alias / id | Description | Speaking pace |
|---|---|---|
| `female` = `default` | Rasa Tamil female book narration | 14.4 chars/s (slowest) |
| `male` = `rasa_tam_m_book_00072` | Rasa Tamil male narration | 15.5 chars/s (~7% faster) |
| `rasa_tam_f_news_00621` | Female, news style | 15.3 chars/s |
| `rasa_tam_f_conv_02748` | Female, conversational | 16.3 chars/s |

IndicF5 copies the speaking pace of the voice's reference clip. Generation speed is the same for every voice.

**To add a voice:** create `assets/voices/<id>/` containing:

- `reference.wav`: 1–15 seconds of clean speech; 5–8 s works well.
- `transcript.txt`: the **exact** words spoken in the clip. A wrong transcript makes every verse sound wrong.
- `voice.json`: `id`, `display_name`, `audio`, `transcript_file`, `audio_sha256`, `transcript_sha256`, `license`, `license_url`, `source_url`, `attribution`, `permission_basis`.

Only use voices you have permission to use. `install_voice_options.py` shows how the existing voices were installed.

## English (Kokoro-82M, World English Bible)

| Part | Detail |
|---|---|
| Engine | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), Apache-2.0, run through `kokoro-onnx` on the CPU in its own environment, `.venv-english` (`engines/kokoro.py`, `engines/kokoro_worker.py`) |
| Model files | `model_cache/kokoro/kokoro-v1.0.onnx` (325 MB) and `voices-v1.0.bin` (28 MB), from the kokoro-onnx GitHub releases |
| Text | `.venv-indicf5/BibleDB/web.sqlite`: World English Bible, public domain. Table `verses(book, chapter, verse, text)`. |
| Voices (chosen by listening) | **male** = `am_michael`, each verse read as one passage (the model chooses its own pauses). **female** = `af_heart`, read sentence by sentence with a 450 ms pause at each full stop. Both at speed 0.9. |
| Output | `outputs\batch_en\<book>\<book>_<chapter>.mp3 / .json`, with the same file names and JSON layout as Tamil |
| Speed | **GPU:** about 8–13× real time with `onnxruntime-gpu` in `.venv-english-gpu`, which reuses the CUDA 12 / cuDNN 9 DLLs from the Tamil environment's PyTorch. It is used automatically when that environment exists. TF32 is off, so the output matches the CPU. **CPU:** about 3.4× real time at best; the worker opts out of Windows power throttling. |

```powershell
.\.venv\Scripts\python.exe batch_generate.py --language en --books matthew,john --voices male,female
.\.venv\Scripts\python.exe batch_generate.py --language en --books nt --voices male,female
```

How English differs from Tamil:

- **Headings** are spoken as "Matthew, chapter 1." (or "Psalm 23."), and numbered books as "First Corinthians".
- **Cleanup keeps** apostrophes ("God's", "didn't"), quotation marks and hyphens. Only merged verse numbers and brackets are removed.
- **Numbers** are left to Kokoro, which reads digits in English.
- **Closing quotation marks** stay with the sentence they end (`…?"'`). Pieces with no letters are merged into the previous piece. Without this, nested quotes in John 1 produced an empty piece.
- **Empty verses:** WEB leaves 5 verses empty (Luke 17:36, Acts 8:37, 15:34, 24:7, Romans 16:25). They have no audio, but the JSON still lists them as zero-length entries (`start_ms == end_ms`, `"omitted_in_source": true`), and `verse_timing.omitted_verses` names them, so every chapter covers all its verse numbers. Players should skip zero-length entries when highlighting.
- **Highlighting detail:** Heart's books have sentence-level pieces (`chunk_sample_boundaries`), like Tamil. Michael's books are verse-level only, by choice, because each verse is read as one passage.
- **Verse numbering** matches the Tamil Bible everywhere except Romans 14:24–26 and 16:25–27, where the closing doxology sits in a different place.

## Using other languages

IndicF5 (`ai4bharat/IndicF5`) supports 11 Indian languages: Assamese, Bengali, Gujarati, Hindi, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil and Telugu. The speed improvements (worker, batching, presets, cache) are language-independent. The **text preparation is Tamil-specific**, so another language needs the following:

1. **A Bible database in that language** with the same SQLite schema (`words` table, and `configuration.booknames` in canonical order). Pass it with `--db`.
2. **A reference voice in that language**, with its exact transcript (see "To add a voice").
3. **Book names and headings.** `services/bible_heading.py` (`BOOKS`, `PREFIXED`, Tamil ordinals such as "முதலாம்", and the words "அதிகாரம்" and "சங்கீதம்") and `services/chapter_plan.py` (`BOOK_IDS`, Tamil name → English id) must be extended for the new language. Without a recognised heading, chapters are not named `<book>_<chapter>` and verse timing is not verified.
4. **Number reading.** `tamil_number()` in `services/speech_normalization.py` calls `indic_numtowords.num2words(..., lang='ta')`, and the digit words are Tamil. Use that library's code for the new language, if it supports it, and translate the `DIGITS` words.
5. **Punctuation.** Sentence and clause splitting already includes `।` (Devanagari danda) and common punctuation. Listen for any mark the model voices aloud, as it did with `;`, and add it to `TRAILING_SEMICOLON` if needed.
6. **Listen to a test chapter first**, before running a whole book.

For a language IndicF5 does not support, a different TTS engine is needed. Engines are pluggable through `engines/registry.py`, and the batch path only needs `synthesize()` or `synthesize_batch()`.

## Tuning knobs

| Setting | Where | Default | Effect |
|---|---|---|---|
| Speed/quality preset | `--quality`, app dropdown | Fast | Steps and precision |
| `TAMIL_TTS_MAX_BATCH` | environment variable | 8 | Maximum chunks per GPU batch |
| `TAMIL_TTS_FRAME_BUDGET` | environment variable | 12000 | GPU memory budget per sub-batch. Lower it if other apps use the GPU. |
| `BATCH_CHUNKS` | `services/chapter_generation.py` | 8 | Chunks per worker request; also sets how often progress updates |
| `MAX_CHUNK_CHARS` | `services/speech_normalization.py` | 220 | Longest sentence sent in one call |
| `PAUSES` | `services/speech_normalization.py` | `.` 450 ms, `;` 350 ms, `?` 500 ms … | Silence after each sentence end |
| Verse gap | app "Pause between chunks" / `pause_ms` | 400 ms | Silence between verses |
| `SEED` | `services/chapter_generation.py` | 1234 | Change it for a different take. Changing it invalidates the resume cache. |

## Ideas not yet done

- **Longer pauses at commas in lists of names** (e.g. Exodus 1:2–4). This would add about 250 ms after commas only where a sentence lists several short items.
- **A speaking-pace option** (`--pace`) to slow down a voice by giving the model more time per sentence.
- **Shorter reference clips** (3–4 s). This would cut per-call cost further, but needs a new exact transcript for each trimmed clip.
- **`torch.compile`** is not used: it needs Triton, which is not available on Windows.
