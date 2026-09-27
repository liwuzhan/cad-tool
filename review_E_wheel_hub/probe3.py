import math
from build123d import *
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_State

# ---- 1) 复现 window_face() 的 2D 轮廓，量它的极径 ----
WIN_R_IN, WIN_R_OUT = 82.0, 208.0
WIN_HALF_ANG_IN, WIN_HALF_ANG_OUT = 21.0, 30.0
WIN_TILT, WIN_FILLET = 8.0, 6.0
a_in, a_out = math.radians(WIN_HALF_ANG_IN), math.radians(WIN_HALF_ANG_OUT)
t = math.radians(WIN_TILT)
pts = [(WIN_R_IN*math.cos(t-a_in), WIN_R_IN*math.sin(t-a_in)),
       (WIN_R_IN*math.cos(t+a_in), WIN_R_IN*math.sin(t+a_in)),
       (WIN_R_OUT*math.cos(a_out), WIN_R_OUT*math.sin(a_out)),
       (WIN_R_OUT*math.cos(-a_out), WIN_R_OUT*math.sin(-a_out))]
print("=== 1) 窗口四边形顶点 (未倒圆) ===")
for p in pts:
    print(f"   {p[0]:8.2f},{p[1]:8.2f}   r={math.hypot(*p):7.2f}  ang={math.degrees(math.atan2(p[1],p[0])):6.2f}")
with BuildSketch() as s:
    with BuildLine():
        Polyline(*pts, close=True)
    make_face()
    fillet(s.vertices(), radius=WIN_FILLET)
w = s.sketch
bb = w.bounding_box()
rmax = max(math.hypot(v.X, v.Y) for v in w.vertices())
print(f"   倒圆后 bbox: X[{bb.min.X:.2f},{bb.max.X:.2f}] Y[{bb.min.Y:.2f},{bb.max.Y:.2f}]")
print(f"   倒圆后顶点最大极径 rmax = {rmax:.2f}")
# 采样外边界（接近外端的弧）最大极径
outer = [e for e in w.edges() if abs(e.center().X - (WIN_R_OUT*math.cos(a_out) - WIN_FILLET)) < 3]
mx = 0.0; mxe = None
for e in w.edges():
    for k in range(201):
        p = e.position_at(k/200)
        r = math.hypot(p.X, p.Y)
        if r > mx: mx, mxe = r, e
print(f"   窗口轮廓上采样到的最大极径 = {mx:.3f}  (筒体内壁 R204, 辐板 R205)")
print(f"   -> 窗口轮廓与筒体内壁 R204 的最近间隙 = {204 - mx:.3f} mm")

# ---- 2) 角向材料扫描：辐条宽度 vs 半径 ----
STEP = "/Users/liwuzhan/Desktop/cad tools v2/models/wheel_hub.456d/artifacts/9a970f6b21d4/model.step"
sol = import_step(STEP).solids()[0]
cls = BRepClass3d_SolidClassifier(sol.wrapped)
def inside(x,y,z):
    cls.Perform(gp_Pnt(x,y,z), 1e-6)
    return cls.State() == TopAbs_State.TopAbs_IN

print()
print("=== 2) Z=-20 平面上按半径扫描：辐条/窗口角向分布 ===")
print("    (窗口中心在 0deg，辐条中心在 36deg)")
for r in (90, 110, 130, 150, 165, 175, 180, 182, 190, 200, 203.6, 205, 206):
    n = 2880
    marks = [inside(r*math.cos(2*math.pi*k/n), r*math.sin(2*math.pi*k/n), -20.0) for k in range(n)]
    # 找材料连续段
    segs = []
    k = 0
    if all(marks):
        segs = [(0.0, 360.0)]
    else:
        start = None
        for k in range(n*2):
            cur = marks[k % n]
            if cur and start is None: start = k
            if not cur and start is not None:
                segs.append((start*360/n, k*360/n)); start = None
            if k >= n and start is not None: break
        segs = [(a, b) for a, b in segs if (b-a) < 360]
    desc = []
    for a, b in segs:
        width = 2*r*math.sin(math.radians((b-a)/2)) if (b-a) < 180 else None
        desc.append(f"[{a:6.2f}..{b:6.2f}]deg 弦宽={width:6.2f}" if width else f"[{a:6.2f}..{b:6.2f}]deg (整圈)")
    print(f"  r={r:6.1f}: {len(segs)} 段材料 | " + " ; ".join(desc[:6]))

print()
print("=== 3) 沿 27.37deg 细扫 (窗口外角圆角附近), Z=-20 ===")
ang = math.radians(27.37)
prev = None; start = None
for i in range(0, 4601):
    r = i*0.05
    st = inside(r*math.cos(ang), r*math.sin(ang), -20.0)
    if st != prev:
        if prev is not None:
            print(f"   r {start:7.2f} -> {r:7.2f} : {'MATERIAL' if prev else 'void'}")
        prev = st; start = r
print(f"   r {start:7.2f} -> 230.00 : {'MATERIAL' if prev else 'void'}")
