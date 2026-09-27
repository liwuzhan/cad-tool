"""Independent geometric probe of models/shaft_support.456d.

Goal: measure what the shaft ACTUALLY is (material-agnostic facts only):
  - per-solid volume / bbox / face inventory
  - radial profile r(z) -> detects steps, keyways, grooves, chamfers
  - z-overlap between shaft and bearing -> can anything be attached?

Everything here is measurement, not declaration.
"""

import importlib.util
import math
import sys

from build123d import Align, Box, Pos

from cadparts import deep_groove_bearing, stepped_shaft

PKG = "/Users/liwuzhan/Desktop/cad tools v2/models/shaft_support.456d"

# --- read the contract exactly like src/main.py does ---
spec = importlib.util.spec_from_file_location("_contract", PKG + "/ports.py")
c = importlib.util.module_from_spec(spec)
sys.modules["_contract"] = c
spec.loader.exec_module(c)

shaft = stepped_shaft(c.SPEC)
bearing = deep_groove_bearing(c.BEARING_CODE)

print("=" * 70)
print("PER-SOLID MEASUREMENT")
print("=" * 70)


def describe(name, obj):
    solids = obj.solids()
    print(f"\n--- {name}: {len(solids)} solid(s)")
    for i, s in enumerate(solids):
        bb = s.bounding_box()
        print(
            f"  solid[{i}] volume={s.volume:.4f} mm3  "
            f"size=({bb.size.X:.4f}, {bb.size.Y:.4f}, {bb.size.Z:.4f})  "
            f"bbox_z=[{bb.min.Z:.4f}..{bb.max.Z:.4f}]  faces={len(s.faces())}"
        )
        for j, f in enumerate(s.faces()):
            print(f"        face[{j}] {f.geom_type:<12} area={f.area:10.4f} mm2")


describe("shaft", shaft)
describe("bearing", bearing)

# --- analytic references ---
print("\n" + "=" * 70)
print("ANALYTIC COMPARISON (is it a plain cylinder?)")
print("=" * 70)
R, L = 10.0, 14.0  # nominal d20 x 14 from the declared seat
vol_cyl = math.pi * R * R * L
vol_ring = math.pi * (23.5**2 - R**2) * L
print(f"  plain d20 x 14 solid cylinder      = {vol_cyl:.4f} mm3")
print(f"  plain ring OD47 / ID20 x 14 (bear.)= {vol_ring:.4f} mm3")
print(f"  sum                                = {vol_cyl + vol_ring:.4f} mm3")

shaft_solids = shaft.solids()
shaft_vol = sum(s.volume for s in shaft_solids)
print(f"  MEASURED shaft volume              = {shaft_vol:.4f} mm3")
print(f"  difference vs plain cylinder       = {shaft_vol - vol_cyl:+.6f} mm3")
print(f"  relative difference                = {(shaft_vol - vol_cyl) / vol_cyl * 100:+.6f} %")

# --- radial profile: detects any step / keyway / groove / chamfer ---
print("\n" + "=" * 70)
print("RADIAL PROFILE OF SHAFT  r(z)  via thin-slab boolean intersection")
print("=" * 70)
T = 0.02  # slab thickness
print(f"  (slab t={T} mm; r_eq = sqrt(area/pi); squareness = Xsize/Ysize)")
print(f"  {'z_mid':>7} {'area mm2':>11} {'r_eq mm':>9} {'Xsize':>9} {'Ysize':>9} {'r_eq-10':>10}")
for zc in [0.05, 0.5, 1.5, 3.0, 5.0, 7.0, 9.0, 11.0, 12.5, 13.5, 13.95]:
    slab = Pos(0, 0, zc) * Box(60, 60, T, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    piece = shaft & slab
    if piece.volume <= 1e-12:
        print(f"  {zc:7.2f}  -- empty (no material at this z) --")
        continue
    area = piece.volume / T
    r_eq = math.sqrt(area / math.pi)
    bb = piece.bounding_box()
    print(
        f"  {zc:7.2f} {area:11.4f} {r_eq:9.4f} {bb.size.X:9.4f} {bb.size.Y:9.4f} "
        f"{r_eq - 10.0:+10.5f}"
    )

# --- axial available length: can ANYTHING be attached? ---
print("\n" + "=" * 70)
print("AXIAL / TORQUE-PATH QUESTION")
print("=" * 70)
sb = shaft.bounding_box()
bb_ = bearing.bounding_box()
print(f"  shaft   z range = [{sb.min.Z:.4f} .. {sb.max.Z:.4f}]  (length {sb.size.Z:.4f})")
print(f"  bearing z range = [{bb_.min.Z:.4f} .. {bb_.max.Z:.4f}]  (width  {bb_.size.Z:.4f})")
protrusion = max(0.0, max(sb.max.Z - bb_.max.Z, bb_.min.Z - sb.min.Z))
print(f"  shaft protrusion beyond bearing envelope = {protrusion:.4f} mm")
print(f"  shaft radial size = ({sb.size.X:.4f}, {sb.size.Y:.4f}) mm")

# --- fit / tolerance evidence ---
print("\n" + "=" * 70)
print("FIT / TOLERANCE EVIDENCE (search the declaration for tolerance data)")
print("=" * 70)


def walk(o, path=""):
    hits = []
    if isinstance(o, dict):
        for k, v in o.items():
            hits += walk(v, f"{path}.{k}")
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            hits += walk(v, f"{path}[{i}]")
    else:
        key = path.lower()
        if any(t in key for t in ("tol", "fit", "clear", "interfer", "g6", "h7", "js", "material")):
            hits.append(f"{path} = {o!r}")
    return hits


print("  shaft derived dims :", walk(c.SPEC and __import__("cadparts").shaft_dimensions(c.SPEC)) or "NONE")
print("  shaft ports        :", walk(c.PORTS) or "NONE")

print("\nPROBE DONE")

result = shaft
