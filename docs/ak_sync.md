# akshare 上游同步自动化

这套工具用于自动化处理以下流程：

1. 检查 `akfamily/akshare` 是否发布新版本
2. 合并上游指定 tag 到当前仓库 `main`
3. 将 `akshare` 包内部的绝对导入改为相对导入
4. 执行基础校验
5. 提交并推送到当前仓库
6. 通过 SSH 进入部署机器执行 `git pull`
7. 发送成功或失败邮件通知

工具入口：

```bash
python3 -m tools.ak_sync.cli --help
```

也可以通过 `Makefile` 调用：

```bash
make sync-check
make sync-merge TAG=release-v1.18.64
make sync-rewrite
make sync-validate
make sync-publish MSG='sync: merge upstream release-v1.18.64' TAG=v1.18.64.0
make sync-deploy
make sync-run PUBLISH=1 DEPLOY=1 PUBLISH_TAG=v1.18.64.0 MSG='sync: merge upstream release-v1.18.64'
make sync-run DRY_RUN=1
```

另外提供了两个辅助文件：

- 环境变量模板: `scripts/ak_sync.env.example`
- 定时执行脚本: `scripts/run_ak_sync.sh`

## 环境变量

所有配置都通过环境变量控制，未设置时使用默认值。

### 上游仓库

```bash
export AKSYNC_UPSTREAM_REMOTE=upstream
export AKSYNC_UPSTREAM_REPO=https://github.com/akfamily/akshare.git
export AKSYNC_UPSTREAM_API=https://api.github.com/repos/akfamily/akshare
export AKSYNC_MAIN_BRANCH=main
```

### 状态和日志

```bash
export AKSYNC_STATE_FILE=/Users/jadyyang/code/repos/akshare/.ak-sync-state.json
export AKSYNC_LOG_ROOT=/Users/jadyyang/code/repos/akshare/.ak-sync-logs
```

状态文件用于记录最近一次处理成功的上游版本。

### 部署 SSH

```bash
export AKSYNC_DEPLOY_HOSTS=pi5,pi52,pi53,pi54,pi55,pi56,pi57
export AKSYNC_DEPLOY_PATH=/home/jadyyang/code/finance/finance/spider/airflow
export AKSYNC_DEPLOY_BRANCH=main
export AKSYNC_SSH_USER=
export AKSYNC_SSH_OPTIONS=-o BatchMode=yes,-o ConnectTimeout=10
```

说明：

- `AKSYNC_SSH_USER` 留空时，直接使用当前用户连接
- `AKSYNC_SSH_OPTIONS` 用逗号分隔多个 `ssh` 参数

### 邮件通知

Hotmail 建议使用 Office 365 SMTP：

```bash
export AKSYNC_MAIL_SMTP_HOST=smtp.office365.com
export AKSYNC_MAIL_SMTP_PORT=587
export AKSYNC_MAIL_USE_TLS=true
export AKSYNC_MAIL_USERNAME=your_hotmail_account@hotmail.com
export AKSYNC_MAIL_PASSWORD=your_password_or_app_password
export AKSYNC_MAIL_FROM=your_hotmail_account@hotmail.com
export AKSYNC_MAIL_TO=alice@example.com,bob@example.com
```

只有 `AKSYNC_MAIL_USERNAME`、`AKSYNC_MAIL_PASSWORD` 和 `AKSYNC_MAIL_TO` 都配置时，邮件通知才会启用。

## 命令说明

### 1. 检查是否有新版本

```bash
python3 -m tools.ak_sync.cli check-upstream
```

输出示例：

```json
{
  "latest_tag": "release-v1.18.64",
  "previous_tag": "v1.18.62",
  "needs_sync": true,
  "release_name": "release-v1.18.64",
  "release_url": "https://github.com/akfamily/akshare/releases/tag/release-v1.18.64",
  "source": "releases",
  "compare_url": "https://github.com/akfamily/akshare/compare/v1.18.62...release-v1.18.64"
}
```

### 2. 合并上游版本

