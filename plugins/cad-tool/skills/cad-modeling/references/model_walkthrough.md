# 可跳过的建模引导

这是一份可选的新手引导，不是固定工作流。熟悉 `.456d`、build123d 和现有工具的模型可以
完全跳过；遇到陌生任务时，也只需读取相关示例。

仓库内有两个完整样本：

- [`wheel_hub.456d`](https://github.com/liwuzhan/cad-tool/tree/main/wheel_hub.456d)：参数较多的单零件，展示从截面和阵列逐步形成轮毂；
- [`bearing_block_assembly.456d`](https://github.com/liwuzhan/cad-tool/tree/main/bearing_block_assembly.456d)：小型装配体，展示标准件代理、
  非标件和显式位姿如何共存。

它们展示一种可行路径，不规定模型必须使用哪些工具、调用顺序或检查数量。

## 读一个 `.456d` 包

最值得先看的通常只有三个位置：

```text
design.md       设计意图、命名尺寸和坐标语义
src/main.py     可编辑的参数化几何；最终对象赋给 result
manifest.json   包类型、当前分支和已保存版本
```

`artifacts/<commit>/` 是某个已保存版本的 STEP、指标和缩略图，`vcs/commits.jsonl` 说明版本
之间发生了什么。`runlog/` 只是运行观察结果，可以不存在，也不应当成为源码的一部分。

模型可以直接改代码，也可以先写 `design.md`；可以先渲染，也可以先查询尺寸；可以在任何
值得保存的时刻 commit。工具提供能力，不要求走完一条流水线。

## 示例一：五辐轮毂

### 目标如何变成参数

[`wheel_hub.456d/design.md`](https://github.com/liwuzhan/cad-tool/blob/main/wheel_hub.456d/design.md) 先把“18 英寸、深盘、五辐”拆成
外半径、筒深、辐板厚度、窗口角度、中心孔和螺栓分布圆等命名参数。这样修改外观时，模型
主要调整参数和少量构造关系，而不必重新理解整个实体。

### 代码如何形成几何

[`wheel_hub.456d/src/main.py`](https://github.com/liwuzhan/cad-tool/blob/main/wheel_hub.456d/src/main.py) 的主要结构是：

1. 挤出环形截面形成轮辋筒体；
2. 在圆盘上用 `PolarLocations` 一次减去五个窗口，形成五辐辐板；
3. 添加中心凸台，再减去中心孔和五个螺栓孔；
4. 用圆角和倒角完成可见边缘。

这里真正可复用的是“参数化分解”和“阵列一次表达重复特征”。样本创建时使用了较密集的
Checkpoint，这是旧模型工作方式留下的记录，不是当前任务必须照搬的检查密度。模型可以完全
不用 Checkpoint，也可以只在某个难以观察的布尔操作后临时添加。

### 版本记录提供了什么

第一次保存后发现螺栓孔沉头只选中一条边；第二个版本把 `sort_by(...)[-1]` 改成筛选全部
五条目标边。这个历史说明版本工具的价值是保留可回看的设计状态，而不是要求模型达到某种
固定的“通过流程”。缩略图适合快速看整体，源码和几何查询适合确认具体原因。

## 示例二：6204 轴承座装配体

### 先复用采购件

装配目标包含一个标准 6204 轴承。模型可以先用目录查询：

```bash
cadparts search "20mm bearing"
cadparts describe 6204
```

目录给出轴承外径 47、内径 20、宽度 14，以及可选的 2RS 密封属性。于是模型无需在当前
上下文重新建立滚珠、保持架或密封圈，只保留采购选择和装配所需的包络、轴线、安装面。

### 把注意力留给非标件

[`bearing_block_assembly.456d/src/main.py`](https://github.com/liwuzhan/cad-tool/blob/main/bearing_block_assembly.456d/src/main.py) 建立：

- 一个带 47 mm 安装孔的非标轴承座；
- 一个由 `cadparts.instantiate("6204")` 返回的采购件代理；
- 一根直径 20 mm 的非标轴。

每个组件使用稳定 label 和显式 `Pos`，最后作为 `Compound(children=...)` 的独立子项输出。
这已经足够生成分色预览、STEP 和总体包络，也让模型能把主要上下文用于轴承座等真正需要设计
的部分。

### 观察与保存

普通正、右、俯和轴测图通常足以确认三件物体的方向和大致位置。模型如果已经发现某处难以
定位，可以按需使用尺寸或剖切 Review，也可以自行写临时几何查询代码。确定一个状态值得保留
时再 commit；是否继续检查由模型依据任务决定。

## 从引导离开

看懂 `result`、模型包和工具目录后，就不必继续模仿示例。新任务可以使用不同的代码结构、
观察方法和版本粒度；只要输出满足用户需要，示例不是约束。
