import os
from pathlib import Path
from typing import List


class RepositoryConfig:
    """Configuration for repository layer"""

    # Repository type: "csv" or "db"
    REPO_TYPE = os.getenv("REPO_TYPE", "csv")

    # CSV file paths (relative to project root)
    CSV_PATHS = [
        Path("apps/grocery-collector/costco_items.csv"),
        Path("apps/grocery-collector/safeway_items.csv"),
    ]

    # Database settings (for future use)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./grocery.db")

    @classmethod
    def get_csv_paths(cls) -> List[Path]:
        """Get absolute paths to CSV files"""
        # Get project root (assuming we're in apps/grocery-api/app/repository/)
        project_root = Path(__file__).parent.parent.parent.parent.parent
        return [project_root / path for path in cls.CSV_PATHS]

    @classmethod
    def is_csv_mode(cls) -> bool:
        """Check if running in CSV mode"""
        return cls.REPO_TYPE.lower() == "csv"

    @classmethod
    def is_db_mode(cls) -> bool:
        """Check if running in database mode"""
        return cls.REPO_TYPE.lower() == "db"
