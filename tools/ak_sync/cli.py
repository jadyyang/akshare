from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
import urllib.error
import urllib.request
from pathlib import Path

from .common import RunContext, SyncError, repo_root_from, run_cmd
from .config import load_config, load_state, save_state
from .import_rewriter import rewrite_file, scan_python_files
from .notify import send_mail


def ensure_upstream_remote(config, ctx: RunContext) -> None:
    log_file = ctx.run_dir / "ensure-upstream.log"
    remotes = run_cmd(["git", "remote"], cwd=config.repo_root, log_file=log_file).stdout.splitlines()
    if config.upstream_remote not in remotes:
        run_cmd(
            ["git", "remote", "add", config.upstream_remote, config.upstream_repo],
            cwd=config.repo_root,
            log_file=log_file,
        )


def fetch_latest_release(config) -> dict:
    request = urllib.request.Request(
        f"{config.upstream_api}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ak-sync"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_latest_tag(config) -> dict:
    request = urllib.request.Request(
        f"{config.upstream_api}/tags?per_page=1",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ak-sync"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload:
        raise SyncError("上游 tags 为空")
    latest = payload[0]
    return {
        "tag_name": latest["name"],
        "name": latest["name"],
        "html_url": f"https://github.com/akfamily/akshare/releases/tag/{latest['name']}",
        "body": "",
        "source": "tags",
    }


def get_upstream_release_info(config) -> dict:
    try:
        payload = fetch_latest_release(config)
        payload["source"] = "releases"
        return payload
    except urllib.error.HTTPError as err:
        if err.code != 404:
            raise SyncError(f"获取上游 release 失败: HTTP {err.code}") from err
    except urllib.error.URLError as err:
        raise SyncError(f"获取上游 release 失败: {err}") from err
    return fetch_latest_tag(config)


def build_compare_url(previous_tag: str, current_tag: str) -> str:
    if not previous_tag:
        return ""
    return f"https://github.com/akfamily/akshare/compare/{previous_tag}...{current_tag}"


def fetch_compare_info(previous_tag: str, current_tag: str) -> dict:
    if not previous_tag:
        return {}
    request = urllib.request.Request(
        f"https://api.github.com/repos/akfamily/akshare/compare/{previous_tag}...{current_tag}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ak-sync"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def git_output(repo_root: Path, *args: str) -> str:
    return run_cmd(["git", *args], cwd=repo_root, check=True).stdout.strip()


def ensure_clean_worktree(repo_root: Path) -> None:
    status = git_output(repo_root, "status", "--short")
    if status:
        raise SyncError(f"工作区存在未提交改动，请先清理后再执行:\n{status}")


def has_staged_or_unstaged_changes(repo_root: Path) -> bool:
    return bool(git_output(repo_root, "status", "--short"))


def collect_summary(repo_root: Path, previous_tag: str, upstream_tag: str, release: dict, rewrite_payload: dict | None, deploy_payload: dict | None, publish_tag: str | None, compare_payload: dict | None, dry_run: bool, publish_payload: dict | None) -> list[str]:
    summary_lines = [
        f"项目: akshare",
        f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"上游版本: {upstream_tag}",
        f"上次已处理版本: {previous_tag or '无'}",
        f"执行模式: {'dry-run' if dry_run else 'apply'}",
        f"上游来源: {release.get('source', 'unknown')}",
        f"上游发布页: {release.get('html_url', '')}",
    ]
    compare_url = build_compare_url(previous_tag, upstream_tag)
    if compare_url:
        summary_lines.append(f"上游对比页: {compare_url}")
    body = (release.get("body") or "").strip()
    if body:
        snippet = "\n".join(body.splitlines()[:20]).strip()
        if snippet:
            summary_lines.append("上游发布摘要:")
            summary_lines.append(snippet)
    if compare_payload:
        summary_lines.append(f"上游变更提交数: {compare_payload.get('total_commits', 0)}")
        files = compare_payload.get("files", [])
        summary_lines.append(f"上游变更文件数: {len(files)}")
        commits = compare_payload.get("commits", [])[:10]
        if commits:
            summary_lines.append("上游提交摘要:")
            for item in commits:
                message = (item.get("commit", {}).get("message", "").splitlines() or [""])[0]
                sha = item.get("sha", "")[:7]
                summary_lines.append(f"- {sha} {message}")
    if rewrite_payload is not None:
        summary_lines.append(f"改写 import 文件数: {len(rewrite_payload.get('changed_files', []))}")
        manual_files = rewrite_payload.get("manual_review_files", [])
        summary_lines.append(f"需人工检查 import 文件数: {len(manual_files)}")
        if manual_files:
            summary_lines.append(f"人工检查文件: {', '.join(manual_files)}")
    if publish_tag:
        summary_lines.append(f"发布标签: {publish_tag}")
    if publish_payload is not None:
        summary_lines.append(f"发布是否跳过: {'是' if publish_payload.get('skipped') else '否'}")
        if publish_payload.get("reason"):
            summary_lines.append(f"发布跳过原因: {publish_payload['reason']}")
    try:
        head_commit = git_output(repo_root, "rev-parse", "--short", "HEAD")
        summary_lines.append(f"当前提交: {head_commit}")
    except SyncError:
        pass
    if deploy_payload is not None:
        results = deploy_payload.get("results", [])
        success_hosts = [item["host"] for item in results if item["returncode"] == 0]
        failed_hosts = [item["host"] for item in results if item["returncode"] != 0]
        summary_lines.append(f"部署成功主机数: {len(success_hosts)}")
        if success_hosts:
            summary_lines.append(f"部署成功主机: {', '.join(success_hosts)}")
        summary_lines.append(f"部署失败主机数: {len(failed_hosts)}")
        if failed_hosts:
            summary_lines.append(f"部署失败主机: {', '.join(failed_hosts)}")
    return summary_lines


def scan_rewrite_candidates(repo_root: Path) -> dict:
    changed_files: list[str] = []
    manual_review_files: list[str] = []
    for path in scan_python_files(repo_root):
        source = path.read_text(encoding="utf-8")
        if "from akshare." in source or "import akshare." in source or "import akshare\n" in source:
            relative = str(path.relative_to(repo_root))
            if "import akshare\n" in source or "import akshare\r\n" in source:
                manual_review_files.append(relative)
            else:
                changed_files.append(relative)
    return {"changed_files": changed_files, "manual_review_files": manual_review_files}


def command_check_upstream(args: argparse.Namespace) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    state = load_state(config.state_file)
    release = get_upstream_release_info(config)
    latest_tag = release["tag_name"]
    previous_tag = state.get("last_upstream_tag", "")
    needs_sync = latest_tag != previous_tag
    payload = {
        "latest_tag": latest_tag,
        "previous_tag": previous_tag,
        "needs_sync": needs_sync,
        "release_name": release.get("name", ""),
        "release_url": release.get("html_url", ""),
        "source": release.get("source", "unknown"),
        "compare_url": build_compare_url(previous_tag, latest_tag),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not args.fail_when_no_update or needs_sync else 1


def command_merge_upstream(args: argparse.Namespace) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    ctx = RunContext.create(repo_root, config.log_root)
    ensure_clean_worktree(repo_root)
    ensure_upstream_remote(config, ctx)
    run_cmd(["git", "fetch", config.upstream_remote, "--tags"], cwd=repo_root, log_file=ctx.run_dir / "fetch.log")
    run_cmd(["git", "checkout", config.main_branch], cwd=repo_root, log_file=ctx.run_dir / "checkout.log")
    run_cmd(["git", "pull", "origin", config.main_branch], cwd=repo_root, log_file=ctx.run_dir / "pull.log")
    merge_ref = args.ref or args.tag
    if not merge_ref:
        raise SyncError("merge-upstream 需要提供 --tag 或 --ref")
    tag_ref = f"refs/tags/{merge_ref}"
    run_cmd(["git", "show-ref", "--verify", tag_ref], cwd=repo_root, log_file=ctx.run_dir / "verify-tag.log")
    try:
        run_cmd(
            ["git", "merge", "--no-ff", merge_ref, "-m", f"Merge upstream {args.tag or merge_ref}"],
            cwd=repo_root,
            log_file=ctx.run_dir / "merge.log",
        )
    except SyncError as err:
        raise SyncError(
            f"合并上游版本失败，可能存在冲突。\n"
            f"可先查看日志: {ctx.run_dir / 'merge.log'}\n"
            f"若确认放弃本次合并，可执行: git merge --abort\n"
            f"原始错误:\n{err}"
        ) from err
    print(f"已合并上游版本 {args.tag or merge_ref}，日志目录: {ctx.run_dir}")
    return 0


def command_rewrite_imports(_: argparse.Namespace) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    ctx = RunContext.create(repo_root, config.log_root)
    results = [rewrite_file(repo_root, path) for path in scan_python_files(repo_root)]
    changed = [str(item.path.relative_to(repo_root)) for item in results if item.changed]
    manual = [str(item.path.relative_to(repo_root)) for item in results if item.manual_review]
    payload = {"changed_files": changed, "manual_review_files": manual}
    ctx.write_json("rewrite-summary.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if manual:
        raise SyncError(f"存在需要人工处理的 import 文件: {', '.join(manual)}")
    return 0


def command_validate(_: argparse.Namespace) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    ctx = RunContext.create(repo_root, config.log_root)
    run_cmd([sys.executable, "-m", "compileall", "akshare"], cwd=repo_root, log_file=ctx.run_dir / "compileall.log")
    import_scan = run_cmd(
        ["rg", "-n", "^from akshare\\.|^import akshare\\.", "akshare", "-g", "*.py"],
        cwd=repo_root,
        log_file=ctx.run_dir / "absolute-import-scan.log",
        check=False,
    )
    if import_scan.returncode == 0 and import_scan.stdout.strip():
        raise SyncError(f"仍存在包内绝对导入:\n{import_scan.stdout}")
    print(f"校验通过，日志目录: {ctx.run_dir}")
    return 0


def command_publish(args: argparse.Namespace) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    ctx = RunContext.create(repo_root, config.log_root)
    status_output = run_cmd(["git", "status", "--short"], cwd=repo_root, log_file=ctx.run_dir / "status.log").stdout.strip()
    if not status_output:
        payload = {"skipped": True, "reason": "no_changes", "tag": args.tag or ""}
        ctx.write_json("publish-summary.json", payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    run_cmd(["git", "add", "-A"], cwd=repo_root, log_file=ctx.run_dir / "git-add.log")
    if not has_staged_or_unstaged_changes(repo_root):
        payload = {"skipped": True, "reason": "no_changes_after_add", "tag": args.tag or ""}
        ctx.write_json("publish-summary.json", payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    run_cmd(["git", "commit", "-m", args.message], cwd=repo_root, log_file=ctx.run_dir / "git-commit.log")
    run_cmd(["git", "push", "origin", config.main_branch], cwd=repo_root, log_file=ctx.run_dir / "git-push.log")
    if args.tag:
        run_cmd(["git", "tag", "-a", args.tag, "-m", f"Release {args.tag}"], cwd=repo_root, log_file=ctx.run_dir / "git-tag.log")
        run_cmd(["git", "push", "origin", args.tag], cwd=repo_root, log_file=ctx.run_dir / "git-push-tag.log")
    payload = {"skipped": False, "reason": "", "tag": args.tag or ""}
    ctx.write_json("publish-summary.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_deploy(_: argparse.Namespace) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    ctx = RunContext.create(repo_root, config.log_root)
    results: list[dict[str, str | int]] = []
    for host in config.deploy_hosts:
        target = f"{config.ssh_user + '@' if config.ssh_user else ''}{host}"
        cmd = ["ssh", *config.ssh_options, target, f"cd {config.deploy_path} && git fetch --all && git checkout {config.deploy_branch} && git pull --ff-only origin {config.deploy_branch}"]
        completed = run_cmd(cmd, cwd=repo_root, log_file=ctx.run_dir / f"deploy-{host}.log", check=False)
        results.append({"host": host, "returncode": completed.returncode})
    failed = [item for item in results if item["returncode"] != 0]
    payload = {"results": results}
    ctx.write_json("deploy-summary.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failed:
        raise SyncError(f"部署失败主机: {', '.join(item['host'] for item in failed)}")
    return 0


def command_run_all(args: argparse.Namespace) -> int:
    repo_root = repo_root_from(Path.cwd())
    config = load_config(repo_root)
    state = load_state(config.state_file)
    release = get_upstream_release_info(config)
    upstream_tag = args.tag or release["tag_name"]
    upstream_ref = args.ref or release["tag_name"]
    previous_tag = state.get("last_upstream_tag", "")
    if upstream_tag == previous_tag and not args.force:
        print(f"上游版本 {upstream_tag} 已处理，无需重复执行")
        return 0

    rewrite_payload = None
    deploy_payload = None
    compare_payload = None
    publish_payload = None
    try:
        try:
            compare_payload = fetch_compare_info(previous_tag, upstream_tag)
        except Exception:
            compare_payload = None
        if args.dry_run:
            rewrite_payload = scan_rewrite_candidates(repo_root)
            summary_lines = collect_summary(
                repo_root,
                previous_tag,
                upstream_tag,
                release,
                rewrite_payload,
                None,
                args.publish_tag,
                compare_payload,
                True,
                None,
            )
            summary_lines.append("结果: dry-run 预览完成")
            summary_lines.append(f"计划 merge 引用: {upstream_ref}")
            summary_lines.append(f"计划执行 publish: {'是' if args.publish else '否'}")
            summary_lines.append(f"计划执行 deploy: {'是' if args.deploy else '否'}")
            print("\n".join(summary_lines))
            return 0
        command_merge_upstream(argparse.Namespace(tag=upstream_tag, ref=upstream_ref))
        rewrite_payload = json.loads(run_cmd([sys.executable, "-m", "tools.ak_sync.cli", "rewrite-imports", "--json"], cwd=repo_root, check=True).stdout)
        command_validate(argparse.Namespace())
        publish_tag = args.publish_tag
        if args.publish:
            publish_payload = json.loads(run_cmd([sys.executable, "-m", "tools.ak_sync.cli", "publish", "--message", args.commit_message, *(["--tag", publish_tag] if publish_tag else [])], cwd=repo_root, check=True).stdout)
        if args.deploy:
            deploy_payload = json.loads(run_cmd([sys.executable, "-m", "tools.ak_sync.cli", "deploy", "--json"], cwd=repo_root, check=True).stdout)
        state["last_upstream_tag"] = upstream_tag
        state["last_release_url"] = release.get("html_url", "")
        save_state(config.state_file, state)
        summary_lines = collect_summary(repo_root, previous_tag, upstream_tag, release, rewrite_payload, deploy_payload, publish_tag, compare_payload, False, publish_payload)
        summary_lines.append("结果: 成功")
        send_mail(config.mail, f"[ak-sync] 成功同步 {upstream_tag}", "\n".join(summary_lines))
        print("\n".join(summary_lines))
        return 0
    except Exception as err:
        summary_lines = collect_summary(repo_root, previous_tag, upstream_tag, release, rewrite_payload, deploy_payload, args.publish_tag, compare_payload, False, publish_payload)
        summary_lines.append("结果: 失败")
        summary_lines.append(f"错误: {err}")
        send_mail(config.mail, f"[ak-sync] 同步失败 {upstream_tag}", "\n".join(summary_lines))
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.ak_sync.cli", description="akshare 上游同步自动化工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check-upstream", help="检查上游是否有新版本")
    check_parser.add_argument("--fail-when-no-update", action="store_true", help="没有更新时返回非零退出码")
    check_parser.set_defaults(func=command_check_upstream)

    merge_parser = subparsers.add_parser("merge-upstream", help="合并指定上游 tag")
    merge_parser.add_argument("--tag", help="用于展示和状态记录的上游版本名，例如 release-v1.18.64")
    merge_parser.add_argument("--ref", help="实际 merge 的 git 引用，默认与 --tag 相同")
    merge_parser.set_defaults(func=command_merge_upstream)

    rewrite_parser = subparsers.add_parser("rewrite-imports", help="将包内绝对导入改为相对导入")
    rewrite_parser.add_argument("--json", action="store_true", help="输出 JSON 结果，供脚本调用")
    rewrite_parser.set_defaults(func=command_rewrite_imports)

    validate_parser = subparsers.add_parser("validate", help="执行同步后的基础校验")
    validate_parser.set_defaults(func=command_validate)

    publish_parser = subparsers.add_parser("publish", help="提交并推送代码，可选创建 tag")
    publish_parser.add_argument("--message", required=True, help="git commit message")
    publish_parser.add_argument("--tag", help="可选：发布 tag")
    publish_parser.set_defaults(func=command_publish)

    deploy_parser = subparsers.add_parser("deploy", help="通过 SSH 在部署机器上更新代码")
    deploy_parser.add_argument("--json", action="store_true", help="输出 JSON 结果，供脚本调用")
    deploy_parser.set_defaults(func=command_deploy)

    run_all_parser = subparsers.add_parser("run-all", help="执行完整同步流程")
    run_all_parser.add_argument("--tag", help="指定上游 tag；默认自动发现最新 release")
    run_all_parser.add_argument("--ref", help="指定实际 merge 的 git 引用；默认与 --tag 相同")
    run_all_parser.add_argument("--force", action="store_true", help="即便已处理过也强制执行")
    run_all_parser.add_argument("--dry-run", action="store_true", help="仅预览将执行的步骤，不修改代码、不发布、不部署")
    run_all_parser.add_argument("--publish", action="store_true", help="完成校验后自动提交并推送")
    run_all_parser.add_argument("--publish-tag", help="publish 时一并创建的仓库 tag")
    run_all_parser.add_argument("--commit-message", default="sync: merge upstream and rewrite internal imports", help="publish 使用的提交信息")
    run_all_parser.add_argument("--deploy", action="store_true", help="publish 后自动部署到目标机器")
    run_all_parser.set_defaults(func=command_run_all)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except SyncError as err:
        print(f"错误: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
