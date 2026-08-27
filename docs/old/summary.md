# CAD CLI v1.0 项目总结

## 项目概述

CAD CLI 是一个从零开始构建的 AI-Native CAD 命令行工具，基于 build123d，实现了"写码 → 执行 → 验证 → 渲染 → 导出"的完整闭环。

### 核心特性

- ✅ **脚本执行**: 执行 build123d 脚本，支持超时保护
- ✅ **几何验证**: BRep 拓扑验证，检测无效几何
- ✅ **属性探针**: 查询体积、面积、边界框等几何属性
- ✅ **拓扑索引**: 查询特定面/边/顶点的属性
- ✅ **离屏渲染**: 生成多视角 PNG 图像（pyvista）
- ✅ **模型导出**: 支持 STEP、STL 格式
- ✅ **版本控制**: Git-like 提交系统，带缩略图和度量
- ✅ **JSONL 输出**: 结构化事件流，便于 AI 解析

### 技术栈

| 组件 | 技术 |
|------|------|
| CLI 框架 | Click 8.1+ |
| CAD 引擎 | build123d 0.5.0+ |
| 几何内核 | OCP (OpenCascade) 7.7.0+ |
| 渲染引擎 | PyVista 0.43.0+ |
| 数据格式 | JSONL (JSON Lines) |
| 测试框架 | pytest 7.4+ |
| 语言 | Python 3.11+ |

---

## 架构设计

### 模块划分

```
cad_cli/
├── cli.py              # CLI 入口，命令定义
├── config.py           # 配置管理
├── constants.py        # 常量和错误码
├── models.py           # 数据模型
│
├── runtime/            # 运行时模块
│   ├── executor.py     # 脚本执行器
│   ├── validator.py    # 几何验证器
│   ├── sandbox.py      # 超时保护
│   └── error_handler.py # 错误格式化
│
├── feedback/           # 反馈系统
│   ├── inspector.py    # 几何探针
│   ├── renderer.py     # 渲染器
│   ├── exporter.py     # 导出器
│   └── camera.py       # 相机视角
│
├── vcs/                # 版本控制
│   ├── repository.py   # 仓库类
│   ├── commit.py       # 提交工具
│   └── storage.py      # 存储工具
│
└── utils/              # 工具集
    ├── jsonl.py        # JSONL 输出
    ├── geometry.py     # 几何计算
    └── logger.py       # 日志工具
```

### 数据流

```
用户脚本 (main.py)
    ↓
ScriptExecutor.execute()
    ↓
Shape 对象 + 错误信息
    ↓
├─→ GeometryValidator.validate()  → 验证结果
├─→ GeometryInspector.inspect()   → 属性查询
├─→ OffscreenRenderer.render()    → PNG 图像
├─→ ModelExporter.export()        → STEP/STL 文件
└─→ Repository.commit()           → 版本记录
    ↓
JSONL 事件流 (stdout)
```

### 核心设计决策

#### 1. 脚本执行约定

脚本必须将最终结果赋值给 `result` 变量：

```python
from build123d import *
result = Box(10, 10, 10)  # 必须命名为 result
```

**理由**:
- 简单明确，避免歧义
- 易于 AI 理解和生成
- 便于缓存和后续操作

#### 2. JSONL 输出格式

所有输出采用 JSONL（每行一个 JSON 对象）：

```json
{"event": "run_start", "ts": "2026-01-29T10:30:00", "payload": {...}}
{"event": "run_success", "ts": "2026-01-29T10:30:01", "payload": {...}}
```

**理由**:
- 易于流式解析
- AI 友好
- 便于日志分析
- 支持事件驱动架构

#### 3. 跨平台超时机制

- **Unix**: 使用 `signal.SIGALRM`
- **Windows**: 使用 `threading.Timer`

**实现** (src/cad_cli/runtime/sandbox.py:15-45):

```python
@contextmanager
def timeout(seconds: int):
    if sys.platform == 'win32':
        # Windows implementation
        timer = threading.Timer(seconds, timeout_handler)
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
    else:
        # Unix implementation
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
```

#### 4. 错误码系统

| 错误码 | 含义 | 示例 |
|--------|------|------|
| E-SYNTAX | Python 语法错误 | 缺少括号、引号 |
| E-RUNTIME | 运行时错误 | NameError, TypeError |
| E-CONSTRAINT | 约束违反 | 体积为零 |
| E-BREP | BRep 验证失败 | 无效拓扑 |
| E-RENDER | 渲染错误 | PyVista 错误 |
| E-IO | 文件 I/O 错误 | 导出失败 |

