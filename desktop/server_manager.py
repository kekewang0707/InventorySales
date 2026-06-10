import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional


class ServerManager:
    """管理 FastAPI 子进程的生命周期（启动、停止、状态检查）。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 18900):
        """初始化服务器管理器，默认监听本机 18900 端口。"""
        self.process: Optional[subprocess.Popen] = None
        self.host = host
        self.port = port
        self.project_root = str(Path(__file__).resolve().parent.parent)
        self._reader_threads: list = []

    def _forward_output(self, stream, prefix: str):
        """将子进程的 stdout/stderr 流输出转发到父进程终端。"""
        try:
            for line in iter(stream.readline, b''):
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"[{prefix}] {text}")
            stream.close()
        except Exception:
            pass

    def start(self):
        """启动 FastAPI 子进程，配置环境变量并启动输出读取线程。"""
        if self.process is not None:
            return

        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        paths = [p for p in pythonpath.split(os.pathsep) if p]
        if self.project_root not in paths:
            paths.insert(0, self.project_root)
        env["PYTHONPATH"] = os.pathsep.join(paths)

        # 强制 Python 输出不缓冲
        env["PYTHONUNBUFFERED"] = "1"

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host", self.host,
            "--port", str(self.port),
            "--log-level", "info",
        ]

        self.process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 启动线程读取 stdout 和 stderr 并打印到终端
        t_out = threading.Thread(
            target=self._forward_output,
            args=(self.process.stdout, "BACKEND"),
            daemon=True,
        )
        t_err = threading.Thread(
            target=self._forward_output,
            args=(self.process.stderr, "BACKEND"),
            daemon=True,
        )
        t_out.start()
        t_err.start()
        self._reader_threads = [t_out, t_err]

    def stop(self):
        """停止 FastAPI 子进程（先终止，超时后强制杀死）。"""
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
            self.process = None

    def is_running(self) -> bool:
        """检查子进程是否仍在运行。"""
        if self.process is None:
            return False
        return self.process.poll() is None
