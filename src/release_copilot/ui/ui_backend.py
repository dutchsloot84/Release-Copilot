import threading, time, os
from typing import Callable, Dict, Any, Optional

class RunThread:
    def __init__(self, target: Callable[..., Dict[str, Any]], kwargs: dict):
        self._target = target
        self._kwargs = kwargs
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self): self._thread.start()
    def is_alive(self): return self._thread.is_alive()
    def _run(self):
        try:
            self.result = self._target(**self._kwargs)
        except Exception as e:  # pragma: no cover - defensive
            self.error = str(e)

def tail_file(path: str, max_bytes: int = 50_000) -> str:
    if not os.path.exists(path):
        return ""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(-max_bytes, os.SEEK_END)
        data = f.read()
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""
