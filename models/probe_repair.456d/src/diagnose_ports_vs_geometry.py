"""诊断脚本：把 ports.py 的声明逐项拿去和 main.py 实际建出的几何对账。

这是「声明 vs 几何」的一致性检查 —— 与 `cad mates` 互补：mates 比的是
「声明 vs 声明」（manifest 的 deps/mates 对 ports.py），本脚本比的是
「声明 vs 实际建出来的 BRep」。二者都不做的那件事，正是本探针包藏的问题。

用法：
    .venv/bin/python <包>/src/diagnose_ports_vs_geometry.py [包目录]
    （缺省诊断脚本自己所在的包）
    .venv/bin/python <包>/src/diagnose_ports_vs_geometry.py <包目录> --step <文件.step>
    （--step：不执行 main.py，直接量一个已保存的 STEP 工件 —— 用来复验
      「提交进 VCS 的那个工件」而不是「刚跑出来的内存对象」）

判据（每一项都必须落到实际几何上，不做「空泛的通过」）：
  cylindrical_bore / clearance_hole
      · 直径     ← 匹配轴线的圆柱面的解析半径 ×2      （BRep 精确值）
      · 轴线位置 ← 声明 origin 到该圆柱面轴线直线的距离
      · 轴线方向 ← 声明 axis 与圆柱面轴线的夹角
      · 长度     ← 该圆柱面顶点沿轴线的跨度（声明了 length 才查）
  planar_face
      · origin   ← 声明 origin 到该平面的距离（必须贴在该面上）
      · 法向     ← 声明 axis 与平面法向的夹角
      · face_size← 该面外环 (outer wire) 边界框的平面内尺寸
另外三条独立证据链：
      · 体积闭解：仅用「声明」重建体积，和实测体积比
      · 镶嵌最小二乘：只用网格顶点拟合孔半径，不走解析曲面
      · STEP 往返：导出再回读，看数值是否在序列化后仍然一致

输出：每个声明项一行 MEASURED / DECLARED / DELTA / VERDICT，末行 SUMMARY。
退出码：0 = 全部一致；1 = 存在不一致（可当回归门禁）。
"""

from __future__ import annotations

import importlib.util
import math
import runpy
import sys
from pathlib import Path

from build123d import Compound, GeomType, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface

TOL = 1e-6  # 声明与几何的容许差（本脚本是「是否忠实」的判定，不是公差判定）

PKG = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
    else Path(__file__).resolve().parents[1]
STEP_FILE = Path(sys.argv[sys.argv.index("--step") + 1]).resolve() \
    if "--step" in sys.argv else None

ROWS: list[tuple[str, str, str, str]] = []  # (port_id, declared, measured, verdict)
NOTES: list[str] = []


# ---------------------------------------------------------------- 载入

