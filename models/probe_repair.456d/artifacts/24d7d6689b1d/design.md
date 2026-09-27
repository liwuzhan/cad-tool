# probe_repair - 声明忠实性探针（已修复）

`fidelity_probe.456d` 的副本，用于诊断并修复「`ports.py` 声明与 `src/main.py` 几何不符」。
原包未改动，保留为回归用的「坏」样本。

## 一、诊断（实测，非读文件比对）

| 项 | 声明 | 实测 | 差 |
|---|---|---|---|
| `plate.central_bore` 直径 | ⌀10.0 | **⌀9.900000** | **−0.100 mm（−1.0%）** |
| `plate.mounting_face` 面尺寸 | 60.0 | 60.000000 | 0 |
| `plate.bolt_hole_{px,py…}` ×4 直径 | ⌀4.5 | ⌀4.500000 | 0 |
| 四孔轴线位置 | (±22, ±22) | (±22.000, ±22.000) | 0 |
| 板外形 | — | 60 × 60 × 8，`solids=1`，`is_valid=True` | — |

六项声明里**只有中心孔直径一项**不忠实。几何本身没坏（单一实体、BRep 有效），
坏的是「声明说了一个几何没建出来的尺寸」。

### 怎么确认的（五条独立证据链，都收敛到 ⌀9.900000）

1. **BRep 圆柱面解析半径** —— `BRepAdaptor_Surface(face).Cylinder().Radius()` 读所有圆柱面，
   中心孔 R=4.950000。不是镶嵌近似，是曲面的解析参数。
2. **镶嵌最小二乘** —— 只用三角网格顶点（506 个落在该柱面上的顶点）到轴线距离取中位数，
   同样得 R=4.950000。与证据 1 走的不是同一条代码路径。
3. **体积闭解** —— 用声明重建体积 = 27662.743459，实测 = 27675.246998，**差 +12.503539 mm³**；
   实测值与「中心孔 ⌀9.9」的闭解 27675.246998 **完全相等（差 0.000000）**。
4. **体积反解** —— 由实测体积反推中心孔直径 = 9.900000 mm。
5. **STEP 往返** —— 导出再回读，直径仍是 [4.5 ×4, 9.9]，序列化没吞掉这个差。

### 功能后果

`ports.py` 的 role 原文写「配 ⌀10 轴」。按声明取 ⌀10.0 名义轴时，实际直径间隙是
**−0.1 mm（过盈，装不进去）**，而不是 `main.py` 里 `FIT_CLEARANCE = 0.4` 表达的 0.4 mm。
按 `main.py` 的 `SHAFT_OD = 9.5` 配，实测间隙正好 +0.4000 mm —— 与意图一致。
也就是说：**几何是对的，漂移的是声明**（role 文本和 `diameter` 一起漂了）。

## 二、修复

方向选择：把**声明**改成忠实于几何，而不是把孔改成 ⌀10.0。
依据是 `main.py` 的尺寸来自具名参数（`SHAFT_OD + FIT_CLEARANCE`）并表达了一个功能意图
（0.4 mm 间隙），而 `ports.py` 原来那个 10.0 是孤立字面量、没有推导链、还和同一文件里的
role 文本自相矛盾；把孔改成 ⌀10.0 会静默改变配合（⌀9.5 轴配 ⌀10 孔 = 0.5 间隙），
那是改设计，不是修不一致。

改法（不只改数字，改掉「两处各自演化」这个成因）：

- 新增包根 **`params.py`** —— 接口尺寸的唯一来源（`BORE_DIAMETER = SHAFT_OD + FIT_CLEARANCE`）。
- **`src/main.py`** 与 **`ports.py`** 都从 `params.py` 取 `BORE_DIAMETER`，用显式路径
  `importlib` 加载（因为 `cad mates` 用 `spec_from_file_location` 执行 `ports.py`，
  不会把包根加进 `sys.path`）。
- `ports.py` 的 role 文本也改成从同一来源生成：`配 ⌀9.5 轴，直径间隙 0.4`，
  文本也不可能再和数字漂开。
- `src/main.py` 加 Checkpoint（几何侧自证），期望值由 `params.py` 闭解算出，
  不是硬编码字面量：`blank` / `central_bore` / `bolt_holes` 三级，全 `expect_solids(1)`。
- 新增 **`src/diagnose_ports_vs_geometry.py`** —— 「声明 vs 几何」对账器，见下。

**几何未改动**：修复前后体积都是 27675.246998，五个圆柱面直径都是 [4.5×4, 9.9]。

## 三、复验

`src/diagnose_ports_vs_geometry.py` 逐项把声明量到几何上（孔径/轴位/轴向/孔长/面尺寸/面位置），
并给出体积闭解、镶嵌最小二乘、STEP 往返、覆盖率四类旁证：

```
修复前（原包 fidelity_probe）: SUMMARY: 1/6 个声明项与几何不符 -> central_bore   （exit 1）
修复后（本包 probe_repair）  : SUMMARY: 6/6 个声明项与几何一致                  （exit 0）
```

再做**灵敏度测试**（在临时副本上单独扰动 `main.py`，确认这个检查不是只会挑那一处）：

| 扰动 | 结果 |
|---|---|
| `BOLT_HOLE_DIAMETER 4.5 → 4.6` | 检出：4 个安装孔直径差 +0.100，5/6 不符 |
| `BOLT_HOLE_PITCH 44 → 43` | 检出：4 个孔找不到轴线过声明位置的特征 + 覆盖率警告，5/6 不符 |
| `SHAFT_OD 9.5 → 9.55` | 检出：中心孔差 +0.050，1/6 不符 |
| `FIT_CLEARANCE 0.4 → 0.45` | 检出：中心孔差 +0.050，1/6 不符 |

零假设检验：原包（坏）→ exit 1，本包（修好）→ exit 0。一个在两种输入上都不报警的检查是
无价值的，这个检查不是。

## 四、这个包的问题，工具原本能不能自动发现

**现有工具：不能。**

- `cad mates` 在本包上给 `overall: NOTHING_TO_CHECK`（6 个接口、0 个被引用）。
  它比的是**声明 vs 声明**（`manifest.json` 的 deps/mates 对 `ports.py`），
  结构上就看不到「声明 vs 几何」。而且它的 `PASS` 也覆盖不到：未声明 matcher 的接口
  直接列进 `not_checked`。
- `cad inspect` / `compute_metrics` 只给 volume / area / bbox / 面边点计数 / solid 数 ——
  **没有任何按特征读取尺寸的能力**。整个 `src/cad_cli` 里搜不到一处圆柱半径读取
  （`grep 'Cylinder()|\.Radius()|BRepAdaptor_Surface'` 零命中）。
- `Checkpoint` 有 `expect_volume / expect_faces / expect_face_type_count / expect_bbox_size /
  expect_solids`，**没有** `expect_cylinder_diameter` 之类按特征断言尺寸的方法。
  体积断言能间接抓到（12.5 mm³ 的差远大于 1e-6 容差），但前提是作者自己写一个闭解期望值。
- 渲染图看不出来：0.1 mm 在 60 mm 板上是 1/600，视觉极限之下。

**结论**：这类问题今天只能靠模型自己写 OCP 代码去量。所以本包把量测脚本留了下来
（`src/diagnose_ports_vs_geometry.py`），它可以直接当回归门禁跑。