**理由**:
- 便于 AI 识别错误类型
- 支持针对性错误处理
- 提供上下文相关的修复建议

#### 5. 线性版本控制

v1.0 采用**线性提交历史**（无分支）：

```
.cad/
├── commits/
│   ├── a1b2c3d4.json    # 提交 1
│   ├── e5f6g7h8.json    # 提交 2
│   └── ...
├── thumbs/
│   ├── commit_20260129_103000.png
│   └── ...
└── config.json
```

**理由**:
- v1.0 专注核心功能
- 分支功能留给 v2.0
- 满足单人设计迭代需求

---

## 核心功能实现

### 1. 脚本执行 (run 命令)

**入口**: src/cad_cli/cli.py:25-42

**核心逻辑**: src/cad_cli/runtime/executor.py:32-98

```python
def execute(self, script_path: Path) -> tuple[Optional[Shape], Optional[ErrorInfo]]:
    """执行 build123d 脚本"""
    try:
        # 1. 读取并编译脚本
        with open(script_path, 'r') as f:
            code = compile(f.read(), str(script_path), 'exec')

        # 2. 在沙箱中执行（带超时）
        namespace = {}
        with timeout(self.timeout_seconds):
            exec(code, namespace)

        # 3. 检查 result 变量
        if 'result' not in namespace:
            return None, ErrorInfo(...)

        # 4. 验证 result 是 Shape
        shape = namespace['result']
        if not self._is_valid_shape(shape):
            return None, ErrorInfo(...)

        # 5. 缓存 shape 供后续使用
        self._save_current_shape(shape)

        return shape, None
    except Exception as e:
        return None, format_error(e, script_path)
```

**特性**:
- ✅ 语法错误检测
- ✅ 运行时错误捕获
- ✅ 超时保护（可配置）
- ✅ 结果验证
- ✅ Shape 缓存（pickle）

### 2. 几何验证 (validate 命令)

**入口**: src/cad_cli/cli.py:45-63

**核心逻辑**: src/cad_cli/runtime/validator.py:14-72

```python
def validate(self, shape: Shape) -> List[ErrorInfo]:
    """执行 BRep 验证"""
    errors = []

    # 1. 基础验证
    if not shape.is_valid:
        errors.append(ErrorInfo(..., code=ErrorCode.E_BREP))

    # 2. OCP BRepCheck 验证
    from OCP.BRepCheck import BRepCheck_Analyzer
    analyzer = BRepCheck_Analyzer(shape.wrapped)
    if not analyzer.IsValid():
        errors.append(ErrorInfo(...))

    # 3. 体积检查
    if shape.volume <= 0:
        errors.append(ErrorInfo(..., code=ErrorCode.E_CONSTRAINT))

    return errors
```

**验证项**:
- ✅ 基础有效性 (`shape.is_valid`)
- ✅ BRep 拓扑检查 (`BRepCheck_Analyzer`)
- ✅ 体积检查（避免退化几何）

### 3. 属性探针 (inspect 命令)

**入口**: src/cad_cli/cli.py:66-91

**核心逻辑**: src/cad_cli/feedback/inspector.py

#### 基础属性查询

```bash
cad inspect --prop=volume   # 体积
cad inspect --prop=area     # 表面积
cad inspect --prop=bounds   # 边界框
```

#### 拓扑计数

```bash
cad inspect --prop=faces     # 所有面的列表
cad inspect --prop=edges     # 所有边的列表
cad inspect --prop=vertices  # 所有顶点的列表
```

#### 目标索引查询

```bash
# 1. 列出所有目标
cad inspect --list-targets

# 输出示例:
{
  "faces": [
    {"index": 0, "area": 100.0, "center": [0, 0, 5]},
    {"index": 1, "area": 100.0, "center": [0, 0, -5]},
    ...
  ],
  "edges": [...],
  "vertices": [...]
}

# 2. 查询特定目标
cad inspect --target=face[0] --target-prop=center
cad inspect --target=edge[2] --target-prop=length
cad inspect --target=vertex[5] --target-prop=position
```

**实现** (src/cad_cli/feedback/inspector.py:106-151):

```python
def query_target(self, shape: Shape, target: str, prop: str) -> Any:
    """查询特定目标属性"""
    target_type, index = self._parse_target(target)  # "face[0]" -> ("face", 0)

    if target_type == "face":
        faces = list(shape.faces())
        face = faces[index]
        if prop == "center":
            return face.center().to_tuple()
        elif prop == "area":
            return face.area
    # ... 处理 edge, vertex
```

