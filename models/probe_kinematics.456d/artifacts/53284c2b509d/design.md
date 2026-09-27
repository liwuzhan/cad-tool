# MGN12 直线导轨 + 滑块 + 端部挡块 —— 行程内干涉判定

## 装配目标

用 `cadparts` 的 `linear.guide.rail` 族真实数据搭一个最小可判定场景，回答一个唯一的工程问题：

> 滑块在整个**可用行程**内，会不会撞到固定在导轨一端的挡块？

- 会 / 不会，撞在哪个位置，还剩多少余量 —— 全部给数字。
- 场景故意做到最小：一根导轨、一个滑块、一块挡块。导轨铺在 Z=0 基准面上。

## 数据来源（不是假设）

全部尺寸来自标准件库，不手填：

```bash
cadparts derive linear.guide.rail --params '{"series":"MGN","size":"12","rail_length":300}'
```

| 库字段 | 值 | 用途 |
|---|---:|---|
| `rail_length` | 300.0 | 导轨长度（选择器，可裁切） |
| `rail_width` / `rail_height` | 12.0 / 8.0 | 导轨截面 |
| `block_length` | 45.4 | **滑块长度** —— 行程的定义量 |
| `block_width` | 27.0 | 滑块宽度 |
| `assembly_height` | 13.0 | 滑块顶面高度 |
| `block_position` | 150.0 | 滑块中心距导轨起点（默认居中） |
| `rail_mounting_pitch` / `rail_hole_count` | 25.0 / 12 | 导轨安装孔 |
| `keepout_envelopes[carriage_sweep]` | box 300×27×13 @ (150, 0, 6.5) | **库自带的滑块扫掠包络** |

库接口 `linear.guide.rail / motion_axis` 对行程的定义（`cadparts/interfaces.py`）：

```
travel = rail_length - block_length = 300.0 - 45.4 = 254.6 mm
```

对应滑块中心的合法区间（`linear_guide_dimensions` 的硬校验
`block_position - block_length/2 >= 0` 且 `+ block_length/2 <= rail_length`）：

```
center_min = block_length / 2      =  22.700 mm
center_max = rail_length - L/2     = 277.300 mm
center_max - center_min            = 254.600 mm  ==  travel
```

## 坐标语义

- 世界坐标：X = 运动轴（+X），Y = 宽度，Z = 高度；**导轨底面 Z=0，导轨起点 X=0，终点 X=300**。
- 滑块随 `block_position` 沿 X 平移；滑块实体占 X ∈ [c − 22.7, c + 22.7]，Z ∈ [8, 13]。
- 挡块固定在 **-X 端**（导轨起点侧）。`STOP_FACE_X = s` 定义为挡块朝向滑块的那个面，
  `s = 0` 即挡块面与导轨起点端面共面。
- 滑块在装配体里**摆在行程 -X 极限位**（c = 22.7）—— 这正是干涉判定的决定性位姿。

## 组件表

| label | 来源 | 位姿 | 说明 |
|---|---|---|---|
| `rail_mgn12_l300` | cadparts `linear_guide('MGN','12',rail_length=300)` | 原样，X∈[0,300] | 导轨，Ø3.5 安装孔 ×12 |
| `carriage_mgn12_xmin` | 同上 Compound 的滑块子实体 | 平移到 c = 22.7 | 滑块，行程 -X 极限位 |
| `end_stop` | 非标 | Pos(s−T, −W/2, 0) | 挡块，X∈[s−8, s]，Y=±16.5，Z∈[0,18] |

挡块尺寸：厚 `STOP_THICKNESS = 8`，高 `STOP_HEIGHT = 18`（> assembly_height 13，能挡住滑块），
宽 `block_width + 2×3 = 33`（> 滑块 27，横向完全遮住滑块）。

## 干涉判定的方法（量，不算）

装配体本身不构成证据，证据是脚本里跑的刚性扫掠探测：

1. **扫掠步进**：把滑块子实体沿 X 从 c=22.7 逐点平移到 c=277.3，步长约 2.12 mm（121 个位姿）。
2. 每个位姿测两个量（都是布尔运算结果，不是公式）：
   - `distance_to(stop)` —— 最近距离；
   - `(carriage & stop).volume` —— **干涉体积**（共面接触时为 0，过盈时为正值）。
3. 记录整个行程上的 **min gap** 与 **max interference volume**。
4. 对 `STOP_FACE_X = s` 做参数扫描（s = −2 … 10），用二分法测出**首次接触的滑块中心 c\***。

## 约束校验项

- [ ] `expect_solids(3)`：导轨 / 滑块 / 挡块 三个独立实体
- [ ] `expect_bbox_size(308, 33, 18)`：总体包络 X∈[−8,300]，Y=±16.5，Z=0..18
- [ ] 导轨体积 27876.37 mm³、滑块体积 6129.00 mm³（= 45.4×27×5）、挡块 4752 mm³
- [ ] 扫掠 min gap 与 max interference 有明确数字
- [ ] `cad validate` / `cad review` 通过
