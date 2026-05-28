from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class SyncError(RuntimeError):
    """同步流程异常。"""


@dataclass
class RunContext:
    repo_root: Path
    run_dir: Path

    @classmethod
    def create(cls, repo_root: Path, log_root: Path) -> "RunContext":
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = log_root / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        return cls(repo_root=repo_root, run_dir=run_dir)

    def write_json(self, name: str, payload: dict[str, Any]) -> None:
        path = self.run_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    log_file: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if log_file is not None:
        content = [f"$ {' '.join(cmd)}", "", completed.stdout]
        if completed.stderr:
            content.extend(["[stderr]", completed.stderr])
        log_file.write_text("\n".join(content), encoding="utf-8")
    if check and completed.returncode != 0:
        raise SyncError(
            f"命令执行失败: {' '.join(cmd)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def repo_root_from(start: Path) -> Path:
    current = start.resolve()
    for path in [current, *current.parents]:
        if (path / ".git").exists():
            return path
    raise SyncError("未找到 git 仓库根目录")