### 4. 离屏渲染 (render 命令)

**入口**: src/cad_cli/cli.py:94-120

**核心逻辑**: src/cad_cli/feedback/renderer.py:18-72

```python
def render(self, shape: Shape, view: CameraView, output_path: Path):
    """使用 pyvista 离屏渲染"""
    import pyvista as pv

    # 1. 转换为 VTK polydata
    poly_data = to_vtk_poly_data(shape)

    # 2. 创建离屏绘图器
    plotter = pv.Plotter(off_screen=True, window_size=self.resolution)

    # 3. 添加网格（显示边）
    plotter.add_mesh(poly_data, color='lightblue', show_edges=True)

    # 4. 设置相机
    plotter.camera.position = view.position
    plotter.camera.focal_point = view.focal_point
    plotter.camera.up = view.view_up
    plotter.camera.zoom(1.2)

    # 5. 截图保存
    plotter.screenshot(str(output_path))
    plotter.close()
```

**标准视角** (src/cad_cli/feedback/camera.py:11-60):

| 视角 | Position | 用途 |
|------|----------|------|
| top | (0, 0, 100) | 俯视图 |
| front | (0, -100, 0) | 正视图 |
| right | (100, 0, 0) | 右视图 |
| iso | (50, -50, 50) | 等轴测图 |

### 5. 模型导出 (export 命令)

**入口**: src/cad_cli/cli.py:123-141

**核心逻辑**: src/cad_cli/feedback/exporter.py:13-36

```python
def export(self, shape: Shape, format: str, output_path: Path):
    """导出模型"""
    if format == 'step':
        shape.export_step(str(output_path))
    elif format == 'stl':
        shape.export_stl(str(output_path))
```

**支持格式**:
- ✅ **STEP** (.step, .stp) - CAD 交换标准
- ✅ **STL** (.stl) - 3D 打印和网格处理

### 6. 版本控制 (commit/log/status)

**入口**: src/cad_cli/cli.py:144-186

**核心逻辑**: src/cad_cli/vcs/repository.py

#### commit - 创建提交

```python
def commit(self, message: str, shape: Shape) -> CommitData:
    """创建提交"""
    # 1. 计算几何度量
    metrics = compute_metrics(shape)  # volume, area, bbox, face/edge/vertex count

    # 2. 生成缩略图（iso 视图）
    thumbnail_path = self.thumbs_dir / f"commit_{timestamp}.png"
    renderer.render(shape, STANDARD_VIEWS["iso"], thumbnail_path)

    # 3. 创建提交对象
    commit_hash = hashlib.sha256(f"{timestamp}{message}".encode()).hexdigest()[:8]
    commit_data = CommitData(
        hash=commit_hash,
        message=message,
        timestamp=timestamp.isoformat(),
        script_path="main.py",
        metrics=metrics.to_dict(),
        thumbnail_path=str(thumbnail_path)
    )

    # 4. 保存为 JSON
    with open(f".cad/commits/{commit_hash}.json", 'w') as f:
        json.dump(commit_data.to_dict(), f, indent=2)

    return commit_data
```

#### log - 查看历史

```python
def log(self) -> List[CommitData]:
    """读取提交历史"""
    commits = []
    for commit_file in self.commits_dir.glob("*.json"):
        data = load_json(commit_file)
        commits.append(dict_to_commit(data))

    # 按时间倒序排列
    commits.sort(key=lambda c: c.timestamp, reverse=True)
    return commits
```

#### status - 当前状态

```python
def status(self) -> dict:
    """检查当前状态"""
    commits = self.log()
    current_commit = commits[0] if commits else None

    # 检查 main.py 是否有修改
    has_changes = False
    if current_commit and Path("main.py").exists():
        script_mtime = Path("main.py").stat().st_mtime
        commit_time = datetime.fromisoformat(current_commit.timestamp).timestamp()
        has_changes = script_mtime > commit_time

    return {
        "current_commit": current_commit.hash if current_commit else None,
        "has_changes": has_changes,
        "total_commits": len(commits)
    }
```

---

## 测试策略

### 测试覆盖

| 模块 | 测试文件 | 覆盖内容 |
|------|---------|---------|
| Runtime | test_executor.py | 脚本执行、错误处理、超时 |
|  | test_validator.py | BRep 验证 |
| Feedback | test_inspector.py | 属性查询、拓扑索引 |
|  | test_renderer.py | 渲染功能 |
|  | test_exporter.py | 导出功能 |
| VCS | test_repository.py | init/commit/log/status |
| CLI | test_integration.py | 端到端工作流 |
| Utils | test_jsonl.py | JSONL 输出 |

