import math
from build123d import import_step
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_State
STEP = "/Users/liwuzhan/Desktop/cad tools v2/models/wheel_hub.456d/artifacts/9a970f6b21d4/model.step"
cls = BRepClass3d_SolidClassifier(import_step(STEP).solids()[0].wrapped)
def interval(ang_deg, z=-20.0):
    a = math.radians(ang_deg); out=[]
    r = 70.0; prev=None; start=None
    while r <= 95.0:
        st = cls.Perform(gp_Pnt(r*math.cos(a), r*math.sin(a), z), 1e-7) or cls.State()==TopAbs_State.TopAbs_IN
        if st != prev:
            if prev is not None: out.append((prev, round(start,2), round(r,2)))
            prev=st; start=r
        r += 0.02
    out.append((prev, round(start,2), round(r,2)))
    return [(("MAT" if f else "void"), a1, b1) for f,a1,b1 in out]

print("=== 窗口内端两个角附近：材料是否越过凸台 R82 形成残余圆角 ===")
print("  窗口: 内弦 r=76.55, 角点 A=-13deg r=82, B=+29deg r=82, 凸台 R82")
for ang in (-10.0, -11.5, -12.5, -13.0, -13.5, -13.72, -14.0, -16.0,
            26.0, 27.5, 28.5, 29.0, 29.5, 30.0, 32.0):
    print(f"  θ={ang:7.2f}deg : {interval(ang)}")
