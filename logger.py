import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD", "123456")


def _ensure_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, data: Dict[str, Any]) -> None:
    _ensure_dir()
    payload = {"timestamp": datetime.utcnow().isoformat(), **data}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def log_all_interactions(student_id: str, payload: Dict[str, Any]) -> None:
    _append_jsonl(LOG_DIR / "all_interactions.jsonl", {"student_id": student_id, **payload})


def save_student_dialog(student_id: str, payload: Dict[str, Any]) -> None:
    safe_id = "".join(c for c in student_id if c.isalnum() or c in "_-") or "unknown"
    _append_jsonl(LOG_DIR / f"{safe_id}.jsonl", payload)


def secure_read_logs(password: str):
    if (password or "") != TEACHER_PASSWORD:
        return {"success": False, "message": "密码错误。"}
    _ensure_dir()
    path = LOG_DIR / "all_interactions.jsonl"
    if not path.exists():
        return {"success": True, "logs": []}
    with path.open("r", encoding="utf-8") as f:
        logs = [json.loads(line.strip()) for line in f if line.strip()]
    return {"success": True, "logs": logs[-200:]}
