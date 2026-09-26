# 自动建模：给该团队的一页行动简报

> 配套详版：`自动建模调研_8节.md`（含全部 8 节、每条断言的 URL 与 ✅/🔶/⚠️ 分级）

## 结论先行

**不需要更好的生成模型，需要"接口可求解 + 结果可验证"。**
你们已有的 288 个命名装配接口（`thread_axis` / `shaft_bore` / `mounting_face` + 数值参数），是本轮调研中发现的**同方向最强工作（ASSEMCAD, arXiv:2607.05123）所给出的答案的核心**。它把这套东西叫 ports + mates + 确定性验证。

## 只做三件事

### 1️⃣ 命名接口 → 可求解的 mate + 确定性位姿变换 + 几何证据验证

- 给每个接口加 mate 语义（同轴 / 贴合 / 插入 / 螺纹副 / 齿轮啮合 / 紧固）
- 实现 `resolve(mates) -> {part: transform}`（起步只需矩阵运算）
- 在真实 B-Rep 上验证：同轴度、贴合面距离、干涉体积

**为什么**：ASSEMCAD 明确论证 "directly generating executable CAD code is **insufficient**"；它的验证管线全部是**纯几何**（接口有效性 / 干涉 / 连通性 / 自由度 / 工程规则）——**不需要仿真器**。这是你们唯一已有 90% 前置条件的方向。

### 2️⃣ helper 库（查表）+ 分层验收（照抄 MUSE）+ 独立裁判

**helper**：`bolt_circle` / `clearance_hole` / `tap_drill` / `bearing_seat` / `gear_pair` / `shaft_step` / `keyway` —— 全查表、全闭式、从标准件库取数，**杜绝 LLM 现算坐标**。
**分层验收**（MUSE 三段漏斗）：L1 代码可执行 → L2 几何有效四项（watertight / manifold / 无自交 / 无重叠）→ L3 你们已有 Checkpoint 数值断言 → L4 逐案 rubric（功能 / 可制造 / 可装配）。
**独立裁判**：验证子代理用不同模型，且**只看几何证据不看生成代码**（CADSmith 用 Sonnet 生成 / Opus 判定，原话 "so it's not just grading its own homework"）。

**为什么**：CADSmith 在 100 条手写 prompt 上，zero-shot 执行率 95% / 平均 CD 28.37 → 全流水线 + 视觉判定 **100% / 0.74**；T3 复杂件去掉视觉后 CD 从 1.42 → 49.68。**提升来自闭环，不来自模型。**

**纪律**：禁止 repair 循环通过"删断言 / 删约束 / 放宽公差"消除报错。AIDL 论文实测记录：LLM 最常见的应对就是"不断删约束直到报错消失"，而 validate-until-correct 会让被删的设计意图**永远回不来**。

### 3️⃣ 钣金做成"可用"，壳体做成"可检查"，明确不做注塑优化

- **钣金**：kerf（MIT）的 `sheet_metal_unfold` / `flat_pattern` 思路 —— K 因子 → 展开长度 → DXF R12；FreeCAD SheetMetal（LGPL-2.1，2026-09 活跃）作参考。**这是唯一"解析可判定"的壳体自动化。**
- **壳体（注塑/压铸）**：只做"生成 + 检查"。拔模角 / 壁厚均匀性 / 筋厚径比 / 最小圆角 → 纯几何断言（几十行）进 L4。商业界的做法本身就是**检查**（CoreTech DesignSim = "DFM **Validations**"）。
- **明确不做**：拓扑优化、模具冷却水道、模流分析。

## 关键核实结论

| 用户的判断 | 核实结果 |
|---|---|
| **"STEP → 可编辑格式对我们没用"** | ✅ **当前成立**。三条支撑：① 你们是正向生成新几何，无存量几何可利用；② Proficiency 类工具输出的是 CATIA/NX/Creo/SW/SE/Inventor **原生特征树**，再翻译成 build123d 是另一个未解问题；③ 成熟方案是服务器级许可 + 人工收尾（Proficiency 自述零件级 94% 自动，剩余靠 Completion Wizard 人工补全）。**触发重估的条件**：开始接"实物/外部 STEP 改型"需求，或开始做仿真前处理（CAD→CAE 几何清理）。 |
| **"齿轮这类参数化生成很容易"** | ✅ 大体成立，且有现成开源：cq_gears（Apache-2.0，渐开线 + 行星 + 锥齿 + 齿条）、py_gearworks（Apache-2.0，2026-09 仍活跃）。⚠️cq_gears 自述"WIP、might be unstable"，需配 Checkpoint 断言；建议两个独立实现交叉验证齿廓。 |
| **"非标件大多是壳体和轴"** | 🔶 **在"几何形状"层面成立**（壳体＝拉伸+抽壳+孔系+筋，轴＝回转+台阶+键槽+螺纹，都是 build123d 十几行）；**在"工程正确性"层面不成立**——壳体的难点是拔模/壁厚/孔边距/装配可达性，轴的难点是配合公差/圆角过渡/螺纹有效深度。**形状便宜，接口贵。** |
| **"没有仿真器也能做自动建模"** | ✅ 成立，且这是最省力的路线。装配正确性检查、约束求解、DFM 规则检查全部是纯几何。但**拓扑优化必须排除**（它本身就是物理仿真）。 |

## 被低估的高价值技巧（纯几何、零物理）