### Fixtures

**conftest.py** 提供以下 fixtures:

```python
@pytest.fixture
def temp_project():
    """临时项目目录"""

@pytest.fixture
def initialized_repo(temp_project):
    """已初始化的仓库"""

@pytest.fixture
def simple_box_script(temp_project):
    """有效的 Box 脚本"""

@pytest.fixture
def invalid_syntax_script(temp_project):
    """语法错误脚本"""

@pytest.fixture
def runtime_error_script(temp_project):
    """运行时错误脚本"""
```

### 运行测试

```bash
# 运行所有测试
pytest

# 带覆盖率
pytest --cov=cad_cli --cov-report=html

# 特定模块
pytest test/test_runtime/

# 详细输出
pytest -v
```

### 集成测试示例

**test/test_cli/test_integration.py:60-95**:

```python
def test_full_workflow(temp_project, cli_runner):
    """测试完整工作流"""
    # 1. Init
    result = cli_runner.invoke(cli, ['init'])
    assert result.exit_code == 0

    # 2. Create script
    script = temp_project / "main.py"
    script.write_text("from build123d import *\nresult = Box(10, 10, 10)")

    # 3. Run
    result = cli_runner.invoke(cli, ['run', str(script)])
    assert result.exit_code == 0

    # 4. Validate
    result = cli_runner.invoke(cli, ['validate'])
    assert result.exit_code == 0

    # 5. Inspect
    result = cli_runner.invoke(cli, ['inspect', '--prop=volume'])
    assert result.exit_code == 0

    # 6. Render
    result = cli_runner.invoke(cli, ['render', '--views=iso'])
    assert result.exit_code == 0

    # 7. Commit
    result = cli_runner.invoke(cli, ['commit', '-m', 'Initial design'])
    assert result.exit_code == 0

    # 8. Export
    result = cli_runner.invoke(cli, ['export', '--format=step', '--output=out.step'])
    assert result.exit_code == 0
```

---

## 使用示例

### 基础工作流

```bash
# 1. 初始化项目
mkdir my_project && cd my_project
cad init

# 2. 创建设计
cat > main.py << 'EOF'
from build123d import *

# 创建一个带孔的盒子
box = Box(100, 50, 20)
hole = Cylinder(15, 30, align=(Align.CENTER, Align.CENTER, Align.CENTER))
result = box - hole
EOF

# 3. 执行并验证
cad run main.py
cad validate

# 4. 查询属性
cad inspect --prop=volume
cad inspect --prop=bounds

# 5. 生成渲染图
cad render --views="top,front,iso"

# 6. 导出模型
cad export --format=step --output=output/part.step

# 7. 提交版本
cad commit -m "Initial design with hole"

# 8. 查看历史
cad log
```

### 参数化设计

**examples/parametric_bracket.py**:

```python
from build123d import *

# 参数定义
width = 80
height = 60
thickness = 10
hole_diameter = 8

# 创建基础形状
base = Box(width, height, thickness)

# 创建孔
hole1 = Cylinder(hole_diameter/2, thickness*2)
hole1 = hole1.translate((width/3, height/3, 0))

# 布尔运算
result = base - hole1
```

### 拓扑查询

```bash
# 列出所有面
cad inspect --list-targets

# 查询特定面的属性
cad inspect --target=face[0] --target-prop=center
# 输出: {"target": "face[0]", "property": "center", "value": [0, 0, 10]}

cad inspect --target=face[0] --target-prop=area
# 输出: {"target": "face[0]", "property": "area", "value": 100.0}
```

---

## 配置管理

### 配置文件 (.cad/config.json)

```json
{
  "unit": "mm",
  "timeout_seconds": 60,
  "render": {
    "default_views": ["top", "front", "right", "iso"],
    "image_format": "png",
    "resolution": [800, 600]
  }
}
```

### 配置优先级

1. **命令行参数** (最高优先级)
2. **config.json**
3. **DEFAULT_CONFIG** (src/cad_cli/constants.py:13-21)

### 配置 API

**src/cad_cli/config.py**:

```python
config = Config(project_dir)
config.load()

# 读取配置
timeout = config.get("timeout_seconds", 60)
resolution = config.get("render.resolution", [800, 600])

# 修改配置
config.set("timeout_seconds", 120)
config.save()
```

