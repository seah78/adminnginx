import json
import os
import uuid

from pathlib import Path
from datetime import datetime
from django.conf import settings


def get_operations_dir() -> Path:
    path = Path(
        os.getenv(
            "ADMINNGINX_OPERATIONS_DIR",
            settings.BASE_DIR / "data" / "operations",
        )
    )

    path.mkdir(parents=True, exist_ok=True)

    return path


def get_operation_path(operation_id: str) -> Path:
    safe_id = Path(operation_id).name
    return get_operations_dir() / f"{safe_id}.json"


def create_operation(kind: str) -> str:
    operation_id = str(uuid.uuid4())

    save_operation(
        operation_id,
        {
            "id": operation_id,
            "kind": kind,
            "status": "running",
            "created_at": datetime.now().isoformat(),
            "steps": [],
        },
    )

    return operation_id


def get_operation(operation_id: str) -> dict:
    path = get_operation_path(operation_id)

    if not path.exists():
        return {
            "id": operation_id,
            "status": "missing",
            "steps": [],
        }

    return json.loads(path.read_text(encoding="utf-8"))


def save_operation(operation_id: str, data: dict) -> None:
    path = get_operation_path(operation_id)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def start_operation_step(
    operation_id: str,
    name: str,
    message: str = "",
) -> int:
    data = get_operation(operation_id)

    data["steps"].append(
        {
            "name": name,
            "status": "running",
            "message": message,
            "created_at": datetime.now().isoformat(),
        }
    )

    save_operation(operation_id, data)

    return len(data["steps"]) - 1


def update_operation_step(
    operation_id: str,
    index: int,
    status: str,
    message: str = "",
) -> None:
    data = get_operation(operation_id)

    if index < len(data["steps"]):
        data["steps"][index]["status"] = status
        data["steps"][index]["message"] = message
        data["steps"][index]["updated_at"] = datetime.now().isoformat()

    save_operation(operation_id, data)


def finish_operation(
    operation_id: str,
    success: bool,
) -> None:
    data = get_operation(operation_id)
    data["status"] = "success" if success else "error"
    data["finished_at"] = datetime.now().isoformat()
    save_operation(operation_id, data)