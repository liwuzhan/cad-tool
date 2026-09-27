import math, sys
from build123d import import_step, Vector
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_State

STEP = "/Users/liwuzhan/Desktop/cad tools v2/models/wheel_hub.456d/artifacts/9a970f6b21d4/model.step"
s = import_step(STEP)
sol = s.solids()[0]
cls = BRepClass3d_SolidClassifier(sol.wrapped)

def inside(x,y,z):
    cls.Perform(gp_Pnt(x,y,z), 1e-6)
    return cls.State() == TopAbs_State.TopAbs_IN

# --- A) radial scan along +X (window centreline, since windows sit at 0,72,144,...) at several Z
print("=== A) 沿 +X 轴 (窗口中心线) 的径向材料分布 ===")
for z in (0.0, -3.0, -6.5, -20.0, -50.0, -58.0, -62.0, -100.0, -168.0):
    runs=[]; cur=None; start=None
    r=0.0
    while r <= 232:
        st = inside(r,0.0,z)
        if st != cur:
            if cur is not None: runs.append((cur, round(start,2), round(r,2)))
            cur=st; start=r
        r += 0.5
    runs.append((cur, round(start,2), round(r,2)))
    solid_runs = [(a,b) for f,a,b in runs if f]
    print(f"  Z={z:7.1f}: material r-intervals = {solid_runs}")

# --- B) radial scan along the spoke centre (36 deg) ---
print()
print("=== B) 沿辐条中心线 (36deg) 的径向材料分布 ===")
for z in (0.0, -6.5, -20.0, -56.0, -100.0):
    ang = math.radians(36)
    runs=[]; cur=None; start=None
    r=0.0
    while r <= 232:
        st = inside(r*math.cos(ang), r*math.sin(ang), z)
        if st != cur:
            if cur is not None: runs.append((cur, round(start,2), round(r,2)))
            cur=st; start=r
        r += 0.5
    runs.append((cur, round(start,2), round(r,2)))
    print(f"  Z={z:7.1f}: material r-intervals = {[(a,b) for f,a,b in runs if f]}")