---

## 错误处理

### 错误信息结构

**src/cad_cli/models.py:17-31**:

```python
@dataclass
class ErrorInfo:
    file: str              # 错误文件路径
    line: int              # 错误行号
    type: str              # 错误类型 (SyntaxError, NameError, etc.)
    code: ErrorCode        # 错误码 (E-SYNTAX, E-RUNTIME, etc.)
    message: str           # 错误消息
    hint: Optional[str]    # 修复建议
```

### 错误示例

#### 语法错误

```json
{
  "event": "run_error",
  "ts": "2026-01-29T10:30:00",
  "payload": {
    "error": {
      "file": "main.py",
      "line": 3,
      "type": "SyntaxError",
      "code": "E-SYNTAX",
      "message": "invalid syntax",
      "hint": "Check syntax near line 3"
    }
  }
}
```

#### 运行时错误

```json
{
  "event": "run_error",
  "payload": {
    "error": {
      "file": "main.py",
      "line": 5,
      "type": "NameError",
      "code": "E-RUNTIME",
      "message": "name 'result' is not defined",
      "hint": "Script must define a 'result' variable with the final shape"
    }
  }
}
```

#### BRep 验证失败

```json
{
  "event": "validate_failed",
  "payload": {
    "errors": [
      {
        "file": "",
        "line": 0,
        "type": "BRepValidation",
        "code": "E-BREP",
        "message": "Invalid BRep: Shape failed basic validity check",
        "hint": "Check for self-intersections or degenerate geometry"
      }
    ]
  }
}
```

---

## 性能优化

### Shape 缓存

**src/cad_cli/runtime/executor.py:100-116**:

```python
def _save_current_shape(self, shape: Shape):
    """缓存 shape 到 .cad/runlog/current_shape.pkl"""
    self._shape_cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(self._shape_cache_path, 'wb') as f:
        pickle.dump(shape, f)

def load_current_shape(self) -> Optional[Shape]:
    """加载缓存的 shape"""
    if not self._shape_cache_path.exists():
        return None
    with open(self._shape_cache_path, 'rb') as f:
        return pickle.load(f)
```

**优势**:
- 避免重复执行脚本
- inspect/render/export 命令复用同一 shape
- 减少计算开销

### 超时控制

**可配置超时** (.cad/config.json):

```json
{
  "timeout_seconds": 60
}
```

**默认值**: 60 秒
**用途**: 防止无限循环或过长计算

---

## 已知限制与未来规划

### v1.0 限制

1. **线性版本控制**
   - 无分支/合并
   - 无回退功能
   - 仅追加式历史

2. **BRep 错误信息**
   - 仅返回 "Invalid BRep"
   - 无详细拓扑错误定位

3. **渲染**
   - 固定样式（浅蓝色 + 黑边）
   - 无光照/阴影控制
   - 无材质系统

4. **脚本隔离**
   - 无沙箱隔离（exec 共享全局命名空间）
   - 无资源限制（内存、磁盘）

### v2.0 规划

1. **高级版本控制**
   - 分支管理 (`cad branch`, `cad checkout`)
   - 差异比较 (`cad diff <hash1> <hash2>`)
   - 版本回退 (`cad reset <hash>`)

2. **约束求解器**
   - 集成 FreeCAD solver
   - 参数化约束
   - 装配体约束

3. **详细 BRep 诊断**
   - 提取 OCP 详细错误信息
   - 定位问题拓扑元素
   - 可视化错误位置

4. **高级渲染**
   - 可配置材质和光照
   - 支持 PBR 渲染
   - 动画/爆炸视图

5. **远程执行**
   - 云端 CAD 服务
   - 分布式计算
   - Web 查看器

6. **装配体支持**
   - 多零件管理
   - 配合关系
   - BOM 生成

---

## 文件清单

### 源代码 (23 个文件)

