"""Tests for Checkpoint feature-level validation"""

import pytest
from pathlib import Path
import tempfile
import shutil


from cad_cli.feedback.checkpoint import Checkpoint, CheckResult, CheckpointState


# ---- Helpers ----

class FakeShape:
    """Minimal shape mock that satisfies Checkpoint's attribute checks"""
    def __init__(self, volume=1000.0, area=600.0, face_count=6, solid_count=1, bbox=None):
        self._volume = volume
        self._area = area
        self._faces = [object() for _ in range(face_count)]
        self._edges = [object() for _ in range(12)]
        self._vertices = [object() for _ in range(8)]
        self._solids = [object() for _ in range(solid_count)]
        self._bbox = bbox  # tuple (xmin,ymin,zmin,xmax,ymax,zmax)

    @property
    def volume(self):
        return self._volume

    @property
    def area(self):
        return self._area

    def bounding_box(self):
        if self._bbox:
            class Min:
                X, Y, Z = self._bbox[0], self._bbox[1], self._bbox[2]
            class Max:
                X, Y, Z = self._bbox[3], self._bbox[4], self._bbox[5]
            class BB:
                min = Min()
                max = Max()
                class Size:
                    X = abs(Max.X - Min.X)
                    Y = abs(Max.Y - Min.Y)
                    Z = abs(Max.Z - Min.Z)
                size = Size()
            return BB()
        class Min2:
            X, Y, Z = -5.0, -5.0, -5.0
        class Max2:
            X, Y, Z = 5.0, 5.0, 5.0
        class BB2:
            min = Min2()
            max = Max2()
            class Size2:
                X, Y, Z = 10.0, 10.0, 10.0
            size = Size2()
        return BB2()

    def faces(self):
        return iter(self._faces)

    def edges(self):
        return iter(self._edges)

    def vertices(self):
        return iter(self._vertices)

    def solids(self):
        return iter(self._solids)


# ---- Tests ----

def test_checkpoint_expect_volume_pass():
    """expect_volume should pass when volume is within tolerance"""
    shape = FakeShape(volume=1000.0)
    Checkpoint.reset()

    cp = Checkpoint(shape, name="vol_test")
    cp.expect_volume(1000.0, tolerance=1.0)
    results = cp.verify(raise_on_fail=False)

    assert len(results) == 1
    assert results[0].passed is True


def test_checkpoint_expect_volume_fail():
    """expect_volume should fail when volume is outside tolerance"""
    shape = FakeShape(volume=500.0)
    Checkpoint.reset()

    cp = Checkpoint(shape, name="vol_fail")
    cp.expect_volume(1000.0, tolerance=1.0)
    results = cp.verify(raise_on_fail=False)

    assert len(results) == 1
    assert results[0].passed is False


def test_checkpoint_expect_solids():
    """expect_solids should check solid count"""
    shape = FakeShape(solid_count=1)
    Checkpoint.reset()

    cp = Checkpoint(shape, name="solid_test")
    cp.expect_solids(1)
    results = cp.verify(raise_on_fail=False)

    assert len(results) == 1
    assert results[0].passed is True


def test_checkpoint_expect_solids_multi():
    """expect_solids should fail when multiple disconnected solids exist"""
    shape = FakeShape(solid_count=3)
    Checkpoint.reset()

    cp = Checkpoint(shape, name="multi_solid")
    cp.expect_solids(1)
    results = cp.verify(raise_on_fail=False)

    assert results[0].passed is False


def test_checkpoint_expect_volume_decreased():
    """expect_volume_decreased should pass when volume drops"""
    Checkpoint.reset()

    shape1 = FakeShape(volume=1000.0)
    cp1 = Checkpoint(shape1, name="before")
    cp1.verify(raise_on_fail=False)

    shape2 = FakeShape(volume=500.0)
    cp2 = Checkpoint(shape2, name="after")
    cp2.expect_volume_decreased()
    results = cp2.verify(raise_on_fail=False)

    assert results[0].passed is True


def test_checkpoint_expect_volume_increased():
    """expect_volume_increased should pass when volume grows"""
    Checkpoint.reset()

    shape1 = FakeShape(volume=500.0)
    cp1 = Checkpoint(shape1, name="before")
    cp1.verify(raise_on_fail=False)

    shape2 = FakeShape(volume=1000.0)
    cp2 = Checkpoint(shape2, name="after")
    cp2.expect_volume_increased()
    results = cp2.verify(raise_on_fail=False)

    assert results[0].passed is True


def test_checkpoint_expect_volume_decreased_no_previous():
    """expect_volume_decreased should fail with no previous checkpoint"""
    Checkpoint.reset()

    shape = FakeShape(volume=500.0)
    cp = Checkpoint(shape, name="first")
    cp.expect_volume_decreased()
    results = cp.verify(raise_on_fail=False)

    assert results[0].passed is False


def test_checkpoint_expect_bbox_size():
    """expect_bbox_size should check bounding box dimensions"""
    Checkpoint.reset()

    shape = FakeShape(bbox=(0, 0, 0, 100, 50, 20))
    cp = Checkpoint(shape, name="bbox_test")
    cp.expect_bbox_size(100, 50, 20, tolerance=0.1)
    results = cp.verify(raise_on_fail=False)

    assert len(results) == 1
    assert results[0].passed is True


def test_checkpoint_expect_bbox_size_fail():
    """expect_bbox_size should fail for wrong dimensions"""
    Checkpoint.reset()

    shape = FakeShape(bbox=(0, 0, 0, 100, 50, 20))
    cp = Checkpoint(shape, name="bbox_fail")
    cp.expect_bbox_size(200, 50, 20, tolerance=0.1)
    results = cp.verify(raise_on_fail=False)

    assert results[0].passed is False


def test_checkpoint_chaining():
    """Multiple expectations can be chained"""
    Checkpoint.reset()

    shape = FakeShape(volume=1000.0, solid_count=1, bbox=(0, 0, 0, 100, 50, 20))
    cp = Checkpoint(shape, name="chain")
    cp.expect_volume(1000.0, tolerance=1.0)
    cp.expect_solids(1)
    cp.expect_bbox_size(100, 50, 20, tolerance=0.1)
    results = cp.verify(raise_on_fail=False)

    assert len(results) == 3
    assert all(r.passed for r in results)


def test_checkpoint_verify_raises():
    """verify() should raise AssertionError when checks fail and raise_on_fail=True"""
    Checkpoint.reset()

    shape = FakeShape(volume=500.0)
    cp = Checkpoint(shape, name="will_fail")
    cp.expect_volume(1000.0, tolerance=1.0)

    with pytest.raises(AssertionError):
        cp.verify(raise_on_fail=True)


def test_checkpoint_reset():
    """reset() should clear history and previous state"""
    Checkpoint.reset()

    shape = FakeShape(volume=1000.0)
    Checkpoint(shape, name="first").verify(raise_on_fail=False)

    assert len(Checkpoint.get_history()) == 1

    Checkpoint.reset()
    assert len(Checkpoint.get_history()) == 0


def test_checkpoint_get_history():
    """get_history should return all checkpoint names"""
    Checkpoint.reset()

    shape = FakeShape()
    Checkpoint(shape, name="cp1").verify(raise_on_fail=False)
    Checkpoint(shape, name="cp2").verify(raise_on_fail=False)

    history = Checkpoint.get_history()
    assert history == ["cp1", "cp2"]
