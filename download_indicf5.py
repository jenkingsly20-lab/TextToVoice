"""Explicit, authenticated download. Run only after model access is approved.

Downloads weights and source for review; does not execute the model's remote code.
"""
from pathlib import Path
from huggingface_hub import HfApi, get_token, snapshot_download

REVISION = 'fb652a96e508091045890dae5bb99fe511facbcf'
ROOT = Path(__file__).resolve().parent

def main():
    token = get_token()
    if not token:
        raise SystemExit('Local Hugging Face login required. Run .\\.venv\\Scripts\\hf.exe auth login. Never paste tokens into chat.')
    api = HfApi(token=token)
    # Verify gated file authorization before the large download.
    from huggingface_hub import hf_hub_download
    hf_hub_download('ai4bharat/IndicF5', 'model.py', revision=REVISION,
                    token=token, cache_dir=ROOT / 'model_cache')
    location = snapshot_download('ai4bharat/IndicF5', revision=REVISION,
        token=token, cache_dir=ROOT / 'model_cache',
        allow_patterns=['model.py', 'config.json', 'model.safetensors', 'checkpoints/vocab.txt', 'README.md'])
    snapshot_download('charactr/vocos-mel-24khz', revision='0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21',
        cache_dir=ROOT / 'model_cache', allow_patterns=['config.yaml', 'pytorch_model.bin', 'README.md'])
    print('Downloaded for inspection:', location)

if __name__ == '__main__':
    main()
