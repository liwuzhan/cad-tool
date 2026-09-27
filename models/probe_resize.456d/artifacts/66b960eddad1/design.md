# shaft_support - 装配设计文档

## 装配目标

一根由单个深沟球轴承支撑的轴，**用来演示 P2 的接口图判定**：装配关系在
`manifest.json` 与 `ports.py` 里声明，`cad mates` 在**不生成任何几何**的前提下判定
它们是否配套。

本包的重点不是这根轴能不能用，而是**检查发生的时机**。编译器先做 IR 类型检查、再生成
代码；如果判定必须先建出几何，那这道检查就只能发生在它本该守住的那一步之后。

## 坐标与接口

- 世界坐标：X 长、Y 宽、Z 高；轴沿 +Z。
- 标准件按 cadparts 命名接口定位，不从 STEP 或图片猜接口。
- 轴承装在轴颈接口 `shaft.seat_support_a` 的 frame 原点上（`main.py` 里用
  `Pos(*seat["frame"]["origin_mm"])`），坐标来自声明而非反推。

## 组件表

| 实例 | 来源 | 数量 | 接口/位姿 | 说明 |
|---|---|---:|---|---|
| `shaft` | 非标（本包 `ports.py` 声明） | 1 | `seat_support_a`（`cylindrical_surface` ⌀20×14） | 轴颈尺寸由下方轴承推导 |
| `bearing_a` | cadparts `bearing.deep_groove` | 1 | `shaft_bore`（`cylindrical_bore` ⌀20） | 型号 `6204`，见 `deps` |

## 声明在哪

| 内容 | 文件 | 为什么在这 |
|---|---|---|
| 依赖与配对关系 | `manifest.json` 的 `deps` / `mates` | 纯 JSON，**读取不需要执行任何脚本** |
| 自建件的接口 | `ports.py` 的 `PORTS` | 契约与实现分家，检查才能先于几何 |
| 几何实现 | `src/main.py` | 从 `ports.py` 读契约，不重新声明尺寸 |

## 装配校验

`cad mates`（**不建几何，可先于建模运行**）：

```
cad mates
```

三条实测结论：

| 场景 | 判决 |
|---|---|
| 轴按 6204 定尺寸，装 6204 轴承 | `PASS` |
| `manifest` 换成 6205，`ports.py` 仍按 6204 | `WARN` — 公称尺寸不符，可能选错件 |
| `ports.py` 按 6205，装 6204 轴承 | `FAIL` — 轴径 ⌀25 > 孔径 ⌀20，装不进去 |

第二行是**漂移检测**：两处声明本应一致而不再一致时会被抓住。

其他校验：

- [x] `result` 为保留独立实体的 Compound（`expect_solids(2)` 通过）
- [ ] `expect_bbox_size` 未加——本包是接口判定的演示，不追总体包络
- [x] `cad run` / `cad mates` 均通过

## 明确不做

- **跨包依赖（`pkg:`）未实现**：引用其它 `.456d` 包的接口解析尚未落地，`cad mates`
  遇到 `pkg:` 会跳过并给出 warning，不会假装验过。
- 配合公差与 ISO 286 配合带不在判定范围；`WARN` 那一档存在的理由正是这里说不清——
  孔径大于轴径既可能是间隙配合，也可能是选错件，仅凭声明无法判定，所以报出来而不是
  默认接受。
- 强度、寿命、热、振动、装配可达性均未验，`cad mates` 的 `boundary` 字段会明说。
