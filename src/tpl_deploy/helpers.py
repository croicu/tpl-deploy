import json
import os
import tempfile
from pathlib import Path


def atomic_json_dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as tmp:
        json.dump(data, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_name = tmp.name

    os.replace(temp_name, path)  # atomic on Windows + POSIX
