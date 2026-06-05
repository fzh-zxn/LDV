"""把 src 加入 sys.path，供 tools/ 下脚本 import paths 等模块。"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