def load_ports(pkg: Path):
    spec = importlib.util.spec_from_file_location("_pkg_ports", pkg / "ports.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PORTS


def load_part(pkg: Path):
    return runpy.run_path(str(pkg / "src" / "main.py"))


# ---------------------------------------------------------------- 测量原语

def vec(a):
    return (float(a[0]), float(a[1]), float(a[2]))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def norm(a):
    return math.sqrt(dot(a, a))


def angle_deg(a, b):
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    c = max(-1.0, min(1.0, dot(a, b) / (na * nb)))
    return math.degrees(math.acos(c))


def point_line_distance(p, a, u):
    """点 p 到「过 a、方向 u」的直线的距离。"""
    d = sub(p, a)
    un = norm(u)
    if un == 0:
        return norm(d)
    u = tuple(c / un for c in u)
    proj = dot(d, u)
    perp = tuple(d[i] - proj * u[i] for i in range(3))
    return norm(perp)


def measured_cylinders(shape):
    """所有圆柱面：(半径, 轴上一点, 轴方向, 沿轴跨度)。半径取自 BRep 解析曲面。"""
    out = []
    for face in shape.faces():
        if face.geom_type != GeomType.CYLINDER:
            continue
        cyl = BRepAdaptor_Surface(face.wrapped).Cylinder()
        ax = cyl.Axis()
        loc, direc = ax.Location(), ax.Direction()
        a, u = vec((loc.X(), loc.Y(), loc.Z())), vec((direc.X(), direc.Y(), direc.Z()))
        ts = []
        for v in face.vertices():
            p = v.center()
            ts.append(dot(sub(vec((p.X, p.Y, p.Z)), a), u))
        span = (max(ts) - min(ts)) if ts else float("nan")
        out.append({"r": cyl.Radius(), "a": a, "u": u, "span": span})
    return out


def measured_planes(shape):
    """所有平面：(平面上一点, 法向, 外环平面内尺寸, 外环中心)。"""
    out = []
    for face in shape.faces():
        if face.geom_type != GeomType.PLANE:
            continue
        try:
            n = face.normal_at(face.center())
            n = vec((n.X, n.Y, n.Z))
            ow = face.outer_wire()
            wb = ow.bounding_box()
            size = (wb.size.X, wb.size.Y, wb.size.Z)
            c = ow.center()
            out.append({"p": vec((c.X, c.Y, c.Z)), "n": n,
                        "size": size, "area": face.area})
        except Exception as exc:  # 面本身读不出来时不要把该项算通过
            NOTES.append(f"平面读取失败：{type(exc).__name__}: {exc}")
    return out


def tessellated_radius(shape, axis_point, axis_dir, radius_hint, tol=0.3):
    """独立证据链：镶嵌网格顶点 → 距轴距离 → 中位数半径。不走解析曲面。"""
    verts, _ = shape.tessellate(0.02)
    pts = []
    for v in verts:
        d = sub(vec((v.X, v.Y, v.Z)), axis_point)
        un = norm(axis_dir)
        u = tuple(c / un for c in axis_dir)
        along = dot(d, u)
        perp = tuple(d[i] - along * u[i] for i in range(3))
        r = norm(perp)
        if abs(r - radius_hint) < tol:
            pts.append(r)
    if not pts:
        return None, 0
    pts.sort()
    n = len(pts)
    med = pts[n // 2] if n % 2 else 0.5 * (pts[n // 2 - 1] + pts[n // 2])
    return med, n


# ---------------------------------------------------------------- 主流程

def main():
    ports = load_ports(PKG)
    if STEP_FILE is not None:
        # 复验模式：量的是已保存的工件，不重新执行 main.py
        part = import_step(str(STEP_FILE))
        ns = {}
        print(f"# 几何来源: STEP 工件 {STEP_FILE}")
    else:
        ns = load_part(PKG)
        part = ns["result"]
        print("# 几何来源: 执行 src/main.py")

    bb = part.bounding_box()
    vol = part.volume
    print(f"# 包: {PKG.name}")
    print(f"# solids={len(part.solids())}  is_valid={part.is_valid}")
    print(f"# bbox = {bb.size.X:.6f} x {bb.size.Y:.6f} x {bb.size.Z:.6f} "
          f"(min {bb.min.X:.3f},{bb.min.Y:.3f},{bb.min.Z:.3f})")
    print(f"# volume = {vol:.6f}")

    cyls = measured_cylinders(part)
    planes = measured_planes(part)
    print(f"# 实测圆柱面 {len(cyls)} 个，平面 {len(planes)} 个")
    for c in sorted(cyls, key=lambda c: -c["r"]):
        print(f"#   cyl R={c['r']:.6f} D={2*c['r']:.6f} "
              f"axis_pt=({c['a'][0]:.3f},{c['a'][1]:.3f},{c['a'][2]:.3f}) span={c['span']:.3f}")

    claimed = set()
    declared_holes: list[tuple[str, float, float | None]] = []  # (pid, 直径, 长度)
    declared_plate = None

    for _inst, plist in ports.items():
        for p in plist:
            pid = p["id"]
            dims = p.get("dimensions_mm", {})
            frame = p.get("frame", {})
            origin = vec(frame.get("origin_mm", [0, 0, 0]))
            axis = vec(frame.get("axis", [0, 0, 1]))

            if p["type"] in ("cylindrical_bore", "clearance_hole"):
                dec_d = float(dims["diameter"])
                # 匹配：轴线到声明 origin 最近，且直径最接近声明值的圆柱面
                cands = sorted(
                    cyls,
                    key=lambda c: (point_line_distance(origin, c["a"], c["u"]),
                                   0 if abs(2 * c["r"] - dec_d) < 1e-6 else 1),
                )
                if not cands or point_line_distance(origin, cands[0]["a"], cands[0]["u"]) > 0.05:
                    ROWS.append((pid, f"D={dec_d:.4f}", "没有轴线过声明 origin 的圆柱面",
                                 "FAIL 找不到对应特征"))
                    continue
                hit = cands[0]
                claimed.add(id(hit))
                meas_d = 2 * hit["r"]
                line_off = point_line_distance(origin, hit["a"], hit["u"])
                ang = angle_deg(axis, hit["u"])
                ang = min(ang, 180 - ang)
                delta = meas_d - dec_d
                problems = []
                if abs(delta) > TOL:
                    problems.append(f"直径差 {delta:+.6f}")
                if line_off > 1e-6:
                    problems.append(f"轴线偏离 {line_off:.6f} mm")
                if ang > 1e-6:
                    problems.append(f"轴向偏 {ang:.6f}°")
                if "length" in dims and abs(hit["span"] - float(dims["length"])) > TOL:
                    problems.append(f"长度差 {hit['span'] - float(dims['length']):+.6f}")
                verdict = "PASS" if not problems else "MISMATCH: " + "; ".join(problems)
                ROWS.append((pid, f"D={dec_d:.4f}"
                             + (f" L={float(dims['length']):.3f}" if "length" in dims else ""),
                             f"D={meas_d:.6f} 轴偏{line_off:.2e} 角偏{ang:.1e}° span={hit['span']:.3f}",
                             verdict))
                # 体积闭解用：声明直径 × 声明长度（缺省按板厚通孔，长度在下面补）
                declared_holes.append((pid, dec_d, dims.get("length")))
                if pid == "central_bore":
                    fit_r, npts = tessellated_radius(part, hit["a"], hit["u"], hit["r"])
                    if fit_r is not None:
                        print(f"# [镶嵌最小二乘] {pid}: R={fit_r:.6f} (D={2*fit_r:.6f}) "
                              f"用 {npts} 个网格顶点")
                    shaft_od = ns.get("SHAFT_OD")
                    clearance = ns.get("FIT_CLEARANCE")
                    if shaft_od is not None:
                        print(f"# [功能后果] 与建模参数 SHAFT_OD=⌀{shaft_od:g} 配："
                              f"实测直径间隙 = {meas_d:.4f} - {shaft_od:g} = "
                              f"{meas_d - shaft_od:+.4f} mm"
                              + (f"（参数里的 FIT_CLEARANCE 是 {clearance:g}）"
                                 if clearance is not None else ""))
                    print(f"# [功能后果] 与「声明直径 ⌀{dec_d:g}」配：间隙 = "
                          f"{meas_d - dec_d:+.4f} mm（负值即过盈，装不进去）")

            elif p["type"] == "planar_face":
                dec_size = float(dims["face_size"])
                best, best_off = None, 1e9
                for pl in planes:
                    ang = angle_deg(axis, pl["n"])
                    ang = min(ang, 180 - ang)
                    if ang > 1e-6:
                        continue
                    off = abs(dot(sub(origin, pl["p"]), pl["n"]))
                    if off < best_off:
                        best, best_off = pl, off
                if best is None:
                    ROWS.append((pid, f"size={dec_size:.4f}",
                                 "没有法向相符的平面", "FAIL 找不到对应特征"))
                    continue
                # 平面内尺寸：按尺寸最大的两个分量取（该面法向为轴对齐）
                in_plane = sorted(best["size"], reverse=True)[:2]
                meas_size = in_plane[0]
                delta = meas_size - dec_size
                verdict = "PASS" if (abs(delta) <= TOL and best_off <= TOL) \
                    else f"MISMATCH: size delta {delta:+.6f}, origin off {best_off:.6f}"
                ROWS.append((pid, f"size={dec_size:.4f}",
                             f"size={meas_size:.6f} origin_off={best_off:.2e}", verdict))
                if declared_plate is None:
                    # 板厚在 ports.py 里没有声明项，只能取实测 bbox 的 Z。
                    # 也就是说下面的闭解不是「纯声明」，板厚这一项是实测的 —— 记在这里，
                    # 免得把这条证据链说成比它实际更强。
                    declared_plate = (dec_size, dec_size, bb.size.Z)
                    NOTES.append(f"闭解用的板厚 {bb.size.Z:.6f} 取自实测 bbox"
                                 f"（ports.py 未声明板厚）")

    # ---- 证据链 1：体积闭解 ----
    # 只用「声明」+ 一个拓扑假设（这是一块声明尺寸的板，孔都是通孔）重建体积，
    # 再和实测体积比。声明与几何若漂移，这里会以一个独立的数值差暴露出来。
    if declared_plate and declared_plate[2] and declared_holes:
        sx, sy, t = declared_plate
        v_decl = sx * sy * t - sum(
            math.pi * (d / 2) ** 2 * (float(L) if L else t)
            for _pid, d, L in declared_holes
        )
        print(f"# [闭解] 仅用声明重建体积 = {v_decl:.6f}"
              f"（板 {sx:g}×{sy:g}×{t:g}，{len(declared_holes)} 个孔）")
        print(f"# [闭解] 实测体积         = {vol:.6f}   差 = {vol - v_decl:+.6f}")

    # 反解：如果只把中心孔换成别的直径，实测体积对应哪个直径？
    if declared_plate and declared_plate[2] and declared_holes:
        sx, sy, t = declared_plate
        rest = sum(
            math.pi * (d / 2) ** 2 * (float(L) if L else t)
            for pid, d, L in declared_holes if pid != "central_bore"
        )
        bore_pid, bore_d, bore_L = next(h for h in declared_holes if h[0] == "central_bore")
        L = float(bore_L) if bore_L else t
        implied = 2 * math.sqrt(max(0.0, (sx * sy * t - rest - vol) / (math.pi * L)))
        print(f"# [反解] 实测体积反推出的中心孔直径 = {implied:.6f} mm"
              f"（声明 {bore_d:g} mm，差 {implied - bore_d:+.6f}）")

    # ---- 证据链 2：STEP 往返 ----
    scratch = Path(__file__).resolve().parents[1] / "runlog"
    scratch.mkdir(parents=True, exist_ok=True)
    tmp = scratch / "_diag_roundtrip.step"
    try:
        export_step(part, str(tmp))
    except RuntimeError:
        # build123d 0.11 回归 #1356：从 STEP 读回来的形状不能直接再导出。
        # 包一层 Compound 即可 —— cad_cli 自己的 runner 也是这么绕的。
        export_step(Compound(children=[part]), str(tmp))
    back = import_step(str(tmp))
    src_d = sorted(2 * c["r"] for c in cyls)
    back_d = sorted(2 * c["r"] for c in measured_cylinders(back))
    same = len(src_d) == len(back_d) and all(abs(a - b) < 1e-9 for a, b in zip(src_d, back_d))
    print(f"# [STEP 往返] 原始直径 {['%.4f' % d for d in src_d]}")
    print(f"# [STEP 往返] 回读直径 {['%.4f' % d for d in back_d]}  一致={same}")
    tmp.unlink(missing_ok=True)

    # ---- 汇总 ----
    print()
    print(f"{'port_id':<20} {'declared':<16} {'measured':<46} verdict")
    for pid, dec, meas, verdict in ROWS:
        print(f"{pid:<20} {dec:<16} {meas:<46} {verdict}")
    for n in NOTES:
        print(f"# 注: {n}")

    unclaimed = [c for c in cyls if id(c) not in claimed]
    if unclaimed:
        print(f"# 覆盖率警告: {len(unclaimed)} 个实测圆柱面没有任何声明项对应 -> "
              + ", ".join(f"D={2*c['r']:.4f}@({c['a'][0]:.1f},{c['a'][1]:.1f})"
                          for c in unclaimed))

    bad = [r for r in ROWS if not r[3].startswith("PASS")]
    print()
    if bad:
        print(f"SUMMARY: {len(bad)}/{len(ROWS)} 个声明项与几何不符 -> "
              + ", ".join(r[0] for r in bad))
    else:
        print(f"SUMMARY: {len(ROWS)}/{len(ROWS)} 个声明项与几何一致")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
