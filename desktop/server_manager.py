import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


class ServerManager:
    """管理 FastAPI 子进程"""

    def __init__(self, host: str = "127.0.0.1", port: int = 18900):
        self.process: Optional[subprocess.Popen] = None
        self.host = host
        self.port = port
        self.project_root = str(Path(__file__).resolve().parent.parent)

    def start(self):
        """在项目根目录启动 uvicorn 子进程"""
        if self.process is not None:
            return

        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        paths = [p for p in pythonpath.split(os.pathsep) if p]
        if self.project_root not in paths:
            paths.insert(0, self.project_root)
        env["PYTHONPATH"] = os.pathsep.join(paths)

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

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
            self.process = None

    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None
