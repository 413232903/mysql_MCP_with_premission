import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，使测试可以直接 import src 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