```
src/cad_cli/
├── __init__.py
├── __main__.py
├── cli.py                  # 406 行 - CLI 入口
├── config.py               # 93 行 - 配置管理
├── constants.py            # 28 行 - 常量定义
├── models.py               # 72 行 - 数据模型
├── runtime/
│   ├── __init__.py
│   ├── executor.py         # 147 行 - 脚本执行
│   ├── validator.py        # 72 行 - 几何验证
│   ├── sandbox.py          # 58 行 - 超时保护
│   └── error_handler.py    # 103 行 - 错误处理
├── feedback/
│   ├── __init__.py
│   ├── inspector.py        # 167 行 - 属性探针
│   ├── renderer.py         # 72 行 - 渲染器
│   ├── exporter.py         # 36 行 - 导出器
│   └── camera.py           # 60 行 - 相机定义
├── vcs/
│   ├── __init__.py
│   ├── repository.py       # 149 行 - 仓库管理
│   ├── commit.py           # 48 行 - 提交工具
│   └── storage.py          # 25 行 - 存储工具
└── utils/
    ├── __init__.py
    ├── jsonl.py            # 28 行 - JSONL 输出
    ├── geometry.py         # 36 行 - 几何计算
    └── logger.py           # 26 行 - 日志工具
```

### 测试代码 (9 个文件)

```
test/
├── conftest.py             # 67 行 - Fixtures
├── fixtures/scripts/
│   ├── simple_box.py
│   ├── invalid_syntax.py
│   └── runtime_error.py
├── test_runtime/
│   ├── test_executor.py    # 62 行
│   └── test_validator.py   # 28 行
├── test_feedback/
│   ├── test_inspector.py   # 73 行
│   ├── test_renderer.py    # 39 行
│   └── test_exporter.py    # 38 行
├── test_vcs/
│   └── test_repository.py  # 52 行
├── test_cli/
│   └── test_integration.py # 85 行
└── test_utils/
    └── test_jsonl.py       # 24 行
```

### 文档 (6 个文件)

```
README.md              # 348 行 - 主文档
QUICKSTART.md          # 243 行 - 快速开始
INSTALL.md             # 112 行 - 安装指南
TESTING.md             # 268 行 - 测试指南
examples/README.md     # 47 行 - 示例说明
docs/summary.md        # 本文件
```

### 示例 (3 个文件)

```
examples/
├── simple_box.py
├── box_with_hole.py
└── parametric_bracket.py
```

### 配置文件

```
pyproject.toml         # 项目配置
.gitignore             # Git 忽略规则
```

---

## 代码统计

| 类型 | 文件数 | 代码行数 |
|------|--------|---------|
| 源代码 | 23 | ~1,500 行 |
| 测试代码 | 9 | ~400 行 |
| 文档 | 6 | ~1,000 行 |
| 示例 | 3 | ~60 行 |
| **总计** | **41** | **~3,000 行** |

---

## 安装与部署

### 环境要求

- Python 3.11+
- Conda (推荐) 或 pip
- 操作系统: Windows / Linux / macOS

### 安装步骤

```bash
# 1. 创建环境
conda create -n cad-cli python=3.11
conda activate cad-cli

# 2. 安装依赖
conda install -c conda-forge build123d pyvista

# 3. 安装 CAD CLI
cd "C:\Users\liwuz\Desktop\test\cad tools"
pip install -e .

# 4. 验证安装
cad --help
```

### 开发安装

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black src/ test/

# 类型检查
mypy src/
```

---

## 命令速查表

| 命令 | 用途 | 示例 |
|------|------|------|
| `cad init` | 初始化项目 | `cad init` |
| `cad run <script>` | 执行脚本 | `cad run main.py` |
| `cad validate` | 验证几何 | `cad validate` |
| `cad inspect --prop=<prop>` | 查询属性 | `cad inspect --prop=volume` |
| `cad inspect --list-targets` | 列出拓扑 | `cad inspect --list-targets` |
| `cad inspect --target=<t> --target-prop=<p>` | 查询目标 | `cad inspect --target=face[0] --target-prop=center` |
| `cad render --views=<views>` | 渲染 | `cad render --views="top,iso"` |
| `cad export --format=<fmt> --output=<path>` | 导出 | `cad export --format=step --output=out.step` |
| `cad commit -m "<msg>"` | 提交 | `cad commit -m "Updated design"` |
| `cad log` | 查看历史 | `cad log` |
| `cad status` | 查看状态 | `cad status` |

---

## 贡献指南

### 开发流程

1. Fork 项目
2. 创建特性分支: `git checkout -b feature/my-feature`
3. 编写代码和测试
4. 运行测试: `pytest`
5. 格式化代码: `black src/ test/`
6. 提交: `git commit -m "Add my feature"`
7. Push: `git push origin feature/my-feature`
8. 创建 Pull Request

### 代码规范

- 遵循 PEP 8
- 使用 Black 格式化 (line-length=100)
- 添加类型提示
- 编写文档字符串
- 测试覆盖率 > 85%

### 提交消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**:
- feat: 新功能
- fix: Bug 修复
- docs: 文档更新
- test: 测试更新
- refactor: 重构
- perf: 性能优化

**示例**:
```
feat(runtime): Add timeout protection for script execution

