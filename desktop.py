#!/usr/bin/env python3
"""快捷启动脚本：从项目根目录启动桌面应用（推荐）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from desktop.app import main

if __name__ == "__main__":
    main()
