from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_DEPLOY_HOSTS = ["pi5", "pi52", "pi53", "pi54", "pi55", "pi56", "pi57"]
DEFAULT_DEPLOY_PATH = "/home/jadyyang/code/finance/finance/spider/airflow"
DEFAULT_UPSTREAM_REPO = "https://github.com/akfamily/akshare.git"
DEFAULT_UPSTREAM_API = "https://api.github.com/repos/akfamily/akshare"


@dataclass
class MailConfig:
    enabled: bool = False
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)
    use_tls: bool = True
    security: str = "starttls"


@dataclass
class SyncConfig:
    repo_root: Path
    state_file: Path
    log_root: Path
    upstream_remote: str = "upstream"
    upstream_repo: str = DEFAULT_UPSTREAM_REPO
    upstream_api: str = DEFAULT_UPSTREAM_API
    main_branch: str = "main"
    deploy_hosts: list[str] = field(default_factory=lambda: list(DEFAULT_DEPLOY_HOSTS))
    deploy_path: str = DEFAULT_DEPLOY_PATH
    deploy_branch: str = "main"
    ssh_user: str = ""
    ssh_options: list[str] = field(default_factory=list)
    mail: MailConfig = field(default_factory=MailConfig)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config(repo_root: Path) -> SyncConfig:
    env = os.environ
    state_file = repo_root / ".ak-sync-state.json"
    log_root = repo_root / ".ak-sync-logs"
    to_addrs = _split_csv(env.get("AKSYNC_MAIL_TO", ""))
    mail_username = env.get("AKSYNC_MAIL_USERNAME", "")
    mail_from = env.get("AKSYNC_MAIL_FROM", mail_username)
    mail_port = int(env.get("AKSYNC_MAIL_SMTP_PORT", "587"))
    mail_security = env.get("AKSYNC_MAIL_SECURITY", "").strip().lower()
    if not mail_security:
        if mail_port == 465:
            mail_security = "ssl"
        elif env.get("AKSYNC_MAIL_USE_TLS", "true").lower() != "false":
            mail_security = "starttls"
        else:
            mail_security = "none"
    mail = MailConfig(
        enabled=bool(mail_username and env.get("AKSYNC_MAIL_PASSWORD") and to_addrs),
        smtp_host=env.get("AKSYNC_MAIL_SMTP_HOST", "smtp.office365.com"),
        smtp_port=mail_port,
        username=mail_username,
        password=env.get("AKSYNC_MAIL_PASSWORD", ""),
        from_addr=mail_from,
        to_addrs=to_addrs,
        use_tls=env.get("AKSYNC_MAIL_USE_TLS", "true").lower() != "false",
        security=mail_security,
    )
    ssh_options = _split_csv(env.get("AKSYNC_SSH_OPTIONS", ""))
    deploy_hosts = _split_csv(env.get("AKSYNC_DEPLOY_HOSTS", "")) or list(DEFAULT_DEPLOY_HOSTS)
    return SyncConfig(
        repo_root=repo_root,
        state_file=Path(env.get("AKSYNC_STATE_FILE", state_file)),
        log_root=Path(env.get("AKSYNC_LOG_ROOT", log_root)),
        upstream_remote=env.get("AKSYNC_UPSTREAM_REMOTE", "upstream"),
        upstream_repo=env.get("AKSYNC_UPSTREAM_REPO", DEFAULT_UPSTREAM_REPO),
        upstream_api=env.get("AKSYNC_UPSTREAM_API", DEFAULT_UPSTREAM_API),
        main_branch=env.get("AKSYNC_MAIN_BRANCH", "main"),
        deploy_hosts=deploy_hosts,
        deploy_path=env.get("AKSYNC_DEPLOY_PATH", DEFAULT_DEPLOY_PATH),
        deploy_branch=env.get("AKSYNC_DEPLOY_BRANCH", "main"),
        ssh_user=env.get("AKSYNC_SSH_USER", ""),
        ssh_options=ssh_options,
        mail=mail,
    )


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
