# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for VideoToolbox (视频处理工具箱)

Build:
    python -m PyInstaller video_toolbox.spec --noconfirm

Output:
    dist/VideoToolbox.exe       ← single-file executable
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── project root ──────────────────────────────────────────────────
ROOT = Path(SPEC).resolve().parent

# ── hidden imports (packages that use dynamic import) ─────────────
_REQUIREMENT_PACKAGES = [
    'gradio',
    'gradio_client',
    'huggingface_hub',
    'safehttpx',
    'groovy',
    'hf_gradio',
]

hiddenimports = []
for pkg in _REQUIREMENT_PACKAGES:
    hiddenimports.extend(collect_submodules(pkg))

hiddenimports += [
    'starlette',
    'fastapi',
    'uvicorn',
    'jinja2',
    'markdown_it',
    'mdurl',
    'linkify_it',
    'pydantic',
    'websockets',
    'PIL',
    'numpy',

    'packaging',
    'anyio',
    'sniffio',
    'h11',
    'httpcore',
    'httpx',
    'certifi',
    'charset_normalizer',
    'idna',
    'typing_extensions',
    'annotated_types',
    'pydantic_core',
    'rich',
    'pygments',
    'tomlkit',
    'python_multipart',

    'orjson',
    'pandas',
    'altair',
]

# ── data files (JS, CSS, templates, etc.) ─────────────────────────
datas = []
for pkg in _REQUIREMENT_PACKAGES:
    datas.extend(collect_data_files(pkg))

# Gradio reads component .py source at import time via pathlib.
# In a PyInstaller bundle these live inside PYZ archive, not on disk.
# Copy them as data so pathlib can find them.
def _collect_gradio_py_files():
    import gradio
    gradio_root = Path(gradio.__file__).parent
    result = []
    for dirpath, _dirnames, filenames in os.walk(gradio_root):
        for fn in filenames:
            if fn.endswith('.py'):
                src = os.path.join(dirpath, fn)
                dest_dir = os.path.relpath(dirpath, gradio_root.parent)
                result.append((src, dest_dir))
    return result

try:
    datas.extend(_collect_gradio_py_files())
except Exception:
    pass

# ── Analysis ──────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / 'video_toolbox.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'tensorflow',
        'torch',
        'transformers',
        'diffusers',
        'tokenizers',
        'sentencepiece',
        'openai',
        'langchain',
        'chromadb',
    ],
    noarchive=False,
)

# strip temp/egg noise
a.datas = [
    (dest, src, typ)
    for dest, src, typ in a.datas
    if 'CONFIG' not in dest and 'RECORD' not in dest
]

# ── Build pipeline (onefile) ──────────────────────────────────────
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    exclude_binaries=False,
    name='VideoToolbox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,               # keep console so users see port & errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='VideoToolbox.ico',
)
