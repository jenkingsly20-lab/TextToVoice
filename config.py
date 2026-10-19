import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS = Path(os.getenv('TAMIL_TTS_OUTPUTS', ROOT / 'outputs')).resolve()
CACHE = ROOT / 'model_cache'
MP3_BITRATE_KBPS = int(os.getenv('TAMIL_TTS_MP3_BITRATE_KBPS', '192'))
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HOME'] = str(CACHE)
os.environ['GRADIO_TEMP_DIR'] = str(OUTPUTS / '.gradio')
