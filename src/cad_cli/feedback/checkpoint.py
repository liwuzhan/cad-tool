"""
Feature Checkpoint - 特征级验证钩子

在每个特征操作后添加断言，验证结果是否符合预期。
类似于单元测试中的断言，但用于 CAD 特征。

使用示例:
    from cad_cli.feedback.checkpoint import Checkpoint

    with BuildPart() as part:
        Cylinder(30, 10)
        Checkpoint(part).expect_volume(28274, tolerance=100)

        Cylinder(10, 10, mode=Mode.SUBTRACT)
        Checkpoint(part).expect_volume_decreased()
        Checkpoint(part).expect_faces(4)  # 顶、底、外壁、内壁
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, List, Any, Callable
from pathlib import Path
import json
import os
import tempfile

if TYPE_CHECKING:
    from build123d import Shape

from ..utils.jsonl import emit_event
from .inspector import classify_face_type


def _render_checkpoint_image(shape, name: str) -> Optional[str]:
    """Render shape to a PNG file for visual feedback.

    Uses pyvista offscreen rendering. Returns the PNG path on success,
    None on failure (never raises — rendering is best-effort).
    """
    try:
        import pyvista as pv
        from build123d import export_stl
    except ImportError:
        return None

    try:
        # Export shape to STL for pyvista
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            export_stl(shape, str(tmp_path))
            mesh = pv.read(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)

        if mesh.n_points == 0:
            return None

        # Render directory
        render_dir = Path(tempfile.gettempdir()) / "cad_checkpoints"
        render_dir.mkdir(exist_ok=True)
        output_png = render_dir / f"{name}.png"

        # Quick isometric render (perspective, matching cad render iso view)
        plotter = pv.Plotter(off_screen=True, window_size=[400, 300])
        plotter.set_background("white")

        feature_edges = mesh.extract_feature_edges(
            boundary_edges=True, feature_edges=True,
            manifold_edges=False, non_manifold_edges=True,
            feature_angle=30
        )
        plotter.add_mesh(mesh, color='#f0f0f0', show_edges=False,
                         lighting=True, ambient=0.3, diffuse=0.6)
        if feature_edges.n_points > 0:
            plotter.add_mesh(feature_edges, color='black', line_width=2)
        plotter.add_silhouette(mesh=mesh, color='black', line_width=2)

        plotter.camera_position = 'iso'
        plotter.reset_camera()
        plotter.screenshot(str(output_png))
        plotter.close()

        return str(output_png)
    except Exception:
        return None


@dataclass
class CheckResult:
    """单个检查的结果"""
    passed: bool
    check_type: str
    expected: Any
    actual: Any
    message: str


@dataclass
class CheckpointState:
    """保存上一个检查点的状态，用于比较"""
    volume: float = 0
    area: float = 0
    face_count: int = 0
    edge_count: int = 0
    vertex_count: int = 0
    solid_count: int = 0
    bbox: tuple = field(default_factory=tuple)
    face_types: dict = field(default_factory=dict)  # type->count mapping


class Checkpoint:
    """
    特征检查点 - 在特征操作后验证几何状态

    用法:
        cp = Checkpoint(part, name="after_hole")
        cp.expect_volume_decreased()
        cp.expect_faces(6)
        cp.verify()  # 执行所有检查并报告

    或者链式调用:
        Checkpoint(part).expect_volume(1000, tolerance=10).verify()
    """

    # 类变量：保存上一个检查点的状态
    _previous_state: Optional[CheckpointState] = None
    _history: List[str] = []

    def __init__(self, part_or_shape, name: str = "checkpoint"):
        """
        创建检查点

        Args:
            part_or_shape: BuildPart 对象或 Shape 对象
            name: 检查点名称（用于日志）
        """
        self.name = name
        self._checks: List[Callable[[], CheckResult]] = []
        Checkpoint._history.append(self.name)

        # 获取 shape
        if hasattr(part_or_shape, 'part'):
            self.shape = part_or_shape.part
        else:
            self.shape = part_or_shape

        # 计算当前状态
        self.state = self._compute_state()

    def _compute_state(self) -> CheckpointState:
        """计算当前几何状态"""
        try:
            bbox = self.shape.bounding_box()
            bbox_tuple = (
                bbox.min.X, bbox.min.Y, bbox.min.Z,
                bbox.max.X, bbox.max.Y, bbox.max.Z
            )
        except:
            bbox_tuple = ()

        # Compute face type breakdown
        face_types: dict = {}
        if hasattr(self.shape, 'faces'):
            try:
                for face in self.shape.faces():
                    ft = classify_face_type(face)
                    face_types[ft] = face_types.get(ft, 0) + 1
            except Exception:
                pass

        return CheckpointState(
            volume=getattr(self.shape, 'volume', 0),
            area=getattr(self.shape, 'area', 0),
            face_count=len(list(self.shape.faces())) if hasattr(self.shape, 'faces') else 0,
            edge_count=len(list(self.shape.edges())) if hasattr(self.shape, 'edges') else 0,
            vertex_count=len(list(self.shape.vertices())) if hasattr(self.shape, 'vertices') else 0,
            solid_count=len(list(self.shape.solids())) if hasattr(self.shape, 'solids') else 0,
            bbox=bbox_tuple,
            face_types=face_types,
        )

    # ========== 体积检查 ==========

    def expect_volume(self, expected: float, tolerance: float = 1.0) -> "Checkpoint":
        """断言体积等于预期值（允许误差）"""
        def check():
            actual = self.state.volume
            passed = abs(actual - expected) <= tolerance
            return CheckResult(
                passed=passed,
                check_type="volume",
                expected=f"{expected} ± {tolerance}",
                actual=actual,
                message=f"Volume: expected {expected}±{tolerance}, got {actual:.2f}"
            )
        self._checks.append(check)
        return self

    def expect_volume_decreased(self, min_decrease: float = 0.1) -> "Checkpoint":
        """断言体积相比上一个检查点减少了"""
        def check():
            if Checkpoint._previous_state is None:
                return CheckResult(
                    passed=False,
                    check_type="volume_decreased",
                    expected="previous state",
                    actual="no previous state",
                    message="No previous checkpoint to compare"
                )
            prev_vol = Checkpoint._previous_state.volume
            curr_vol = self.state.volume
            decrease = prev_vol - curr_vol
            passed = decrease >= min_decrease
            return CheckResult(
                passed=passed,
                check_type="volume_decreased",
                expected=f"decrease >= {min_decrease}",
                actual=f"decreased by {decrease:.2f}",
                message=f"Volume change: {prev_vol:.2f} -> {curr_vol:.2f} (Δ={-decrease:.2f})"
            )
        self._checks.append(check)
        return self

    def expect_volume_increased(self, min_increase: float = 0.1) -> "Checkpoint":
        """断言体积相比上一个检查点增加了"""
        def check():
            if Checkpoint._previous_state is None:
                return CheckResult(
                    passed=False,
                    check_type="volume_increased",
                    expected="previous state",
                    actual="no previous state",
                    message="No previous checkpoint to compare"
                )
            prev_vol = Checkpoint._previous_state.volume
            curr_vol = self.state.volume
            increase = curr_vol - prev_vol
            passed = increase >= min_increase
            return CheckResult(
                passed=passed,
                check_type="volume_increased",
                expected=f"increase >= {min_increase}",
                actual=f"increased by {increase:.2f}",
                message=f"Volume change: {prev_vol:.2f} -> {curr_vol:.2f} (Δ=+{increase:.2f})"
            )
        self._checks.append(check)
        return self

    # ========== 拓扑检查 ==========

    def expect_faces(self, expected: int) -> "Checkpoint":
        """断言面的数量"""
        def check():
            actual = self.state.face_count
            passed = actual == expected
            return CheckResult(
                passed=passed,
                check_type="face_count",
                expected=expected,
                actual=actual,
                message=f"Face count: expected {expected}, got {actual}"
            )
        self._checks.append(check)
        return self

    def expect_faces_increased(self, min_increase: int = 1) -> "Checkpoint":
        """断言面数相比上一个检查点增加了"""
        def check():
            if Checkpoint._previous_state is None:
                return CheckResult(
                    passed=False,
                    check_type="faces_increased",
                    expected="previous state",
                    actual="no previous state",
                    message="No previous checkpoint to compare"
                )
            prev = Checkpoint._previous_state.face_count
            curr = self.state.face_count
            increase = curr - prev
            passed = increase >= min_increase
            return CheckResult(
                passed=passed,
                check_type="faces_increased",
                expected=f"increase >= {min_increase}",
                actual=f"increased by {increase}",
                message=f"Face count: {prev} -> {curr} (Δ=+{increase})"
            )
        self._checks.append(check)
        return self

    def expect_solids(self, expected: int) -> "Checkpoint":
        """断言 solid 数量（通常应该是 1）"""
        def check():
            actual = self.state.solid_count
            passed = actual == expected
            return CheckResult(
                passed=passed,
                check_type="solid_count",
                expected=expected,
                actual=actual,
                message=f"Solid count: expected {expected}, got {actual}"
            )
        self._checks.append(check)
        return self

    def expect_face_type_count(self, face_type: str, expected: int) -> "Checkpoint":
        """断言特定类型的面数（如 'planar', 'cylindrical'）"""
        def check():
            actual = self.state.face_types.get(face_type, 0)
            passed = actual == expected
            return CheckResult(
                passed=passed,
                check_type="face_type_count",
                expected=f"{face_type}={expected}",
                actual=f"{face_type}={actual}",
                message=f"Face type '{face_type}': expected {expected}, got {actual}"
            )
        self._checks.append(check)
        return self

    # ========== 边界框检查 ==========

    def expect_bbox_within(self, x_range: tuple, y_range: tuple, z_range: tuple) -> "Checkpoint":
        """断言边界框在指定范围内"""
        def check():
            if len(self.state.bbox) != 6:
                return CheckResult(
                    passed=False,
                    check_type="bbox",
                    expected="valid bbox",
                    actual="invalid bbox",
                    message="Could not compute bounding box"
                )
            xmin, ymin, zmin, xmax, ymax, zmax = self.state.bbox
            x_ok = x_range[0] <= xmin and xmax <= x_range[1]
            y_ok = y_range[0] <= ymin and ymax <= y_range[1]
            z_ok = z_range[0] <= zmin and zmax <= z_range[1]
            passed = x_ok and y_ok and z_ok
            return CheckResult(
                passed=passed,
                check_type="bbox",
                expected=f"X:{x_range}, Y:{y_range}, Z:{z_range}",
                actual=f"X:[{xmin:.1f},{xmax:.1f}], Y:[{ymin:.1f},{ymax:.1f}], Z:[{zmin:.1f},{zmax:.1f}]",
                message=f"BBox check: {'PASS' if passed else 'FAIL'}"
            )
        self._checks.append(check)
        return self

    def expect_bbox_size(self, x: float, y: float, z: float, tolerance: float = 1.0) -> "Checkpoint":
        """断言边界框尺寸"""
        def check():
            if len(self.state.bbox) != 6:
                return CheckResult(
                    passed=False,
                    check_type="bbox_size",
                    expected="valid bbox",
                    actual="invalid bbox",
                    message="Could not compute bounding box"
                )
            xmin, ymin, zmin, xmax, ymax, zmax = self.state.bbox
            actual_x = xmax - xmin
            actual_y = ymax - ymin
            actual_z = zmax - zmin
            x_ok = abs(actual_x - x) <= tolerance
            y_ok = abs(actual_y - y) <= tolerance
            z_ok = abs(actual_z - z) <= tolerance
            passed = x_ok and y_ok and z_ok
            return CheckResult(
                passed=passed,
                check_type="bbox_size",
                expected=f"({x}, {y}, {z}) ± {tolerance}",
                actual=f"({actual_x:.2f}, {actual_y:.2f}, {actual_z:.2f})",
                message=f"BBox size: expected ({x},{y},{z}), got ({actual_x:.1f},{actual_y:.1f},{actual_z:.1f})"
            )
        self._checks.append(check)
        return self

    # ========== 执行验证 ==========

    def verify(self, raise_on_fail: bool = True, render: bool = True) -> List[CheckResult]:
        """
        执行所有检查，可选自动渲染当前几何体

        Args:
            raise_on_fail: 如果有检查失败，是否抛出异常
            render: 是否自动渲染当前形状为 PNG（用于视觉反馈）

        Returns:
            所有检查的结果列表
        """
        results = [check() for check in self._checks]

        # 更新全局状态（供下一个检查点比较）
        Checkpoint._previous_state = self.state

        # 输出结果
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)

        payload = {
            "name": self.name,
            "passed": passed_count,
            "total": total_count,
            "state": {
                "volume": self.state.volume,
                "area": self.state.area,
                "face_count": self.state.face_count,
                "edge_count": self.state.edge_count,
                "vertex_count": self.state.vertex_count,
                "solid_count": self.state.solid_count,
                "bbox": list(self.state.bbox) if self.state.bbox else [],
                "face_types": self.state.face_types,
            },
            "checks": [
                {
                    "type": r.check_type,
                    "passed": r.passed,
                    "expected": str(r.expected),
                    "actual": str(r.actual),
                    "message": r.message
                }
                for r in results
            ]
        }

        # 自动渲染（best-effort，失败不影响验证）。某些无显示环境会在
        # VTK 内部直接段错误，无法由 Python try/except 捕获，因此允许部署层
        # 显式关闭所有预览，同时保留完整的几何断言与 JSONL 结果。
        render_disabled = os.environ.get("CAD_SKIP_RENDER", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if render and not render_disabled:
            image_path = _render_checkpoint_image(self.shape, self.name)
            if image_path:
                payload["image"] = image_path

        if passed_count == total_count:
            emit_event("checkpoint_passed", payload)
        else:
            emit_event("checkpoint_failed", payload)
            if raise_on_fail:
                failed = [r for r in results if not r.passed]
                messages = "\n".join(f"  - {r.message}" for r in failed)
                raise AssertionError(f"Checkpoint '{self.name}' failed:\n{messages}")

        return results

    @classmethod
    def reset(cls):
        """重置全局状态（通常在脚本开始时调用）"""
        cls._previous_state = None
        cls._history = []

    @classmethod
    def get_history(cls) -> List[str]:
        """返回本次执行中所有 checkpoint 的名称列表"""
        return list(cls._history)


# 便捷函数
def checkpoint(part_or_shape, name: str = "checkpoint") -> Checkpoint:
    """创建检查点的便捷函数"""
    return Checkpoint(part_or_shape, name)
