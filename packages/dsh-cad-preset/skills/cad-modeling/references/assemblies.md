# 模型装配工作流

本文描述当前已经实现、可直接使用的最小装配协议。它服务于语言模型使用
`cad-tool` 和可选的 `cad-parts` 完成“标准件占位 + 非标件设计 + 总体装配”，不承诺
约束求解、运动仿真、受力分析或制造级标准件细节。

## 1. 工具目录

| 目的 | DSH / CAD 工场 | Codex / CLI |
|---|---|---|
| 检查环境与零件库 | `cad_env_status` | `cad.py check` |
| 查询标准件 | 当前平台 shell 中运行 `cadparts search/compare/describe` | `cad.py parts -- search/compare/describe` |
| 创建装配包 | `cad_init(kind="assembly")` | `cad init <path> --name <name> --kind assembly` |
| 执行与校验 | `cad_run`、`cad_validate`、`cad_inspect` | `cad run`、`cad validate`、`cad inspect` |
| 视觉审查 | `cad_review`、`cad_render` | `cad review`、`cad render` |
| 固化与输出 | `cad_commit`、`cad_export` | `cad commit`、`cad export` |

标准件目录采用渐进式读取：

```text
search → compare（有多个候选时）→ describe → instantiate
```

不要遍历 `cad-parts` 源码，也不要从截图、STEP 或型号记忆中猜尺寸。没有完全匹配项时，
保留最接近候选和未满足约束，不得编造型号。

## 2. 包边界

当前可靠的默认方式是一个装配体对应一个 `kind: "assembly"` 的 `.456d` 包：

- 非标件在 `src/main.py` 中参数化建模；
- 标准件通过 `cadparts.instantiate()` 生成代理几何和采购语义；
- 每个组件应用显式 `Pos/Rot`，最终用 `Compound(children=...)` 保留独立实体；
- `design.md` 保存组件表、坐标、接口、配合与采购描述。

不要在 `BuildPart` 中把装配组件融合成一个零件。跨 `.456d` 包版本 pin 和自动依赖解析
仍属于后续能力；在它们落地前，不要在 Skill 中假装这些命令已经存在。

## 3. 坐标和接口约定

- 世界坐标固定为：X 长、Y 宽、Z 高，单位 mm。
- 每个标准件 family 的本地坐标以 `cadparts describe` 的 `orientation` 为准。
- `cadparts.instance/v2.interfaces` 中的 `frame.origin_mm` 和 `frame.axis` 都是零件本地坐标。
- 对零件应用位姿时，同一个位姿也应用于接口原点和轴向；不要只移动实体后继续使用原始接口坐标。
- 每个实例必须有唯一、稳定的 `label`。左右件、重复紧固件和镜像件都要分别命名。
- 安装尺寸来自命名接口；图片只用于审查形状和方向，不作为尺寸来源。

`design.md` 至少包含：

| 实例 label | 来源 | 数量 | 接口/位姿 | 配合 | BOM/采购描述 |
|---|---|---:|---|---|---|
| `bearing_6204_2RS` | `cadparts` 6204 | 1 | `shaft_bore`, Z=3 | 轴承孔/轴 | 6204-2RS |
| `housing` | 非标 | 1 | 孔轴 +Z | 轴承座孔/外圈 | 自制 |

闭式、游隙等不改变占位几何的属性写入 `selection`；它们仍必须进入 BOM，不能因几何相同而丢失。

## 4. 装配脚本模式

```python
from build123d import *
from cad_cli.feedback import Checkpoint
from cadparts import instantiate

Checkpoint.reset()

# 非标件：把上下文用于真正需要设计的几何。
with BuildPart() as custom_builder:
    Box(90, 70, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    Cylinder(23.5, 20, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
housing = custom_builder.part
housing.label = "housing"

# 标准件：使用目录参数和采购属性，不要重新画。
bearing = instantiate(
    "6204",
    selections={"closure": "2RS", "clearance": "normal"},
)
bearing_shape = Pos(0, 0, 3) * bearing.shape
bearing_shape.label = "bearing_6204_2RS"

shaft = Pos(0, 0, -20) * Cylinder(
    10, 60, align=(Align.CENTER, Align.CENTER, Align.MIN)
)
shaft.label = "shaft"

assembly = Compound(children=[housing, bearing_shape, shaft])
assembly.label = "bearing_block_assembly"

Checkpoint(assembly, "layout") \
    .expect_solids(3) \
    .expect_bbox_size(90, 70, 60, tolerance=0.1) \
    .verify()

result = assembly
```

在脚本旁保留实例的 `bearing.spec["purchase"]` 和接口信息，用于填写 `design.md` 或 BOM；
不要从代理实体的 label 反向推断完整采购型号。

## 5. 验证顺序

1. 逐个非标件验证自身实体数和关键包络。
2. 装配检查总实体数，防止遗漏、意外融合或重复实例。
3. 检查总体 bbox 与设计空间预算。
4. 用 `cad validate` 做 BRep 校验；装配包允许多个独立实体。
5. 用 `cad inspect` 核对聚合体积、面积、包络和 `solid_count`。
6. 渲染正、右、俯、轴测图；同时查看标准件自身的接口标注 PNG。
7. 核对每个标准件的采购描述和 selection，再 commit/export。

轴与轴承孔、螺栓与通孔等合法配合可能共享或接触名义表面。当前版本尚无带豁免表的自动干涉
检查，不要把简单的两两求交体积当成最终判据。先在 `design.md` 明确配合关系，再审查非配合件
之间是否出现明显穿透。

Linux 无 DISPLAY/Wayland 时渲染器会自动使用 Matplotlib，并按 solid 分色，避免 VTK 在进入
Python 异常处理前退出。Windows 关闭显示器或远程会话导致 VTK 不稳定时，可显式设置
`CAD_RENDER_BACKEND=matplotlib`；`CAD_SKIP_RENDER=1` 仍只用于完全跳过 PNG 的自动化测试。

## 6. 当前边界

- 有：标准件搜索与实例化、命名接口、显式位姿、多实体验证、聚合指标、STEP/PNG 输出。
- 没有：约束求解器、运动副、载荷/寿命分析、自动 BOM、跨包 commit pin、自动干涉豁免。
- 代理几何只保证声明中列出的包络和接口；真实螺纹、轴承内部、齿轮制造齿面等可能省略。

发现重复性的真实缺口时，优先补 CLI/目录数据或本文件；不要把一次性补丁不断堆进 Skill 主体。
