"""本包自建件的接口契约 —— 只做声明，不建模。

这是探针包：用来检验「声明与几何是否一致」这件事，今天的工具链能不能自己发现。
`central_bore` 声明的是 ⌀10.0。
"""

PORTS = {
    "plate": [
        {
            "id": "central_bore",
            "type": "cylindrical_bore",
            "role": "中心定位孔，配 ⌀10 轴",
            "frame": {"origin_mm": [0.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]},
            "dimensions_mm": {"diameter": 10.0, "length": 8.0},
        },
        {
            "id": "mounting_face",
            "type": "planar_face",
            "role": "安装基准面",
            "frame": {"origin_mm": [0.0, 0.0, -4.0], "axis": [0.0, 0.0, -1.0]},
            "dimensions_mm": {"face_size": 60.0},
        },
        {
            "id": "bolt_hole_px_py",
            "type": "clearance_hole",
            "role": "安装通孔",
            "frame": {"origin_mm": [22.0, 22.0, 0.0], "axis": [0.0, 0.0, 1.0]},
            "dimensions_mm": {"diameter": 4.5},
        },
        {
            "id": "bolt_hole_mx_py",
            "type": "clearance_hole",
            "role": "安装通孔",
            "frame": {"origin_mm": [-22.0, 22.0, 0.0], "axis": [0.0, 0.0, 1.0]},
            "dimensions_mm": {"diameter": 4.5},
        },
        {
            "id": "bolt_hole_px_my",
            "type": "clearance_hole",
            "role": "安装通孔",
            "frame": {"origin_mm": [22.0, -22.0, 0.0], "axis": [0.0, 0.0, 1.0]},
            "dimensions_mm": {"diameter": 4.5},
        },
        {
            "id": "bolt_hole_mx_my",
            "type": "clearance_hole",
            "role": "安装通孔",
            "frame": {"origin_mm": [-22.0, -22.0, 0.0], "axis": [0.0, 0.0, 1.0]},
            "dimensions_mm": {"diameter": 4.5},
        },
    ],
}
