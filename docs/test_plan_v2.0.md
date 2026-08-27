# CAD CLI v2.0 测试计划（实践建模）

## 1. 目标与原则

**目标**：通过“从简单到复杂”的真实建模实践，验证 v2.0 的模型包、构建流程与工件管理是否稳定可用，同时评估建模能力边界。  
**原则**：
*   以实践模型为主线，不做纯接口测试
*   每个关键特征后插入 Checkpoint 进行特征级验证
*   每次构建都记录：metrics、渲染元数据、validate 结果
*   失败即记录并回溯到最小复现模型

## 2. 测试环境

*   Python 版本
*   build123d / OCP / pyvista 版本
*   操作系统
*   单位约定（mm）

## 3. 测试流程总览

1.  创建模型包（`cad init`）
2.  编写脚本（feature + Checkpoint）
3.  执行 `cad run` 验证执行与指标输出
4.  执行 `cad commit` 生成 STEP/缩略图/metrics/validate
5.  执行 `cad checkout` / `cad inspect` / `cad render` 复验工件可用性

## 4. Checkpoint 规范（特征级验证）

**使用方式**：每个特征操作完成后立即插入 `Checkpoint` 断言。  
**推荐断言**：
*   体积：`expect_volume` / `expect_volume_increased` / `expect_volume_decreased`
*   拓扑：`expect_faces` / `expect_solids`
*   尺寸：`expect_bbox_size` / `expect_bbox_within`

**验证策略**：
*   每个特征至少 1 个断言
*   布尔运算后必须验证体积变化
*   复杂特征后验证面数变化（趋势即可，不强求唯一值）

## 5. 测试模型梯度（从简单到复杂）

### T1 基础几何（单特征）
**模型**：Box / Cylinder / Sphere  
**目标**：
*   run/commit 成功
*   STEP 可加载
*   缩略图与 JSON 元数据生成
**Checkpoint**：
*   体积与 bbox 尺寸一致性

### T2 基础布尔（双特征）
**模型**：Box + 圆柱孔（减去）  
**目标**：
*   体积下降符合预期
*   面数增加趋势正确
**Checkpoint**：
*   `expect_volume_decreased`
*   `expect_faces_increased`

### T3 多特征堆叠
**模型**：底板 + 孔阵列 + 倒角  
**目标**：
*   多特征顺序执行无错误
*   render 多视图输出稳定
**Checkpoint**：
*   每个特征后验证体积变化
*   倒角后面数趋势变化

### T4 旋转体与壳体
**模型**：旋转体 + hollow  
**目标**：
*   薄壁生成不报错
*   validate 无非流形
**Checkpoint**：
*   体积变化符合预期
*   `expect_solids(1)`

### T5 复杂布尔组合
**模型**：多实体 union/subtract 组合  
**目标**：
*   BRep check 无错误
*   STEP 导出稳定
**Checkpoint**：
*   `expect_solids(1)`
*   体积变化趋势正确

### T6 曲面与放样
**模型**：Loft / Sweep  
**目标**：
*   复杂曲面不崩溃
*   渲染/工件可生成
**Checkpoint**：
*   bbox/体积合理范围

### T7 参数化变化（回归）
**模型**：T3/T4 参数变体（尺寸扩大/缩小）  
**目标**：
*   参数变动后结果可预期
*   体积变化趋势与参数一致
**Checkpoint**：
*   `expect_volume_increased` / `expect_volume_decreased`

### T8 体量压力（复杂度）
**模型**：齿轮或包含大量孔阵列的模型  
**目标**：
*   STEP 导出可靠
*   工件清理策略不误删 HEAD
**Checkpoint**：
*   体积/面数是否异常剧增

## 6. 输出验收清单

每个测试模型需确认：
*   `artifacts/<hash>/model.step` 存在且可加载
*   `artifacts/<hash>/metrics.json` 正确
*   `artifacts/<hash>/thumb_*.png + thumb_*.json` 成对存在
*   `validate.json` 写入并记录错误列表
*   `commits.jsonl` 追加记录正确
*   `manifest.json` HEAD 更新正确

## 7. 缺陷记录模板

*   模型名称 / 版本
*   失败步骤（run/commit/render/checkout）
*   复现脚本片段
*   Checkpoint 失败项
*   错误输出（JSONL）
*   影响评估（是否阻断流程）

## 8. 退出准则

*   T1–T6 全部通过
*   T7 至少 2 组参数变体通过
*   T8 至少 1 个复杂模型通过
*   无阻断性错误（run/commit/checkout 失败）
