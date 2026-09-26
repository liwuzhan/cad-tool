# 自动建模（Automatic / Generative CAD Modeling）真实版图调研

**调研日期**：2026-09-26
**调研对象**：插件体积受限、无物理仿真器、已有 288 型号命名装配接口标准件库、LLM 子代理写 build123d 脚本的团队

## 证据分级说明

| 标记 | 含义 |
|---|---|
| ✅已验证 | 我实际抓取并读到来源正文（README / 论文摘要 / 官方文档 / API 参考 / GitHub API 元数据） |
| 🔶推论 | 由已验证事实推导，属判断而非来源结论 |
| ⚠️未验证 | 取不到来源正文，或仅有二手摘要，**不可当事实用** |

⚠️ 时间提示：本次检索命中大量 2026 年文献（arXiv 编号 26xx、文档日期 2026-08）。即当前时点已到 2026 年 9 月，下述"近年"包含 2025–2026 年工作。

---

## 1. LLM → CAD 程序合成（重点）

### 1.1 生成的是"程序"还是"几何"？两条路线的实际分野

✅已验证 —— **近两年的主流工作几乎全部转向"生成程序/代码"，而不是"直接生成几何"**：

| 工作 | 输出表示 | 来源 |
|---|---|---|
| **CAD-Recode** (ICCV 2025) | 点云 → **CadQuery Python 代码**；基座 Qwen2-1.5B，保留原 tokenizer，仅加一层线性层 | [README](https://raw.githubusercontent.com/filaPro/cad-recode/main/README.md) |
| **Text2CAD** (NeurIPS'24 Spotlight) | 文本 → **命令序列**（DeepCAD 式 sketch-and-extrude 参数向量） | [README](https://raw.githubusercontent.com/SadilKhan/Text2CAD/main/README.md) |
| **CAD-MLLM** | 命令序列 → 可导出 STEP / PLY；数据集 Omni-CAD | [README](https://raw.githubusercontent.com/CAD-MLLM/CAD-MLLM/main/README.md) |
| **Query2CAD** | 文本 → **可执行 FreeCAD 宏（Python）** | [README](https://raw.githubusercontent.com/akshay140601/Query2CAD/main/README.md) |
| **Text-to-CadQuery** | 文本 → **CadQuery 代码**，明确主张"跳过中间命令序列" | [ar5iv 正文](https://ar5iv.labs.arxiv.org/html/2505.06507) |
| **BlenderLLM** | 指令 → **bpy 脚本**（Blender Python） | [README](https://raw.githubusercontent.com/FreedomIntelligence/BlenderLLM/main/README.md) |
| **AIDL** (MIT/UW, CGF) | LLM → **求解器辅助的层次化 DSL**（约束由几何约束求解器解） | [ar5iv 正文](https://ar5iv.labs.arxiv.org/html/2502.09819) |

Text-to-CadQuery 的作者把这件事讲得很清楚（✅已验证，我读到正文）：命令序列"不是预训练模型能直接处理的任务特定序列，必须先转成 CAD vector 才能出模型，这要求从零训练模型并增加不必要的流水线复杂度"；而 CadQuery 是"纯 Python 包、无需外部软件依赖"；且"现代大模型本来就会写 Python"。
🔗 https://ar5iv.labs.arxiv.org/html/2505.06507

**两条路线的实际差别（🔶推论，基于以上已验证事实）**：

1. **可编辑性**：命令序列是"任务特定中间表示"，要执行必须先有专门的解码器把它变成几何，且序列本身不是人能改的代码；代码路线产出的就是可读、可改、可 diff、可进 git 的参数化程序——与你们 build123d 流水线同构。
2. **参数可控性**：AIDL 论文直接做了消融实验（✅已验证）：关掉约束后，"缩放需要逐个调整每个部件"，且"经常产生分离的部件"；关掉层次后，局部编辑会破坏模型（拨号盘移动而孔不动）。也就是说，**约束与层次这两个语言特性，而不是模型规模，决定了生成结果能不能被工程化复用**。
3. **失败模式不同**：代码路线把"几何错误"转化成"可执行的报错"，从而可以进入 repair 循环；命令序列路线的错误往往直接表现为几何不合法。

⚠️未验证：**我没有检索到任何以 build123d 为目标语言发表的论文或专门微调权重**。现有一手来源中出现的 DSL 是 CadQuery、FreeCAD 宏、OpenSCAD、KCL(Zoo)、bpy。这是检索结果，不等于不存在。

### 1.2 有没有可复用的开源实现或权重？

✅已验证的开源现状（用 GitHub API 元数据核实了 pushed_at / license）：

| 项目 | 权重 | 代码 | 许可 | 最近推送 | 备注 |
|---|---|---|---|---|---|
| CAD-Recode | ✅ [v1](https://huggingface.co/filapro/cad-recode) / [v1.5](https://huggingface.co/filapro/cad-recode-v1.5) | ✅ [filaPro/cad-recode](https://github.com/filaPro/cad-recode) | 见仓库 | — | 另有关联工作 [cadrille](https://github.com/col14m/cadrille)（Apache-2.0，186★，2026-09 仍在推） |
| Text2CAD | ✅ [HF checkpoint](https://huggingface.co/datasets/SadilKhan/Text2CAD) | ✅ [SadilKhan/Text2CAD](https://github.com/SadilKhan/Text2CAD) | 见仓库 | — | 数据准备/训练/推理代码全放 |
| Text-to-CadQuery | ⚠️ 论文称 release，未在本轮核实权重 | ✅ [Text-to-CadQuery](https://github.com/Text-to-CadQuery/Text-to-CadQuery)（115★，2026-08 推送） | 仓库未标 license | 2026-08 | 170k text–CadQuery 标注数据 |
| CADSmith | — | ✅ [jabarkle/CADSmith](https://github.com/jabarkle/CADSmith)（35★，2026-06） | **无 license** | 2026-06 | 多智能体 + 内核度量 + 视觉判定，可读性最好 |
| MUSE 基准 | — | ✅ [dong7313/muse](https://github.com/dong7313/muse)（MIT） | MIT | 2026-05 | 装配级评测 |
| BlenderLLM | ✅ [HF 权重](https://huggingface.co/FreedomIntelligence/BlenderLLM) | ✅ [BlenderLLM](https://github.com/FreedomIntelligence/BlenderLLM) | 见仓库 | — | Qwen2.5-Coder-7B 微调，bpy 脚本 |
| CAD-MLLM | ❌ **未发布** | 部分 | — | — | README 明确：**Inference Code / Training Code 均未勾选**，只放了 Omni-CAD 数据集与评测指标代码 |
| DeepCAD | — | 官方仓库本轮 API 查询失败（⚠️未验证）；检索到社区镜像 [MeitarShechterLeo/DeepCAD](https://github.com/MeitarShechterLeo/DeepCAD) | — | — | 2021 老工作，作为数据集仍被广泛复用 |
| AIDL | ⚠️ 未核实 | ⚠️ 未核实 | — | — | 论文为语言设计研究，2D 实验 |

**结论（🔶推论）**：**没有"装上就能用"的成品**。开源的是研究代码（Demo/复现脚本）+ 研究权重（1.5B 级、"输出 CadQuery"），不是可维护的工程 SDK。真正可直接借鉴的是**架构与闭环方法**，不是模型本身。

### 1.3 评测指标能说明"工程上可用"吗？

**不能。这是本轮调研最重要的发现之一。**

✅已验证的证据链：

1. **成功率本身很低且波动大**。Query2CAD（GPT-4 Turbo）：首次尝试成功率 **53.6%**，加入自省循环后提升 **23.1%**，但"后续迭代对正确设计的准确率没有显著提升"。[README](https://raw.githubusercontent.com/akshay140601/Query2CAD/main/README.md)
2. **论文报告的"高准确率"是字符串指标**。Text-to-CadQuery 报告 top-1 **exact match 69.3%**（best model，Mistral-7B + LoRA）、Invalid Rate 1.32%、CD 下降 48.6%（[ar5iv](https://ar5iv.labs.arxiv.org/html/2505.06507)）。top-1 exact match 是 token 级匹配，**代码字符串对 ≠ 几何正确 ≠ 可制造**。同一论文的评测里还有一项"Gemini 2.0 Flash 视觉判断"，基座 Text2CAD Transformer 得分 58.80%——即**用 VLM 当裁判，最好的基线也只有约六成被认为"看起来是同一个东西"**。
3. **Chamfer Distance 在装配场景被证明不可靠**。ASSEMCAD 专门写了附录《On the Unreliability of Chamfer Distance for Assembly Evaluation》，论证 CD 在点集投影下存在信息损失、缺乏装配结构可辨识性、缺乏排序一致性、存在表面积偏置（✅已验证为该论文 HTML 的章节目录与标题）。[arXiv:2607.05123](https://arxiv.org/html/2607.05123)
4. **有专门的"工程可用性"基准，结论是失败级联**。MUSE（HK PolyU，2026）用三段漏斗评测：代码可执行 → 几何有效（watertight/manifold/无自交/无重叠四项 OCCT 检查）→ 设计意图（按逐案 rubric 评 functionality / manufacturability / assemblability，由 VLM 裁判，并做人标注验证）。结论原文："**a clear failure cascade from executable code to valid geometry and finally to engineering-ready design, with even the strongest models achieving limited success on fine-grained engineering criteria**"。[MUSE 摘要](https://arxiv.org/abs/2605.28579) / [基准首页](https://dong7313.github.io/muse-benchmark/)
5. **最"能打"的系统靠的是闭环，不是模型**。CADSmith 在 100 条手写 prompt 上：zero-shot 执行率 95%、平均 CD 28.37；全流水线 + 视觉判定 **执行率 100%、CD 中位 0.48 / 均值 0.74**；去掉视觉后 T3 复杂件的平均 CD 从 1.42 涨到 49.68（38×）。并且作者**主动公开了一个反例**：四轴机架（T3_019）F1=0.963、IoU=0.985，通过全部校验，但"中心毂与机臂之间有小缝隙，内核度量和三个固定视角都没发现"。[README](https://raw.githubusercontent.com/jabarkle/CADSmith/main/README.md)

🔶推论：**指标层面没有"工程可用"的证明**。可以说明"方法在进步"，不能说明"能交给产线"。对你们的实际含义是：**别用论文指标做验收标准，要自建你们自己的验收（内核度量 + 多视角渲染 + 接口断言）**。

### 1.4 多零件/装配级生成

✅已验证：

- **ASSEMCAD**（上海 AI Lab 等，2026-07）是本轮找到的**与你们架构最接近的工作**。它把装配生成显式建模为"工程流水线"而非"代码生成问题"：
  - 中间表示 `Assembly Specification = (P, M, A)`：**typed parts（含 factory + 参数 + ports）**、**typed mates**、**engineering axioms**；
  - **62 条工程公理**，分 10 个 MECE 类目（Foundations 5 / Constraints 5 / Kinematic 5 / Bearings 4 / Gears 9 / Structural 7 / Power-Shafts 3 / Sequencing 6 / Fastening 12 / Hinges 6），41 条从装配教科书用三阶段 LLM 抽取、21 条为覆盖库中存在但语料缺失的族而合成；
  - **port- and mate-based CAD 装配库**：确定性 mate 变换 + 用真实 B-Rep 几何证据验证声明的接口；
  - 确定性验证管线检查：接口有效性、干涉一致性、图连通性、自由度约束、工程规则合规；
  - 论文里有一段直接打脸代码中心路线的话："**directly generating executable CAD code is insufficient**"；并明确对比："AssemCAD improves practical reliability by coupling an assembly-oriented component library, a curated engineering axiom system, and a deterministic verification pipeline"。
  - 相关链接：[arXiv:2607.05123](https://arxiv.org/html/2607.05123) · [Semantic Scholar 条目](https://www.semanticscholar.org/paper/ASSEMCAD%3A-Production-Ready-CAD-Assembly-Generation-Dong-Zou/e56ca094677e3af7dd8410d14df5e3ad0236c0a2)
  ⚠️未验证：**是否开源我未核实**（论文正文我读到的是方法章节，未见到代码仓库链接）。
- **MUSE** 同样以"complex, editable B-Rep **assemblies**"为对象，配套 Design Specification 与逐案 rubric。[摘要](https://arxiv.org/abs/2605.28579)
- **CAD-MLLM** 的定位是"多模态条件 CAD 生成"，属**单实体**层面，不做零件间关系。[README](https://raw.githubusercontent.com/CAD-MLLM/CAD-MLLM/main/README.md)

🔶推论：**"装配级 LLM 生成"在 2026 年已经从"没人认真做"变成"有人做对了方向"**，而且做对的那些人采取的方案——**命名端口 + 类型化配合 + 确定性变换 + 几何证据验证**——正是你们标准件库已经有的东西。你们缺的不是端口，是**基于端口的装配求解与验证闭环**。

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| CAD-Recode / cadrille 权重 | **需外部调用 / 仅供了解**：1.5B 级模型，需 GPU 与 Python 环境，插件内不可能内置；对你们的价值是"点云/扫描件 → CadQuery 代码"这条入口，而不是日常建模路径 |
| Text-to-CadQuery 数据集与结论 | **直接可用（作为方法论）**：它验证了"直接生成可执行 Python CAD 代码 > 生成中间命令序列"，这是你们已经在走的路；可考虑把 170k text–CadQuery 对当领域语料参考（⚠️许可未标，商用前须核实） |
| CADSmith 架构 | **直接可用（强烈推荐）**：多智能体 + 内核精确度量 + 独立裁判（生成用 Sonnet、判定用 Opus 以避免"自己批自己作业"）+ 三级难度基准。**它是你们现有 pipeline 最值得逐行抄的工程实现**（⚠️仓库无 license，只能学结构不能拷代码） |
| MUSE 三段漏斗 | **直接可用（作为验收设计模板）**：代码可执行 → 几何有效（4 项 OCCT 布尔检查）→ 设计意图 rubric。你们已有 Checkpoint 数值断言，缺"几何有效性四项"和"rubric 层" |
| ASSEMCAD 的 ports + mates + 公理 | **直接可用（架构蓝本）**：把 62 条公理的思想降到你们能维护的 10–20 条（螺纹副、轴承座同轴、齿轮中心距、紧固件过孔间隙、装配可达性…） |
| 论文指标（CD / exact match） | **不适用**：不可作为验收依据 |
| CAD-MLLM 推理/训练代码 | **不适用**：未发布 |

---

## 2. 拓扑优化作为"可调用工具"

### 2.1 开源可用的 Python 实现（含维护状态核实）

✅已验证（GitHub API 元数据）：

| 工具 | 仓库 | 最近推送 | ★ | 许可 | 状态判断 |
|---|---|---|---|---|---|
| **ToPy** | [williamhunter/topy](https://github.com/williamhunter/topy) | **2022-08-31** | 577 | NOASSERTION | 🔶**事实停更 4 年**。README 自述："我 2005 年开始写、2009 年写完，所以 stable release 只支持 Python 2；master 是 unstable 但可在 Python 3 跑"。功能：compliance（刚度）、机构综合、热传导，2D/3D |
| TopOpt-MMA-Python | [arjendeetman/TopOpt-MMA-Python](https://github.com/arjendeetman/TopOpt-MMA-Python) | **2025-10-11** | 55 | 无 license | 仍在维护，但定位是"GCMMA-MMA-Python 在拓扑优化中的**用法示例**"（教学/参考实现） |
| DTU TopOpt 官方页 | [topopt.mek.dtu.dk](https://www.topopt.mek.dtu.dk/apps-and-software/topology-optimization-codes-written-in-python) | — | — | — | 页面存在，列出"用 Python 写的拓扑优化代码" ⚠️该页正文为 JS 渲染，我未取到具体代码清单与链接，**不引用具体仓库名** |

ToPy 的输入形态（✅已验证 README）：TPD 文本文件或 Python Config 字典，必填项包括 `PROB_TYPE / ETA / DOF_PN / VOL_FRAC / FILT_RAD / P_FAC / ELEM_K / NUM_ELEM_X/Y/Z / NUM_ITER / FXTR_NODE_X / FXTR_NODE_Y / LOAD_NODE_Y / LOAD_VALU_Y`——即**载荷节点、约束节点、体积分数**这三类东西就是它的全部物理输入。

### 2.2 商业工具是否可被外部程序调用

✅已验证：

- **nTop（nTopology）**：有 **nTop Automate (ntopcl)** 命令行。官方文档给出实际调用形式：
  `"C:/Program Files/nTopology/nTopology/ntopcl.exe" -i "C:\nTopCLI_101\CLI-numtext" -i 7mm -i 7mm -i 7mm SampleFile.ntop`
  即**把一个 .ntop notebook 当函数调用，参数和输出路径从命令行注入，输出可写成 JSON**。
  🔗 [Getting Started](https://docs.ntop.com/Product-Documentation/ntop/using-ntopcl/getting-started) · [Commands](https://docs.ntop.com/Product-Documentation/ntop/using-ntopcl/commands) · [nTop Core / Python Package / C++ API 章节](https://docs.ntop.com/Product-Documentation/ntop/using-ntopcl/getting-started)
- **Altair Inspire**：存在 **Inspire Python API** 参考文档（✅文档页存在：[help.altair.com/inspire/.../python_api_c.htm](https://help.altair.com/inspire/jp_jp/topics/inspire/reference/python_api_c.htm)；⚠️我读的是日文版目录页，未逐条核对可调用范围）。
- **Autodesk**：Fusion 有"Generative Design"工作区并在教学材料中列为 manufacturing methods（⚠️帮助页正文抓取为空，仅命中 URL `GD-MFG-METHODS`；**不据此断言其 API 细节**）。APS/Design Automation 的产品页存在（⚠️未核实其对 generative design outcome 的暴露程度）。

🔶推论：商业 TO 工具**存在外部调用面**（至少 nTop 是明确的 CLI + 参数注入），但**许可与部署形态都是服务器级**，不可能进插件。

### 2.3 ⚠️关键问题：输出的 mesh 能不能自动变回可编辑 B-rep？

**这是决定 TO 对你们是否有用的唯一门槛。答案是："学术上已解，工业上仍是半自动，且不在你的流水线里。"**

✅已验证：

1. **问题的定义被学术界明确承认**。清华大学 AMRTO（CMAME 2024-12-24 在线，2025 年 435 卷 117673）的官方报道原文：
   - "目前最流行的拓扑优化方法所产生的最优拓扑**缺乏显式的、CAD 友好的表达形式**"；
   - "经过常规平滑化后处理，拓扑优化结果**通常以三角面片网格表示，编辑困难且缺乏参数控制**，传统的人工重构过程繁琐复杂且严重依赖设计人员的经验"；
   - "主流商业软件的重构方法**鲁棒性差**、生成模型的 NURBS 面片和控制点数量过多"。
   - AMRTO 声称实现**全自动**输出"光滑、显式、精确、且易于编辑的 B-rep"，并在运行效率、NURBS 面片数、控制点数、文件大小、鲁棒性、输入网格容忍度、碎面数等指标上**优于 Rhino 7 / HyperMesh 2021 / Design X 2022 / nTopology 5.3.2 / Geomagic Studio 12 / Abaqus 6.14 / COMSOL 6.2**。
   - 代码：**Python 代码（PYTOCAD）与测试模型**开放在 [rhy-thu/AMRTO](https://github.com/rhy-thu/AMRTO)（**MIT**，35★，2025-02 最后推送）与 [zenodo 14381998](https://zenodo.org/records/14381998)。
   - 来源：[3D科学谷报道](http://www.3dsciencevalley.com/?p=38539)（中文，含论文信息与代码链接）；论文 DOI `10.1016/j.cma.2024.117673`
2. **商业上这条路已经被产品化，但是"半自动"**：[CAD Interop / ITI Proficiency](https://www.cadinterop.com/en/our-products/proficiency.html) 声称"**the only solution on the market that rebuilds an editable parametric feature tree in the target CAD**"，客户数据：Marelli 零件级 **94%** 自动、装配级 67%，瑞士钟表集团 **72%** 参数化恢复。**关键**：它自己的流程图写着 "automated translation → target X% parametric → **Completion Wizard 引导式人工补全** → 100% reusable"。也就是说**剩下的部分是人工**。
3. **Autodesk 在 Fusion API 里给了 mesh→B-rep 的编程入口，但明确是 preview**：[MeshConvertFeature.bodies Property](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_MeshConvertFeature_bodies.htm) 返回 `BRepBodies`，版本 "Introduced in version July 2025"，且页面顶部警告："This functionality is provided as a **preview** of intended future API capabilities… you should **never deliver any programs that use any preview capabilities**"。
4. **新玩家（AI 路线）**：Backflip AI 的 Mesh-to-CAD 引擎，"reverses engineer a part into fully editable parametric CAD, with a feature tree"，支持 3D 扫描/STL/mesh；但官方定位是 "excels at **moderate-complexity 3-axis CNC milled and turned parts**"，Fast 模式几分钟、Thinking 模式更久，以 Autodesk Fusion 插件与网页形式提供，**$20/月起**，宣称把逆向工程从约 $1500/件 降到约 $10/件。[DEVELOP3D 报道](https://develop3d.com/ai/backflip-ai-reverse-engineering/)

🔶推论（**给你们的直接结论**）：mesh → B-rep 在 2026 年**不是"没有工具"，而是"没有一个能进你插件的工具"**：
- AMRTO 最接近"自动"，但它是论文附带的 Python 研究框架（35★、最后一次推送 2025-02），依赖重网格化、广义摩托车图、调和映射、多分辨率 NURBS 控制等一整套算法，**不是 pip 可维护的库**；
- 商业产品（Proficiency / Backflip）能力真实，但**它们是服务器/云/付费产品，且 Proficiency 自认需要人工收尾**；
- Fusion 的 API 入口是 preview，Autodesk 自己说不要用于交付。

### 2.4 它需要什么输入？没有仿真器的团队从哪来这些输入？

✅已验证（ToPy README）：载荷节点与值、约束节点、体积分数、惩罚因子、滤波半径、单元数。

🔶推论：**这恰好是问题的核心——TO 的输入不是几何参数，而是物理量。** 而 TO 的意义恰恰在于"用 FEA 把材料搬到该去的地方"，**它本身就是物理仿真**。

对你们的实际含义：
- 如果做 TO，就必须持有"载荷/边界条件/材料"三件套，而这三件套要么来自仿真（你们没有）、要么来自规范/经验公式（那就是查表，不是优化）、要么来自用户手填（那就把问题推给了用户）；
- 更糟的是，**你们即使算出 TO 结果，还要跨过 2.3 那道 mesh→B-rep 门槛**才能回到 build123d。

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| ToPy | **不适用**：事实停更 4 年，stable 仅 Py2，且需要你自备物理输入 |
| TopOpt-MMA-Python | **仅供了解**：教学参考实现 |
| nTop CLI / Altair Inspire API | **需外部调用**：能力真实、有编程接口，但服务器级许可，且要用户/上游提供载荷 |
| AMRTO (PYTOCAD) | **仅供了解 / 有条件外部调用**：MIT 许可、是唯一"全自动 TO→B-rep"的公开可读实现，可作为"如果哪天必须做 TO"的技术储备；但它进不了插件 |
| Autodesk MeshConvertFeature | **需外部调用，且不建议**：preview API，官方禁止用于交付 |
| 整体（TO as a tool） | **不适用（当前阶段）**：你们缺的不是优化器，是**几何生成 + 接口正确性**。TO 的收益（减重）只在已有载荷谱的场景兑现，而你们明确没有仿真器。**给壳体加筋的收益，用规则式（等距筋阵列 + 壁厚/拔模规则）能拿到 80%，成本是 TO 的 2%** |

---

## 3. 参数化/模板式生成（KBE 传统）

### 3.1 KBE 那一波为什么没普及？——找到了诚实的复盘

这是本轮调研**最有战略价值的一份来源**：欧盟 ITEA3 DEFAINE 项目交付物 **D3.1.1 Requirement-product-process ontology**（TU Delft 撰写，v1.5，2022-05-02，Public）。
🔗 https://itea4.org/project/workpackage/document/download/8208/D3.1.1%20Requirement-product-process%20ontology.pdf

✅已验证（我把 PDF 下载后逐字提取原文，以下均为原文引述）：

**（a）时间被开发本身吃掉**
> "From the experience gleaned in the past projects, **majority of the time is invested in KBE application (or design automation) development and setting up the simulation workflows**. Consequently, little or no time is available to perform design space exploration (DOE and full-blown MDO), which promises the most benefits in front-loading…"

**（b）"知识模型 → 代码"这一步完全没有自动化**
> "Since neutral language knowledge model does not exist, developers take on the role of converting knowledge model into source code. In the MOKA approach that is practiced today, **this process is completely manual (i.e., no automation scripts or software programs are available to (even partly) generate the code)**."

**（c）三大结构性缺陷（原文 3.4 Summary: Limitations of current KBE application development）**
> i. "The encapsulation of knowledge within source code is largely a **manual process**… tedious manual approach can lead to human-errors."
> ii. "Generally, the KBE application **source-code tends to be big**. When programmed manually, only the developer is conversant with information within the source code… the KBE application becomes a **black-box**."
> iii. "In case formal knowledge model is not developed before (manual) code generation, **permanent knowledge loss can occur if the domain expert and the programmer leave the organization**."
> iv. "**Till date, industry-accepted neutral-language knowledge model schema is not available**… This is a **major bottleneck**."
> v. "Even if a neutral language knowledge model schema were to be developed, **no mechanism exists to automatically convert the formal knowledge models (UML/MML diagrams) into neutral language knowledge model schema**."

**（d）三个信任场景，每一个都在讲同一件事：别人看不懂你的自动化，所以不信任它**
> Scenario 1（有知识工程师）："the domain expert is **not able to see or understand how knowledge has been implemented** … there is a **lack of trust** in the KBE application… gives the domain expert a feeling of exclusion, causing **insufficient participation**… which could **hinder adoption of KBE technology**."
> Scenario 2（小团队，一人多角色）："**no formal models to compare the code with**… the developer will be prone to making errors."
> Scenario 3（专家自己写代码）："when a domain expert leaves the company… **the knowledge contained in the mind of the expert is lost**… It is also **hard to find out where the knowledge is in the vast amount of application source code**."
> 以及一句几乎是为 LLM 时代写的判词："**the fact that the application came to the correct conclusion does not mean it did so by deriving the correct facts.**"

🔶推论（**这一节对你们的意义**）：KBE 死在**"知识 → 代码"的人工翻译成本**上，加上**黑箱导致的组织不信任**上。LLM 恰好把第一项的成本砍掉一个数量级——**你们现在做的事情，本质上是"用 LLM 替掉 KBE 里最贵的那一环"**。但请注意：
- （c-ii）（c-iii）**没有因为 LLM 而消失**：LLM 生成的 build123d 脚本同样是"只对生成者透明的黑箱"。这就是为什么 CADSmith 那种"用另一个模型当独立裁判 + 内核度量"的闭环不是锦上添花，而是**KBE 教训的直接对策**；
- （d）**更没有消失**：如果你们的子代理生成的脚本，人类工程师看不懂为什么这个孔在这个位置，他们会像 2005 年的 KBE 用户一样不信任它。**可追溯性（哪条规则决定了这个尺寸）比生成能力更重要**。

补充来源（⚠️未取到正文，仅作索引）：Verhagen / Bermell-Garcia 等《A critical review of Knowledge-Based Engineering: An identification of research challenges》，*Advanced Engineering Informatics* 26(1)，DOI `10.1016/j.aei.2011.06.004`（[ACM DL 条目](https://dl.acm.org/doi/abs/10.1016/j.aei.2011.06.004)；开放版 [HAL hal-00649053](https://hal.science/hal-00649053v1/document)，本轮 PDF 抓取被工具限制阻断，**未读正文**）。

### 3.2 商业实现实际能自动生成什么

✅已验证（我读到的是 Siemens 官方 PDF 与 Dassault 官方课程 PDF 的检索命中）：
- **NX Knowledge Fusion**：Siemens 官方文档《NX programming and customization》与 NX6 案例 PDF 均将其列为编程/定制手段；检索摘要中出现客户原话 "We selected NX Knowledge Fusion because it has great potential"。🔗 [NX programming and customization (Siemens PDF)](https://www.plm.automation.siemens.com/en_gb/Images/nx%20programming%20and%20customization%20fs%20W%203_tcm642-4564.pdf) · [NX6 design brochure (PDF)](https://www.plm.automation.siemens.com/legacy/flash/NX6/nx_design_br_W3.pdf)
- **CATIA EKL**：Dassault 官方培训目录中有专门的 EKL 课程 PDF。🔗 [3DS EKL course (PDF)](https://www.3ds.com/fileadmin/Training/PDF/V6courses/CATIA/EKL.pdf)
- **Creo Pro/PROGRAM**：PTC 官方 refdocs（Creo Parametric Toolkit 用户手册）中检索到 `ProResetToModelItem()` 等 API 条目。🔗 [PTC tkuse_Creo10000.pdf](https://www.ptc.com/support/-/media/support/refdocs/Creo_Parametric/10,-d-,0/tkuse_Creo10000.pdf)

⚠️未验证：这三个系统**具体能自动生成到什么复杂度**、以及各自的语言表达力边界，我没有取到一手正文（以上是官方 PDF 的存在性 + 检索摘要命中，未逐页阅读能力矩阵）。**不要据此向团队断言"NX 能做到 X"**。

🔶推论：这类商业 KBE 的共性能力是**规则驱动的参数联动 + 特征模板实例化 + 变体配置**，其天花板由（a）规则库的覆盖度与（b）几何内核的稳健性共同决定——而不是由"是否智能"决定。

### 3.3 Product configurator / master model / configurable component 的现状

⚠️**本轮未取到可直接引用的一手来源来支撑这一小节的现状判断。**为避免编造，我只给可验证的相邻事实：
- MOKA（Methodology and tools Oriented to Knowledge-based engineering Applications）作为方法论在 ✅已验证的 DEFAINE 文档中被反复引用为"今天仍在实践的做法"，并同时被指出其"知识模型→代码"环节完全手工；
- 另有 ✅已验证的学术产出在该方法上继续工作：Chalmers 学位论文 [research.chalmers.se/publication/544934](https://research.chalmers.se/publication/544934/file/544934_Fulltext.pdf)（⚠️PDF 未能取正文）。

🔶推论：KBE 的"方法论层"（MOKA、知识建模、可配置主模型）没有死，死的是"把它做成通用平台"的商业尝试；它现在的存活形态是**垂直行业里的配置器**（电梯、工程机械、船舶内装），而这些行业共有的特征是：**接口标准化 + 规则稳定 + 变体数量有限**——这三条你们的标准件库恰好都满足。

### 3.4 齿轮/轴这类"参数即生成"：有没有成熟**开源代码**可直接借鉴？

✅已验证（GitHub API 元数据 + README 正文）：

| 项目 | 能力 | 许可 | ★ | 最近推送 |
|---|---|---|---|---|
| **[meadiode/cq_gears](https://github.com/meadiode/cq_gears)** | CadQuery 渐开线齿轮生成器。README 列出：直齿、斜齿、人字齿、内齿圈（含斜/人字）、**行星轮系**、直齿与斜齿**锥齿轮**、**齿条**。API 形态：`SpurGear(module=1.0, teeth_number=19, width=5.0, bore_d=5.0)` → `cq.Workplane('XY').gear(spur_gear)`；实例只预算参数与曲线，build 时才成实体；并暴露 `r0`（节圆半径）等参数供**参考/中心距计算**。README 自述"**Work in progress… Might be unstable, but somewhat usable**" | **Apache-2.0** | 162 | 2024-12-27 |
| **[GarryBGoode/py_gearworks](https://github.com/GarryBGoode/py_gearworks)** | Python 齿轮生成器 | **Apache-2.0** | 76 | **2026-09-24（活跃）** |
| FreeCAD 生态 | ⚠️ 齿轮工作台存在但本轮未核实具体仓库 |

**轴的"车削特征"**：⚠️本轮**没有**检索到专门的"开源轴类零件生成源码"。🔶推论：轴的本质是**回转体 + 台阶 + 退刀槽 + 键槽 + 螺纹 + 中心孔**，用 build123d 的 `Cylinder`/`revolve` + `Mode.SUBTRACT` 就是十几行，**没有值得引入的外部依赖**；真正的价值不在"怎么画轴"，而在"轴的**接口数值**从哪来"（见第 8 节）。

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| DEFAINE 的 KBE 复盘 | **直接可用（战略级）**：它精确预言了你们会踩的三个坑（黑箱不可验证、知识随人流失、缺中立知识模型）。建议把它的五条 limitations 当作你们 pipeline 的验收清单 |
| NX KF / CATIA EKL / Creo PRO/PROGRAM | **仅供了解**：思路（规则驱动参数联动 + 模板实例化）就是你们 build123d 已经实现的；这些是闭源服务器级产品，**不可调用** |
| MOKA / master model 方法论 | **仅供了解**：适合在你们做"标准件 family 的参数化定义"时参考术语与结构，不带来工程收益 |
| cq_gears | **直接可用（需小幅移植）**：Apache-2.0，渐开线数学 + 行星/锥齿/齿条已解，可直接移植到 build123d（同 OCCT 内核，几何运算可平移；CadQuery API 调用需改写）。**注意 README 自述不稳定，必须配你们的 Checkpoint 断言** |
| py_gearworks | **直接可用（参考实现）**：Apache-2.0，2026-09 仍在维护，可作为 cq_gears 的交叉验证来源（两个独立实现的齿廓互相对齐，是最便宜的正确性证据） |
| 轴 | **不适用（不需要外部工具）**：自己写，成本极低 |

---

## 4. 壳体（housing）的自动建模

### 4.1 注塑件 / 压铸件 / 钣金：自动化程度差异巨大

🔶推论（贯穿本节的核心判断）：**钣金是特例，注塑/压铸不是。**理由是几何可判定性：
- 钣金的**设计对象**（折弯线、展开图、K 因子）与**制造对象**（下料 DXF、折弯序）之间存在**解析映射**，因此可自动化、可验证、可出图；
- 注塑件的关键设计规则（拔模角、壁厚均匀性、加强筋厚径比、圆角）在**几何上是可检查的但不可解析生成的**——它依赖分型面/脱模方向的选取，而分型面本身是一个需要判断的全局决策。

### 4.2 钣金：有没有可调用的开源工具

✅已验证：

| 项目 | 内容 | 许可 | ★ | 最近推送 |
|---|---|---|---|---|
| **[shaise/FreeCAD_SheetMetal](https://github.com/shaise/FreeCAD_SheetMetal)** | "A simple sheet metal workbench for FreeCAD"；仓库含 `SheetMetalUnfoldCmd.py` 等展开命令实现 | **LGPL-2.1** | 343 | **2026-09-20（活跃）** |
| **[vul-os/kerf](https://github.com/vul-os/kerf)** | MIT 许可的 CAD 项目（自述"Free, MIT-licensed CAD for every discipline"），其 `kerf-cad-core/src/kerf_cad_core/sheet_metal.py` 模块**已把钣金展开做成 LLM 可调用的工具**：`sheet_metal_flange` / `sheet_metal_unfold` / `sheet_flat_pattern`。README 给出 `BA = angle_rad × (bend_radius + k_factor × thickness)`，输出**最小 DXF R12 展开图**（外形为 layer "0" 的闭合 POLYLINE、折弯线为 layer "BEND" 的 LINE） | **MIT** | 11 | 2026-08-11 |

🔗 [FreeCAD SheetMetal 仓库](https://github.com/shaise/FreeCAD_SheetMetal) · [FreeCAD SheetMetal 官方文档页](https://wiki.freecad.org/SheetMetal_Workbench) · [kerf sheet-metal 文档](https://raw.githubusercontent.com/vul-os/kerf/refs/heads/main/docs/sheet-metal.md)

🔶推论：**钣金是本轮调研中"自动化程度最高 + 开源最完整 + 与 LLM 工具调用最贴合"的一个领域**。kerf 的做法尤其值得抄：**它把"K 因子 → 展开长度 → DXF 实体"整条链封装成 3 个函数 + 一个 JSON 参数表，直接暴露给 LLM 当 tool spec**。这正是你们"轻量辅助函数"策略的现成范本。

### 4.3 注塑件设计自动化（拔模/壁厚/加强筋规则）有没有可复用实现

✅已验证存在但均为商业产品：
- **CoreTech DesignSim**：定位是"Real-Time Injection Molding **DFM Validations**"，并已作为 **Siemens NX 的插件**发布。🔗 [CoreTech 官方新闻](https://www.moldex3d.com/news/coretech-system-to-officially-launch-designsim-delivering-real-time-injection-molding-dfm-validations/) · [Engineering.com 报道](https://www.engineering.com/coretech-announces-designsim-for-dfm-validation-in-siemens-nx/)
- **Cimatron**：官方发布"简化冷却系统设计"的功能。🔗 [Cimatron 新闻](https://www.cimatron.com/de/news/cooling-system-design)
- **Maya HTT / SimForm Mold Cooling**：加入 Polygonica 网格库（说明这条链同样在跟网格打交道）。🔗 [Engineering.com](https://www.engineering.com/maya-htt-adds-polygonica-mesh-library-to-simform-mold-cooling/)
- 学术侧：有一篇 2025 年会议论文《Integrating manufacturing constraints in existing generative design workflows: **wall thickness and cooling channel** considerations》（Cambridge，DOI 前缀 `S2732527X26104179`，⚠️PDF 抓取被工具限制阻断，**未读正文**）。🔗 [链接](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/9D48FF3010CDB18E5254298E77BF3C39/S2732527X26104179a.pdf/integrating-manufacturing-constraints-in-existing-generative-design-workflows-wall-thickness-and-cooling-channel-considerations.pdf)

⚠️**未检索到任何开源、可 pip 安装、可被外部程序调用的"注塑件 DFM 规则引擎"**。这是明确的信息缺口，不是"我没找到所以不存在"的断言。

🔶推论：**注塑件自动化在商业上做的是"检查（validation）"而不是"生成（generation）"**——DesignSim 的名字就是 DFM **Validations**。检查比生成便宜得多，也可靠得多。**这对你们是个好消息**：你们不需要"自动设计注塑壳体"，你们只需要"自动检查生成的壳体是否违反了拔模/壁厚/筋厚规则"，而后者是纯几何运算，可以在 build123d/OCP 里直接实现。

### 4.4 模具/冷却水道自动生成的现状

✅已验证：Cimatron 有"冷却系统设计"简化功能；Maya HTT SimForm Mold Cooling 走网格路线（见上）。
⚠️未验证：这些工具的自动化程度（是"自动布线"还是"辅助手动布线"）我未取到可引用的能力描述；**不做断言**。

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| 钣金（kerf / FreeCAD SheetMetal） | **直接可用（最高优先级）**：MIT/LGPL 许可、活跃维护、K 因子展开与 DXF 输出已被封装成 LLM 工具形式。若你们的标准件库要覆盖钣金件，**这是本轮唯一"拿来就能进流水线"的自动建模能力** |
| 注塑件 DFM 规则 | **需外部调用 or 自研轻量**：无开源引擎；但"拔模角/壁厚/筋厚比/最小圆角"都是纯几何可判定项，建议**自研成 Checkpoint 断言**（几十行），而不是引入商业 DFM |
| 压铸件 | ⚠️未验证：本轮未找到独立的压铸自动化来源。🔶推论：与注塑同构（拔模 + 壁厚 + 圆角），可用同一套规则断言 |
| 模具/冷却水道自动生成 | **仅供了解**：商业闭源，且强依赖模流仿真，与"无仿真器"约束冲突 |
| 整体（壳体自动建模） | **部分直接可用**：钣金壳＝可用；注塑/压铸壳＝**"能生成 + 能检查"而非"能优化"**。🔶对"非标件大多是壳体和轴"这一判断的核实结论见第 6 节末尾 |

---

## 5. 装配级生成（不只单零件）

### 5.1 "给定功能需求，自动生成装配体"有没有工作？

✅已验证：

- **ASSEMCAD（2026）** —— 本轮的答案主体。详见 1.4。它的贡献恰恰是宣告"直接生成 CAD 代码不足以构造机械上有效且可复用的装配"，并给出**公理 + 端口/配合 + 确定性验证**的方案。🔗 [arXiv:2607.05123](https://arxiv.org/html/2607.05123)
- **MUSE（2026）** —— 评测对象就是 **B-Rep 装配**，指标体系里明确含 Assemb**lability**。🔗 [arXiv:2605.28579](https://arxiv.org/abs/2605.28579)
- **经典约束式装配建模**（ASSEMCAD 的 related work 归纳，✅已验证为其正文表述）：装配通过几何配合约束表示，并推理**欠约束/过约束/完全约束**配置、干涉与剩余自由度；文献可追到 Anantha et al. 1996、Zou et al. 2022。

### 5.2 与"装配序列规划（ASP）"的区别与现状

🔶推论（基于以上已验证事实的区分）：
- **装配生成（assembly synthesis / configuration design）**：输入功能需求 → 输出**有哪些零件、什么接口、怎么配合**。是"从无到有"。
- **装配序列规划（ASP）**：输入**已给定的零件集合与几何** → 输出**装配/拆卸的次序**。是"给定集合求排列"。
- 前者是设计问题（开放、需要工程语义），后者是规划问题（组合优化，可用拆卸法、AND/OR 图、遗传算法等）。

✅已验证的 ASP 现状证据：ASSEMCAD 的 related work 指出，已有工作研究"B-Rep-based automatic mate prediction"与"physically feasible assembly planning, often through **assembly-by-disassembly**"，并列出 Tian et al. 的相关工作；同时明确这些方法"**typically assume that component geometries are already given** and focus on recovering or predicting assembly relations"。
另：检索到 2026 年 ISARC 论文《A Decision-Oriented Synthesis of AI-Based Assembly Sequence Planning for Construction Automation》（[PDF](https://www.iaarc.org/publications/fulltext/ISARC2026_1298.pdf)），⚠️未读正文；以及一篇 IEEE 综述的中文摘要片段"all the approaches examined are geared toward specific operational planning cases"（⚠️未验证，不作为事实）。

🔶推论：**ASP 对你们当前阶段价值低于装配生成**——因为 ASP 的输入（已定几何的零件集合）你们还在努力产出，而 ASP 解决的是产线问题不是设计问题。

### 5.3 有没有开源实现？

✅已验证（GitHub API 元数据）：

| 项目 | 内容 | 许可 | ★ | 最近推送 |
|---|---|---|---|---|
| **Fusion 360 Gallery Dataset — Assembly Joint Data** | **19,156 个 joint set / 32,148 个 joint / 23,029 个零件**。每个 joint set 含：B-Rep（.smt + .step）、mesh（.obj，带 face/halfedge 分组）、**图表示（NetworkX node-link JSON，节点＝B-Rep 面/边，含 JoinABLe 用的特征与 UV-Net 的 UV-grid 特征）**、joint JSON（含 Fusion 的 7 种 joint 类型：Rigid / Revolute / Slider / Cylindrical / PinSlot / Planar / Ball，各带自由度、运动轴、限位、rest state）、**contacts（装配态下间距 ≤0.1mm 的接触面对）**、**holes（用 Autodesk Shape Manager 特征识别工具标注，含 24 种孔类型、直径、长度、原点、方向、所属面/边）**、`transform`（每个 body 从局部坐标到装配态的刚体变换）。🔗 [assembly_joint.md](https://raw.githubusercontent.com/AutodeskAILab/Fusion360GalleryDataset/master/docs/assembly_joint.md) | 见仓库 | — | — |
| **[AutodeskAILab/JoinABLe](https://github.com/AutodeskAILab/JoinABLe)**（CVPR 2022） | 从实体模型**预测参数化 CAD joint**（bottom-up assembly of parametric CAD joints） | 未标 | 120 | **2022-04**（🔶事实停更） |
| **[deGravity/automate](https://github.com/deGravity/automate)**（SIGGRAPH Asia 2021） | AutoMate：**自动配对（automatic mating）CAD 装配**的数据集与学习方法 | 未标 | 59 | **2024-01**（🔶基本停更） |
| **AutoMate 论文** | Jones et al., *AutoMate: a dataset and learning approach for automatic mating of CAD assemblies*, ACM TOG 40(6):227, DOI `10.1145/3478513.3480562`（✅由 AIDL 论文参考文献列表验证） | — | — | — |

**⚠️关键缺口**：ASSEMCAD 是否开源，**我未核实**。它的方法（ports + mates + 62 公理 + 确定性验证）是公开的，但代码可得性未知。

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| ASSEMCAD 架构 | **直接可用（复制架构，不是复制代码）**：它的 `Assembly Specification = (typed parts, typed mates, axioms)` 与你们的"命名装配接口 + 数值参数"几乎同构。**你们应该做的是把 ports 升级为 mates，并加确定性变换与验证** |
| Fusion 360 Gallery Assembly Joint 数据 | **需外部调用 / 数据资产**：19k joint set 是公开数据（⚠️需自行核实 license），可用于**离线校验你们的 mate 求解器**（拿真人的 joint 定义当 ground truth），但不能进插件 |
| JoinABLe / AutoMate | **仅供了解**：均停更 2–4 年，且它们的任务是"给定几何预测配合"（逆向），不是"给定需求生成装配"（正向） |
| ASP（装配序列规划） | **不适用（当前）**：解决的是产线问题，你们的设计问题还没闭环 |
| 装配级 LLM 生成整体 | **直接可用（架构级）**：这是本轮"最应该抄"的一块。**核心 takeaway：装配级不能用"生成一大段 CAD 代码"来做，必须"先生成结构化装配规格 → 再确定性求解 → 再用几何证据验证"** |

---

## 6. 特征识别 / STEP → 可编辑格式（核实用户判断）

### 6.1 正式名称与现状

✅已验证，它有三个互相重叠的正式名称与各自的技术社区：

1. **Feature Recognition（特征识别）**：从纯几何（B-rep/网格）中识别出工程特征（孔、槽、凸台、倒角）。
   - 商业产品实证：Autodesk Inventor 应用商店有 **Feature Recognition** 应用（[apps.autodesk.com 条目](https://apps.autodesk.com/invntor/en/Detail/Index?appLang=en&id=9172877436288348979&os=Win32_64)）。
   - 数据实证：Fusion 360 Gallery 的 holes 标注明确写着"we use the **Autodesk Shape Manager feature recognition tool** to identify and label holes in each part"，并给出 **24 种孔类型**枚举（Round/Counterbore/Countersunk/Tapered × Blind/Through × 平底/锥底/球底/阶梯底）。🔗 [assembly_joint.md](https://raw.githubusercontent.com/AutodeskAILab/Fusion360GalleryDataset/master/docs/assembly_joint.md)
2. **CAD Feature Tree Reconstruction（特征树重建）**：把"冻结的 B-rep"重建成"可编辑的特征树 + 草图 + 约束 + 参数"。
   - 商业实证（✅已验证）：[CAD Interop / ITI Proficiency](https://www.cadinterop.com/en/our-products/proficiency.html) 自述是"**the only solution on the market that rebuilds an editable parametric feature tree in the target CAD, where a STEP, IGES or Parasolid export only delivers frozen B-Rep geometry**"；覆盖 CATIA V5 / NX / Creo / SolidWorks / Solid Edge / Inventor 六者的**双向**读写，并搬运 PMI / GD&T。客户量化：Marelli 零件级 **94% 自动**、装配级 67%、迁移周期 6 周→2 周、每项目省 700–1,200 小时；Wärtsilä 18 个月迁移 5,200 零件、省 up to 20,000 工程小时；瑞士钟表集团 up to **72% 参数化恢复、98% IP 保全、×20 重建时间**。
   - **但同页也写着它的真实边界**：流程分两段，第一段"fully automated"，第二段"semi-automatic"，处理"features arriving as **NPF (Non-Parametric Feature) or NPB (Non-Parametric Body)**"，靠 **Completion Wizard**（内嵌于目标 CAD 的插件）做"guided delete & reattach"，目标是把"X% parametric"变成"100% ReUsable"。**即：X% 自动 + 人工补全。**
   - 学术实证：**eCAD-Net: Editable Parametric CAD Models Reconstruction from Dumb B-Rep Models Using Deep Neural Networks**，*Computer-Aided Design*（[ScienceDirect 条目](https://www.sciencedirect.com/science/article/abs/pii/S0010448524001337)，⚠️仅条目，未读正文）。
3. **Reverse Engineering（逆向工程）**：从点云/扫描/网格重建 CAD。见第 1 节的 CAD-Recode、cadrille，以及第 2 节的 Backflip。

### 6.2 它真正的应用场景是什么？

✅已验证（来自厂商自述，属于一手但带营销色彩，需打折读取）：

- **大规模多 CAD 迁移 / 并购后整合**："mass multi-CAD migration, post-M&A consolidation and long-term preservation of native data beyond 15 years"；
- **长期归档与知识产权保全**："Preservation of design intent and key parameters at the heart of the CAD intellectual property protection strategy"；
- **异构供应链互操作**：A400M 项目"3 source formats → 1 Catia V5 deliverable"；
- **几何质量审计**：配套 CADIQ 做"conversion 前后的几何与参数质量验证"。
🔗 均为 [Proficiency 产品页](https://www.cadinterop.com/en/our-products/proficiency.html)

✅已验证的另一条应用线（**仿真前处理 / CAD-CAE 集成**）：
- 《Toward fully automated CAD-CAE integration through **design feature recognition** and small language models》，*Journal of Computational Design and Engineering*（JCDE），DOI `10.1093/jcde/qwaf137`（[论文 PDF](https://academic.oup.com/jcde/advance-article-pdf/doi/10.1093/jcde/qwaf137/66002278/qwaf137.pdf)）⚠️**PDF 抓取被工具限制阻断，未读正文；仅据标题判断方向**。
- 另有一篇 MDPI 论文的表格标题为"**CAD reconstruction pathways for manufacturing RE and simulation readiness**"（🔶据标题，把"制造逆向工程"与"仿真就绪"并列为两条路径；⚠️未读正文不作断言）。🔗 [MDPI Appl. Sci. 16(3):1229](https://www.mdpi.com/2076-3417/16/3/1229/pdf?version=1769334525)

✅已验证（**零件复用 / 降本**这条应用线的商业化）：
- Backflip 的采访给出很强的一手数字："until now, turning any physical part into a usable CAD model has meant **hours of skilled reverse-engineering work at a typical cost of $1,500 or more per part**… its latest tools can reduce that figure to roughly **$10**… in **one to five minutes**"，CEO 原话"Why when something breaks, [factory staff] have to start by reverse engineering it"。🔗 [DEVELOP3D](https://develop3d.com/ai/backflip-ai-reverse-engineering/)

🔶推论：**这个方向的真实价值锚点是"存量实物 → 可编辑数字资产"的一次性转换成本**，而不是"设计新零件"。它的客户画像是：有大量历史图纸/实物/异构 CAD 要盘活的大型制造企业；场景是**迁移、归档、复用、审计、仿真前处理**。

### 6.3 用户的判断"对我们没用"是否成立？

**成立，但有三个前置条件，且有一个例外场景。**（以下为 🔶推论，基于上述 ✅已验证事实）

**判断成立的理由**：
1. **收益侧为零**。特征识别的价值来自"存量几何的再利用"。而你们的工作流是**从需求生成新几何**——你们的零件不是从 STEP 逆向来的，是从标准件库 + LLM 脚本正向生成的。**没有存量，就没有可识别的特征。**
2. **技术侧对不上**。你们需要的是"可编辑的参数化程序"（build123d 代码），而特征识别的输出是"目标 CAD 的原生特征树"（Proficiency 只输出 CATIA/NX/Creo/SW/SE/Inventor 六家的原生格式）。**把 CATIA 特征树再翻译成 build123d 脚本这一步，没有现成工具**，等于把问题后移。
3. **成本侧不划算**。这条路成熟方案是服务器级商业许可（Proficiency）+ 人工收尾（Completion Wizard），或云服务（Backflip $20/月起）。对"插件体积受限"的团队，它**根本进不了插件**，只能作为外部服务——而你们没有需要它服务的存量数据。

**三个让判断失效的前置条件**（即：满足任一条，就该回头重估）：
- (a) **你们开始接"客户给定实物/STEP 文件，要求改型"的需求**。这是 6.2 里 Backflip 描述的场景（"when something breaks"），也是 Proficiency 的主战场；
- (b) **你们需要做仿真前处理**（几何清理、特征简化、中面抽取）——注意：**这条是"特征识别"应用线里对你们最可能变得相关的一条**，因为它是"CAD 进 CAE"的必经步骤，而你们即便不装仿真器，也可能需要给用户导出可仿真的几何；
- (c) **你们的"标准件库"需要吸收外部供应商的 3D 模型**（供应商往往只给 STEP，而你们需要它是参数化的、带接口的）。

**一个例外场景**：**你们自己的零件需要"降级复用"**。比如某个非标壳体改型时，希望从上一个版本的 STEP 自动恢复成 build123d 脚本。🔶但这个场景下更便宜的解法不是特征识别，而是**"从第一天起就保留脚本"**——也就是你们已经在做的"程序化建模 + 版本历史"。**你们用"保留源码"绕过了整个特征识别问题**，这正是程序化 CAD 相对交互式 CAD 的结构性优势。

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| 特征识别（通用） | **不适用**：无存量几何可利用，且输出格式与 build123d 不同构 |
| Proficiency / ITI | **需外部调用（但现阶段无需求）**：真实能力（零件级 94% 自动）+ 真实的半自动边界（Completion Wizard 人工补全）。服务器级 Windows + MySQL + 六家 CAD 安装，进不了插件 |
| Backflip / AI 逆向 | **需外部调用（观望）**：$20/月起，Fusion 插件 + 网页，强在"moderate-complexity 3-axis CNC milled and turned parts"。若你们接到实物改型需求，这是最省事的入口 |
| Autodesk MeshConvertFeature | **不适用**：preview，官方禁止交付 |
| eCAD-Net 类学术工作 | **仅供了解** |
| CAD-CAE 特征识别（JCDE 2025/2026） | **仅供了解，但要记住**：这是"特征识别什么时候会重新变得有用"的答案——当你们要做仿真前处理时 |
| **用户判断核实结论** | **✅ 判断成立**：在"正向生成新几何 + 无存量数据 + 插件体积受限"这三条约束下，STEP→可编辑格式这条路对你们**当前无用**。**触发重估的条件**是"开始接实物/外部 STEP 改型需求"或"开始做仿真前处理" |

---

## 7. 生成式设计的评价与可靠性（泼冷水）

### 7.1 有没有**独立**的评测？

✅已验证，有，而且是 2026 年集中出现的：

1. **MUSE**（HK PolyU + Curvature Flow，2026-05，v2 2026-06）—— 三段漏斗：**代码可执行 → 几何有效（watertight / manifold / 无自交 / 无重叠，四项 OCCT 布尔检查全过）→ 设计意图（逐案 rubric 评 Functionality / Manufacturability / Assemblability，Gemini-3.1-Pro 当 VLM 裁判，并用人工标注验证裁判可靠性）**。核心结论原文："**a clear failure cascade from executable code to valid geometry and finally to engineering-ready design, with even the strongest models achieving limited success on fine-grained engineering criteria**"。数据开放：[HF dataset](https://huggingface.co/datasets/dongxiaoyu/MUSE)，代码 MIT。🔗 [摘要](https://arxiv.org/abs/2605.28579) · [基准页](https://dong7313.github.io/muse-benchmark/) · [排行榜](https://dong7313.github.io/muse-benchmark/leaderboard.html)
2. **CADBench**（BlenderLLM 配套，2024-12）—— 500 条模拟样本 + 200 条**来自网络论坛的真实样本**；维度指标：`Attr.`（属性）、`Spat.`（空间）、`Inst.`（指令遵循）、`E_syntax`（语法错误率）。🔗 [BlenderLLM README](https://raw.githubusercontent.com/FreedomIntelligence/BlenderLLM/main/README.md)
   **这张表本身就是最有力的冷水**（✅已验证）：
   | 模型 | CADBench-Sim Avg ↑ | CADBench-Wild Avg ↑ | Wild 语法错误率 ↓ |
   |---|---|---|---|
   | BlenderLLM（专门微调） | 0.748 | 0.664 | 3.5% |
   | o1-Preview | 0.687 | 0.583 | 17.5% |
   | GPT-4-Turbo | 0.589 | 0.515 | 24.5% |
   | Claude-3.5-Sonnet | 0.593 | 0.489 | 26.5% |
   | GPT-4o | 0.565 | 0.444 | 28.5% |
   | Gemini-1.5-Pro | 0.468 | 0.380 | 38.0% |
   | Qwen2.5-Coder-7B-Instruct | 0.353 | 0.310 | 37.0% |
   | LLaMA-3.1-8B-Instruct | 0.094 | 0.120 | 65.5% |
   | Mistral-7B-Instruct-V0.3 | 0.016 | 0.028 | 93.0% |
   | CodeLLaMA-7B-Instruct | 0.003 | 0.014 | 96.5% |
   **注意**：这是 **Blender bpy 脚本**任务（不是机械 CAD），但结论对"直接让通用 LLM 写 CAD 脚本"这件事高度可迁移——**通用顶级模型的语法错误率在 15%–38%，小型开源模型基本不可用**。
3. **CADSmith 基准**（CMU，2026）—— 100 条手写 prompt，三档难度（T1 图元 50 / T2 工程件 25 / T3 复杂件 25），**所有参考脚本由人手写、执行并目视检查，不是 LLM 生成**；指标用**绝对毫米空间的 CD/F1/IoU（带 ICP 对齐）**，即"尺寸精度算数，不只是形状相似"。🔗 [README](https://raw.githubusercontent.com/jabarkle/CADSmith/main/README.md)
4. **ASSEMCAD 的 AssemBench** + 专章论证 CD 在装配评测上不可靠。🔗 [arXiv:2607.05123](https://arxiv.org/html/2607.05123)
5. **Text2CAD / Text-to-CadQuery** 用的是 DeepCAD 派生分布 + CD + VLM 判断。🔗 [ar5iv](https://ar5iv.labs.arxiv.org/html/2505.06507)

### 7.2 常见失败模式（全部有一手来源）

| 失败模式 | 证据 |
|---|---|
| **代码语法/API 错误** | CADBench-Wild 语法错误率 3.5%（专门微调）～96.5%（通用小模型）——[来源](https://raw.githubusercontent.com/FreedomIntelligence/BlenderLLM/main/README.md) |
| **执行成功但几何不合法** | MUSE 第二段四项 OCCT 检查（watertight/manifold/无自交/无重叠）就是为此设的；CAD-MLLM 提出专门指标 **SegE（Segment Error）、DangEL（Dangling Edge Length，只被一个面约束的悬边长度）、SIR（自交率）、FluxEE（通量包围误差）**，并给出示例"蓝线表示只被一个面约束的悬边"——[CAD-MLLM README](https://raw.githubusercontent.com/CAD-MLLM/CAD-MLLM/main/README.md) |
| **看起来对、指标好，但有微小结构性缺陷** | CADSmith 自曝 T3_019 四轴机架 F1=0.963、IoU=0.985、**通过全部校验**，但"arms 与 central hub 之间有小缝隙，内核度量与三个固定视角都发现不了"；并指出这是"需要自适应视角选择或更高分辨率裁剪才能捕获的 **near-miss**"——[README](https://raw.githubusercontent.com/jabarkle/CADSmith/main/README.md) |
| **修正循环退化成"删掉设计意图"** | AIDL 论文原文：当错误被报给 LLM 时，"**the most common response is to try removing constraints or structures until the error goes away**"；由于采用 validate-until-correct 模式，"**the removed design intent (e.g. rectangle rotation) is never returned to the model**"——[ar5iv](https://ar5iv.labs.arxiv.org/html/2502.09819) |
| **自省循环收益递减** | Query2CAD 原文："With subsequent refinements, the accuracy of the correct designs **did not improve significantly**"（首次 53.6%，首轮自省 +23.1%，之后停滞）——[README](https://raw.githubusercontent.com/akshay140601/Query2CAD/main/README.md) |
| **LLM 幻觉不存在的 API** | AIDL 论文："In cases where the LLM attempted to do this, it **hallucinated a non-existent constraint like `Rotate`**"——[ar5iv](https://ar5iv.labs.arxiv.org/html/2502.09819) |
| **开源模型根本不认识这个 DSL** | Text-to-CadQuery 原文："most open-source models—including Gemma, Qwen, Mistral, and Llama (**including the well-regarded Llama 3 series**)—fail to generate valid CadQuery, often **not recognizing the syntax or semantics of the language at all**"；Llama 3 系列在"你知不知道 CadQuery"这类探针问题上"**consistently failed both questions, exhibiting strong hallucinations**"——[ar5iv](https://ar5iv.labs.arxiv.org/html/2505.06507) |
| **评测指标本身误导** | ASSEMCAD 附录 H 论证 CD 的四宗罪：点集投影信息损失、缺乏装配结构可辨识性、缺乏排序一致性、表面积偏置——[arXiv](https://arxiv.org/html/2607.05123) |

### 7.3 "看起来对但不能制造/不能装配"的公开案例

✅已验证（**制造约束如何改写生成结果**，这是本轮最干净的一个量化案例）：
《Influence of Manufacturing Constraints on Generative Design Outcomes: A Lightweight Automotive Brake Pedal Case Study》，Diyala Journal of Engineering Sciences 18(4):182-190, 2025-12，DOI `10.24237/djes.2025.18413`。
用**同一套载荷、约束、材料**在 Autodesk Fusion 360 里对同一刹车踏板跑三种制造约束：
- **增材（AM）**：1.36 kg → **0.58 kg（−41.3%）**，仍满足 FoS ≥ 2.0；
- **压铸**：均值 **0.70 kg**（需遵守拔模与壁厚规则）；
- **机加工**：**最重 2.77 kg**，但刚度最高、FoS = 5.84。
论文原话："the final result is **highly dependent upon manufacturing constraints** during the design phase"；"Manufacturing limits impact geometric design results by **limiting feasible forms** while varying mechanical component functionalities"。
🔗 [DJES PDF](https://djes.info/index.php/djes/article/download/2098/1092/16303)

🔶推论：**同一份"优化结果"在三种工艺下差 4.8 倍重量。**这说明"生成式设计给出了漂亮几何"与"这个几何能被制造"之间的距离不是最后一公里的打磨，而是**结果本身的量级差异**。你们的场景（壳体 + 轴 + 标准件）里，这个距离主要体现为：拔模角、壁厚、刀具可达性、螺纹有效深度、以及**装配时的可达性/工具空间**。

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| MUSE 三段漏斗 | **直接可用（验收设计模板）**：建议照抄"代码可执行 → 4 项几何有效性 → 逐案 rubric"三层，把你们现有 Checkpoint 从"数值断言"升级为"分层验收" |
| CADBench 的 `E_syntax` 维度 | **直接可用（监控指标）**：把"生成脚本首次执行成功率"和"语法/API 错误率"作为你们子代理的**常驻仪表盘指标** |
| CADSmith 的 near-miss 记录 | **直接可用（为何需要多视角 + 自适应裁剪）**：三个固定视角会漏掉小缝隙。建议渲染视角由被生成特征的位置驱动，而非固定 |
| AIDL 的"删约束"失败模式 | **直接可用（对抗设计）**：你们的 repair 循环必须**禁止 LLM 通过删除设计意图来消除报错**（例如：删掉 `Checkpoint` 断言、删掉同心约束、放宽公差）。这是最容易被忽视的失败模式 |
| Query2CAD 的自省停滞 | **直接可用（预期管理）**：别指望"多迭代几轮就好了"。要优先改**输入的结构化程度**（规格 → 代码），而不是加迭代轮数 |
| ASSEMCAD 对 CD 的批评 | **直接可用（别用 CD 验收装配）**：装配验收要用接口/干涉/连通/自由度，不是形状相似度 |
| 刹车踏板案例 | **直接可用（给决策者的论据）**：如果有人说"让 AI 优化一下壳体"，把 4.8× 重量差和它背后的工艺假设摆出来 |
| 整体（可靠性） | **结论：当前技术不能"免验证"使用。**所有能打的系统（CADSmith 100% 执行率）都是**因为闭环**才达标 |

---

## 8. 轻量化落地路径（最重要的一节）

### 8.1 可以外部调用的技术（不占插件体积）

| 能力 | 形态 | 证据 | 对你们的价值 |
|---|---|---|---|
| **Zoo Text-to-CAD API** | REST，返回 **KCL 代码**（`code` 字段）或几何，`output_format` 支持 `step` / `stl` / `glb` / `gltf` / `obj` / `ply` / `fbx`；计费标注 **"No usage charge"**；异步任务有 `queued/uploaded/in_progress/completed/failed` 状态机 | ✅ [API 参考](https://docs.zoo.dev/docs/developer-tools/api/ml/get-a-text-to-cad-response) · [Zoo API 总览](https://docs.zoo.dev/docs/developer-tools/api) · [ML API](https://zoo.dev/machine-learning-api) | **最有价值的"外部大脑"**：不占体积、有免费额度、**输出是代码不是网格**（所以结果可读、可改、可进你们的版本系统）。另有 **Agent API（Zookeeper）** 与 **File Format API（格式互转）** |
| **Zoo Engine API / File Format API** | REST + WebSocket；Engine 做几何创建与编辑；File Format 做 CAD 格式互转 | ✅ [同上](https://docs.zoo.dev/docs/developer-tools/api) | 若你们需要 STEP/STL/glTF 互转而不想引入重依赖，这是外部化的选项 |
| **nTop Automate（ntopcl）** | CLI，`ntopcl.exe -i <in> -i <param> ... file.ntop`，输出可写 JSON | ✅ [nTop 文档](https://docs.ntop.com/Product-Documentation/ntop/using-ntopcl/getting-started) | 仅在真的要做隐式建模/晶格/TO 时才需要；服务器级许可 |
| **AMRTO（PYTOCAD）** | Python 代码，MIT | ✅ [GitHub](https://github.com/rhy-thu/AMRTO) · [Zenodo](https://zenodo.org/records/14381998) | "TO 结果 → B-rep"的储备方案 |
| **CAD-Recode / cadrille 权重** | HF 模型（1.5B 级） | ✅ [cad-recode](https://github.com/filaPro/cad-recode) · [cadrille](https://github.com/col14m/cadrille) | "扫描件/点云 → CadQuery 代码"的入口；GPU 环境，纯外部 |
| **Backflip AI** | Fusion 插件 + 网页，$20/月起 | ✅ [DEVELOP3D](https://develop3d.com/ai/backflip-ai-reverse-engineering/) | 实物改型需求出现时的外部入口 |
| **Proficiency (ITI)** | 服务器软件（Windows + 32GB RAM + MySQL 8.2 + UNC） | ✅ [产品页](https://www.cadinterop.com/en/our-products/proficiency.html) | 大规模 CAD 迁移场景 |

🔶推论：**外部调用路线的正确用法是"降级为可选增强"**：默认全本地（build123d + 标准件库 + LLM），把"我没见过这种零件"或"这是扫描件"作为触发器，才去调外部服务。这既满足"重组件必须可选调用、不能内置"，也让外部依赖的失效不阻塞主流程。

### 8.2 可以直接内嵌进 prompt 或轻量辅助函数的技巧

**这是本节的核心，也是投入产出比最高的地方。**

**（A）把接口数学做成 helper —— 让子代理"不可能算错孔位"**

你们已经有 288 个带 `nominal_diameter` / `pitch` / `axis` 的命名接口。🔶推论：把下列计算**从"LLM 每次现算"变成"调用函数"**：

| Helper | 输入 | 输出 | 消灭的错误类型 |
|---|---|---|---|
| `bolt_circle(center, pcd, n, start_angle)` | 分布圆直径、孔数、起始角 | 孔中心坐标列表 | 均布孔的角度算错、首孔相位错、不对称分布 |
| `bolt_pattern_rect(w, h, n_x, n_y, margin)` | 矩形法兰尺寸 | 孔位列表 + 边距校验 | 边距不足（孔破边） |
| `clearance_hole(thread_spec, fit)` | 螺纹规格（M3/M4…） | 通孔直径 + 沉孔/倒角参数 | 通孔小于螺纹大径（装不进去）——**这是最高频的装配失败** |
| `tap_drill(thread_spec)` | 螺纹规格 | 底孔直径 + 有效螺纹深度 | 底孔错误、螺纹深度不足 |
| `bearing_seat(bearing_id)` | 轴承型号（**查标准件库**） | 内圈配合轴径 + 外圈座孔 + 挡肩尺寸 + 圆角 | 轴承座与轴承外径不匹配 |
| `gear_pair(m1, z1, z2, helix_angle)` | 模数、齿数 | 中心距 + 两齿轮节圆半径 + 旋向 | 中心距算错（齿轮啮合不上） |
| `shaft_step(d, d_next, fillet_r)` | 相邻轴径与圆角 | 退刀槽 + 圆角 + 过渡长度 | 阶梯轴应力集中点几何不合法 |
| `keyway(d, key_spec)` | 轴径 + 键规格（**查表，不靠 LLM 记忆**） | 键槽宽深 + 公差 | 键槽尺寸记错 |
| `thread_axis_align(port_a, port_b, offset)` | 两个命名端口的轴 | 确定性刚体变换 | 同轴度靠 LLM 拼坐标，必然出错 |

🔶推论：**上表里每一项都是"查表/闭式公式"，不是"空间推理"**。AIDL 论文的实测支持这个方向："LLMs perform better with external solvers"、"we aim to enable LLMs to express design intent by specifying geometric relationships **instead of performing direct computation**"（✅已验证，[ar5iv](https://ar5iv.labs.arxiv.org/html/2502.09819)）。

**（B）把"约束求解"而不是"坐标"作为生成目标**

AIDL 的四条语言设计目标（✅已验证，均为论文原文标题级结论）：
> **dependencies**（引用已构造几何，避免重算坐标）、**constraints**（显式声明几何关系，交给求解器）、**semantics**（语义化命名的算子）、**hierarchy**（层次化结构，支持模块化与局部编辑）。

并给出关键约束："our analysis shows that **LLMs struggle to reason about queries with long chains**, motivating our choice to **disable them by design**"。
🔗 [ar5iv 正文 §3.1 表 1](https://ar5iv.labs.arxiv.org/html/2502.09819)

🔶推论：**"让 LLM 只声明关系，不计算坐标"是这条路线唯一被实验验证过的设计原则。** 你们的标准件接口已经是"语义化命名 + 数值参数"，距此只差一步：**让接口的数值参数在位置求解中作为约束使用，而不是作为提示词里的文本**。

**（C）把"可行性规则"做成 Checkpoint 断言，而不是写进 prompt**

🔶推论：prompt 里的规则会被 LLM 打折执行，断言不会。低成本可实现的纯几何断言清单（全部来自第 4、7 节的已验证证据，且无需仿真）：

| 断言 | 依据 |
|---|---|
| 壁厚均匀性（采样对面距离，检查 min/max 比） | 注塑/压铸 DFM 基本规则 |
| 拔模角（对指定脱模方向检查所有侧面的倾角） | 同上 |
| 加强筋厚径比（筋厚 / 主壁厚） | 同上 |
| 通孔 ≥ 螺纹大径 + 间隙；底孔 = 螺纹小径 | 紧固件配合基本规则 |
| 孔边距 ≥ 1.5×孔径（防止破边） | 钣金/机加工经验规则 |
| 干涉检查：任意两零件交集体积 ≤ 阈值 | ✅ ASSEMCAD 的 Definition 2 第 4 条正是此式 |
| 连通性：装配图连通且有指定根零件 | ✅ ASSEMCAD Definition 2 第 3 条 |
| 自由度检查：装配后剩余 DOF 符合预期 | ✅ ASSEMCAD 第 4.4 节验证项 |
| 端口的几何证据：声明的接口必须能落到真实 B-Rep 面/边上 | ✅ ASSEMCAD 的 "port-geometry verification" |
| **几何有效性四项**：watertight / manifold / 无自交 / 无重叠 | ✅ MUSE Stage 2 的四项 OCCT 检查 |

**（D）错误知识库（RAG）**

CADSmith 的做法（✅已验证）：`rag_kb1.py` = **155 条 CadQuery API 条目 + 28 个完整示例**；`rag_kb2.py` = **25 个"错误 → 解法"模式**。
🔗 [README](https://raw.githubusercontent.com/jabarkle/CADSmith/main/README.md)

🔶推论：这是**最便宜的可靠性提升**。把你们已有的 `docs/build123d_skills.md`（API 速查 + 陷阱）扩展成"错误→解法"配对库，并在每次子代理报错时自动追加。**注意这是 build123d 版本，CADSmith 是 CadQuery 版本，语法不能直接搬，但结构可以。**

**（E）用独立模型当裁判**

CADSmith 明确做了模型隔离（✅已验证）：代码生成用 **Claude Sonnet**，验证判定用 **Claude Opus**——"a stronger model than the Sonnet used for code generation, **so it's not just grading its own homework**"。
🔶推论：对你们的多子代理编排，这意味着：**"装配验证子代理"必须和"零件绘制子代理"使用不同的模型或至少不同的、只看几何证据（不看成因代码）的上下文**。否则它会倾向于认可同源生成的错误。

**（F）约束求解器可以内嵌**

✅已验证（均为当前活跃、可 pip 安装或轻量集成）：

| 库 | 能力 | 许可 | 活跃度 | 集成成本 |
|---|---|---|---|---|
| **[planegcs](https://pypi.org/project/planegcs/)**（0.8.0） | FreeCAD PlaneGCS **2D 几何约束求解器**的 Python 绑定，`pip install planegcs`；API 形如 `s.add_line/ s.equal_length/ s.horizontal/ s.set_p2p_distance/ s.solve()` | **LGPL-2.1-or-later** | PyPI 0.8.0；仓库 [spookylukey/planegcs](https://github.com/spookylukey/planegcs) 2026-06 推送 | **低**（纯 pip；无 wheel 时需 eigen3/boost 编译） |
| **[FreeCAD/OndselSolver](https://github.com/FreeCAD/OndselSolver)** | 装配约束 + 多体动力学 | **LGPL-2.1** | 2026-09 推送 | 中 |
| **[realthunder/slvs_py](https://github.com/realthunder/slvs_py)** | SolveSpace Python 绑定 | **GPL-3.0** | 2026-04 推送 | 中（⚠️GPL 对闭源插件有许可风险） |
| FreeCAD Assembly4 | 装配求解技术手册存在 | — | — | ⚠️未验证细节 |

🔶推论：**2D 约束求解已经是一个 `pip install` 就能解决的问题**（planegcs）。这意味着：**你们的草图可以退化到"LLM 只写约束，求解器算坐标"的模式**——这正是 AIDL 验证过的方向，而你们不需要自己造求解器。3D 装配位姿求解方面，OndselSolver 是 LGPL，可评估；slvs_py 是 GPL，闭源分发须谨慎。

### 8.3 "值得知道但现在不要碰"

| 技术 | 为什么现在不要碰 |
|---|---|
| **拓扑优化（整体）** | 缺物理输入（无仿真器）+ 输出是网格 + mesh→B-rep 需外部工具（第 2 节）。**给它加筋用规则式即可** |
| **mesh → B-rep 自动重建** | AMRTO 是研究框架不是库；商业方案是服务器级 + 人工收尾（第 2.3 / 6.1 节） |
| **特征识别 / STEP→特征树** | 你们没有存量几何；判断成立（第 6.3 节） |
| **从零训练/微调 CAD 生成模型** | Text-to-CadQuery 说明：微调 7B 模型需 33 小时 A100，且 top-1 exact match 只有 69.3%，这个指标还不代表几何正确（第 1.3 节）。**收益/成本比远低于改进闭环** |
| **通用 LLM 直接生成 CAD 脚本（无闭环）** | CADBench-Wild 显示通用模型语法错误率 15%–38%（第 7.1 节） |
| **装配序列规划（ASP）** | 解决产线问题，不是设计问题（第 5.2 节） |
| **注入 B-rep 生成模型（BrepGen / SolidGen / BrepDiff / HoLa）** | ⚠️本轮未评估其可用性；从定位看是"直接合成 B-rep 而无需构造历史"（ASSEMCAD related work 表述，✅已验证），但其输出是几何而非可编辑程序——**与你们"生成 build123d 脚本"的路线正交** |

### 8.4 被低估的"纯几何、不需要物理"的高价值技巧

**这一小节的判断依据**：ASSEMCAD 的整篇论文就是一个论证——"装配的正确性主要不是物理问题，而是**接口、关系、连通性、自由度**问题"，而它验证这四件事用的是一个**纯几何的确定性验证管线**（✅已验证）。AIDL 同理——它把 LLM 最弱的"空间推理"外包给**几何约束求解器**，而求解器里没有物理（✅已验证）。

| 被低估的技巧 | 为什么价值高 | 证据 |
|---|---|---|
| **1. 端口/配合的位姿求解（deterministic mate transform）** | 把"两个零件怎么对上"从 LLM 的空间推理变成矩阵求解。**这是你们现有资产变现的最大杠杆**——288 个命名接口就是 288 个"可被求解的端口" | ✅ ASSEMCAD 的 port/mate 库与确定性 mate 变换 |
| **2. 几何约束求解（2D 草图 + 3D 装配）** | AIDL 实测：约束开启时"一次编辑影响所有几何"，关闭时"经常产生分离的部件" | ✅ [AIDL §4 Ablations](https://ar5iv.labs.arxiv.org/html/2502.09819)；✅ planegcs 可 pip 安装 |
| **3. 层次化特征复用（hierarchy / 结构化子模块）** | AIDL 实测：有层次时局部编辑不破坏模型，无层次时"拨号盘移动而孔不动" | ✅ 同上 |
| **4. 参数联动（一条规则改所有实例）** | 这是你们相对交互式 CAD 的结构性优势；KBE 时代靠手写规则实现，现在靠生成代码时引用同一变量实现 | ✅ DEFAINE 对 KBE 的机制描述 |
| **5. "接口几何证据"验证（声明的接口必须能落到真实面/边）** | 这是**唯一能防住"LLM 声称同轴但实际偏了 0.3mm"的手段**——因为它在真实 B-Rep 上验，不在文本上验 | ✅ ASSEMCAD "validates declared interfaces using concrete B-Rep geometric evidence" |
| **6. 干涉/连通/自由度的图论检查** | 纯几何、O(n²) 级别、毫秒量级，却能挡住绝大多数"看起来对但装配不上" | ✅ ASSEMCAD Definition 2 的三条判据 |
| **7. 多视角渲染 + 自适应裁剪做视觉回归** | CADSmith 证明视觉判定把 T3 复杂件平均 CD 从 49.68 降到 1.42；但固定三视角会漏 near-miss，需要视角由特征驱动 | ✅ [CADSmith README](https://raw.githubusercontent.com/jabarkle/CADSmith/main/README.md) |
| **8. 钣金展开（K 因子 → 展开长度 → DXF）** | 唯一"解析可判定 + 可出生产文件"的自动建模能力 | ✅ kerf 的 `sheet_metal_unfold/flat_pattern` |
| **9. 螺纹/键/轴承的查表 helper** | 消灭最高频装配失败；且完全不需要物理 | 🔶推论（依据：CAD-Recode/Text2CadQuery 均属"查表类"生成，非推理类） |
| **10. 标签化孔特征（typed holes）** | Fusion 360 Gallery 用 **24 种孔类型**枚举来标注孔——说明"孔"的工程语义是可枚举、可机器处理的，比自由几何友好得多 | ✅ [assembly_joint.md](https://raw.githubusercontent.com/AutodeskAILab/Fusion360GalleryDataset/master/docs/assembly_joint.md) |

### 对本团队的可用性

| 项 | 结论 |
|---|---|
| 接口数学 helper 库（A 组） | **直接可用（第一优先级）**：纯 Python、零依赖、直接消灭最高频错误。工作量以天计 |
| 约束式生成（B 组）+ planegcs（F 组） | **直接可用**：`pip install planegcs`（LGPL-2.1）即可把 2D 草图交给求解器。**这是"把空间推理外包出去"的最低成本实现** |
| ports → mates + 确定性变换（8.4-1） | **直接可用（最高杠杆）**：你们已有的 288 个命名接口是这项工作的全部前置条件，几乎等于已经在做 |
| 接口几何证据验证（8.4-5） | **直接可用** |
| 干涉/连通/自由度检查（8.4-6） | **直接可用** |
| DFM 规则断言（C 组） | **直接可用（自研轻量）**：无开源引擎，但每条都是纯几何 |
| 错误→解法 RAG（D 组） | **直接可用（最便宜）**：把已有 API 文档扩成配对库 |
| 独立裁判模型（E 组） | **直接可用（架构调整）**：验证子代理换模型 + 只看几何证据 |
| 钣金（8.4-8） | **直接可用**：kerf（MIT）可参考/移植 |
| Zoo API | **需外部调用**：免费额度，输出 KCL 代码，适合做"兜底生成器" |
| 拓扑优化 / mesh→B-rep / 特征识别 / 自训模型 | **不适用（见 8.3）** |

---

## 一页结论：只做三件事

### 第 1 件：把"命名接口"升级为"可求解的 mate + 确定性变换 + 几何证据验证"（最重要）

**做什么**：为现有 288 个命名接口增加 `mate` 语义（同轴 / 贴合 / 插入 / 螺纹副 / 齿轮啮合 / 紧固），实现一个**确定性位姿求解函数**（`resolve(mates) -> {part: transform}`，纯矩阵运算，无迭代优化即可起步），并把求解结果在真实 B-Rep 上验证（同轴度、贴合面距离、干涉体积）。

**为什么是这一件**：
1. **这是你们唯一已经有 90% 前置条件的资产**。端口已存在、数值已存在、`axis` 已存在。
2. **这是学术界给出的答案**。ASSEMCAD 是 2026 年同方向最强的工作，它的核心贡献就是宣告"直接生成 CAD 代码不足以构造有效装配"，并把问题拆成 `typed parts + typed mates + axioms` + **确定性验证管线**。你要复制的不是它的模型，是它的表示与验证。
3. **它绕开了你们最大的短板**。你们没有仿真器，也不需要——装配正确性检查（接口、干涉、连通、自由度）**全部是纯几何**。
4. **它同时解决 KBE 的历史教训**。DEFAINE 文档里 KBE 死于"黑箱不可验证"。端口/mate 是**可被人类工程师读懂并质疑**的表示，这是可追溯性的载体。

**不做什么**：不训练模型、不做 mesh→B-rep、不做特征识别、不做拓扑优化。

---

### 第 2 件：建"接口数学 helper 库 + 分层验收 + 独立裁判"的闭环

**做什么**（三小步，按顺序）：
1. **helper 库**：`bolt_circle / clearance_hole / tap_drill / bearing_seat / gear_pair / shaft_step / keyway / bolt_pattern_rect` 等——全部是查表与闭式公式，全部从标准件库取数，**杜绝 LLM 现算**。
2. **分层验收**（照抄 MUSE 漏斗）：L1 代码可执行 → L2 几何有效四项（watertight / manifold / 无自交 / 无重叠）→ L3 你们已有的 Checkpoint 数值断言 → L4 逐案 rubric（功能/可制造/可装配）。
3. **独立裁判**：验证子代理使用**不同的模型**、且**只看几何证据（度量 + 渲染）不看生成代码**。

**为什么是这一件**：
1. **这是唯一被验证能提升可靠性的机制**。CADSmith 在 100 条手写 prompt 上：zero-shot 执行率 95% / 平均 CD 28.37 → 全流水线 + 视觉判定 **100% / 0.74**；T3 复杂件去掉视觉后 CD 从 1.42 涨到 49.68。**提升来自闭环，不来自模型。**
2. **它直接对冲 KBE 的三大死因**：黑箱（分层验收给了可读证据）、知识流失（helper 库把知识存在代码里而不是专家的直觉里）、缺中立表示（helper 签名就是中立接口）。
3. **它是唯一能防住"看起来对但装配不上"的手段**。CADSmith 自曝的 near-miss（F1=0.963、IoU=0.985、通过全部校验、但机臂与中心毂之间有缝隙）说明：**没有多视角 + 特征驱动的裁剪，光靠内核度量会漏**。
4. **成本极低**。helper 库以天计；planegcs（LGPL-2.1）一个 `pip install` 就能接上 2D 约束求解。

**关键纪律**（来自 AIDL 的实测失败模式）：**禁止 repair 循环通过"删除设计意图"（删断言、删约束、放宽公差）来消除报错。** AIDL 论文明确记录 LLM 最常见的应对就是"不断删掉约束直到报错消失"，而 validate-until-correct 模式会让被删掉的设计意图**永远回不来**。

---

### 第 3 件：把钣金做成"可用"，把壳体做成"可检查"，明确不做注塑优化

**做什么**：
1. **钣金**：接入或移植 kerf（MIT）的 `sheet_metal_unfold` / `sheet_metal_flat_pattern` 思路——K 因子 → 展开长度 → DXF R12。参考 FreeCAD SheetMetal（LGPL-2.1，2026-09 仍活跃）。
2. **壳体（注塑/压铸）**：**只做"生成 + 检查"，不做"优化"**。把拔模角、壁厚均匀性、加强筋厚径比、最小圆角实现成纯几何断言（几十行），进 L4 rubric。
3. **明确不做**：拓扑优化、模具冷却水道、模流分析。

**为什么是这一件**：
1. **钣金是本轮唯一"自动化程度高 + 开源完整 + 已封装成 LLM 工具"的壳体能力**。原因是它的设计对象与制造对象之间存在**解析映射**（K 因子 → 展开长度 → 下料图），因此可自动、可验证、可出生产文件。注塑不具备这个性质——它的关键决策（分型面、脱模方向）是全局判断，不是解析计算。
2. **商业界的做法本身就是"检查"而非"生成"**。CoreTech 的产品叫 **DesignSim — real-time injection molding DFM Validations**（插件形态，NX 版），Cimatron 做的是"简化冷却系统设计"。**行业共识是：生成难、检查相对容易且可靠。** 对"无仿真器"的你们，检查才是可负担的那一半。
3. **它给"非标件大多是壳体和轴"这个判断落地**：🔶**这个判断在"几何形状"层面大体成立**（你们的目标零件里，壳体＝拉伸+抽壳+孔系+筋，轴＝回转+台阶+键槽+螺纹，两者都是 build123d 十几行能覆盖的），但它**在"工程正确性"层面不成立**——壳体真正的难点不是形状，是拔模/壁厚/孔边距/装配可达性，轴真正的难点不是轮廓，是配合公差/圆角过渡/螺纹有效深度。**形状便宜，接口贵。** 所以你们的投入应该压在接口（第 1 件）和检查（第 2 件），而不是压在"能不能画出更复杂的壳体"。

---

### 一句话总结

**你们不需要更好的生成模型，你们需要"接口可求解 + 结果可验证"。你们已有的 288 个命名接口，是这个方向上最值钱的资产；而市面上最强的同方向工作（ASSEMCAD）给出的答案，恰好就是把这套东西变成 ports + mates + 确定性验证。**
