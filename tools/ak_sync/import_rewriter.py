from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RewriteResult:
    path: Path
    changed: bool
    manual_review: bool
    details: list[str]


def _module_parts(repo_root: Path, file_path: Path) -> list[str]:
    relative = file_path.relative_to(repo_root).with_suffix("")
    return list(relative.parts)


def _relative_level(file_module_parts: list[str], target_parts: list[str]) -> tuple[int, list[str]]:
    source_pkg = file_module_parts[:-1]
    common = 0
    for left, right in zip(source_pkg, target_parts):
        if left != right:
            break
        common += 1
    up_levels = len(source_pkg) - common
    remaining = target_parts[common:]
    return up_levels + 1, remaining


def _build_from_import(file_module_parts: list[str], module_name: str, imported_name: str, asname: str | None) -> str:
    target_parts = module_name.split(".")
    level, remaining = _relative_level(file_module_parts, target_parts)
    prefix = "." * level
    module = ".".join(remaining)
    import_part = imported_name if asname is None else f"{imported_name} as {asname}"
    return f"from {prefix}{module} import {import_part}" if module else f"from {prefix} import {import_part}"


def rewrite_file(repo_root: Path, file_path: Path) -> RewriteResult:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_parts = _module_parts(repo_root, file_path)
    lines = source.splitlines()
    changed = False
    manual_review = False
    details: list[str] = []

    replacements: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.module or not node.module.startswith("akshare."):
                continue
            target_parts = node.module.split(".")
            level, remaining = _relative_level(module_parts, target_parts)
            names = ", ".join(
                alias.name if alias.asname is None else f"{alias.name} as {alias.asname}"
                for alias in node.names
            )
            prefix = "." * level
            module = ".".join(remaining)
            replacement = f"from {prefix}{module} import {names}" if module else f"from {prefix} import {names}"
            replacements.append((node.lineno, node.end_lineno or node.lineno, replacement))
            changed = True
            details.append(f"ImportFrom: {node.module} -> {replacement}")
        elif isinstance(node, ast.Import):
            matched = [alias for alias in node.names if alias.name == "akshare" or alias.name.startswith("akshare.")]
            if not matched:
                continue
            if len(node.names) != 1:
                manual_review = True
                details.append(f"Import 需人工处理(单行多个导入): {ast.get_source_segment(source, node) or 'import akshare'}")
                continue
            alias = matched[0]
            if alias.name == "akshare":
                manual_review = True
                details.append("Import 需人工处理: import akshare")
                continue
            if alias.asname and alias.asname != alias.name.split(".")[-1]:
                manual_review = True
                details.append(f"Import 需人工处理(别名不安全): {ast.get_source_segment(source, node) or alias.name}")
                continue
            imported_name = alias.name.split(".")[-1]
            replacement = _build_from_import(module_parts, alias.name, imported_name, alias.asname)
            replacements.append((node.lineno, node.end_lineno or node.lineno, replacement))
            changed = True
            details.append(f"Import: {alias.name} -> {replacement}")

    for start, end, replacement in sorted(replacements, reverse=True):
        start_index = start - 1
        end_index = end
        lines[start_index:end_index] = [replacement]

    if changed:
        file_path.write_text("\n".join(lines) + ("\n" if source.endswith("\n") else ""), encoding="utf-8")

    return RewriteResult(path=file_path, changed=changed, manual_review=manual_review, details=details)


def scan_python_files(repo_root: Path) -> list[Path]:
    return sorted(path for path in (repo_root / "akshare").rglob("*.py") if path.is_file())
