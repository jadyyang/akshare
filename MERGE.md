# 日常从 akshare merge 流程

<!-- ## 备份当前内容

```bash
# 切换到备份分支
git checkout backup

# 从 main merge
git merge main

# 推送到远端
git push origin backup

# 切换回 main 
git checkout main
``` -->

## 获取 akshare 更新并进行比较

```bash
# 拉取官方所有分支和tags
git fetch upstream --tags

# 查看本地与目标tag的完整差异
git diff main release-v1.17.25 --color-words

# 查看文件变更概览（更简洁）
git diff main release-v1.17.25 --name-status
```

## 合并 akshare 最新 tag

```bash
# 合并官方tag到当前分支（使用no-ff保留合并记录）
git merge release-v1.17.25 --no-ff -m "Merge upstream tag v1.17.25"

# 如果遇到冲突，查看冲突文件：
git status
```

## 打 Tag 并推送到远端

```bash
# 给当前状态打tag（格式建议：my-version-日期）
git tag my-release-v1.17.25.2

# 推送tag到你的仓库
git push origin my-release-v1.17.25.2

# 推送主分支变更
git push origin main

# 推送所有本地tags
git push --tags
```

## 异常处理

### 快速回滚方案

如果合并后出现问题，可通过以下方式回退：

**方法1**

```bash
# 强制回退主分支
git checkout main
git reset --hard my-release-v1.17.25.2
git push -f origin main
```

**方法2**

```bash
# 基于标签创建还原分支
git checkout -b restored-version my-release-v1.17.25.2

# 推送到远程
git push -u origin restored-version

# 然后将此分支设为新的main
git checkout main
git reset --hard restored-version
git push -f origin main
```
