import os
import sys
from pathlib import Path

# 优先加载 .env 文件（若存在），使环境变量提前就绪
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)


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


# ---- LLM / AI 配置 ----
# 优先读取 DEEPSEEK_* 环境变量，也兼容 OPENAI_* 作为 fallback

OPENAI_API_KEY: str = (
    os.environ.get("DEEPSEEK_API_KEY") or ""
)
OPENAI_MODEL: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
OPENAI_BASE_URL: str = os.environ.get(
    "DEEPSEEK_BASE_URL",
    "https://api.deepseek.com/v1"
)


def is_openai_configured() -> bool:
    """检查 LLM API Key 是否已配置"""
    key = OPENAI_API_KEY.strip()
    if not key or len(key) < 8:
        return False
    return True
