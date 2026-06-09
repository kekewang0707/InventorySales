"""打印处理器 — 接收 PDF 路径，调用系统打印对话框"""
import os
import sys
import subprocess
import platform
from pathlib import Path


def print_pdf(pdf_path: str) -> bool:
    """
    打开系统打印对话框打印 PDF。
    macOS: 使用 lp / open
    Windows: 使用 os.startfile 或 subprocess
    Linux: 使用 lp / xdg-open
    """
    path = Path(pdf_path)
    if not path.exists():
        print(f"PDF 文件不存在: {pdf_path}")
        return False

    system = platform.system()

    try:
        if system == "Darwin":
            # macOS — 打开系统预览后自动触发打印
            subprocess.run(["lp", str(path)], check=True)
        elif system == "Windows":
            os.startfile(str(path), "print")
        else:
            subprocess.run(["lp", str(path)], check=True)
        return True
    except Exception as e:
        print(f"打印失败: {e}")
        return False


def get_default_printer() -> str:
    """获取系统默认打印机名称"""
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(["lpstat", "-d"], capture_output=True, text=True)
            if result.returncode == 0:
                # Output: "system default destination: HP_LaserJet"
                return result.stdout.strip().split(": ")[-1]
        elif system == "Windows":
            import win32print
            return win32print.GetDefaultPrinter()
        else:
            result = subprocess.run(["lpstat", "-d"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split(": ")[-1]
    except Exception:
        pass
    return "未知"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print_pdf(sys.argv[1])
    else:
        print("用法: python print_handler.py <pdf_path>")
