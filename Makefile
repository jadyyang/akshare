# Akshare Makefile
# 使用方法:
#   make version bump       - 更新小版本
#   make version v1.17.26.1 - 设置版本号
#   make show-version       - 显示当前版本

.PHONY: help version show-version

# 默认目标
help:
	@echo "Available targets:"
	@echo "  version major      - 发布主版本 (vX.0.0.0)"
	@echo "  version minor      - 发布次版本 (vX.Y.0.0)"
	@echo "  version patch      - 发布补丁版本 (vX.Y.Z.0)"
	@echo "  version bump       - 发布构建版本 (vX.Y.Z.W)"
	@echo "  version vX.Y.Z.W   - 设置指定版本"
	@echo "  show-version       - 显示当前部署版本"

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
