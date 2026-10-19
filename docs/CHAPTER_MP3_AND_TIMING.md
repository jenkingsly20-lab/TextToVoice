# Chapter MP3, verse timestamps and performance logs

This update keeps IndicF5, the default Tamil voice and the existing local generation workflow. No model or speculative performance optimization was added. Only Python syntax checks were run; no automated suites, GPU inference or audio generation were executed for this update.

## Input and files

Paste a recognized reference heading on the first nonempty line, then **one complete numbered verse per line**:

```text
1 யோவான் 2:1-4
1 [paste your exact verse 1 text here]
2 [paste your exact verse 2 text here]
3 [paste your exact verse 3 text here]
4 [paste your exact verse 4 text here]
```

Replace the bracketed placeholders with your scripture. Positive, strictly increasing labels are required. A known chapter heading plus consistently numbered lines automatically identifies Bible verse metadata; without a heading, choose the existing Verse-numbered Bible text format explicitly. Ordinary prose counts are never stripped automatically. Wrapped/mixed numbered layouts are rejected instead of guessing verse boundaries. A prose chapter without verse labels can still generate audio, but its JSON has no invented verse timestamps. No heading means null book/chapter and generic `narration` filenames.

Each request automatically saves **MP3, chapter JSON and performance JSONL** under `outputs/<book_chapter>/<unique-generation-id>/`, e.g. `outputs/1john_02/<id>/1john_02.mp3`, `1john_02.json` and `1john_02.jsonl`. No UI download is required to preserve files. Separate generation subfolders prevent overwriting earlier takes. The completion status shows the absolute saved folder. IDs use stable lowercase English book slugs, with numeric prefixes: john, 1john, 2corinthians, romans, psalms, etc. The mapping is in services/chapter_plan.py. Chapter formatting uses at least two digits. Only the provided text is narrated; the app does not infer that a partial passage is a complete canonical chapter.

Both downloads are visible in the main UI. The player and comparison player use MP3. New generation does not retain a chapter WAV; encoding uses a scoped temporary WAV removed on success/failure. Temporary worker chunk WAV files are removed after reading. Cached reference WAV/PCM remains intentionally reusable; existing older user output files are not deleted.

Default bitrate is **192 kbps CBR**, configurable before launch:

```powershell
$env:TAMIL_TTS_MP3_BITRATE_KBPS = '192'
.\.venv\Scripts\python.exe app.py
```

`.env.example` documents this variable but is not loaded automatically. IndicF5 remains at native 24 kHz. MP3 encoding resamples to 48 kHz because 192 kbps requires MPEG-1 rather than the native 24 kHz MPEG-2 bitrate range. This is output-format handling, not a model change.

## Timestamp contract

JSON schema version 2.0 includes `book_id`, `chapter`, `audio_filename`, `metadata_filename`, `total_duration_ms` and `verses`. Each public verse entry contains `verse_number`, `start_ms`, `end_ms` and `speech_end_ms`. End is exclusive. Flutter should highlight when `start_ms <= position_ms < end_ms`. The initial heading and the following pause occur before the first verse start. Pauses inside a verse remain within that verse; a pause between verses belongs to the preceding verse. Last verse ends at the final PCM content end.

Each original numbered line is explicitly associated with its generated chunks. Boundaries are derived from their actual returned PCM lengths after silence insertion and concatenation. Multiple chunks within a verse remain one verse entry. No text-length estimates, inference-duration estimates or chunk-as-verse assumptions are used. `verse_pcm_segments`, `chunk_verse_numbers` and sample boundaries provide an audit trail. Original scripture and heading remain in `original_text`; only the separate model-bound text is normalized.

FFmpeg writes encoder delay/padding metadata. After encoding, the app decodes the final MP3 in memory, checks decoded sample count against the resampled chapter PCM and checks for encoder skip metadata. The public timestamps use this **gapless decoded MP3 playback timeline**, not the raw compressed/container duration. JSON `verse_timing.playback` records the decoder, sample counts, sample rate, encoder skip and container start time. `total_duration_ms` uses actual decoded samples when available. `requires_gapless_player` and `flutter_player_verification_required` make the playback dependency explicit.

**If MP3 validation fails or explicit verse identity is unavailable, `verse_timing.available` is false and `verses` is empty.** Actual PCM segment data may still be included for debugging but must not be treated as approved MP3 highlighting timestamps. Warnings explain the limitation. Model-generated leading/trailing silence remains part of each segment: these are accurate segment boundaries, not forced word/phoneme alignments. A player ignoring MP3 delay/padding can display an offset; verify the chosen Flutter player before production use. No alignment model was introduced.

## Performance

The chapter JSON includes `performance.stages_ms`, per-chunk wall times and generated durations, chunk count, total generation time, final duration and real-time factor. Stages include reference parsing, text preprocessing, chunking, default reference preparation/cache status, model-lock wait, engine load/switch, synthesis, PCM assembly/silence, temporary WAV/JSON writing, MP3 encoding and MP3 timeline verification.

Workers report audio preparation, synthesis wall time, actual CUDA-event elapsed time (null on CPU), temporary chunk writing and peak allocated VRAM. Adapter metrics include reference-cache reuse, model load and worker round-trip time. These measurements are nested, not additive. `planning_wall_ms` includes its parsing/preprocessing/chunking breakdown. Encoding includes writing the MP3 to disk; Python `file_writing_ms` separately covers temporary WAV and manifest writes. Instrumentation does not claim to separate disk time inside FFmpeg.

Default logging is compact: started, text-prepared, completed or failed events only. These are saved in the chapter's JSONL and the shared `outputs/.performance/generation.jsonl` index. Repeated per-chunk disk logging and duplicate detailed worker metrics in exported reports are disabled. Stage totals, chunk count, duration and real-time factor remain; verse timing and original-text audit data remain unchanged. Set `TAMIL_TTS_DETAILED_LOGGING=1` before starting the app to restore detailed chunk events and exported metrics for diagnostics. Logging previously took only milliseconds; this change does not promise a large synthesis speedup. The completed log event includes time through final manifest writing. The manifest's own total excludes its last accounting rewrite and final log flush; Gradio frontend queue waiting is not included.

## Manual verification

1. Refresh localhost:7860, paste one chapter heading and 2–4 complete numbered verses, then Generate Speech once.
2. Download the MP3 and JSON. Confirm matching chapter filenames, 192 kbps, correct heading once, no spoken verse labels, and unchanged in-verse numbers/wording.
3. Check `verse_timing.available` and `verse_timing.playback.verified`. If false, read warnings before using highlighting.
4. Play/seek the MP3 in the intended player. Compare transitions with JSON starts/ends, including introduction and pauses. Check first, middle and final verses; ignore highlighting during the introduction. Repeat this check in the intended Flutter audio player.
5. Review `performance.stages_ms` and `performance.chunks` to find the dominant stage. Read the matching `generation_id` events in `.performance/generation.jsonl`. Do not add overlapping wall/GPU submetrics together.
6. Confirm the chapter's generation folder contains MP3, JSON and JSONL, with no retained chapter WAV. Generate the same chapter again to confirm the previous take is preserved in a separate subfolder.