```bash
python3 -m tools.ak_sync.cli merge-upstream --tag release-v1.18.64
```

### 3. 改写包内导入

```bash
python3 -m tools.ak_sync.cli rewrite-imports
```

当前策略：

- 自动改写 `from akshare.xxx import yyy`
- 自动改写安全场景下的 `import akshare.xxx`
- 如果遇到 `import akshare` 或复杂 alias/多导入场景，会直接报错并提示人工处理
- 只处理 `akshare/**/*.py`

### 4. 基础校验

```bash
python3 -m tools.ak_sync.cli validate
```

校验内容：

- `python3 -m compileall akshare`
- 检查包内是否残留 `from akshare.` 或 `import akshare.`

### 5. 提交和推送

```bash
python3 -m tools.ak_sync.cli publish \
  --message 'sync: merge upstream release-v1.18.64 and rewrite internal imports' \
  --tag v1.18.64.0
```

说明：

- 如果当前没有任何待提交改动，`publish` 会跳过提交和推送，并返回 JSON 说明原因
- 如果有改动，会正常执行 `git add`、`git commit`、`git push`

### 6. 部署到多台机器

```bash
python3 -m tools.ak_sync.cli deploy
```

每台机器执行的命令为：

```bash
cd /home/jadyyang/code/finance/finance/spider/airflow \
  && git fetch --all \
  && git checkout main \
  && git pull --ff-only origin main
```

### 7. 一键执行

```bash
python3 -m tools.ak_sync.cli run-all \
  --publish \
  --publish-tag v1.18.64.0 \
  --commit-message 'sync: merge upstream release-v1.18.64 and rewrite internal imports' \
  --deploy
```

如果只想预览将会执行什么，不实际修改仓库：

```bash
python3 -m tools.ak_sync.cli run-all --dry-run
```

如果要指定上游版本：

```bash
python3 -m tools.ak_sync.cli run-all --tag release-v1.18.64 --publish --deploy
```

`dry-run` 会输出：

- 将处理的上游版本
- 计划 merge 的 git 引用
- 预估需要改写 import 的文件数
- 上游 compare 链接
- 上游提交摘要
- 是否计划 publish / deploy

## 定时执行

推荐使用 `cron`。示例：每天上午 9 点检查并执行完整流程。

```cron
0 9 * * * /bin/zsh -lc 'cd /Users/jadyyang/code/repos/akshare && chmod +x scripts/run_ak_sync.sh && ./scripts/run_ak_sync.sh' >> /Users/jadyyang/code/repos/akshare/.ak-sync-cron.log 2>&1
```

建议先手工跑通后再加到 `cron`。

如果你想把环境变量和代码分开管理，可以：

1. 复制 `scripts/ak_sync.env.example` 为 `scripts/ak_sync.env`
2. 填入真实邮箱密码和通知地址
3. 直接执行 `./scripts/run_ak_sync.sh`

如果想只做预演：

```bash
AKSYNC_DRY_RUN=1 ./scripts/run_ak_sync.sh
```

## 日志

每次执行会在 `.ak-sync-logs/<timestamp>/` 下生成日志文件，用于排查问题。

成功邮件和失败邮件会尽量包含这些信息：

- 上游 release 链接
- 上游 compare 链接
- 上游提交数、文件数
- 前 10 条提交标题摘要
- import 改写统计
- 部署成功/失败主机汇总

## 当前限制

1. `rewrite-imports` 目前会自动处理 `from akshare.xxx import yyy` 和部分安全的 `import akshare.xxx`
2. 遇到 `import akshare`、单行多个导入或复杂 alias 仍会中断并要求人工处理
3. `check-upstream` 优先读取 GitHub Latest Release；如果 release 不可用，会自动回退到 tags API
4. 当前上游 release 名称形如 `release-v1.18.64`，请以 `check-upstream` 实际输出为准
5. `merge-upstream` 要求工作区干净；如果合并冲突，错误信息里会提示查看日志和执行 `git merge --abort`
