#!/bin/bash

# 通用版本发布脚本
# 支持语义化版本管理: vFirst.Second.Third.Fourth
# 使用方法:
#   ./version.sh major      # 升级主版本 v1.2.3.4 -> v2.0.0.0
#   ./version.sh minor      # 升级次版本 v1.2.3.4 -> v1.3.0.0
#   ./version.sh patch      # 升级补丁版本 v1.2.3.4 -> v1.2.4.0
#   ./version.sh build      # 升级构建版本 v1.2.3.4 -> v1.2.3.5
#   ./version.sh set v2.1.0.3  # 设置指定版本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认分支配置
MAIN_BRANCH="main"
RELEASE_BRANCH="release"

# 帮助信息
show_help() {
    echo -e "${BLUE}通用版本发布脚本${NC}"
    echo -e "${YELLOW}使用方法:${NC}"
    echo "  $0 major           升级主版本 (v1.2.3.4 -> v2.0.0.0)"
    echo "  $0 minor           升级次版本 (v1.2.3.4 -> v1.3.0.0)"
    echo "  $0 patch           升级补丁版本 (v1.2.3.4 -> v1.2.4.0)"
    echo "  $0 build           升级构建版本 (v1.2.3.4 -> v1.2.3.5)"
    echo "  $0 set v2.1.0.3    设置指定版本"
    echo "  $0 --help          显示此帮助信息"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo "  $0 patch    # 从 v1.2.3.4 升级到 v1.2.4.0"
    echo "  $0 set v2.0.0.0  # 直接设置为 v2.0.0.0"
}

# 检查git状态
check_git_status() {
    echo -e "${YELLOW}🔍 检查Git状态...${NC}"
    
    # 检查是否在git仓库中
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo -e "${RED}❌ 错误: 当前目录不是Git仓库${NC}"
        exit 1
    fi
    
    # 检查工作区是否干净
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${RED}❌ 错误: 工作区有未提交的更改${NC}"
        echo -e "${YELLOW}请先提交或储藏所有更改${NC}"
        git status --short
        exit 1
    fi
    
    echo -e "${GREEN}✅ Git状态检查通过${NC}"
}

# 获取当前最新版本
get_latest_version() {
    # 获取所有的版本标签，按版本号排序
    latest_tag=$(git tag -l "v*.*.*.*" | sort -V | tail -n 1)
    
    if [ -z "$latest_tag" ]; then
        echo "v0.0.0.0"
    else
        echo "$latest_tag"
    fi
}

# 解析版本号
parse_version() {
    version="$1"
    # 移除v前缀
    version_num=${version#v}
    
    # 分割版本号
    IFS='.' read -r major minor patch build <<< "$version_num"
    
    # 设置默认值
    major=${major:-0}
    minor=${minor:-0}
    patch=${patch:-0}
    build=${build:-0}
    
    echo "$major $minor $patch $build"
}

# 计算新版本
calculate_new_version() {
    bump_type="$1"
    current_version="$2"
    custom_version="$3"
    
    if [ "$bump_type" = "set" ]; then
        # 验证自定义版本格式
        if [[ ! "$custom_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo -e "${RED}❌ 错误: 版本号格式不正确，应为 vX.Y.Z.W${NC}"
            exit 1
        fi
        echo "$custom_version"
        return
    fi
    
    # 解析当前版本
    read -r major minor patch build <<< "$(parse_version "$current_version")"
    
    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            build=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            build=0
            ;;
        patch)
            patch=$((patch + 1))
            build=0
            ;;
        build)
            build=$((build + 1))
            ;;
        *)
            echo -e "${RED}❌ 错误: 不支持的版本类型 '$bump_type'${NC}"
            show_help
            exit 1
            ;;
    esac
    
    echo "v${major}.${minor}.${patch}.${build}"
}

# 创建发布分支
setup_release_branch() {
    echo -e "${YELLOW}🌿 设置发布分支...${NC}"
    
    # 确保在main分支
    current_branch=$(git branch --show-current)
    if [ "$current_branch" != "$MAIN_BRANCH" ]; then
        echo -e "${YELLOW}切换到${MAIN_BRANCH}分支...${NC}"
        git checkout "$MAIN_BRANCH"
    fi
    
    # 拉取最新代码
    echo -e "${YELLOW}拉取最新代码...${NC}"
    git pull origin "$MAIN_BRANCH"
    
    # 检查release分支是否存在
    if git show-ref --verify --quiet refs/heads/"$RELEASE_BRANCH"; then
        echo -e "${YELLOW}切换到${RELEASE_BRANCH}分支...${NC}"
        git checkout "$RELEASE_BRANCH"
        echo -e "${YELLOW}合并${MAIN_BRANCH}分支到${RELEASE_BRANCH}...${NC}"
        git merge "$MAIN_BRANCH" --no-ff -m "Merge $MAIN_BRANCH for release"
    else
        echo -e "${YELLOW}创建${RELEASE_BRANCH}分支...${NC}"
        git checkout -b "$RELEASE_BRANCH"
    fi
}

# 创建标签并推送
create_and_push_tag() {
    new_version="$1"
    
    echo -e "${YELLOW}🏷️ 创建版本标签 $new_version...${NC}"
    
    # 创建标签
    git tag -a "$new_version" -m "Release $new_version"
    
    # 推送分支和标签
    echo -e "${YELLOW}📤 推送到远程仓库...${NC}"
    git push origin "$RELEASE_BRANCH"
    git push origin "$new_version"
    
    echo -e "${GREEN}✅ 标签 $new_version 已创建并推送${NC}"
}

# 主函数
main() {
    if [ $# -eq 0 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_help
        exit 0
    fi
    
    bump_type="$1"
    custom_version="$2"
    
    echo -e "${BLUE}🚀 开始版本发布流程...${NC}"
    echo "=========================="
    
    # 检查Git状态
    check_git_status
    
    # 获取当前版本
    current_version=$(get_latest_version)
    echo -e "${BLUE}📊 当前版本: ${current_version}${NC}"
    
    # 计算新版本
    new_version=$(calculate_new_version "$bump_type" "$current_version" "$custom_version")
    echo -e "${BLUE}🎯 新版本: ${new_version}${NC}"
    
    # 确认发布
    echo ""
    echo -e "${YELLOW}确认发布版本 ${new_version}? (y/N)${NC}"
    read -r confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}⏹️ 发布已取消${NC}"
        exit 0
    fi
    
    # 设置发布分支
    setup_release_branch
    
    # 创建并推送标签
    create_and_push_tag "$new_version"
    
    # 将 release 分支的更新合并回 main 分支
    echo -e "${YELLOW}🔄 同步更新到${MAIN_BRANCH}分支...${NC}"
    git checkout "$MAIN_BRANCH"
    git merge "$RELEASE_BRANCH" --no-ff -m "Sync release $new_version back to main"
    git push origin "$MAIN_BRANCH"
    
    echo ""
    echo -e "${GREEN}🎉 版本发布完成!${NC}"
    echo "===================="
    echo -e "${GREEN}✅ 版本: ${new_version}${NC}"
    echo -e "${GREEN}✅ 分支: ${RELEASE_BRANCH}${NC}"
    echo -e "${GREEN}✅ 标签已推送到远程仓库${NC}"
    echo ""
}

# 执行主函数
main "$@"
