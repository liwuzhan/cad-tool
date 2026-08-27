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

if TYPE_CHECKING:
    from build123d import Shape

from ..utils.jsonl import emit_event


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

    def __init__(self, part_or_shape, name: str = "checkpoint"):
        """
        创建检查点

        Args:
            part_or_shape: BuildPart 对象或 Shape 对象
            name: 检查点名称（用于日志）
        """
        self.name = name
        self._checks: List[Callable[[], CheckResult]] = []

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

        return CheckpointState(
            volume=getattr(self.shape, 'volume', 0),
            area=getattr(self.shape, 'area', 0),
            face_count=len(list(self.shape.faces())) if hasattr(self.shape, 'faces') else 0,
            edge_count=len(list(self.shape.edges())) if hasattr(self.shape, 'edges') else 0,
            vertex_count=len(list(self.shape.vertices())) if hasattr(self.shape, 'vertices') else 0,
            solid_count=len(list(self.shape.solids())) if hasattr(self.shape, 'solids') else 0,
            bbox=bbox_tuple
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

    def verify(self, raise_on_fail: bool = True) -> List[CheckResult]:
        """
        执行所有检查

        Args:
            raise_on_fail: 如果有检查失败，是否抛出异常

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


# 便捷函数
def checkpoint(part_or_shape, name: str = "checkpoint") -> Checkpoint:
    """创建检查点的便捷函数"""
    return Checkpoint(part_or_shape, name)
