from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"
CRITEO_PATH = DATA_DIR / "criteo-research-uplift-v2.1.csv.gz"
