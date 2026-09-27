import math
from build123d import import_step, GeomType
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_ShapeEnum
from OCP.TopoDS import TopoDS
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepAdaptor import BRepAdaptor_Surface

STEP = "/Users/liwuzhan/Desktop/cad tools v2/models/wheel_hub.456d/artifacts/9a970f6b21d4/model.step"
s = import_step(STEP)
sol = s.solids()[0]
sh = sol.wrapped

print("=== BRepCheck_Analyzer ===")
an = BRepCheck_Analyzer(sh)
print("  whole solid valid:", an.IsValid())
exp = TopExp_Explorer(sh, TopAbs_FACE)
i = 0
bad = []
while exp.More():
    f = TopoDS.Face_s(exp.Current())
    sub = BRepCheck_Analyzer(f)
    if not sub.IsValid():
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        bad.append((i, g.Mass()))
    i += 1
    exp.Next()
print("  total faces:", i, " invalid faces:", bad)

print()
print("=== 网格化后 null triangulation 的面 ===")
BRepMesh_IncrementalMesh(sh, 0.5, False, 0.3, True)
exp = TopExp_Explorer(sh, TopAbs_FACE)
i = 0; nulls = []
while exp.More():
    f = TopoDS.Face_s(exp.Current())
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(f, loc)
    if tri is None:
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        c = g.CentreOfMass()
        ad = BRepAdaptor_Surface(f)
        nulls.append((i, round(g.Mass(),4), (round(c.X(),2), round(c.Y(),2), round(c.Z(),2)), ad.GetType().name))
    i += 1
    exp.Next()
for n in nulls: print("  face", n)

print()
print("=== 面积 < 0.5 mm^2 的面（可疑碎片）===")
exp = TopExp_Explorer(sh, TopAbs_FACE)
i = 0; tiny = []
while exp.More():
    f = TopoDS.Face_s(exp.Current())
    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
    if g.Mass() < 0.5:
        c = g.CentreOfMass()
        tiny.append((i, round(g.Mass(),5), (round(c.X(),2), round(c.Y(),2), round(c.Z(),2))))
    i += 1
    exp.Next()
for t in tiny: print("  face", t)
print("  小面总数:", len(tiny))

print()
print("=== 极短边 (< 0.05 mm) ===")
exp = TopExp_Explorer(sh, TopAbs_EDGE)
i = 0; short = []
while exp.More():
    e = TopoDS.Edge_s(exp.Current())
    try:
        L = BRep_Tool.Degenerated_s(e)
    except Exception:
        L = False
    g = GProp_GProps(); BRepGProp.LinearProperties_s(e, g)
    if g.Mass() < 0.05:
        short.append((i, round(g.Mass(),6)))
    i += 1
    exp.Next()
print("  短边数:", len(short), short[:20])
