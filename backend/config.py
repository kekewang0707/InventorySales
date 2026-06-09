import sys
from pathlib import Path


def get_data_dir() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DATABASE_URL = f"sqlite+aiosqlite:///{get_data_dir() / 'inventory_sales.db'}"
API_HOST = "127.0.0.1"
API_PORT = 18900

def get_fonts_dir() -> Path:
    base = Path(__file__).resolve().parent
    fonts_dir = base / 'assets' / 'fonts'
    fonts_dir.mkdir(parents=True, exist_ok=True)
    return fonts_dir
