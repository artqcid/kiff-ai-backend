import sys
from pathlib import Path

# Add repository root (two levels up from tests/) to sys.path
# tests/ -> backend/ -> kiff-ai/
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
