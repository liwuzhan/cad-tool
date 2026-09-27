import math
from build123d import import_step
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_State
STEP = "/Users/liwuzhan/Desktop/cad tools v2/models/wheel_hub.456d/artifacts/9a970f6b21d4/model.step"
cls = BRepClass3d_SolidClassifier(import_step(STEP).solids()[0].wrapped)
def scan(ang_deg, z, r0=170.0, r1=215.0, step=0.02):
    a=math.radians(ang_deg); segs=[]; prev=None; start=None; r=r0
    while r <= r1:
        cls.Perform(gp_Pnt(r*math.cos(a), r*math.sin(a), z), 1e-7)
        st = cls.State()==TopAbs_State.TopAbs_IN
        if st != prev:
            if prev is not None: segs.append((prev, round(start,2), round(r,2)))
            prev=st; start=r
        r += step
    segs.append((prev, round(start,2), round(r1,2)))
    return " ".join(f"{'MAT' if f else 'void'}[{a1}..{b1}]" for f,a1,b1 in segs)

for z in (-6.05, -6.5, -7.0, -10.0, -20.0):
    print(f"--- Z={z} ---")
    for ang in (25.0, 27.0, 27.37, 28.0, 29.0, 29.4, 29.8, 31.0, 36.0):
        print(f"   θ={ang:6.2f}: {scan(ang, z)}")
