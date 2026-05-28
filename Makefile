# Akshare Makefile
# 使用方法:
#   make version bump       - 更新小版本
#   make version v1.17.26.1 - 设置版本号
#   make show-version       - 显示当前版本

.PHONY: help version show-version deploy sync-check sync-merge sync-rewrite sync-validate sync-publish sync-deploy sync-run

# 默认目标
help:
	@echo "Available targets:"
	@echo "  deploy major      - 更新版本 + Build Image + 发布服务器。发布主版本 (vX.0.0.0)"
	@echo "  deploy minor      - 更新版本 + Build Image + 发布服务器。发布次版本 (vX.Y.0.0)"
	@echo "  deploy patch      - 更新版本 + Build Image + 发布服务器。发布补丁版本 (vX.Y.Z.0)"
	@echo "  deploy bump       - 更新版本 + Build Image + 发布服务器。发布构建版本 (vX.Y.Z.W)"
	@echo "  deploy vX.Y.Z.W   - 更新版本 + Build Image + 发布服务器。设置指定版本"
	@echo "  version major      - 发布主版本 (vX.0.0.0)"
	@echo "  version minor      - 发布次版本 (vX.Y.0.0)"
	@echo "  version patch      - 发布补丁版本 (vX.Y.Z.0)"
	@echo "  version bump       - 发布构建版本 (vX.Y.Z.W)"
	@echo "  version vX.Y.Z.W   - 设置指定版本"
	@echo "  show-version       - 显示当前部署版本"
	@echo "  sync-check         - 检查上游仓库是否有新版本"
	@echo "  sync-merge TAG=... - 合并指定上游 tag"
	@echo "  sync-rewrite       - 将包内绝对导入改为相对导入"
	@echo "  sync-validate      - 校验同步结果"
	@echo "  sync-publish MSG=... [TAG=...] - 提交并推送代码"
	@echo "  sync-deploy        - 通过 SSH 更新部署机器代码"
	@echo "  sync-run           - 执行完整同步流程，可配合 DRY_RUN=1 预览"

# 统一版本管理命令
version:
	@$(eval ARGS := $(filter-out $@,$(MAKECMDGOALS)))
	@if [ -z "$(ARGS)" ]; then \
		echo -e "$(BLUE)版本管理命令$(NC)"; \
		echo -e "$(YELLOW)使用方法:$(NC)"; \
		echo "  make version major           升级主版本 (v1.2.3.4 -> v2.0.0.0)"; \
		echo "  make version minor           升级次版本 (v1.2.3.4 -> v1.3.0.0)"; \
		echo "  make version patch           升级补丁版本 (v1.2.3.4 -> v1.2.4.0)"; \
		echo "  make version bump       升级构建版本 (v1.2.3.4 -> v1.2.3.5)"; \
		echo "  make version set v2.1.0.3    设置指定版本"; \
		echo "  make version v2.1.0.3        设置指定版本（简写）"; \
		echo ""; \
		echo -e "$(YELLOW)示例:$(NC)"; \
		echo "  make version patch           # 升级补丁版本"; \
		echo "  make version v1.0.0.0        # 设置为v1.0.0.0"; \
		echo "  make version bump       # 升级构建版本"; \
	else \
		chmod +x scripts/version.sh; \
		if echo "$(ARGS)" | grep -q "^v[0-9]"; then \
			./scripts/version.sh set $(ARGS); \
		elif [ "$(ARGS)" = "set" ]; then \
			echo -e "$(RED)❌ 错误: 请提供版本号，例如: make version set v1.2.3.4$(NC)"; \
		elif [ "$(ARGS)" = "bump" ]; then \
			./scripts/version.sh build; \
		else \
			./scripts/version.sh $(ARGS); \
		fi; \
	fi

# 防止make将参数当作目标
major minor patch set bump:
	@:

# 防止版本号被当作目标处理
v%:
	@:

# 显示版本
show-version:
	@chmod +x scripts/get-version.sh
	@./scripts/get-version.sh

sync-check:
	@python3 -m tools.ak_sync.cli check-upstream

