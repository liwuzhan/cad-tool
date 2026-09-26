# 模型主导的装配审查图

`cad review` 默认生成三视图、轴测图和 `review.md`。多数简单零件和装配只需要这些图。
当模型已经看到疑点、但普通视图不足以定位时，可以额外提交
`cad.review-drawing/v1` 说明，按需生成尺寸、文字引线或剖切图。

这项能力是观察工具，不是装配求解器或质量门禁：

- 模型决定观察哪个版本、视图、坐标、尺寸和剖面；
- 工具只做严格投影、测量和绘图，不选择“关键尺寸”；
- 输出不含合格/不合格判断，也不会修改几何、源码或 commit；
- 尺寸成功生成不代表设计正确，失败也只表示该观察请求无法完成。

## 何时使用

先看普通 `front/top/right/iso`。只有在需要确认被遮挡结构、端面位置、轴向距离、
局部间隙方向或具体问题位置时，再使用审查图。不要把它添加到每个简单零件的固定流程。

## CLI

审查当前脚本输出：

```bash
cad review --views front,top,right,iso --drawing-spec review-request.json
```

审查某个不可变版本的 STEP；结果只写入 `runlog`，无需 checkout 或回滚：

```bash
cad review --commit 9ae3620050dd --views front --drawing-spec review-request.json
```

DSH 中仍使用 `cad_review`。普通调用省略 `drawing`；需要进一步定位时，将同一 JSON
对象放入 `drawing` 参数，并可用 `commit` 指定版本。

## 说明格式

所有三维坐标使用模型世界坐标，单位 mm。视图使用严格正交预设，不依赖“看起来像正面”
的自由相机。

```json
{
  "schema": "cad.review-drawing/v1",
  "title": "Bearing block diagnostic",
  "views": [
    {
      "name": "front_dimensions",
      "view": "front",
      "hidden_lines": true,
      "dimensions": [
        {
          "id": "overall_width",
          "from": [-45, 0, -20],
          "to": [45, 0, -20],
          "offset_mm": -12
        }
      ],
      "callouts": [
        {
          "id": "bearing_axis",
          "at": [0, 0, 10],
          "text": "bearing axis",
          "offset_mm": [12, 10]
        }
      ]
    },
    {
      "name": "shaft_section",
      "view": "right",
      "hidden_lines": false,
      "section": {
        "origin": [0, 0, 10],
        "normal": [1, 0, 0],
        "keep": "bottom"
      }
    }
  ]
}
```

### `views[]`

| 字段 | 含义 |
|---|---|
| `name` | 输出文件的稳定名称；同一说明内不可重复 |
| `view` | `front/back/left/right/top/bottom/iso` |
| `hidden_lines` | 是否显示灰色虚线，默认 `true` |
| `dimensions` | 模型指定的尺寸端点与标注偏移 |
| `callouts` | 模型指定的三维锚点、文字与二维引线偏移 |
| `section` | 可选剖切平面与保留侧 |

### 尺寸

`from`、`to` 是三维世界坐标。工具将其投影到当前视图，并在 JSON 中同时返回：

- `projected_distance_mm`：图面投影距离；
- `true_distance_mm`：两个三维点的空间距离。

默认图面文字使用投影距离。模型可以提供 `label` 覆盖显示文字，但原始两个距离仍会保留
在 JSON 中。若端点在该视图中重合，工具会拒绝这个观察请求，因为它无法形成可读尺寸线。

`offset_mm` 是尺寸线相对投影线的有符号偏移；正负分别位于投影线两侧。

### 标注

`at` 是三维锚点，`offset_mm` 是文字相对锚点在图面上的 `[x, y]` 偏移。标注文字用于模型
自己建立视觉锚点，不会写入 STEP。为保证无头 Linux/Windows 字体一致，优先使用简短的
ASCII 标识符；完整中文说明可以保留在 `design.md` 或说明 JSON 中。

### 剖切

`section.origin` 和 `section.normal` 定义无限平面，`keep` 选择保留法向的 `top` 或
反向的 `bottom` 一侧。它生成的是临时切除后的正投影，不会改变原模型。当前版本不自动
填充剖面线；模型可结合实体边界、隐藏线和尺寸理解内部关系。

## 输出

每个视图在模型包 `runlog/` 中产生：

```text
review_drawing_<name>.png   多模态模型直接查看
review_drawing_<name>.svg   分层矢量图：visible / hidden / dimensions
review_drawing_<name>.json  相机、剖面、尺寸读数、标注和顶层组件名称
```

STEP 中的装配体和顶层组件 label 会进入 JSON，便于模型定位组件；面和边的序号不作为
源码映射，因为布尔运算后拓扑编号并不稳定。模型需要更细的定位时，应在代码或零件库接口中
声明语义坐标，再把该坐标作为尺寸、标注或剖切输入。

## 当前边界

- 不自动标注所有尺寸，不自动选择风险点；
- 不把相交、距离或尺寸解释成报警；
- 不建立 STEP 面到 Python 行号的映射；
- 不执行装配约束求解或自动修复；
- 不保证自由文字在所有无头环境都有完整 CJK 字形；
- 只生成模型要求的证据，最终判断仍由模型完成。
