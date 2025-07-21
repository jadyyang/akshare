# 日常从 akshare merge 流程

## 备份当前内容

```bash
# 切换到备份分支
git checkout backup

# 从 main merge
git merge main

# 推送到远端
git push origin backup

# 切换回 main 
git checkout main
```

## 合并 akshare 最新 tag

```bash
# 拉取官方所有分支和tags
git fetch upstream --tags

# 合并官方tag到当前分支
git merge release-v1.17.25 -m "Merge upstream tag v1.17.25"

# 如果遇到冲突，查看冲突文件：
git status
```