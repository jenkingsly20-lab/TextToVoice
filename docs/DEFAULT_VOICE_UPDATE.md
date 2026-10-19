# Text-only generation update — 2026-10-17

The existing IndicF5 app now defaults to a configured Tamil narration voice. Normal workflow: open localhost:7860, enter Tamil text, Generate Speech, play audio or download MP3. Reference recording, transcript and consent controls are optional custom experiments inside a collapsed Advanced Settings panel. Old hidden custom recordings are ignored unless custom mode is explicitly enabled. Compare and diagnostics remain available.

## Reference provenance

User accepted access to AI4Bharat Rasa. One complete 486,380-byte WAV was retrieved from its Tamil test split (row 16), sample `TAM_F_BOOK_00014`, female book-narration style, 5.066 seconds. Exact paired transcript is in assets/voices/default_tamil/transcript.txt, unchanged. Dataset revision: `632f55c7ac590219d41cd7adffce5b440e4604f5`. Audio SHA-256: `8444fc8c0c3753bb73c2ff9bedaf33162115d81e7eeb53b516e515558b055224`. The full dataset and shards were not downloaded. Signed download links/tokens are not stored in attribution or generated metadata.

The [publisher](https://huggingface.co/datasets/ai4bharat/Rasa) labels Rasa CC BY 4.0 and provides it for expressive speech synthesis. [License terms](https://creativecommons.org/licenses/by/4.0/) permit redistribution/adaptation, including commercially, subject to attribution and other terms; privacy/personality rights and no-warranty caveats remain. Attribution, source and changes are included next to the assets. This does not certify the narrator's pronunciation or imply endorsement.

We did not substitute the publisher's unverified demo clip: the selected audio and transcript come from the same licensed dataset row after access approval. `install_default_voice.py` documents one-time restoration. No retraining, new TTS model, STT app or cloud inference was introduced.

## Implementation

`services/default_voice.py` checks source/transcript existence, provenance fields and hashes and caches FFmpeg PCM preprocessing in model_cache/reference_pcm. The app validates this setup at startup. `services/generation.py` automatically resolves defaults when no custom reference fields are supplied; generated metadata records the selected voice and provenance. The existing persistent GPU worker and WAV/MP3 pipeline are reused. The adapter reuses prepared custom/default audio across chunks rather than repeating conversion each time.

Main UI contains the Tamil text field, Generate, status, audio player and MP3 download. Status transitions include Ready, Generating, Completed and Error. Advanced Settings retains optional file input, engine and CPU settings, chunking, custom reference controls and detailed WAV/metadata downloads.

## Validation

22 dependency-light tests passed, with 21 existing Gradio migration warnings. Tests cover default lookup/integrity failures, preprocessing reuse, explicit custom-mode validation and ignoring stale hidden recording fields, in addition to existing audio/text checks.

All three supplied Bible samples were submitted through the running Gradio queue with `custom=False`, `reference=None`, empty transcript and `consent=False`. Each produced actual local GPU audio. WAV playback-file delivery and MP3 download endpoints returned HTTP 200; original input text was preserved exactly in metadata.

| Sample | Output audio | Generation elapsed* | MP3 bytes | Local output folder |
|---|---:|---:|---:|---|
| 1 — கர்த்தர் என் மேய்ப்பராயிருக்கிறார்… | 3.904 s | 6.087 s | 32,685 | outputs/20261018T024726_ef1519ac5fca43d0b8aff57793472f2e |
| 2 — ஆதியிலே வார்த்தை இருந்தது… | 6.176 s | 7.040 s | 52,605 | outputs/20261018T024742_542bab6f016e49d18969592e6a4481a6 |
| 3 — தேவன் தம்முடைய ஒரேபேறான… | 10.763 s | 10.484 s | 95,421 | outputs/20261018T024804_e77b350474a84ddf8f81628c7b2789d4 |

*Metadata elapsed includes synthesis and file encoding, excludes initial model load. First-request wall time can be longer. Folder timestamps are UTC; this report uses the user's local date. These short clips do not benchmark full chapters.

Live UI configuration confirms Advanced Settings is collapsed and the default status is Ready. Browser automation was unavailable; end-to-end checks used localhost upload/queue/output HTTP transport rather than a simulated click in a browser. WAV/MP3 validity and routing were verified. **Human listening is still required to judge intelligibility, omissions, biblical names and pronunciation**; no claim of perfect narration or complete audible wording is made.

Reproduce: `.\.venv\Scripts\python.exe -m pytest -q --disable-warnings` and, with the app running, `.\.venv\Scripts\python.exe check_ui_transport.py --default --sample 1` (repeat with 2 and 3). Ordinary launch remains `.\.venv\Scripts\python.exe app.py`.