Implement cross-platform timeout mechanism using signal.alarm (Unix)
and threading.Timer (Windows) to prevent infinite loops.

Closes #123
```

---

## 常见问题 (FAQ)

### Q1: 为什么脚本必须定义 `result` 变量？

**A**: 这是为了明确指定最终输出，避免歧义。AI 可以轻松理解和生成这种约定。

### Q2: 如何处理大模型的超时？

**A**: 在 `.cad/config.json` 中增加 `timeout_seconds`:

```json
{
  "timeout_seconds": 300
}
```

### Q3: 渲染失败怎么办？

**A**:
1. 确保安装 pyvista: `pip install pyvista`
2. 在无头环境中，pyvista 会自动使用软件渲染
3. 检查 `.cad/thumbs/` 目录权限

### Q4: 如何添加自定义相机视角？

**A**: 编辑 `src/cad_cli/feedback/camera.py`:

```python
STANDARD_VIEWS["my_view"] = CameraView(
    name="my_view",
    position=(100, 100, 100),
    focal_point=(0, 0, 0),
    view_up=(0, 0, 1)
)
```

### Q5: 支持哪些导出格式？

**A**: 当前支持:
- STEP (.step, .stp) - CAD 交换标准
- STL (.stl) - 3D 打印

v2.0 计划支持: IGES, OBJ, GLTF

### Q6: 如何调试脚本？

**A**: 使用标准 Python 调试器:

```bash
# 在脚本中添加断点
import pdb; pdb.set_trace()

# 或使用 IPython
ipython -i main.py
```

### Q7: 版本控制能回退吗？

**A**: v1.0 不支持回退。v2.0 将支持 `cad reset <hash>` 命令。

---

## 致谢

### 核心依赖

- **build123d**: CAD 建模框架
- **OCP**: OpenCascade Python 绑定
- **PyVista**: 3D 可视化
- **Click**: CLI 框架

### 参考项目

- CadQuery
- FreeCAD
- OpenSCAD

---

## 许可证

MIT License

---

## 联系方式

- 项目地址: `C:\Users\liwuz\Desktop\test\cad tools`
- 文档: README.md, QUICKSTART.md, INSTALL.md, TESTING.md

---

**文档版本**: 1.0
**最后更新**: 2026-01-29
**文档生成**: AI-assisted

---

## 附录 A: 完整工作流示例

```bash
# ============================================
# 完整工作流示例: 参数化支架设计
# ============================================

# 1. 初始化项目
mkdir bracket_project
cd bracket_project
cad init

# 2. 创建参数化脚本
cat > main.py << 'EOF'
from build123d import *

# 参数定义
width = 80
height = 60
thickness = 10
hole_diameter = 8
fillet_radius = 5

# 创建基础板
base = Box(width, height, thickness)

# 创建安装孔
hole1 = Cylinder(hole_diameter/2, thickness*2,
                 align=(Align.CENTER, Align.CENTER, Align.CENTER))
hole1 = hole1.translate((width/3, height/3, 0))

hole2 = Cylinder(hole_diameter/2, thickness*2,
                 align=(Align.CENTER, Align.CENTER, Align.CENTER))
hole2 = hole2.translate((-width/3, -height/3, 0))

# 布尔运算
bracket = base - hole1 - hole2

# 赋值给 result
result = bracket
EOF

# 3. 执行并验证
cad run main.py
cad validate

# 4. 查询属性
echo "=== 几何属性 ==="
cad inspect --prop=volume
cad inspect --prop=area
cad inspect --prop=bounds

echo "=== 拓扑信息 ==="
cad inspect --list-targets

# 5. 查询特定面
cad inspect --target=face[0] --target-prop=center
cad inspect --target=face[0] --target-prop=area

# 6. 生成渲染图
cad render --views="top,front,right,iso"

# 7. 导出模型
mkdir output
cad export --format=step --output=output/bracket.step
cad export --format=stl --output=output/bracket.stl

# 8. 提交版本
cad commit -m "Initial parametric bracket design"

# 9. 修改参数
sed -i 's/width = 80/width = 100/' main.py
sed -i 's/height = 60/height = 80/' main.py

# 10. 重新执行
cad run main.py
cad validate
cad inspect --prop=volume
cad render --views="iso"

# 11. 提交新版本
cad commit -m "Increased bracket size to 100x80"

