# Branch Support 测试计划

## 概述

本文档描述 CAD CLI v2.0 分支管理功能的测试计划。测试覆盖四个 CLI 命令：
- `cad branch list`
- `cad branch create <name>`
- `cad branch switch <name>`
- `cad branch delete <name>`

## 测试环境准备

```bash
# 进入项目目录
cd "C:\Users\liwuz\Desktop\test\cad tools"

# 清理之前的测试包（如果存在）
rm -rf test_branch.456d

# 初始化新的测试包
python -m cad_cli.cli_v2 init test_branch --name="Branch Test"
cd test_branch.456d
```

## 测试用例

### TC-01: 无提交时列出分支

**前置条件**: 刚初始化的包，没有任何提交

**步骤**:
```bash
python -m cad_cli.cli_v2 branch list
```

**预期结果**:
```json
{"event": "branch_list", "payload": {"branches": [{"name": "main", "head": null, "is_current": true, "commit_count": 0}]}}
```

---

### TC-02: 无提交时创建分支（应失败）

**前置条件**: 刚初始化的包，没有任何提交

**步骤**:
```bash
python -m cad_cli.cli_v2 branch create feature-1
```

**预期结果**:
- 退出码: 1
- 事件: `branch_create_error`
- 错误类型: `NoCommits`
- 提示信息包含: "Create a commit first"

---

### TC-03: 创建首次提交

**前置条件**: 刚初始化的包

**步骤**:
```bash
# 编辑 src/main.py
echo "from build123d import *" > src/main.py
echo "result = Box(10, 10, 10)" >> src/main.py

# 提交
python -m cad_cli.cli_v2 commit -m "Initial commit"
```

**预期结果**:
- 事件: `commit_success`
- 返回 commit hash（记录为 `$HASH1`）

---

### TC-04: 有提交后列出分支

**前置条件**: 已完成 TC-03

**步骤**:
```bash
python -m cad_cli.cli_v2 branch list
```

**预期结果**:
```json
{
  "branches": [{
    "name": "main",
    "head": "$HASH1",
    "is_current": true,
    "commit_count": 1
  }]
}
```

---

### TC-05: 创建分支（从当前 HEAD）

**前置条件**: 已完成 TC-03

**步骤**:
```bash
python -m cad_cli.cli_v2 branch create feature-1
```

**预期结果**:
- 事件: `branch_create_success`
- `name`: "feature-1"
- `head`: 等于 `$HASH1`（与 main 相同）

---

### TC-06: 创建重复分支（应失败）

**前置条件**: 已完成 TC-05

**步骤**:
```bash
python -m cad_cli.cli_v2 branch create feature-1
```

**预期结果**:
- 退出码: 1
- 错误类型: `BranchExists`
- 提示信息包含: "Use 'cad branch switch'"

---

### TC-07: 列出多个分支

**前置条件**: 已完成 TC-05

**步骤**:
```bash
python -m cad_cli.cli_v2 branch list
```

**预期结果**:
- 两个分支: main 和 feature-1
- main 的 `is_current` 为 true
- feature-1 的 `is_current` 为 false
- 两者的 `head` 相同

---

### TC-08: 切换到分支

**前置条件**: 已完成 TC-05

**步骤**:
```bash
python -m cad_cli.cli_v2 branch switch feature-1
```

**预期结果**:
- 事件: `branch_switch_success`
- `name`: "feature-1"

**验证**:
```bash
python -m cad_cli.cli_v2 status
```
- `branch` 字段应为 "feature-1"

---

### TC-09: 切换到不存在的分支（应失败）

**前置条件**: 已完成 TC-05

**步骤**:
```bash
python -m cad_cli.cli_v2 branch switch nonexistent
```

**预期结果**:
- 退出码: 1
- 错误类型: `BranchNotFound`
- 提示信息包含: "cad branch create"

---

### TC-10: 在新分支上提交

**前置条件**: 已完成 TC-08（当前在 feature-1 分支）

**步骤**:
```bash
# 修改脚本
echo "from build123d import *" > src/main.py
echo "result = Box(20, 20, 20)" >> src/main.py

# 提交
python -m cad_cli.cli_v2 commit -m "Bigger box on feature-1"
```

**预期结果**:
- 事件: `commit_success`
- 返回新的 commit hash（记录为 `$HASH2`）

---

### TC-11: 验证分支头更新

**前置条件**: 已完成 TC-10

