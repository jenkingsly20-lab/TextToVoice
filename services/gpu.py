import importlib.util
import shutil
import subprocess
import json
from config import ROOT

def diagnostics():
    result = {'ffmpeg': shutil.which('ffmpeg'), 'cuda_available': False}
    try:
        p = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used',
                            '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
        result['nvidia_smi'] = p.stdout.strip() or p.stderr.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        result['nvidia_smi'] = str(exc)
    if importlib.util.find_spec('torch'):
        try:
            import torch
            result.update(torch_version=torch.__version__, cuda_runtime=torch.version.cuda,
                          cuda_available=torch.cuda.is_available())
            if result['cuda_available']:
                result['gpu'] = torch.cuda.get_device_name(0)
        except Exception as exc:
            result['torch_error'] = str(exc)
    else:
        result['torch'] = 'Not installed in this environment. NVIDIA driver detection does not prove PyTorch CUDA availability.'
        engine_python = ROOT / '.venv-indicf5/Scripts/python.exe'
        if engine_python.exists():
            try:
                p = subprocess.run([str(engine_python), '-c',
                    "import torch,json; print(json.dumps({'torch_version':torch.__version__,'cuda_runtime':torch.version.cuda,'cuda_available':torch.cuda.is_available(),'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"],
                    capture_output=True, text=True, timeout=30,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if p.returncode == 0:
                    engine_status = json.loads(p.stdout.strip())
                    result['indicf5_environment'] = engine_status
                    result['cuda_available'] = engine_status['cuda_available']
                    result['torch'] = 'UI environment is dependency-light; IndicF5 uses .venv-indicf5.'
                else:
                    result['indicf5_environment_error'] = p.stderr[-1000:]
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                result['indicf5_environment_error'] = str(exc)
    return result