# 12. 查看历史
cad log
cad status

# 输出示例:
# {
#   "event": "log_result",
#   "payload": {
#     "commits": [
#       {
#         "hash": "e5f6g7h8",
#         "message": "Increased bracket size to 100x80",
#         "timestamp": "2026-01-29T10:35:00",
#         "metrics": {"volume": 80000, ...}
#       },
#       {
#         "hash": "a1b2c3d4",
#         "message": "Initial parametric bracket design",
#         "timestamp": "2026-01-29T10:30:00",
#         "metrics": {"volume": 48000, ...}
#       }
#     ]
#   }
# }
```

---

## 附录 B: JSONL 事件参考

### run_start

```json
{
  "event": "run_start",
  "ts": "2026-01-29T10:30:00.123456",
  "payload": {
    "script": "main.py"
  }
}
```

### run_success

```json
{
  "event": "run_success",
  "ts": "2026-01-29T10:30:01.234567",
  "payload": {
    "metrics": {
      "volume": 1000.0,
      "area": 600.0,
      "bbox": [-5, -5, -5, 5, 5, 5],
      "face_count": 6,
      "edge_count": 12,
      "vertex_count": 8
    }
  }
}
```

### run_error

```json
{
  "event": "run_error",
  "ts": "2026-01-29T10:30:00.456789",
  "payload": {
    "error": {
      "file": "main.py",
      "line": 3,
      "type": "SyntaxError",
      "code": "E-SYNTAX",
      "message": "invalid syntax",
      "hint": "Check syntax near line 3"
    }
  }
}
```

### validate_success

```json
{
  "event": "validate_success",
  "ts": "2026-01-29T10:30:02.000000",
  "payload": {}
}
```

### validate_failed

```json
{
  "event": "validate_failed",
  "ts": "2026-01-29T10:30:02.111111",
  "payload": {
    "errors": [
      {
        "file": "",
        "line": 0,
        "type": "BRepValidation",
        "code": "E-BREP",
        "message": "Invalid BRep: Shape failed basic validity check",
        "hint": "Check for self-intersections or degenerate geometry"
      }
    ]
  }
}
```

### inspect_result

```json
{
  "event": "inspect_result",
  "ts": "2026-01-29T10:30:03.222222",
  "payload": {
    "property": "volume",
    "value": 1000.0
  }
}
```

### inspect_targets

```json
{
  "event": "inspect_targets",
  "ts": "2026-01-29T10:30:04.333333",
  "payload": {
    "targets": {
      "faces": [
        {"index": 0, "area": 100.0, "center": [0, 0, 5]},
        {"index": 1, "area": 100.0, "center": [0, 0, -5]}
      ],
      "edges": [
        {"index": 0, "length": 10.0}
      ],
      "vertices": [
        {"index": 0, "position": [5, 5, 5]}
      ]
    }
  }
}
```

### render_success

```json
{
  "event": "render_success",
  "ts": "2026-01-29T10:30:05.444444",
  "payload": {
    "views": ["top", "front", "iso"],
    "paths": [
      ".cad/thumbs/top.png",
      ".cad/thumbs/front.png",
      ".cad/thumbs/iso.png"
    ]
  }
}
```

### export_success

```json
{
  "event": "export_success",
  "ts": "2026-01-29T10:30:06.555555",
  "payload": {
    "format": "step",
    "path": "output/part.step"
  }
}
```

### commit_success

```json
{
  "event": "commit_success",
  "ts": "2026-01-29T10:30:07.666666",
  "payload": {
    "hash": "a1b2c3d4",
    "message": "Initial design"
  }
}
```

### log_result

```json
{
  "event": "log_result",
  "ts": "2026-01-29T10:30:08.777777",
  "payload": {
    "commits": [
      {
        "hash": "e5f6g7h8",
        "message": "Updated design",
        "timestamp": "2026-01-29T10:30:07.666666",
        "script_path": "main.py",
        "metrics": {
          "volume": 1200.0,
          "area": 720.0,
          "bbox": [-6, -6, -6, 6, 6, 6],
          "face_count": 6,
          "edge_count": 12,
          "vertex_count": 8
        },
        "thumbnail_path": ".cad/thumbs/commit_20260129_103007.png"
      }
    ]
  }
}
```

### status_result

```json
{
  "event": "status_result",
  "ts": "2026-01-29T10:30:09.888888",
  "payload": {
    "current_commit": "e5f6g7h8",
    "has_changes": false,
    "total_commits": 2
  }
}
```

---

**文档结束**