**步骤**:
```bash
python -m cad_cli.cli_v2 branch list
```

**预期结果**:
- main 分支: `head` = `$HASH1`, `commit_count` = 1
- feature-1 分支: `head` = `$HASH2`, `commit_count` = 1, `is_current` = true

---

### TC-12: 切换回 main 分支（验证脚本恢复）

**前置条件**: 已完成 TC-10

**步骤**:
```bash
python -m cad_cli.cli_v2 branch switch main
```

**预期结果**:
- 事件: `branch_switch_success`
- `head` = `$HASH1`
- `script_restored` = true

**验证 1: 检查状态**
```bash
python -m cad_cli.cli_v2 status
```
- `head` 字段应为 `$HASH1`
- `branch` 字段应为 "main"

**验证 2: 检查脚本内容已恢复**
```bash
cat src/main.py
```
- 应包含 `Box(10, 10, 10)`（不是 `Box(20, 20, 20)`）
- 脚本内容应与 main 分支的首次提交一致

---

### TC-13: 删除非当前分支

**前置条件**: 已完成 TC-12（当前在 main 分支）

**步骤**:
```bash
python -m cad_cli.cli_v2 branch delete feature-1
```

**预期结果**:
- 事件: `branch_delete_success`
- `name`: "feature-1"
- `deleted_head`: `$HASH2`

**验证**:
```bash
python -m cad_cli.cli_v2 branch list
```
- 只剩 main 分支

---

### TC-14: 删除 main 分支（应失败）

**前置条件**: 任何状态

**步骤**:
```bash
python -m cad_cli.cli_v2 branch delete main
```

**预期结果**:
- 退出码: 1
- 错误类型: `CannotDeleteMain`
- 消息: "Cannot delete 'main' branch"

---

### TC-15: 删除当前分支（无 --force，应失败）

**前置条件**: 创建并切换到新分支

**步骤**:
```bash
python -m cad_cli.cli_v2 branch create temp-branch
python -m cad_cli.cli_v2 branch switch temp-branch
python -m cad_cli.cli_v2 branch delete temp-branch
```

**预期结果**:
- 退出码: 1
- 错误类型: `CannotDeleteCurrent`
- 提示信息包含: "--force"

---

### TC-16: 强制删除当前分支

**前置条件**: 已完成 TC-15

**步骤**:
```bash
python -m cad_cli.cli_v2 branch delete temp-branch --force
```

**预期结果**:
- 事件: `branch_delete_success`

**验证**:
```bash
python -m cad_cli.cli_v2 status
```
- 自动切换回 main 分支
- `branch` 字段应为 "main"

---

### TC-17: 从指定提交创建分支

**前置条件**: 有多个提交

**步骤**:
```bash
# 确保有提交
python -m cad_cli.cli_v2 log
# 获取第一个提交的 hash，假设为 $HASH1

python -m cad_cli.cli_v2 branch create from-old --from=$HASH1
```

**预期结果**:
- 事件: `branch_create_success`
- `head` = `$HASH1`

---

### TC-18: 从不存在的提交创建分支（应失败）

**步骤**:
```bash
python -m cad_cli.cli_v2 branch create bad-branch --from=nonexistent
```

**预期结果**:
- 退出码: 1
- 错误类型: `CommitNotFound`
- 提示信息包含: "cad log"

---

### TC-19: 删除不存在的分支（应失败）

**步骤**:
```bash
python -m cad_cli.cli_v2 branch delete nonexistent
```

**预期结果**:
- 退出码: 1
- 错误类型: `BranchNotFound`

---

### TC-20: 验证脚本快照保存和恢复

**目的**: 验证 commit 时保存脚本快照，switch 时恢复脚本到工作区

**前置条件**: 清理并重新初始化测试包

