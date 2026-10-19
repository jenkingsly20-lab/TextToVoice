# Completion report — 2026-10-17

**Latest enhancement:** normal generation now needs only Tamil text. A licensed Tamil narration reference/transcript is automatically loaded; manual recording controls are in collapsed Advanced Settings. Three requested Bible samples passed local GPU generation and WAV/MP3 HTTP delivery. See [DEFAULT_VOICE_UPDATE.md](DEFAULT_VOICE_UPDATE.md) for provenance, measured results and listening-review limitations. Earlier reference-recording instructions below are historical.

## Current result — Phase 2 completed for one engine

Final checks: **12 tests passed** (17 Gradio 6 migration warnings), real MP3 decoded successfully with FFmpeg, live diagnostics reported CUDA available from the isolated environment. Updated app restarted at `127.0.0.1:7860` with IndicF5 as its default installed engine. Human browser click-through/visual inspection remains unperformed because browser-control tooling was unavailable; backend UI callback and HTTP/configuration checks cover functional integration. The speech sample is available for the user's listening review.

After explicit download authorization and local Hugging Face authentication, IndicF5 has been installed in `.venv-indicf5` and integrated into the app through a persistent offline subprocess. Browser-only login initially returned 401 to downloads; local authorization resolved it. CUDA Torch 2.6.0+cu126 / Torchaudio 2.6.0+cu126 passed actual GPU execution. NVIDIA driver was not changed. Dependencies are pinned in requirements-indicf5-lock.txt and `pip check` passed. A premature unconstrained dependency install was interrupted before installation; the final install used explicit Torch/NumPy/Transformers constraints.

Model revision: fb652a96e508091045890dae5bb99fe511facbcf. Source: 13f7c4d627cc10111aea8fe9c0039462cacacdc7. Vocos config: 0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21. Weights: 1,402,789,408 bytes; Vocos artifact 54,365,991 bytes; CUDA Torch wheel roughly 2.5 GB plus dependencies. Downloaded artifacts are local and Git-ignored. No credentials were printed or committed.

Offline smoke test created a 3.05-second Tamil clip on CUDA, approximately 22 seconds including startup; peak PyTorch allocated VRAM was 1,475,271,680 bytes. The actual Gradio generation callback also produced WAV/MP3/metadata at `outputs/20261017T223025_ec84b5ab1dcc4243a9028cd91dfa47a8/`. Input: `தமிழ் வாழ்வு அறிவு அருள் பள்ளி நன்றி.` The official README's supplied demo reference was used internally. Human pronunciation review remains pending; synthesized speech is not certified accurate. No ASR or cloud inference was used.

New files: engines/indicf5.py, engines/indicf5_worker.py, download_indicf5.py, verify_indicf5.py, requirements-indicf5-constraints.txt, requirements-indicf5-lock.txt and tests/test_indicf5.py. Updated UI exposes authorized reference upload/microphone, exact transcript, explicit consent and Auto/CPU device selection. Eager strict-checkpoint inference avoids torch.compile Windows constraints and upstream punctuation substitutions. The UI now lists IndicF5 as usable; mock remains marked test-only. Single-model A/B takes and assessment export are supported. A second real engine, CPU benchmarking and long-chapter VRAM profiling remain outside the completed verification.

The following is the historical Phase 1 report; its IndicF5 access blocker is resolved above.

## Delivered

Functional Phase 1 in `C:\John\TextToVoice`: local Gradio UI, UTF-8 Tamil input/upload, lossless line/sentence chunking, test-only engine registry, WAV/MP3 creation, UUID output folders, metadata, diagnostics, retained B output and guarded assessment CSV/JSON export. No actual TTS engine is installed; no speech or pronunciation claim is made. Real voice/reference selectors and two-engine comparison remain pending verified adapters.

Created `app.py`, `config.py`, `start.ps1`, `requirements.txt`, `requirements-lock.txt`, `.gitignore`, `.env.example`; packages `engines/` and `services/`; `tests/test_core.py`; README and MODEL_RESEARCH, WINDOWS_SETUP, TROUBLESHOOTING and this report under docs. Original implementation brief was preserved.

## Commands executed

* `py -0p`, `python --version`, `nvidia-smi`, `ffmpeg -version`.
* `py -3.10 -m venv .venv`.
* `.\.venv\Scripts\python.exe -m pip install 'gradio>=5.49,<6' 'numpy>=1.26,<3' 'pytest>=8,<9'`.
* `.\.venv\Scripts\python.exe -m pip freeze` saved as requirements-lock.txt.
* `.\.venv\Scripts\python.exe -m pytest -q`: **8 passed**, 15 future Gradio 6 migration warnings.
* `.\.venv\Scripts\python.exe -m pip check`: **No broken requirements found**.
* `.\.venv\Scripts\python.exe -u app.py`: serves loopback port 7860, opens browser.
* `Invoke-WebRequest http://127.0.0.1:7860`: **HTTP 200**.
* `services.generation.generate` produced persistent WAV/MP3/metadata in `outputs/20261017T220423_1bdc77cd315d428f87d202047e9f1ae7/` (test tone, not speech).

Tests cover exact Tamil/line-break preservation, missing engines, PCM pauses and sample boundaries, valid WAV and FFmpeg MP3 decoding, unique output paths, metadata, assessment guards and UTF-8 export, Gradio construction. Browser visual inspection and interactive browser click-through were not performed.

## Remaining blocker and smallest action

Both intended model repositories are gated. IndicF5 primary weights are listed as 1.4 GB and Indic-Speak as 6.6 GB, excluding secondary artifacts/packages. No large model/CUDA download or license acceptance was performed. The brief explicitly says to ask before large downloads and gated license acceptance.

User must review and accept access conditions at https://huggingface.co/ai4bharat/IndicF5 and authorize the multi-GB installation. Do not paste tokens into chat. Then verify exact accessible revisions, code license and secondary artifacts, install a separate engine environment, test native Windows and a consented reference recording, measure VRAM and produce real Tamil WAV/MP3. CUDA-enabled Torch is not installed; NVIDIA driver detection succeeded but Torch CUDA operation remains untested. Do not mark Phase 2 complete until audible speech is produced and checked.
