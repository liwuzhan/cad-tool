---
name: cad-modeling
description: build123d 参数化建模工作流。在 CAD 工场 preset 内完成 .456d 模型包创建、特征级 Checkpoint 验证、视觉审查与版本提交。使用前先 cad_env_status 确认环境；建模 API 细节见 docs/build123d_skills.md。
---

# CAD 建模工作流（CAD 工场）

## 工具总览

| 阶段 | 工具 | 说明 |
|------|------|------|
| 环境 | `cad_env_status` / `cad_env_bootstrap` | 检查 / 安装 venv + build123d + cad-cli |
| 包管理 | `cad_pkg_list` / `cad_init` | 发现 / 创建 `.456d` 模型包 |
| 建模 | `cad_run` | 执行 `src/main.py`（内存，不保存工件） |
| 验证 | `cad_validate` / `cad_inspect` | BRep 有效性 / 体积面积边界框面数 |
| 版本 | `cad_commit` | 执行 + 验证 + STEP/缩略图/metrics + 历史记录 |

工作区有多个 `.456d` 包时，所有工具都要用 `package` 参数明确指定。

## 标准流程

1. **design.md**：零件描述、关键尺寸表（X/Y/Z 总尺寸 + 特征尺寸）、建模策略（基体 → 特征顺序）、约束校验项。
2. **src/main.py**：
   - 顶部 `# === 参数 ===` 区，从 design.md 复制所有数值；
   - 禁止 magic numbers：所有尺寸必须是命名变量；
   - 每个特征操作后加 `Checkpoint`，必须含 `.expect_solids(1)`；
   - 基体 Checkpoint 必须含 `.expect_bbox_size(X, Y, Z)`。
3. **cad_run** 迭代：`ok=false` 时读 `error.hint`；`checkpoints` 里 `checkpoint_failed` 立即定位是哪个特征出错。
4. **cad_inspect --prop=volume/bounds** 核对关键尺寸。
5. **cad_commit -m "..."** 仅在所有 Checkpoint 通过后执行。

## Checkpoint 模板

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    Cylinder(30, 10)
    Checkpoint(part, "base") \
        .expect_volume(28274, tolerance=100) \
        .expect_solids(1) \
        .expect_bbox_size(60, 60, 10, tolerance=1) \
        .verify()

    Cylinder(10, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, "hole") \
        .expect_volume_decreased() \
        .expect_solids(1) \
        .verify()

result = part.part
```

方法：`expect_volume` / `expect_volume_decreased` / `expect_volume_increased` / `expect_solids` / `expect_faces` / `expect_bbox_size`，最后链式 `.verify()`。

## 致命陷阱（L4，仅 5 个）

1. **extrude() 默认 Mode.ADD** —— 打孔必须 `extrude(amount=..., mode=Mode.SUBTRACT)`。
2. **Loft 需要不同平面** —— `Locations` 不改变 sketch 平面；用 `Plane.XY.offset(30)`。
3. **Mode.ADD 不合并不相交实体** —— 无重叠 = 多个 solids；Checkpoint 的 `expect_solids(1)` 会立刻报错。
4. **Cylinder 居中 vs extrude 从 Z=0** —— `Cylinder(r,h)` Z: -h/2..+h/2；`extrude(amount=h)` Z: 0..h；混用会切偏。
5. **循环里手动布尔不可靠** —— 用 `PolarLocations` / `GridLocations` 一次完成。

## 常见错误码

| code | 处理 |
|------|------|
| `E-ENV` | 环境未就绪 → `cad_env_bootstrap` |
| `E-SYNTAX` | 检查 main.py 语法，看 hint 行号 |
| `E-RUNTIME` | 脚本运行期错误；Checkpoint 断言失败也在 runlog |
| `E-BREP` | 布尔/几何错误：自相交、零厚度、不相交切割 |
| `E-PATH` | 脚本/包路径越界或不存在 |

## 提交前检查清单

- [ ] 所有 `checkpoint_passed`，无 `checkpoint_failed`
- [ ] `cad_validate` ok
- [ ] `cad_inspect` 的体积/边界框与 design.md 一致
- [ ] 渲染图人工看过（当前版本用 `cad run` 后 Checkpoint 自动渲染图路径核对）