**步骤**:
```bash
# 1. 初始化
cd "C:\Users\liwuz\Desktop\test\cad tools"
rm -rf test_script_restore.456d
python -m cad_cli.cli_v2 init test_script_restore --name="Script Restore Test"
cd test_script_restore.456d

# 2. 创建脚本 A 并提交到 main
echo "from build123d import *" > src/main.py
echo "result = Box(10, 10, 10)  # Script A" >> src/main.py
python -m cad_cli.cli_v2 commit -m "Script A on main"

# 3. 创建分支并切换
python -m cad_cli.cli_v2 branch create feature
python -m cad_cli.cli_v2 branch switch feature

# 4. 修改脚本为 B 并提交
echo "from build123d import *" > src/main.py
echo "result = Box(20, 20, 20)  # Script B" >> src/main.py
python -m cad_cli.cli_v2 commit -m "Script B on feature"

# 5. 验证当前脚本是 B
cat src/main.py
# 应包含: result = Box(20, 20, 20)  # Script B

# 6. 切换回 main
python -m cad_cli.cli_v2 branch switch main

# 7. 验证脚本已恢复为 A
cat src/main.py
# 应包含: result = Box(10, 10, 10)  # Script A

# 8. 切换回 feature
python -m cad_cli.cli_v2 branch switch feature

# 9. 验证脚本恢复为 B
cat src/main.py
# 应包含: result = Box(20, 20, 20)  # Script B
```

**预期结果**:
- 步骤 5: 脚本内容包含 `Box(20, 20, 20)` 和注释 `# Script B`
- 步骤 7: 脚本内容恢复为 `Box(10, 10, 10)` 和注释 `# Script A`
- 步骤 9: 脚本内容恢复为 `Box(20, 20, 20)` 和注释 `# Script B`
- 所有 switch 命令返回 `script_restored: true`

**验证 artifacts 目录**:
```bash
ls artifacts/*/script.py
```
- 每个 commit 目录下都应有 `script.py` 文件

---

### TC-21: 旧提交无脚本快照时的兼容性

**目的**: 验证切换到没有脚本快照的旧提交时不会报错

**前置条件**: 存在没有 `script.py` 的旧提交

**步骤**:
```bash
# 手动删除某个 commit 的 script.py
rm artifacts/<some_hash>/script.py

# 切换到该分支
python -m cad_cli.cli_v2 branch switch <branch_name>
```

**预期结果**:
- 命令成功执行
- `script_restored` = false
- 工作区脚本保持不变

---

## Manifest 验证

在关键步骤后，检查 `manifest.json` 确保数据一致：

```bash
cat manifest.json
```

验证点：
- `branches` 字典包含所有期望的分支
- `current_branch` 与当前分支一致
- `head` 与当前分支的头一致
- 分支切换时 `head` 正确更新

---

## 清理

测试完成后清理测试包：

```bash
cd ..
rm -rf test_branch.456d
```

---

## 测试结果摘要

| 测试用例 | 描述 | 结果 |
|---------|------|------|
| TC-01 | 无提交时列出分支 | |
| TC-02 | 无提交时创建分支 | |
| TC-03 | 创建首次提交 | |
| TC-04 | 有提交后列出分支 | |
| TC-05 | 创建分支（从当前 HEAD） | |
| TC-06 | 创建重复分支 | |
| TC-07 | 列出多个分支 | |
| TC-08 | 切换到分支 | |
| TC-09 | 切换到不存在的分支 | |
| TC-10 | 在新分支上提交 | |
| TC-11 | 验证分支头更新 | |
| TC-12 | 切换回 main 分支（脚本恢复） | |
| TC-13 | 删除非当前分支 | |
| TC-14 | 删除 main 分支 | |
| TC-15 | 删除当前分支（无 force） | |
| TC-16 | 强制删除当前分支 | |
| TC-17 | 从指定提交创建分支 | |
| TC-18 | 从不存在的提交创建分支 | |
| TC-19 | 删除不存在的分支 | |
| TC-20 | **脚本快照保存和恢复** | |
| TC-21 | **旧提交兼容性（无脚本快照）** | |

---

## 修改的文件清单

供参考，本次实现修改的文件：

### 核心功能
1. `src/cad_cli/package/manifest.py` - 添加 `update_nested()` 方法
2. `src/cad_cli/vcs/repository_v2.py` - 添加分支管理方法（list, create, switch, delete）
3. `src/cad_cli/cli_v2.py` - 添加 branch 命令组
4. `src/cad_cli/runtime/workflow.py` - 修复分支头更新

### Bug 修复: 脚本恢复
5. `src/cad_cli/package/artifact.py` - 添加脚本保存/加载方法（save_script, load_script）
6. `src/cad_cli/runtime/workflow.py` - 提交时保存脚本快照
7. `src/cad_cli/vcs/repository_v2.py` - 切换分支时恢复脚本

### 文档
8. `CLAUDE.md` - 添加分支命令文档
9. `docs/test_plan_branch.md` - 测试计划