sync-merge:
	@if [ -z "$(TAG)" ]; then \
		echo "请通过 TAG=v1.18.64 指定上游 tag"; \
		exit 1; \
	fi
	@python3 -m tools.ak_sync.cli merge-upstream --tag $(TAG)

sync-rewrite:
	@python3 -m tools.ak_sync.cli rewrite-imports

sync-validate:
	@python3 -m tools.ak_sync.cli validate

sync-publish:
	@if [ -z "$(MSG)" ]; then \
		echo "请通过 MSG='...' 指定提交信息"; \
		exit 1; \
	fi
	@python3 -m tools.ak_sync.cli publish --message "$(MSG)" $(if $(TAG),--tag $(TAG),)

sync-deploy:
	@python3 -m tools.ak_sync.cli deploy

sync-run:
	@python3 -m tools.ak_sync.cli run-all $(if $(UPSTREAM_TAG),--tag $(UPSTREAM_TAG),) $(if $(FORCE),--force,) $(if $(DRY_RUN),--dry-run,) $(if $(PUBLISH),--publish,) $(if $(PUBLISH_TAG),--publish-tag $(PUBLISH_TAG),) $(if $(MSG),--commit-message "$(MSG)",) $(if $(DEPLOY),--deploy,)

# 完整部署流程（版本管理 + 远程构建 + 远程重启）
deploy:
	@$(eval ARGS := $(filter-out $@,$(MAKECMDGOALS)))
	@if [ -z "$(ARGS)" ]; then \
		printf "$(BLUE)完整部署流程命令$(NC)\n"; \
		printf "$(YELLOW)使用方法:$(NC)\n"; \
		echo "  make deploy major            主版本升级并部署"; \
		echo "  make deploy minor            次版本升级并部署"; \
		echo "  make deploy patch            补丁版本升级并部署"; \
		echo "  make deploy bump             构建版本升级并部署"; \
		echo "  make deploy vX.Y.Z.W         指定版本并部署"; \
		echo ""; \
		printf "$(YELLOW)部署流程:$(NC)\n"; \
		echo "  1. 更新版本号并推送到代码仓库"; \
		echo "  2. 通过 ansible 远程构建镜像"; \
		echo "  3. 通过 ansible 远程重启服务"; \
		echo ""; \
		printf "$(YELLOW)示例:$(NC)\n"; \
		echo "  make deploy bump             # 构建版本+1并部署"; \
		echo "  make deploy v1.2.3.4         # 设置为v1.2.3.4并部署"; \
		echo "  make deploy patch            # 补丁版本升级并部署"; \
	else \
		printf "$(BLUE)🚀 开始完整部署流程...$(NC)\n"; \
		printf "$(YELLOW)📋 部署参数: $(ARGS)$(NC)\n"; \
		echo ""; \
		printf "$(YELLOW)🏷️ 步骤 1/2: 更新版本号...$(NC)\n"; \
		if echo "$(ARGS)" | grep -q "^v[0-9]"; then \
			make version $(ARGS); \
		elif [ "$(ARGS)" = "bump" ]; then \
			make version bump; \
		else \
			make version $(ARGS); \
		fi; \
		if [ $$? -ne 0 ]; then \
			printf "$(RED)❌ 版本更新失败，部署终止$(NC)\n"; \
			exit 1; \
		fi; \
		echo ""; \
		printf "$(YELLOW)🏗️ 步骤 2/2: 发布到服务器...$(NC)\n"; \
		if [ -f "ansible-playbooks/akshare-sync" ]; then \
			ansible-playbook ansible-playbooks/akshare-sync; \
		else \
			printf "$(RED)❌ ansible-playbooks/akshare-sync 文件不存在$(NC)\n"; \
			exit 1; \
		fi; \
		if [ $$? -ne 0 ]; then \
			printf "$(RED)❌ 发布到服务器失败，部署终止$(NC)\n"; \
			exit 1; \
		fi; \
		echo ""; \
		printf "$(GREEN)✅ 完整部署流程执行成功！$(NC)\n"; \
		printf "$(BLUE)📊 当前部署版本:$(NC)\n"; \
		make show-version; \
	fi
