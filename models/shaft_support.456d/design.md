# Shaft support: declared mates, checked before geometry - 装配设计文档

## 装配目标
<!-- 功能、总体包络、必须保留的非标设计上下文 -->

## 坐标与接口

- 世界坐标：X 长、Y 宽、Z 高。
- 每个实例使用唯一 label；所有 Pos/Rot 显式写出。
- 标准件按 cadparts 命名接口定位，不从 STEP 或图片猜接口。

## 组件表

| 实例 label | 来源 | 数量 | 接口/位姿 | BOM/采购描述 |
|---|---|---:|---|---|
| | 非标 / cadparts | | | |

## 装配校验

- [ ] result 为保留独立实体的 Compound
- [ ] expect_solids(组件实体总数)
- [ ] expect_bbox_size(总体 X, Y, Z)
- [ ] cad validate / inspect / review 通过
