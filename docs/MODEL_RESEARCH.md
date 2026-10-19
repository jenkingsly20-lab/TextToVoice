# Model research — 2026-10-17

## Installation update (supersedes initial gate below)

User authorized multi-GB downloads and completed local Hugging Face login. IndicF5 revision `fb652a96e508091045890dae5bb99fe511facbcf` and official source Git commit `13f7c4d627cc10111aea8fe9c0039462cacacdc7` are installed. Weights are exactly 1,402,789,408 bytes. CUDA PyTorch 2.6.0+cu126 and Torchaudio 2.6.0+cu126 passed actual RTX 4060 tensor execution with driver 566.36. Full dependency resolution is recorded in requirements-indicf5-lock.txt; `pip check` passed.

Native Windows short Tamil inference passed: 3.05 seconds of output, approximately 22 seconds including model startup, peak PyTorch allocated VRAM 1,475,271,680 bytes. This excludes driver/other application VRAM and is not a long-chapter capacity guarantee. WAV/MP3 files are valid; pronunciation remains subject to human listening.

The published wrapper calls torch.compile and upstream inference rewrites punctuation. Our adapter uses the same official DiT/CFM architecture with strict weights loading in eager float32 mode, removes only saved `_orig_mod` key prefixes and feeds original characters directly. Model and vocoder each load strictly; no missing weights are ignored. Reference audio is decoded/resampled locally with no transcription or automatic trimming. A separating space joins reference conditioning text to the unchanged requested text. Chunk boundaries remain approximate audio boundaries.

[Vocos model](https://huggingface.co/charactr/vocos-mel-24khz) and [code license](https://github.com/gemelo-ai/vocos/blob/main/LICENSE) are MIT-labeled. Vocos revision `0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21` config and 54,365,991-byte checkpoint were explicitly cached. The IndicF5 checkpoint contains its vocoder weights, which are loaded strictly; cached Vocos config defines its architecture. Model workers force offline mode and do not run gated remote model.py. The official README's supplied Punjabi demo prompt was used only for the internal smoke test; the user-facing UI requires an explicitly permitted reference voice. No source or weights are being redistributed; the initial code-license uncertainty remains relevant before redistribution.

The following sections preserve the initial pre-install research and limitations. Their installation/access blocker has now been resolved for IndicF5. Indic-Speak remains uninstalled.

## Decision and gate

Phase 1 runs locally. Phase 2 is blocked by gated model access, pending download consent and unverified native-Windows inference. No model was substituted. No weights, CUDA packages or engine source were installed. No license was accepted on the user's behalf. Actual GPU: RTX 4060 Laptop, 8188 MiB, driver 566.36; 1507 MiB was already used at inspection. Python 3.10 and 3.13 are installed; app uses 3.10.

## IndicF5

[Official card](https://huggingface.co/ai4bharat/IndicF5): exact ID `ai4bharat/IndicF5`; explicitly supports Tamil. Card labels weights MIT, requires reference audio and transcript, and permits cloning only with explicit permission. Example uses `AutoModel.from_pretrained(..., trust_remote_code=True)` and 24 kHz output. There is no fixed stock voice count in the inspected example. Access requires sharing contact information and accepting conditions. The card recommends Python 3.10.

[Official files](https://huggingface.co/ai4bharat/IndicF5/tree/main): primary weights listed as 1.4 GB; checkpoints, vocoder, dependencies and cache add more. Exact total not verified. [Code repository](https://github.com/AI4Bharat/IndicF5) has no top-level LICENSE visible; fetching `/blob/main/LICENSE` returned 404. Do not infer code redistribution permission from the model's MIT label.

[Upstream requirements](https://raw.githubusercontent.com/AI4Bharat/IndicF5/main/requirements.txt) specify NumPy <=1.26.4, Torch/Torchaudio >=2, Transformers <4.50, Vocos and additional packages. [setup.py](https://raw.githubusercontent.com/AI4Bharat/IndicF5/main/setup.py) leaves Transformers unconstrained: explicitly apply requirements constraints in an isolated environment. Neither inspected upstream page guarantees native Windows operation or 8 GB VRAM. Short inference is a candidate to test after access, not a compatibility claim. Inspect downloaded custom code and any secondary downloads before execution. First priority remains IndicF5 once authorized and available.

## Indic-Speak

[Official card](https://huggingface.co/bodhan-ai/indic-speak): current ID `bodhan-ai/indic-speak`; Tamil `ta` supported, documented voices Anitha and Arun. Stock voices; no cloning/reference audio. Uses Transformers >=5, Torch, SNAC, SoundFile and supplied inference/Vocos code at 24 kHz. Card example still refers to `bodhan-ai/indic-speak-preview-v2`: reconcile against downloaded inference source before integration. Native Windows, exact compatible Torch version and 8 GB operation are not established. Weights/inference source are gated. Model's production label does not establish Bible pronunciation quality.

[File tree](https://huggingface.co/bodhan-ai/indic-speak/tree/main): main weights listed 6.6 GB, plus tokenizer, Vocos, SNAC and package downloads. Exact aggregate size is unverified. With about 6.5 GiB free VRAM at inspection, full GPU residency is doubtful; this is a memory estimate, not a measured failure. CPU/offload or quantization needs upstream-supported validation, with no silent change of model.

[Full Indic Open Model License v1.0](https://github.com/Bodhan-AI/bodhan-model-info/blob/main/licenses/indic-open-model-license/v1/Indic_Open_Model_License.md) covers distributed weights and associated inference code. It allows conditional commercial use; attribution, derivative licensing, hosting and very large product conditions apply. Llama/SNAC/Vocos upstream terms must also be checked. This is not an unrestricted MIT release. Do not distribute it without reviewing the full license.

## Runtime and next steps

[PyTorch official Windows builds](https://pytorch.org/get-started/previous-versions/) list 2.6.0 Torch/Torchaudio CUDA 12.6 packages. [NVIDIA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) supports considering a CUDA 12.x runtime with this driver; actual Torch CUDA execution remains untested. These are runtime candidates, not a verified complete engine combination. Separate `.venv-indicf5` and `.venv-indicspeak` environments avoid conflicting NumPy/Transformers versions; a subprocess adapter should exchange local WAV/JSON, load one model at a time and unload on switching.

Smallest next action: user reviews/accepts the IndicF5 access conditions in Hugging Face and authorizes the multi-GB download. Obtain exact file sizes/revisions after access, review code licensing, and test a consented reference clip and short Tamil sentence. No HF token should be pasted into chat. Use local `hf auth login` after access approval. Validate real audio, peak VRAM and elapsed time before declaring Phase 2 complete.

Alternative proposal if Windows remains blocked: investigate a Tamil MMS/VITS local CPU engine in an isolated environment. It has not been selected or installed; its model license, Windows runtime and suitability must be checked before substitution. WSL/Docker/cloud are outside the requested scope.

Offline operation of either real model is not yet verified: secondary artifacts may download during initialization. UI test mode has no model downloads and inference performs no network calls.