1. **端口位姿求解** —— 把"两个零件怎么对上"从 LLM 空间推理变成矩阵求解
2. **几何约束求解** —— `pip install planegcs`（LGPL-2.1，FreeCAD PlaneGCS 的 Python 绑定，0.8.0）就能把 2D 草图交给求解器。AIDL 实测：约束开启时一次编辑影响所有几何，关闭时"经常产生分离的部件"
3. **层次化复用** —— AIDL 实测：有层次时局部编辑不破坏模型；无层次时"拨号盘移动而孔不动"
4. **接口几何证据验证** —— 唯一能防住"声称同轴但实际偏了 0.3mm"的手段
5. **干涉 / 连通 / 自由度图论检查** —— 毫秒量级，挡住绝大多数"看起来对但装配不上"
6. **钣金 K 因子展开** —— 唯一可直接产出生产文件（DXF）的能力
7. **独立裁判 + 自适应视角渲染** —— CADSmith 自曝 near-miss：F1=0.963、IoU=0.985、**通过全部校验**，但机臂与中心毂之间有缝隙，三个固定视角都看不到

## 明确不要碰

拓扑优化（无物理输入 + 输出网格 + mesh→B-rep 需外部工具）· mesh→B-rep 自动重建（AMRTO 是研究框架 35★、2025-02 最后推送；商业方案服务器级 + 人工收尾；Fusion 的 MeshConvertFeature 是 preview 且官方禁止交付）· 特征识别 / STEP→特征树 · 从零训练 CAD 生成模型（Text-to-CadQuery：微调 7B 需 33h A100，top-1 exact match 仅 69.3%）· 装配序列规划（解决产线问题，不是设计问题）

## 冷水数据（用于校准预期）

- **BlenderLLM 的 CADBench-Wild**（200 条真实论坛样本）：GPT-4o 语法错误率 **28.5%**、Claude-3.5-Sonnet **26.5%**、o1-Preview **17.5%**、Gemini-1.5-Pro **38.0%**；Llama-3.1-8B **65.5%**、Mistral-7B **93.0%**、CodeLLaMA-7B **96.5%**
- **MUSE**：一段清晰的失败级联，从可执行代码 → 合法几何 → 工程可用设计；"even the strongest models achieving limited success on fine-grained engineering criteria"
- **Query2CAD**：首次成功率 53.6%，首轮自省 +23.1%，之后"**没有显著提升**"
- **Chamfer Distance 对装配评测不可靠**（ASSEMCAD 附录 H：信息损失 / 无结构可辨识性 / 无排序一致性 / 表面积偏置）
- **刹车踏板案例**（DJES 18(4):182-190, 2025）：同一载荷与材料下，增材 0.58 kg（−41.3%）/ 压铸 0.70 kg / 机加工 **2.77 kg**（FoS 5.84）。**同一份"优化结果"，三种工艺差 4.8 倍重量。**

## 主要来源

- ASSEMCAD（装配级、ports+mates+62 公理+确定性验证）https://arxiv.org/html/2607.05123
- MUSE（装配级三段漏斗基准，失败级联）https://arxiv.org/abs/2605.28579 · https://dong7313.github.io/muse-benchmark/
- CADSmith（多智能体 + 内核度量 + 独立裁判，有 near-miss 自曝）https://github.com/jabarkle/CADSmith
- AIDL（求解器辅助 DSL；层次/约束消融；"删约束"失败模式）https://ar5iv.labs.arxiv.org/html/2502.09819
- Text-to-CadQuery（代码 > 命令序列；开源模型不认识 CadQuery）https://ar5iv.labs.arxiv.org/html/2505.06507
- CAD-Recode（点云→CadQuery 代码，权重开源）https://github.com/filaPro/cad-recode
- DEFAINE D3.1.1（**KBE 诚实复盘**，五大 limitations）https://itea4.org/project/workpackage/document/download/8208/D3.1.1%20Requirement-product-process%20ontology.pdf
- ToPy（事实停更 4 年）https://github.com/williamhunter/topy
- nTop Automate CLI https://docs.ntop.com/Product-Documentation/ntop/using-ntopcl/getting-started
- AMRTO（TO→B-rep，MIT）https://github.com/rhy-thu/AMRTO
- Proficiency（特征树重建，94% 自动 + 人工补全）https://www.cadinterop.com/en/our-products/proficiency.html
- Backflip AI（mesh→可编辑特征树，$20/月起）https://develop3d.com/ai/backflip-ai-reverse-engineering/
- cq_gears https://github.com/meadiode/cq_gears · py_gearworks https://github.com/GarryBGoode/py_gearworks
- kerf sheet metal（MIT，已封装为 LLM 工具）https://github.com/vul-os/kerf
- FreeCAD SheetMetal（LGPL-2.1，活跃）https://github.com/shaise/FreeCAD_SheetMetal
- planegcs（pip，LGPL-2.1）https://pypi.org/project/planegcs/
- Fusion 360 Gallery Assembly Joint（19,156 joint set / 24 种孔类型）https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/docs/assembly_joint.md
- BlenderLLM / CADBench（语法错误率表）https://github.com/FreedomIntelligence/BlenderLLM
- Zoo Text-to-CAD API（输出 KCL 代码，No usage charge）https://docs.zoo.dev/docs/developer-tools/api/ml/get-a-text-to-cad-response
- 刹车踏板制造约束研究 https://djes.info/index.php/djes/article/download/2098/1092/16303
