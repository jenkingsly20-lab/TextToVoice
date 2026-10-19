# Troubleshooting

* **Normal use now needs only Tamil text:** the default voice is configured automatically. You can leave Advanced Settings closed. Old reference-recording error instructions below apply only when custom voice mode is explicitly enabled.
* **Default voice setup error:** restore `assets/voices/default_tamil/reference.wav`, `transcript.txt` and `voice.json`. Hash mismatches are rejected rather than silently using a changed recording/transcript. Attribution and source are in the same folder. The one-time installer requires accepted Rasa access; routine inference stays offline.

* **M4A / phone recording format:** references are now decoded by local FFmpeg to 24 kHz mono PCM WAV before SoundFile/model inference. WAV, M4A/AAC, MP3 and browser formats supported by the installed FFmpeg can be used. The original clip is not altered or trimmed. References must still be 1–15 seconds; a reported 26.3-second recording needs a shorter new clip and matching transcript.

* **Only test tone appears:** IndicF5 is available only after its verified marker, cached artifacts and isolated environment exist. Restart/refresh the app after installation. This workspace now has a verified IndicF5 install; inspect `model_cache/indicf5_verified.json` and `outputs/.engine_logs/indicf5.log` if it fails. The test engine never reads text aloud.
* **GPU listed but CUDA unavailable:** diagnostics now query `.venv-indicf5` separately. Run `nvidia-smi` and `.\.venv-indicf5\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"`. This computer passed CUDA execution. Do not upgrade drivers automatically.
* **MP3 unavailable:** run `ffmpeg -version`, ensure PATH contains its directory and restart the app terminal. WAV and metadata remain available if MP3 encoding fails.
* **Invalid text file:** save it as UTF-8. Original text, punctuation, combining marks and line breaks are retained; the app does not normalize wording.
* **Port 7860 occupied:** stop the earlier app terminal with Ctrl+C before restarting. Do not terminate unrelated Python processes.
* **Memory exhausted:** shorten input and select line chunks; close unrelated GPU applications. Select CPU explicitly to restart IndicF5 on the CPU. No automatic retry silently changes the device. CPU may be much slower.
* **Cancel:** removes queued work. A synchronous inference or FFmpeg call already running can finish; its files are retained.
* **Rating unavailable:** test tones are deliberately ineligible. Real A/B outputs must use identical original text.
* **Terminal MXC launcher error:** the initial sandbox launcher reported inaccessible X: credentials before running any command. The read/build checks used approved host execution in this workspace; it was not a project or Python error.

This version pins Gradio 5.50.0. Gradio emits migration warnings about future 6.x APIs; current tests pass. Do not upgrade to 6.x without updating and checking the UI.
