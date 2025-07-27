#!/bin/bash

# 通用版本获取脚本
# 从Git release分支获取最新版本号

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取最新版本号
get_latest_version() {
    local current_branch=""
    local switch_back=false
    
    # 检查是否在git仓库中
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo -e "${RED}❌ 错误: 当前目录不是Git仓库${NC}" >&2
        return 1
    fi
    
    # 保存当前分支
    current_branch=$(git branch --show-current 2>/dev/null || echo "")
    
    # 获取远程最新标签（如果有的话）
    echo -e "${YELLOW}🔍 获取远程最新版本...${NC}" >&2
    git fetch --tags > /dev/null 2>&1 || true
    
    # 获取所有的版本标签，按版本号排序
    latest_tag=$(git tag -l "v*.*.*.*" | sort -V | tail -n 1)
    
    if [ -z "$latest_tag" ]; then
        latest_tag="v0.0.0.0"
        echo -e "${YELLOW}⚠️ 未找到版本标签，使用默认版本: ${latest_tag}${NC}" >&2
    else
        echo -e "${GREEN}✅ 最新版本: ${latest_tag}${NC}" >&2
    fi
    
    # 输出版本号（去掉v前缀）
    echo "${latest_tag#v}"
}

# 获取完整版本号（包含v前缀）
get_latest_version_tag() {
    local version_num
    version_num=$(get_latest_version)
    echo "v${version_num}"
}

# 主函数
main() {
    case "${1:-}" in
        "--tag"|"-t")
            get_latest_version_tag
            ;;
        "--num"|"-n")
            get_latest_version
            ;;
        "--help"|"-h")
            echo -e "${BLUE}版本获取脚本${NC}"
            echo -e "${YELLOW}使用方法:${NC}"
            echo "  $0              获取版本号 (不含v前缀)"
            echo "  $0 --tag        获取完整标签 (含v前缀)"
            echo "  $0 --num        获取版本号 (不含v前缀)"
            echo "  $0 --help       显示此帮助信息"
            ;;
        "")
            get_latest_version
            ;;
        *)
            echo -e "${RED}❌ 未知参数: $1${NC}" >&2
            echo "使用 $0 --help 查看帮助" >&2
            return 1
            ;;
    esac
}

# 如果脚本被直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
