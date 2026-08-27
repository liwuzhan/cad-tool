# CAD CLI 项目指令

## 分层验证架构

建模验证分四层，由底向上：

| 层 | 手段 | 目的 |
|----|------|------|
| **L1** | API 速查参考 (`docs/build123d_skills.md`) | 知道有什么操作可用 |
| **L2** | Checkpoint 自动渲染 | 每个 verify() 自动生成渲染图，多模态模型直接看 |
| **L3** | Checkpoint 数值断言 | 体积、实体数、边界框的精确验证（兜底） |
| **L4** | 致命陷阱文档 | 仅保留 5 个最常见的死法 |

### 核心：特征级 Checkpoint

**每个特征操作后必须添加 Checkpoint**。verify() 现在会自动渲染当前几何体为 PNG（保存到 `%TEMP%\cad_checkpoints\`），多模态模型可直接观察。

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    Cylinder(30, 10)
    Checkpoint(part, "base").expect_volume(28274, tolerance=100).expect_solids(1).verify()

    Cylinder(10, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, "hole").expect_volume_decreased().expect_solids(1).verify()

result = part.part
```

**Checkpoint 方法**:
- `.expect_volume(value, tolerance=1.0)` - 断言体积
- `.expect_volume_decreased()` / `.expect_volume_increased()` - 断言体积变化方向
- `.expect_solids(1)` - 断言单一实体（必查）
- `.expect_faces(count)` - 断言面数
- `.expect_bbox_size(x, y, z, tolerance=1.0)` - 断言边界框
- `.verify(render=True)` - 执行检查 + 自动渲染，失败抛异常
- `.verify(render=False)` - 仅数值检查，不渲染

## 建模工作流

**design.md → main.py → review → commit** 四步流程。

### Step 1: 填写 design.md

- 填写零件描述、关键尺寸表（X/Y/Z 总尺寸 + 关键特征尺寸）
- 写出建模策略（基体形状 → 特征顺序）
- 列出约束校验项

### Step 2: 编写 main.py

- 顶部 `# === 参数 ===` 区，从 design.md 复制所有数值
- **禁止 magic numbers**：所有尺寸必须是命名变量
- 每个特征后 Checkpoint（必含 expect_solids(1)）
- 基体 Checkpoint 必含 expect_bbox_size(X, Y, Z)

### Step 3: `cad review` — 视觉审查（关键步骤）

运行 `cad review` 后：
1. **读取每张渲染图**（等轴、前视、顶视、右视）
2. **用语言描述**看到的内容（强制将视觉转为语言）
3. **逐特征分析**：
   - 这个特征的物理目的是什么？
   - 从图上看到了什么？
   - 力从哪来？传到哪？能工作吗？
4. **发现问题 → 退回 Step 2 修改 → 重新 review**
5. **全部通过 → 进入 Step 4**

### Step 4: `cad commit`

仅在 review 通过后执行。

## CLI 命令

```bash
cad init <path> --name=<name>    # 创建模型包
cad run [script]                  # 执行脚本（内存，不保存）
cad commit -m "msg"               # 执行+保存工件+记录历史
cad validate                      # BRep 验证
cad inspect --prop=volume         # 查询属性（volume/area/bounds/faces/edges）
cad inspect --list-targets        # 列出拓扑元素
cad log                           # 提交历史
cad status                        # 当前状态
cad checkout <hash>               # 切换版本（加载STEP + 恢复脚本）
cad render --views=iso,top        # 渲染
cad review                        # 执行+渲染+生成审查模板
cad export --format=step --output=out.step
cad artifacts list                # 工件列表
cad artifacts clean               # 清理工件
cad branch list                   # 列出分支
cad branch create <name>          # 创建分支
cad branch switch <name>          # 切换分支
cad branch delete <name>          # 删除分支
```

## 输出格式

JSONL，关注：
- `checkpoint_passed` / `checkpoint_failed` - 验证结果（含 `image` 字段指向渲染图）
- `run_success` → `payload.metrics` - 几何指标
- `run_error` → `payload.error.hint` - 错误提示

## 建模参考

- **API 速查 + 陷阱**：`docs/build123d_skills.md`（完整 build123d 操作参考）
