from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]  # monorepo 根（按你仓库层级调整）
DATA_CSV_FILES = [
    ROOT / "grocery-collector" / "costco_items.csv",
    ROOT / "grocery-collector" / "safeway_items.csv",
]
DEFAULT_LIMIT = 20
