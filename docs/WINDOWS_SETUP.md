# Windows setup

**Installed status:** this workspace includes verified IndicF5 in `.venv-indicf5` and a configured default Tamil narration reference under `assets/voices/default_tamil`. Start the app using the existing `.venv` commands below, paste Tamil text and select Generate Speech. No recording/transcript entry is needed. Advanced Settings optionally permits custom voice experiments. No model or voice download occurs at launch/inference. CUDA was verified on the RTX 4060 with Torch 2.6.0+cu126 and driver 566.36.

Reproduction after access approval: clone `https://github.com/AI4Bharat/IndicF5.git` into `engine_sources/IndicF5` and check out `13f7c4d627cc10111aea8fe9c0039462cacacdc7`; install CUDA Torch/Torchaudio as below; install the cloned package with `-c requirements-indicf5-constraints.txt`. The exact resolved versions are in requirements-indicf5-lock.txt (its f5-tts entry refers to the local source checkout). Authenticate locally with `.\.venv\Scripts\hf.exe auth login`, then run `.\.venv\Scripts\python.exe download_indicf5.py`. Vocos config/cache revision is recorded in MODEL_RESEARCH.md. `verify_indicf5.py` explicitly runs the real-model offline smoke test; it is not part of the ordinary test suite. Initial gated-access instructions later in this document are historical context.

Run PowerShell in `C:\John\TextToVoice`:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe app.py
```

Optional activation: `.\.venv\Scripts\Activate.ps1`. Activation is unnecessary with the explicit interpreter paths above; no execution-policy change is required. `start.ps1` is a convenience launcher. UI binds only to http://127.0.0.1:7860. Close its terminal or press Ctrl+C to stop. No share link or deployment is used.

Already installed: Python 3.10, FFmpeg 8.1.1 GPL build with libmp3lame, NVIDIA driver 566.36. FFmpeg is invoked as an existing executable and is not bundled. See [FFmpeg license](https://ffmpeg.org/legal.html) before redistributing binaries. On a machine missing it, inspect `winget show --id Gyan.FFmpeg --exact`, then explicitly install with `winget install --id Gyan.FFmpeg --exact`; review its installation prompts. No installer is run automatically.

Outputs are unique folders containing audio.wav, audio.mp3 (when FFmpeg succeeds) and metadata.json. Set a custom location before launch:

```powershell
$env:TAMIL_TTS_OUTPUTS = 'C:\John\TextToVoice\outputs'
.\.venv\Scripts\python.exe app.py
```

The `.env.example` is documentation; the app does not load `.env` automatically. `model_cache/` is the project Hugging Face cache, ignored by Git. Reference recordings should remain in ignored `reference_audio/`.

## IndicF5 environment commands (installation now completed)

Keep this environment separate from the UI. The following official Torch build has now passed actual CUDA inference on this computer:

```powershell
py -3.10 -m venv .venv-indicf5
.\.venv-indicf5\Scripts\python.exe -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu126
.\.venv-indicf5\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
nvidia-smi
```

The large runtime installation was authorized and completed. Upstream dependencies require NumPy <=1.26.4 and Transformers <4.50; our constraints use NumPy 1.26.4 and Transformers 4.49.0. The adapter uses strict local checkpoint loading rather than executing remote model.py. Run `download_indicf5.py` only for explicit model installation/recovery; it downloads the pinned weights, source for review and Vocos configuration/artifact into the local cache.

Firewall: loopback-only app does not require public-network access. Do not disable Defender or open inbound public ports. If Defender reports a problem, inspect the executable/source path rather than adding blanket exclusions.
