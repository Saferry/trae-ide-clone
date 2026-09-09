"""单元测试统一入口。"""

import os
import sys
import tempfile
from pathlib import Path

# 让 pytest 能找到 src/
HERE = Path(__file__).parent
SRC = HERE.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# 让 sqlite 测试在临时目录
os.environ.setdefault("TRAE_CONFIG", str(HERE / "fixtures" / "trae.test.yaml"))