import sys
import os
import time
import urllib.request
import subprocess
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineProfile

from desktop.server_manager import ServerManager

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 18900
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"


def kill_process_on_port(port: int):
    try:
        result = subprocess.run(
            ["lsof", "-t", "-i", f":{port}"],
            capture_output=True, text=True, timeout=3
        )
        if not result.stdout.strip():
            return
        pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
        my_pid = str(os.getpid())
        for pid in pids:
            if pid != my_pid:
                subprocess.run(["kill", "-9", pid], capture_output=True, timeout=3)
                print(f"  已终止旧进程 PID={pid}")
        time.sleep(1)
    except Exception as e:
        print(f"  关闭旧进程时出错: {e}", file=sys.stderr)


def wait_for_backend(url: str, timeout: float = 15.0, interval: float = 0.3) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.urlopen(f"{url}/api/health", timeout=2)
            req.read()
            return True
        except Exception:
            time.sleep(interval)
    return False


class MainWindow(QMainWindow):
    def __init__(self, url: str):
        super().__init__()
        self.setWindowTitle("InventorySales - 工厂销售出库管理")
        self.resize(1280, 800)
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(url))
        self.setCentralWidget(self.browser)

        # 接管下载请求
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self.handle_download)

    def handle_download(self, download: QWebEngineDownloadRequest):
        """处理文件下载，保存到用户下载目录"""
        suggested = download.downloadFileName()
        print(f"下载文件: {suggested}")
        download.accept()


def main():
    kill_process_on_port(BACKEND_PORT)

    manager = ServerManager(host=BACKEND_HOST, port=BACKEND_PORT)
    manager.start()
    print("正在启动后端服务...")

    if not wait_for_backend(BACKEND_URL):
        print("后端启动失败（详见上方错误信息）", file=sys.stderr)
        manager.stop()
        sys.exit(1)

    print("后端服务已就绪")

    frontend_url = BACKEND_URL
    print(f"前端服务: {frontend_url}")

    app = QApplication(sys.argv)
    window = MainWindow(frontend_url)
    window.show()
    exit_code = app.exec()
    manager.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
