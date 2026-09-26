# 库驱动规则校验（Library-Driven Rule Checking）的先例调研

> 针对「标准件库 + 声明式接口元数据 ⇒ 确定性规则校验（像编译器一样 pass/fail）」这一构想的前期技术调研。
>
> **证据标注约定**
> - ✅ **已验证** = 我实际抓取并读到了一手来源（官方文档 / 厂商资料 / 项目文档），附原文引用或链接。
> - 🔶 **推论** = 我基于已验证事实做出的推理，**不是**来源中的原话。
> - ⚠️ **未验证** = 我看到了标题/入口但**未能取得正文**（页面超时、需登录、PDF 损坏等）。请勿当作事实使用。
>
> 抓取失败的清单集中列在文末「附录：未验证清单」。

---

## 执行摘要（先看这个）

| 结论 | 证据强度 |
|---|---|
| **EDA 的 DRC/ERC 就是他们想抄的那套架构**，而且 KiCad 的实现细节完全公开：语义模型（`.kicad_sch` / 网表 / netclass）与规则（`.kicad_dru`）分离，规则是 S-表达式 + 布尔条件表达式，引擎把规则编译后对着「连接图（connectivity graph）」逐对对象求值。 | ✅ |
| **ERC 的「引脚电气类型冲突矩阵」是「A 类接口能不能接 B 类接口」最直接的模板**——一个 N×N 矩阵，值域 {allowed, warning, error}。这正是「螺钉↔螺母」「型材↔角码」要的东西。 | ✅ |
| **商业 MCAD 确实有规则校验，但绝大多数是单零件几何/制图规范**（NX Check-Mate、Creo ModelCHECK、SolidWorks Design Checker/DFMXpress 一类）。**跨零件「配套性」语义规则基本不是开箱能力，而是「自定义 checker 框架」**（NX 用 Knowledge Fusion 写 `do_check`）。 | ✅（NX 部分）/ 🔶（SolidWorks·Creo 部分未能读正文） |
| **PLM 侧的 DMU 主要做几何干涉/间隙**；语义层面的「配套性」由字典库承担，例如 Teamcenter 的 **ClearanceDB**（明确的语义配对数据库）。 | ✅（ClearanceDB 存在）/ ⚠️（细节未验证） |
| **零件库目前普遍只给几何 + 参数表，不给「A 配 B」的机器可读配对关系**。McMaster-Carr 的 Product Information API 有结构化 `Specifications` 数组和 `SuggestedProductDifferences`，但**没有** mating/compatibility 字段。TraceParts API 只覆盖取模型/取元数据。 | ✅ |
| **型材的「系列/槽宽」配套表是公开的、可编码的**（item24 的 Line 5/6/8/10/12 与槽宽/芯孔/螺纹对应关系有官方博客明说）。**但没人把它做成开放数据集**——需要团队自己誊写成表。 | ✅（item24 部分） |
| **螺钉↔螺母的「螺纹规格一致」可以由公开标准（ISO 261/262、ISO 68-1、ASME B1.1）推导**，但**没有权威的机器可读 ISO 螺纹数据集**；能复用的是开源实现里的参数表（FreeCAD Fasteners/BOLTS 一类），**不是**标准原文。 | ✅（标准存在性）/ 🔶（无开放数据集这点是我的判断） |
| **「mechanical netlist」是有学术传统的概念**：liaison graph / assembly constraint graph / assembly liaison graph 都是既有术语（至少可追到 1990s–2008 的装配序列规划文献）。 | ✅（至少一篇有全文入口） |
| **最接近他们构想的具体实现是 FreeCAD Fasteners Workbench**：它按圆边半径自动选型，并且区分 **「Match for tap hole」vs「Match for pass hole」**——这就是「接口类型 + 匹配规则」。 | ✅ |

---

## A. 直接可借鉴的先例

### A.1 EDA 的 DRC / ERC —— 范式本体（首选蓝本）

#### A.1.1 KiCad：规则的存储、加载与求值

✅ **已验证。** 来源：[KiCad PCB Editor 手册 · Custom design rules](https://docs.kicad.org/master/en/pcbnew/pcbnew.html)（我抓的是文档源文件 [`pcbnew_advanced.adoc`](https://gitlab.com/kicad/services/kicad-doc/-/raw/master/src/pcbnew/pcbnew_advanced.adoc)，第 960 行起）。

**关键架构事实（逐条有原文）：**

1. **规则独立成文件，与设计文件并列**：
   > "Custom design rules are stored in a separate file with the extension `kicad_dru`. This file is created automatically when you start adding custom rules to a project. If you are using custom rules in your project, make sure to save the `kicad_dru` file along with the `kicad_pcb` and `kicad_pro` files when making backups or **committing to a version control system**."

   注意最后半句——KiCad 官方文档**明确把规则文件当作应当进版本控制的一等公民**。这是「rules-as-code」的直接先例。

2. **规则文件有版本头**：
   > "The Custom Rules file must start with a version header defining the version of the rules language. As of KiCad 10.0, the version is `1`."

3. **规则求值顺序是「后来居上」，且首命中即停止**：
   > "Rules are evaluated in **reverse order**, meaning the last rule in the file is checked first. Once a matching rule is found for a given set objects being tested, no further rules will be checked. In practice, this means that more specific rules should be later in the file."

   🔶 **推论**：这等价于 CSS 的层叠 / 防火墙的 first-match，是「特例覆盖通例」的经典解法；他们的配套性规则表如果会生长，必须一开始就定好这个优先级语义，否则后期无法维护。

4. **规则的语法骨架**（原文语法定义）：
   ```
   (rule <name>
       [(severity <severity>)]
       [(layer <layer_name>)]
       [(condition <expression>)]
       (constraint <constraint_type> [constraint_arguments]))
   ```

5. **一条真实规则示例**（原文）：
   ```
   # Clearance for 400V nets to anything else
   (rule HV
       (condition "A.hasNetclass('HV')")
       (constraint clearance (min 1.5mm)))
   ```

6. **条件表达式语言的核心设计**：被测对象叫 `A` 和 `B`，**顺序无关（引擎会双向试探）**，成对测试的函数用 `AB`：
   > "The objects being tested are referred to as `A` and `B` in the expression language. The order of the two objects is not important because the design rule checker will test both possible orderings. … There are some expression functions that test both objects together; these use `AB` as the object name."

7. **可用操作符**：`==` `!=` `>` `>=` `<` `<=` `&&` `||` `!`，**同优先级、从左到右求值**（原文明确说明）。单位后缀 `mm` / `mil` / `th` / `in` / `"` / `deg` / `rad`，以及 `null`（可空属性）。

8. **规则里可以引用工程级变量**：
   > "Text variables could be used, for example, to define a project-wide value … like `(constraint clearance (min ${hv_clearance}))`, where `${hv_clearance}` is a text variable defined in the project as `${3 mm}`."

   🔶 **推论**：这对应他们「M5 螺纹啮合长度下限」这类**可调工程参数**——不要硬编码进规则，而是做成可注入变量。

9. **对象模型（可被规则引用的属性）**——这是「数据模型声明意图」那一半，十分具体：
   - 通用：`Layer`、`Locked`、`Parent`、`Position_X/Y`、`Type`（枚举 `"Footprint"`/`"Pad"`/`"Track"`/`"Via"`/`"Zone"`/`"Text"`/…）
   - 与网络相关：`Net`、`NetClass`、`NetName`，及函数 `hasNetclass(<nc>)`、`hasExactNetclass(<list>)`
   - 封装相关：`Reference`、`Library_Link`（`library_name:footprint_name` 格式）、`Library_Description`、`Keywords`、`Component_Class`、`Do_not_Populate`、`Not_in_Schematic`、`Exempt_From_Courtyard_Requirement` …

   ⚠️ 注意 `Library_Link` 与 `Library_Description` 的存在 —— **规则可以直接查询「这个器件来自哪个库、库里的描述是什么」**。这正是他们想要的「零件来自受管理的库」的可判定性来源。

10. **约束类型清单（节选，全部为已验证原文表述）**，可用于类比他们需要的约束词汇：

    | 约束 | 语义 |
    |---|---|
    | `clearance` | 不同网络铜对象之间的电气间隙 |
    | `physical_clearance` | 不论网络、不论层（含非铜层）的物理间隙（较慢） |
    | `courtyard_clearance` | 封装 courtyard 之间的间隙；**没有 courtyard 的封装不产生错误** |
    | `edge_clearance` | 对象到板边的间隙（原文：可理解为"铣削公差"） |
    | `hole_size` / `hole_to_hole` / `physical_hole_clearance` | 孔径 min/opt/max、孔间距、孔到对象的间隙（原文：可理解为"钻孔公差"） |
    | `annular_width` | 环宽 |
    | `disallow` | 禁止某些对象类型（`track`/`via`/`pad`/`zone`/`footprint`/…）出现在匹配区域 |
    | `length` / `skew` / `diff_pair_gap` / `diff_pair_uncoupled` | 高速布线约束（min/opt/max） |
    | `text_height` / `text_thickness` | 文字尺寸 |
    | `microvia_aspect_ratio` / `microvia_stack_depth` | 工艺能力 |
    | **`assertion`** | **「检查布尔表达式为真，否则报 DRC 错误」** |

    ⭐ **`assertion` 这个约束类型极其重要**：它把整套系统从「只能用内置几何检查」变成「**图灵完备的任意谓词都能写成规则**」。见下一节。

11. **`assertion` 的两种用法（这是他们最该抄的机制）**：

    (a) 规则层断言：
    > "`assertion` | boolean expression | Checks that the boolean expression is true. If the expression is false, a DRC error will be created. The expression can use any of the properties listed in the Object Properties section."

    (b) **PCB 上的文本对象可以产生 DRC 错误**——原文（Text variables 节）：
    > "`DRC_ERROR <errorname>` | Generates a DRC error named `<errorname>`. Everything … braces is included in the descriptive text for the DRC violation. … For example, a text item containing `${DRC_ERROR TODO}Length match tracks` will display as the text "Length match tracks" and generate a DRC error …"
    > 同节还有 `DRC_WARNING <warningname>`。

    🔶 **推论**：这是「**模型自己声明一个待办/断言，检查器负责保证它不被遗漏**」的机制。对他们的 LLM 工作流有直接启发：与其让模型在 Python 里 `assert volume == X`（自证），不如让模型产出一个**结构化的待验证声明**，由外部检查器消费。

12. **严重度可配**：`error` / `warning` / `ignore` / `exclusion`，并有一个**陷阱式官方警告**：
    > "Setting a rule's severity to `ignore` does not disable the rule; only the effects of the rule are disabled. **The rule is still evaluated and can still override previous rules.**"

13. **前置语法门禁**：自定义规则编辑器提供 "a syntax checker that will test your custom rules and note any errors"；且
    > "**Any errors in the custom rules will prevent the design rule checker from running.**"

    🔶 **推论**：规则文件本身要过 parser —— **规则坏了就整体拒绝跑检查**，而不是静默跳过。这是防「规则悄悄失效」的关键设计。

14. **DRC 输出**：✅ 来源 [`pcbnew_inspecting.adoc`](https://gitlab.com/kicad/services/kicad-doc/-/raw/master/src/pcbnew/pcbnew_inspecting.adoc)
    - "**A report file in plain text format can be created after running DRC using the Save... button.**"
    - 违规可被 **exclude**（单条）、**exclude with comment**（带理由）、或整类 ignore；**排除项在多次 DRC 之间被记住**（"Excluded and ignored violations are remembered between runs"）。
    - 可勾选 "Test for parity between PCB and schematic" —— **把「原理图 vs PCB 是否一致」也纳入同一套检查**。

    🔶 **推论**：「带理由的豁免 + 豁免被持久化」是他们**必须**提前设计的，否则一旦规则表上线，第一周就会被 `# noqa` 式的静默豁免淹没。

#### A.1.2 KiCad ERC —— 「接口类型兼容矩阵」的教科书实现

✅ **已验证。** 来源：[KiCad 手册 · Electrical rules checking](https://docs.kicad.org/master/en/eeschema/eeschema.html)，抓自 [`eeschema_inspecting_a_schematic.adoc`](https://gitlab.com/kicad/services/kicad-doc/-/raw/master/src/eeschema/eeschema_inspecting_a_schematic.adoc)。

**最重要的一句（原文）**：
> "The quality of the ERC is directly related to the care taken in declaring electrical pin properties during symbol creation. **If symbols are designed incorrectly, ERC will not report accurate information.**"

🔶 **推论**：这**就是**他们构想的成立条件的一般化陈述 —— **规则引擎的可靠性上限 = 库中接口元数据的质量上限**。这句话可以直接放进他们的设计文档当立项理由。

**Pin Conflicts Map（接口兼容矩阵）** —— 原文：
> "The **Pin Conflicts Map** panel in Schematic Setup allows you to configure connectivity rules to define electrical conditions for errors and warnings based on what types of pins are connected to each other. For example, by default an error is produced when an output pin is connected to another output pin."
> "**Rules can be changed by clicking on the desired square of the matrix, causing it to cycle through the choices: allowed, warning, error.**"

这是一个 **N×N 矩阵，值域 {allowed, warning, error}** —— 与「M5 螺钉头 × M5 螺母 = allowed」「M5 螺钉头 × M6 螺母 = error」在结构上完全同构。

**引脚电气类型全集**（✅ 来源 [`eeschema_symbols_and_libraries.adoc`](https://gitlab.com/kicad/services/kicad-doc/-/raw/master/src/eeschema/eeschema_symbols_and_libraries.adoc)，`[[pin-electrical-types]]` 节）：

| 类型 | 默认冲突行为（原文要点） |
|---|---|
| Input | 默认允许连多数类型；**未被驱动则报错** |
| Output | 允许连多数「非 output」类型 |
| Bidirectional | 类似 input，限制略多 |
| Tri-state | 与多数 output/power 相连时产生 **warning** |
| Passive | 允许连多数类型 |
| Free | 允许连多数类型；PCB 侧对应焊盘可连任意网络而不报 DRC |
| Unspecified | 与多数类型相连时 **warning** |
| Power input | **未连到 power output 则报错** |
| Power output | 可连多数 input，**不可连 output** |
| Open collector / Open emitter | 可连多数 input 及同类，**不可连多数其它 output** |
| **Unconnected** | **不允许连任何其它类型**；且「悬空」本身不报错。不可在矩阵中配置 |

⭐ 注意 **Unconnected** 这一类型的语义：**「这个引脚永远不该被连」是一条硬规则，且它同时「关闭了悬空告警」**。这是「显式声明意图」的极端例子 —— 用类型编码「不该连」这件事，而不是靠检查器去猜。

**ERC 检查项清单也值得抄其分类法**（原文表）：分为 **Connections / Conflicts / Miscellaneous** 三类，每项带**默认严重度**且**全部可配置**：
- Connections：Pin not connected / Input pin not driven / Input Power pin not driven / Label not connected / Label connected to only one pin / Duplicate pins with different nets（**Error，不可配置**）/ Symbol pin or wire end off connection grid …
- Conflicts：Duplicate reference designators / Units of same symbol have different values / Different footprint assigned in another unit / Mismatch between hierarchical labels and sheet pins / Conflict between bus alias definitions across sheets / **Net is graphically connected to a bus but not a bus member** …
- Miscellaneous：Symbol is not annotated / Unresolved text variable / **Undefined netclass** / Field name has leading or trailing whitespace …

🔶 **推论**：三个可直接搬的分类维度是 —— **(i) 连接完整性**（该连的没连）、**(ii) 一致/冲突性**（同一实体的多个声明互相矛盾）、**(iii) 元数据卫生**（引用了不存在的 netclass、名字带空白等）。第三类看起来琐碎，但**正是它让「库」保持干净**，否则规则引擎查的东西本身是脏的。

**「每网络只报一次」的降噪设计**（原文）：
> "Some violations are reported only once per net. For example, the 'Input Power pin not driven by any Output Power pins' error technically applies to each Input Power Pin … but only one marker is shown per net. This is to avoid producing a large number of markers for a single root cause."

#### A.1.3 Altium Designer

✅ **已验证（仅文件格式这一点）。** 来源：[Altium KB · Import or export Design Rules](https://www.altium.com/documentation/knowledge-base/altium-designer/import-or-export-design-rules)
> 在 PCBDoc 中 **Design » Rules** 打开 **PCB Rules and Constraints Editor**；右键 Design Rules 文件夹 → **Import Rules** / **Export Rules**，选择规则类型。
> "If Importing, the option would be to **Load** a **PCB Rules File (.rul)**"
> "If Exporting, the option would be to **Save** a **PCB Rules File (.rul)**"

→ **`.rul` 是 Altium 的规则交换文件格式（已确认存在此扩展名与导入导出流程）**。

🔶 **推论**：Altium 的规则是**查询式（query-based）**——规则用类 SQL 的查询表达式选中对象集合（形如 `IsVia`、`InNetClass('...')`），这一点与其知识库中单独存在的 "Query Language" 参考资料一致。但 ⚠️ **我没有读到 Altium 官方 Query Language 参考页的正文**，因此**不在此断言其具体语法**。

⚠️ **未验证**：Altium 规则类别的完整清单（Electrical / Routing / SMT / Mask / Plane / Testpoint / Manufacturing / High Speed / Placement / Signal Integrity）、Online DRC 的具体行为、`.rul` 内部是否为可读文本或二进制。我**没有**取得这些的一手正文。

#### A.1.4 其他 EDA

- **OrCAD / Allegro Constraint Manager**：⚠️ **未验证**。仅见第三方页面标题（[EMA Design Automation](https://www.ema-eda.com/products/orcad/features/constraint-management/)），未读正文。**不做任何具体断言。**
- **Eagle `.dru`**：⚠️ **未验证**。**不做任何具体断言。**

---

### A.2 商业 MCAD 的规则校验

#### A.2.1 Siemens NX Check-Mate —— 最完整的「自定义规则」框架先例

✅ **已验证。** 来源（一手，Siemens/UGS 官方技术演讲 PDF）：*Customizing Check-Mate – Where Do I Start?*（Taylor Anderson, NX Product Manager, UGS Corp. 2007）
🔗 <https://ww3.cad.de/foren/ubb/uploads/schulze/NXCK2-Anderson.pdf>
（另有官方产品简介 *NX Check-Mate / NX Quick Check*：原 URL `https://www.plm.automation.siemens.com/cz_cz/Images/fs_checkmate_quickcheck_tcm841-11882.pdf` —— ⚠️ **该链接现已 301 跳转到 siemens.com 首页，未能取得 PDF 正文**。）

**已验证的架构要点（逐条为原文）：**

1. **Checker 的定义**：
   > "A 'check' (aka checker) is **a small piece of logic that looks for a particular condition within a model**."
   > "Individual check(er)s may validate anything from layering conventions to drafting standards to various modeling best practices **or even techniques for organizing and working with assemblies**."

2. **Profile = 一组 checker 的集合 + 预配置参数**：
   > "A Check-Mate 'profile' is **a collection of checks that will be executed together at the same time**. Checks contained in a profile can be pre-configured with any default values or needed input parameters."
   > "A profile is a great tool for ensuring that a **complete set of checks** is performed using a desired set of quality criteria."

   ⭐ **这就是「规则集 / ruleset」概念的工业实现**。🔶 推论：他们应该把「型材框架配套性检查集」定义为一个 profile，而不是一堆散装规则。

3. **实现成本谱系（"The Configuration Continuum"）** —— 原文列出的 7 档，从便宜到昂贵：
   ```
   OOTB check "as-is"      → 直接用出厂 checker
   OOTB template check     → 用出厂模板
   Modified OOTB check     → 改出厂 checker
   Heavily modified check  → 大改
   New check from KF Functions  → 用 Knowledge Fusion 函数写新 checker
   New check from NX/Open API   → 用 NX Open API 写
   Check done outside NX entirely → 完全在 NX 之外做
   ```
   并注明 "Relative Frequency of Use"（越靠前用得越多）。

4. **Checker 的编写语言是 Knowledge Fusion（KF），文件是 `.dfa`**。已验证的原文片段：
   - `do_check:` 属性承载 checker 主体逻辑，语法形如：
     ```
     (Any Uncached)   do_check:
     @{
     $orphan_layers << mqc_askOrphanLayers();
     ...
     $write_log << Loop
     {
     For $layer_num In  $layers_of_orphaned_entities;
     For $detail_msg Is  "Layer " + Stringvalue( $layer_num ) + " is not empty and not in a category.";
     Do ug_mqc_log( LOG_ERROR, {}, $usr_msg + $detail_msg );
     };
     };
     ```
   - 报告/记录函数：`ug_mqc_log( LOG_ERROR, {}, <msg> )`，原文注："Calling `ug_mqc_log` multiple times in one checker is just fine. (Useful for more descriptive messages.)"
   - 谓词/查询函数命名空间为 `mqc_*` 与 `ug_mqc_*`，例如 `mqc_askOrphanLayers()`、`mqc_ask_layer_entities(...)`、`mqc_collect_entity_layers(...)`、`mqc_ask_part_attributes()`、`mqc_ask_all_referencesets()`、`mqc_askCategoryOfLayer()`、`ug_mqc_checkLayerEntityType()`、`ug_mqc_askLayerWithoutCategory()`。
   - **类型/子类型定义在 `..\UGCHECKMATE\dfa\mixins\ug_object_types.dfa`** —— 这是原文给出的路径，说明**对象类型系统本身就是一份可编辑的 `.dfa` 声明文件**。
   - 原文："Check-Mate is **fundamentally based on KF**, and so any of the normal KF functions are fair game for use when writing checkers."
   - 内置示例 checker：`%mqc_check_preferences`（位于 `mqc_check_preferences.dfa`），"Verifies that the customer defaults are set properly according to the defaults specified in the user-defined XML files." ← **注意：规则参数来自用户可编辑的 XML 文件**，checker 逻辑与规则数据分离。

5. **Checker 的编写方法学（原文的"Thought Process"表）**：对每个 desired check 明确三件事 —— **Required Failure Condition / Reports**。例如：

   | Desired Check | Required Failure Condition | Reports |
   |---|---|---|
   | Check for layers with entities but without any categories | Fails when layers have entities but no category | The layer numbers that have entities but no category |
   | Check for required attribute names | Fails when any required attribute names are missing | The missing attribute names |
   | Check for approved categories | Fails when any unapproved categories are present | The unapproved categories and their corresponding layer numbers |
   | "Check Drafting Preferences" | Fail if any Drafting entity settings is not the same as specified in the customer default file | The Drafting Entities that have been changed from the default |

   ⭐ **「必需项缺失」与「出现了未批准的项」是对偶的两类规则**（required-names ⊂ part vs part ⊂ approved-names）。🔶 推论：他们的配套性规则表也需要这对偶 —— 「该有的接口元数据字段必须有」（required）和「不允许出现未登记的标准件/系列」（approved allowlist）。

6. ⚠️ **未验证**：Check-Mate 是否有**开箱的跨零件配套性 checker**。已读材料只泛泛提到 checker 可以验证 "techniques for organizing and working with assemblies"，**没有给出任何具体的 mating/compatibility checker 例证**。🔶 **推论**：NX Check-Mate 的定位是**可扩展的校验框架**，跨零件语义规则需要用户自己用 KF 写。

#### A.2.2 SolidWorks（DFMXpress / Design Checker / TolAnalyst）

⚠️ **重要限制：SolidWorks 官方帮助站（`help.solidworks.com`）对本环境不可读** —— 页面由 JS 组装，抓取只得到 CSS 与导航壳，`curl` 多次超时；`my.solidworks.com` 返回 403。因此**本节几乎没有可引用的一手正文**。

我能确认的**仅限搜索引擎索引中出现的页面标题与片段**（**不足以支撑任何功能断言**）：
- DFMXpress 规则参数页存在：`help.solidworks.com/2015/spanish/SolidWorks/dfmxpress/r_settings.htm`（⚠️ 正文未取得）
- Design Checker 页存在：`help.solidworks.com/2026/.../HIDD_TASK_DESIGN_CHECKER.htm`、`.../solidworks_design_checker/c_check_active_document.htm`（⚠️ 正文未取得）
- TolAnalyst Overview 页存在：`help.solidworks.com/2026/English/SolidWorks/tolanalyst/c_TolAnalyst_Overview.htm`、`help.solidworks.com/2025/English/solidworks/sldworks/c_TolAnalyst_Overview.htm`（⚠️ 正文未取得）
- 搜索引擎返回的 2008 版 What's New PDF 片段中含 "Fillets on Outside Edges: Checks that chamfers rather than radii are specified for top face boundary edges"（⚠️ **PDF 未下载成功**，`files.solidworks.com` 连接超时）—— 🔶 若该片段属实，它是「DFMXpress 规则可具体到几何细节」的一个例证，但**我无法验证，故不作为事实**。

🔶 **推论（明确标注为推论）**：业界通识是 DFMXpress 做**单零件可制造性**（注塑壁厚/拔模、铣削内圆角半径与刀具、钣金等），Design Checker 做**工程图/文档规范**对照，TolAnalyst 做**装配尺寸链**。但这**三点我都没有一手来源**，请勿在正式文档中引用为事实。**如果这个点对他们重要，需要有人用可访问的网络环境重新取证。**

#### A.2.3 PTC Creo / CATIA

- **Creo ModelCHECK**：⚠️ **未验证**（仅见第三方 PTC 支持 PDF 中被搜索引擎索引的片段提及 ModelCHECK，未读正文）。**不对其配置文件格式做任何断言。**
- **CATIA Knowledge Expert / EKL**：⚠️ **未验证**。见于搜索引擎结果的 *CATIA V5 Knowledgeware User Guide* PDF（`bndtechsource.ucoz.com/V5_Online_Docs/Knowledgeware/kwxug2.pdf`，含章节 "Using Types in the Check/Rule Editor"），但**下载失败（TLS 错误）**，未读正文。**不对 EKL 语法做任何断言。**

#### A.2.4 DFM/DFA 规则引擎

**DFMPro（HCLTech / 原 Geometric）**：⚠️ **未验证**。仅见其白皮书 *The other side of design for assembly* 被索引（`dfmpro.geometricglobal.com/files/2017/05/Whitepaper-The-other-side-of-design-for-assembly.pdf`），未读正文。**不对其规则类别做任何断言。**

**aPriori**：⚠️ **未验证**（`docs.apriori.com` 返回 403）。

**Boothroyd Dewhurst DFA —— 这一项有可用的一手材料，而且是真正的「规则集」** ✅

来源：[DFMA® 官方 "What Is Design for Assembly (DFA)?"](https://www.dfma.com/design-for-assembly.asp)（Boothroyd Dewhurst, Inc. 官方站点）

**已验证的核心内容 ——「最小零件判据」三问（minimum part criteria）**，原文逐条：
> "For each part, ask whether it fundamentally needs to be separate from the parts it connects to:
> **1. Material or process** — Does it need a different material or process? (insulation, wear, sealing, heat, conductivity, chemistry)
> **2. Relative motion** — Must it move relative to the parts it connects to in order to perform its function?
> **3. Assembly or service** — Must it stay separate to allow assembly sequence, serviceability, or adjustment?
> If a part cannot justify itself on any of these three fundamentals, it is a prime candidate to combine or eliminate."

**DFA checklist**（原文，节选 —— 注意这些都可机械化为布尔谓词）：
> Structure & part count: "Can this part be eliminated or combined with an adjacent part?" / "Does it truly need a different material or process?" / "Must it move relative to the parts it connects to?" / "Can unique part variants be reduced or standardized?"
> Handling, insertion & fastening: "Can fasteners be replaced with snap-fits or integral features?" / "**Can the assembly be built from a single direction?**" / "Are alignment features self-locating, so no separate holding step is needed?"

**DFA Index 定义**（原文）：
> "The DFA Index (design efficiency) is a measure used in Design for Assembly analysis that compares **the theoretical minimum assembly effort with the actual assembly effort** of a design."

**量化案例（IDEXX Catalyst Dx）**：183 → 31 零件；63 → 0 紧固件；装配时间 45 → 11 min；DFA Index 3.8 → 35.8。

⭐ **为什么这对他们重要**：Boothroyd-Dewhurst 的 DFA 是**唯一被广泛接受、且写成了明确判据的「装配级」规则集**。「能否从单一方向装配」「是否自定位」这类判据，在他们的 build123d 世界里可以**从接口元数据直接求值**（装配方向 = 各接口法向的可行性交集；自定位 = 接口是否含定位特征）。🔶 推论。

⚠️ **未验证**：DFMPro / aPriori 是否内置了类似 DFA 的装配规则。**不做断言。**

#### A.2.5 公差栈分析工具如何建模配合面

**SolidWorks TolAnalyst**：⚠️ **未验证**（正文不可读，见 A.2.2）。
**Cetol 6σ / 3DCS / VSA / Enventive**：⚠️ **未验证**。**不做任何具体断言。**

🔶 **仅作方向性推论（不做事实引用）**：这类工具的一般做法是把「装配 = 一串步骤，每步选择配合特征 + 尺寸方案」，然后用蒙特卡洛/极值法传播。**若团队需要这一环，必须单独取证。**

---

### A.3 DMU / 干涉检查 / PLM 装配验证

✅ **已验证存在、且与「语义配对」直接相关的一项**：**Siemens Teamcenter ClearanceDB**
来源（Siemens 官方文档服务器上的 ClearanceDB 管理员指南）：<https://docs.sw.siemens.com>
已验证的原文片段（来自搜索索引对该官方 PDF 的引用）：
> "Vous pouvez associer **ClearanceDB** et l'application **Conception avec contexte** de Teamcenter pour créer un système ICM (Integrated …)"

⚠️ **诚实说明**：我**只**确认了「ClearanceDB 是 Teamcenter 的一个真实组件，且其管理员指南存在」这一点，**没有读到其数据模型细节**。它值得团队后续专门取证，因为从命名与定位看，**它是 PLM 里少见的、以「配对/间隙规则数据库」而非纯几何为核心的组件**。🔶 推论：这可能是「semantic compatibility 而非纯几何」最接近的工业先例。

⚠️ **未验证**：Windchill、3DEXPERIENCE 的装配验证机制；Teamcenter 的 DMU 干涉/间隙分析细节；「Lifecycle Visualization Mockup」PDF（`plm.automation.siemens.com/en_us/Images/3235_tcm1023-4788.pdf`）未取得。

🔶 **概括性推论（非事实）**：PLM 的 DMU 传统上以**几何干涉 / 间隙 / 剖切 / 运动包络**为主，语义配套性通常不在其中，而由配置器（configurator）或专用字典库承担。**ClearanceDB 可能是个例外，需取证确认。**

---

### A.4 标准件库是否暴露机器可读的配对数据

#### A.4.1 已验证的具体事实

**McMaster-Carr Product Information API** ✅ —— <https://www.mcmaster.com/help/api/>
- 面向**已批准客户**（需客户端证书 + 用户名/密码），REST + Bearer token（24h 有效）。
- 端点：`/v1/login`、`/v1/logout`、`PUT /v1/products`（订阅式）、`DELETE /v1/products`、`GET /v1/products/{pn}`、`GET /v1/products/{pn}/price`、`GET /v1/images/*`、`GET /v1/cad/*`、`GET /v1/datasheets/*`。
- **产品信息返回结构化 `Specifications` 数组**（原文示例）：
  ```json
  {
    "PartNumber": "4936K451",
    "ProductStatus": "Active",
    "FamilyDescription": "Compact Extreme-Pressure Steel Pipe Fitting",
    "DetailDescription": "Adapter, 1/2 NPT Female, M20 x 1.5mm Male Thread",
    "Specifications": [
      { "Attribute": "Shape", "Values": ["Straight"] },
      { "Attribute": "For Use With", "Values": ["Water","Air","Hydraulic Fluid","Oil"] }
    ],
    "Links": [ {"Key":"Price","Value":"/v1/products/4936K451/price"}, …,
               {"Key":"3-D STEP","Value":"…/4936K451_…STEP"} ]
  }
  ```
- **停产件有结构化替代关系**（原文示例字段）：`ProductStatus: "Discontinued"`、`Links[].Key = "SuggestedProduct"`，以及
  ```json
  "SuggestedProductDifferences": [
    { "Attribute": "Material", "DiscontinuedProductValue": "Plastic", "SuggestedProductValue": "Stainless Steel" },
    { "Attribute": "Width", "DiscontinuedProductValue": "1-3/4\"", "SuggestedProductValue": "2\"" }
  ]
  ```
- 限制：订阅数量与每日新增有上限；CAD 类端点有速率限制。

⭐ **这是本次调研中最有价值的「零件数据 API」事实**：
- ✅ **有**：结构化属性（`Specifications[].Attribute/Values`）、衍生替代品与**结构化差异**（`SuggestedProductDifferences`）、CAD 文件直链。
- ❌ **没有**（就官方文档所列端点与字段而言）：任何 **「part A mates with part B」** 字段。`For Use With` 描述的是**介质兼容性**（水/空气/液压油），**不是**机械配合关系。
- 🔶 **推论**：`SuggestedProductDifferences` 的**结构**（属性名 + 旧值 + 新值）非常值得抄进自己的库——**「替代件是否仍满足约束」正是一个可判定的规则检查**。

**TraceParts API** ✅ —— <https://developers.traceparts.com/docs/upgrade-webservices-api-gateway>
- 端点族（已验证名称）：`SupportedLanguages`、`YourOwnCode/Availability`、`PartNumber/Availability`、`Product/CadDataAvailability`、`Product/cadRequest`、`Product/cadFileUrl`、`Account/CheckLogin`、`Account/SignUp`、`RequestToken`（`tenantUid` + `apiKey` → Bearer，24h）。
- 返回：`partFamilyCode`、`selectionPath`、`cadFormatId`/`cadFormatName`、`deliveryMethod`。
- 明确建议对响应做 24h 缓存。
- ❌ **就所列端点而言，没有任何兼容/配对端点。**

**Misumi** ✅（部分）—— 搜索引擎索引到的官方目录标题含：
> "Standard products / Economy series products" 对照表（`my.misumi-ec.com/pr/vona/free_download_misumi_economy_catalog/pdf/index_019_aluminum_frames_related_accessories.pdf`）
> "Standard Extrusion Size(mm) | 20 | Extrusion Size | 20x40 | Extrusion Shape…"（Misumi 官方 TDS，经 Clearpath Robotics 文档镜像：`docs.clearpathrobotics.com/assets/files/clearpath_robotics_026926-TDS1-…pdf`）
> Misumi 铝型材手册：`th.misumi-ec.com/th/pr/vona/campaign/economy_library/file/misumi_aliminum_frame_booklet.pdf`
⚠️ **正文未取得**，因此**不断言** Misumi 是否提供机器可读的兼容表。
🔶 但「Standard vs Economy 系列」这一区分本身提示：**同一厂商内部存在「系列」这一层级，系列内互配、跨系列未必**——这与他们的 2020/4040 判断同构。

**Bossard**：⚠️ **未验证**。仅见官方下载中心页面（<https://www.bossard.com.cn/cn-zh-cn/knowledge-hub/resources/download-center/>），**未读内容**。

#### A.4.2 铝型材：系列/槽宽配套表 —— 可编码，但需自己誊写

**item 24（item Industrietechnik）** ✅ —— <https://blog.item24.com/en/item-world/aluminium-profile-types-an-overview-of-the-differences/>（官方博客，2023-07-19）

已验证的原文事实：
- **产品线即「系列」**：`Line 5 / Line 6 / Line 8 / Line 10 / Line 12`（+ `Line X`）。
- **三个几何特征决定一切**（原文三条）：
  > "**Modular dimension**: Each line is based on mostly square profiles with an external dimension of **20, 30, 40, 50 or 60 mm**. Continuous grooves run along all four sides."
  > "**Groove dimension**: The size and load-carrying capacity of the groove increase in line with the modular dimension. **Most profile connections are anchored in the groove.**"
  > "**Bore diameter**: The core bore offers a stable fastening point at the end faces … This bore can be used as a basis for **subsequently tapping a thread**."
- **逐线对应关系**（原文）：
  - Line 5 = 模数 **20 mm**
  - Line 6 = 模数 **30 mm**
  - Line 8 = 模数 **40 mm**（"the most frequently used of all the item aluminium profiles worldwide"）
  - Line 10 = 模数 **50 mm**，"**The 10 mm groove width makes it possible to work with accessories with thread size M10.**"，"The maximum permissible load-bearing capacity is **7000 N**"
  - Line 12 = 模数 **60 mm**，"tensile loading of up to **10,000 N per screw connection**"
  - Line X："uses the **Line 8 profile groove**"（⭐ **显式声明跨系列槽型复用**）
- **命名即接口描述**（原文）：产品名形如 `Profile 8 40×40 1N light, natural`，各段含义在官方博客图中逐段解释。
- **规模**："more than **4,500 mutually compatible components**"（原文）。
- **同一系列内还有设计变体**：`Standard` / `Light` / `Economy`，原文注 "not every aluminium profile is available in all three designs"，且 Light/Economy 的 "maximum tensile loading … is reduced"。

⭐ **可直接编码为规则的部分**（🔶 推论）：
- `series` → `slot_width` → 允许的 `thread_size` 三元组链（Line 10 → 10 mm 槽 → M10 附件，原文明确）。
- `Line X` 显式声明复用 Line 8 槽型 ⇒ **兼容性是「槽型」而非「系列名」的属性** —— 这是一个重要的建模教训：**不要把兼容性绑在商品系列名上，要绑在几何接口特征上**。
- `Standard/Light/Economy` 影响**承载能力**而非**几何互配** ⇒ 需要区分「几何可配」与「力学可配」两类规则。

❌ **诚实结论**：item 的公开材料里**没有**机器可读的兼容性表（无 JSON/CSV/API）。**每一条都得人工誊写。**

**80/20 Inc**：⚠️ **部分未验证**。官方《80/20 University》手册 PDF 我已下载（16 MB，`otcindustrial.com/media/sftp_uploads/documents/brochures/8020/8020-university-booklet.pdf`），但**pypdf 报 `PdfReadError: Invalid object in /Pages`，文本抽取失败**。因此我**无法引用其任何具体规格**。搜索索引显示该手册含 "categorize fasteners into two main groups: internal fasteners…" 等字样，但**不足以作为事实**。

**Bosch Rexroth**：⚠️ **未验证**。官方铝型材选型 PDF `dc-mkt-prod.cloud.bosch.tech/us/media/products_1/product_groups/assembly_technology/pdfs_1/r999001283.pdf` **未取得正文**。**不断言其槽宽系列编号。**

**T-slot structural framing（Wikipedia）**：⚠️ 未验证正文，不作为来源。

---

### A.5 开源/研究系统

#### A.5.1 FreeCAD Fasteners Workbench —— **最接近他们构想的具体实现** ✅

来源：[FreeCAD 官方文档 · Fasteners Workbench](https://wiki.freecad.org/Fasteners_Workbench)

**已验证的关键机制**：
> "**Attached fasteners** have a Data **Base Object**, a circular edge, and their Data **Placement** is dynamically linked to that object."
> 使用流程：**先**指定所选孔是 **tap hole** 还是 **pass hole**（`Fasteners_MatchTypeInner` / `Fasteners_MatchTypeOuter`，原文："Specify if the selected holes are tap holes or pass holes by selecting Match for tap hole or Match for pass hole respectively"），然后选择圆边，再选螺钉；
> "The default dimensions of each fastener **depend on the radius of the circular edge it is attached to**. **Countersunk screws are matched by their head diameter, other fasteners are matched by their shaft diameter.**"

⭐ 这直接就是**基于接口几何的确定性选型规则**：接口类型（tap/pass/countersunk）+ 几何量（半径）→ 零件规格。**而且是可判定的、非模型猜测的。**

其它已验证事实：
- 螺纹是可选生成的（`Data Thread` 属性），原文警告 "Generating threads is costly. Recomputes take much longer if there are many fasteners with threads in a document." ⇒ **载荷/性能与语义分离**。
- 提供 `Fasteners_ScrewCalculator`（底孔计算器）、`Fasteners_ChangeParameters`、`Fasteners_Search`、`Fasteners_BOM`（生成 BOM 电子表格）。
- 支持的紧固件标准极多，且**标准号即规格身份**：ASME B18.2.1.1 / B18.2.1.6 / B18.2.1.8、DIN 571 / 933 / 961 / 6912 / 7984、EN 1662 / 1665、ISO 4014 / 4015 / 4016 / 4017 / 4018 / 4162 / 8676 / 8765 / 15071 / 15072、ISO 4762 / 7379 / 7380-1 / 7380-2 / 10642、ISO 14579–14584、ISO 1207 / 1580 / 2009 / 2010 / 7045–7048 …（文档列出完整清单，含 **Nuts** 与 **T-slot fasteners** 两个分类）。

🔶 **推论**：`Fasteners_MatchTypeInner` / `MatchTypeOuter` 这个二分**就是**一个最小的「接口类型系统」。他们的标准件库应该把每个配合接口标注为**接口类别**（`threaded_hole` / `clearance_hole` / `slot` / `face` / `bore` / `shaft`…）+ **接口参数**（螺纹规格、孔径、槽宽、公差带…），然后规则在**类别 × 参数**上求值。

#### A.5.2 BOLTS —— 「开放的技术规格库」 ✅（标题级）

来源：<https://github.com/boltsparts/BOLTS_archive>，仓库描述原文：
> "**BOLTS is an open library of technical specifications**"

✅ 已验证：BOLTS 是**以「技术规格」而非几何为中心**的开放库，并且有 FreeCAD 集成（`BOLTSFC Workbench`，见 [Thread for Screw Tutorial](https://wiki.freecad.org/Thread_for_Screw_Tutorial)："BOLTSFC Workbench, to place fasteners from the BOLTS library"）。

⚠️ **未验证**：BOLTS 的数据文件格式细节（是否 YAML/JSON、是否含 mating 语义）。**不断言。**

#### A.5.3 FreeCAD Assembly3 —— 几何约束求解器，**不是**语义规则检查器 ✅

来源：[FreeCAD 文档 · Assembly3 Workbench](https://wiki.freecad.org/Assembly3_Workbench)

已验证要点：
- 定位是 **"dynamic/interactive solver"**，基于 FreeCAD 0.19 的 App Link。
- 约束是**纯几何**的：`Locked`、`Plane alignment`、`Plane coincidence`、`Attachment`、`Axial alignment`、`Same orientation`、`Multi parallel`、`Angle`、`Perpendicular`、`Points coincident`、`Point on plane/line/circle`、`Points distance`、`Point plane/line distance`、`Symmetric`，以及 Sketch 类约束（`Equal length`、`Colinear`、`Diameter`…）。
  - 例如 `Plane alignment`："Add a 'Plane alignment' constraint to align planar faces of two or more parts. The faces become coplanar or parallel with an optional distance."
  - `Attachment`："attach two parts with the selected geometry elements. This constraint completely fixes the parts relative to each other."
- **"assembly freeze"** 机制（原文）："As the CPU can only handle a restricted number of concurrent constraints in real time, to freeze an assembly allows to use constraints even for large assemblies. By freezing finished assemblies or constraints that are not required to remain dynamic (e.g. welded, bolted or glued parts) those are excluded from update calculations and considered fixed geometry by the Assembly3 solver."
- 层次装配（hierarchical assemblies）、一个零件多处复用（links）、外部文件链接。
- ⚠️ 文档中**没有**出现任何「语义兼容性」或「规则检查」概念。

🔶 **推论**：Assembly3 证明的是「**几何约束**可以求解」，而**不能**证明「M5 螺钉配 M5 螺母」——**求解器不检查语义**。这正好把他们要做的事和已有开源能力区分开了：**几何求解 ≠ 接口语义校验**。

#### A.5.4 Assembly4 / CadQuery CI / 其他

- **FreeCAD Assembly4**：⚠️ **未验证正文**。技术手册存在于 `github.com/chennes/FreeCAD_Assembly4-1/blob/master/TECHMANUAL.md`，**未读取**。
- **CadQuery 的构建与测试**：⚠️ **未验证正文**。仅见 [DeepWiki · CadQuery Building and Testing](https://deepwiki.com/CadQuery/cadquery/5.1-building-and-testing)（第三方镜像，非一手）。
- **"CAD linter" / "assembly lint" / "unit test framework for CAD"**：⚠️ **未找到有价值的、可验证的一手来源**。搜索结果中出现的相关条目质量很低（个人博客、无关论文）。
  🔶 **推论**：**「CAD 的 CI / linter」这一命名空间基本是空的**。这对团队是**好消息**（有先例可借，但没人占位）也是**坏消息**（没有现成轮子）。
- **build123d / cadquery 社区的规则检查器**：⚠️ **未找到**。**不做断言。**

#### A.5.5 学术概念：「mechanical netlist」是有传统的

✅ **已验证存在的一篇**（有全文入口）：
> *Evaluating Assemblies of Planar Parts Using the **Liaison Graph** and System Dynamics* — eCAADe 2008
> <https://papers.cumincad.org/data/works/att/ecaade2008_013.content.pdf>
（⚠️ 我只验证了标题与 PDF 入口，**未读正文**，因此**不断言**其方法细节。）

⚠️ **未验证但反复出现的术语**（搜索引擎索引命中，正文未读，**仅作为「检索词」而非事实**）：
- "assembly constraint graph"、"assembly liaison graph"、"interface graph"、"mating graph"、"joint graph"、"kinematic graph"
- 装配本体 / OWL-RDF 零件本体：命中 [CEUR-WS Vol-4176 (FOMI)](https://ceur-ws.org/Vol-4176/fomi-5.pdf)、Springer *IJIDeM* `10.1007/s12008-023-01242-7`、KTH DiVA `diva2:1173873`（含 `is-Feature-For-Assembly`、`GFO: Feature-For-Assembly`、`AM-DO:DOF` 之类术语片段）
- 装配序列规划 / 子装配识别：`10.1007/s00170-013-4799-y`

🔶 **推论**：**「装配的图模型」在学术界有几十年传统，术语已稳定**（liaison graph / constraint graph）。他们**不需要发明新词**；但**没有证据表明**有人把这个图模型与「标准件库的声明式接口元数据 + 规则引擎」组合成产品。

#### A.5.6 STEP AP242 / PMI

⚠️ **未验证**。我没有取得 ISO 10303-242 或 AP242 PMI 语义的一手正文。
- 搜索引擎命中一篇 NIST 出版物（`tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958015`）提及 "ISO 14649"，但**与 AP242 PMI 无直接关系，且未读**。
- 🔶 **仅作方向性提示**：AP242 承载 semantic PMI/GD&T 是行业常识，**但我这次没有取证**。若团队要用 PMI 喂检查器，**必须单独验证 AP242 的 PMI 语义能否无损映射到自己的接口模型**。

---

## B. 规则/数据格式参考（可直接抄的语法与 schema）

### B.1 ⭐ KiCad `.kicad_dru` —— **最值得抄的规则 DSL 形态** ✅

**为什么值得抄**：S-表达式（易解析、易 diff、易生成）、条件与约束分离、A/B 双向配对语义、单位后缀内建、变量注入、规则文件独立且进版本控制。

**完整骨架（原文语法）：**
```
(version 1)

# 注释以 # 开头

(rule <name>
    [(severity <severity>)]      ; error | warning | ignore | exclusion
    [(layer <layer_name>)]       ; 或 outer / inner；省略则适用所有层
    [(condition <expression>)]   ; 无 condition 则无条件适用
    (constraint <constraint_type> [constraint_arguments]))
```

**条件表达式（原文示例与规则）：**
```
(rule "Top side footprints only"
    (layer B.Cu)
    (constraint disallow footprint))

(rule "clearance_outer"
    (layer outer)
    (constraint clearance (min 0.25mm)))

(rule HV
    (condition "A.hasNetclass('HV')")
    (constraint clearance (min 1.5mm)))
```
- 对象：`A` / `B`（顺序无关，引擎双向测试）/ `AB`（成对函数）
- 属性/函数语法：`<object>.<property>`、`<object>.<function>([arguments])`
- 运算符：`==` `!=` `>` `>=` `<` `<=` `&&` `||` `!`（**同优先级，左到右**）
- 单位后缀：`mm` `mil`/`th` `in`/`"` `deg` `rad`；无后缀则为内部单位
- 数值可用简单算术：`(condition "A.Hole_Size_X == 1.0mm + 0.1mm")`、`(constraint clearance (min 0.5mm + 0.1mm))`
- 可空属性与 `null`：`(condition "A.Soldermask_Margin_Override != null")`
- 布尔属性直接写：`A.Do_not_Populate` / `!A.Do_not_Populate`（⚠️ 原文明确：规则语言里**不存在** `true`/`false` 字面量）
- 变量注入：`(constraint clearance (min ${hv_clearance}))`

**min/opt/max 三段值（原文）：**
> "Min/opt/max values are specified as `(min <value>)`, `(opt <value>)`, and `(max <value>)`. … The **minimum** and **maximum** values are used for design rule checking … The **optimal** value is only used for some constraints, and informs KiCad of a 'best' value to use by default."

⭐ **「opt 不参与 pass/fail，只作为默认/推荐值」是一个极其有用的设计**：它把「**必须满足**」与「**建议值**」放进同一个句式而不混淆。

### B.2 ⭐ KiCad ERC 的 `Pin Conflicts Map` —— **N×N 兼容矩阵** ✅

**结构**：行 = A 引脚电气类型，列 = B 引脚电气类型，单元格 ∈ {`allowed`, `warning`, `error`}。点击循环切换。

**为什么这是他们最该照抄的数据结构**（🔶 推论）：
- 「螺钉 ↔ 螺母」的兼容矩阵天然是**对称或近对称的稀疏矩阵**，用矩阵表示可以**一次定义、批量求值**，且**冲突对可以枚举出来做覆盖率检查**。
- 值域里同时有 `warning` ⇒ **允许「能配上但可疑」**（例如 M5 螺钉拧进 M5 螺母但啮合长度只有 3 mm）。
- 矩阵是**配置数据、不是代码** ⇒ 规则变更不需要发版，且可被非程序员审阅。

**建议的映射（🔶 推论，非任何来源的说法）：**

| 电气概念（KiCad） | 机械对应物 |
|---|---|
| 引脚电气类型（Input/Output/Passive/Power input…） | 接口类别（`threaded_hole` / `clearance_hole` / `slot` / `boss` / `bore` / `shaft` / `face`…） |
| Pin Conflicts Map 单元格 {allowed, warning, error} | 「A 类接口能否与 B 类接口配合」+ 严重度 |
| netclass | 零件族 / 系列（`2020-series` / `4040-series` / `M5-coarse`） |
| netlist / connectivity graph | 装配接口图（谁接谁、通过哪个接口） |
| `library_link` = `lib:footprint` | 标准件库引用 = `lib:part@revision` |
| ERC "Input pin not driven" | 「螺纹孔没有任何紧固件接入」/「角码没有连接到型材槽」 |
| `Unconnected` 引脚类型 | 接口标记为「本设计中不得被连接」 |

### B.3 Altium `.rul` ✅（仅格式存在性）

- 文件扩展名 `.rul`，通过 **Design » Rules → 右键 → Import/Export Rules → 选规则类型** 交互。
- ⚠️ **内部语法未验证**。**不要假设它是文本或二进制。**

### B.4 NX Check-Mate：KF `.dfa` + XML 参数文件 ✅（部分）

- **Checker 逻辑**：Knowledge Fusion，`.dfa` 文件，核心是 `do_check:` 属性；报告用 `ug_mqc_log(LOG_ERROR, {}, msg)`。
- **对象类型系统**：`..\UGCHECKMATE\dfa\mixins\ug_object_types.dfa`（原文给出的路径）。
- **规则参数**：来自 "user-defined **XML** files"（对应 `%mqc_check_preferences` checker）。
- **Profile**：一组 checker + 预配置参数的打包。

⭐ **「逻辑在 `.dfa`，参数在 XML」的分离值得抄**：它让同一份 checker 逻辑服务多套质量标准。

### B.5 McMaster-Carr 产品 JSON schema ✅

```json
{
  "PartNumber": "…",
  "ProductStatus": "Active | Discontinued",
  "FamilyDescription": "…",
  "DetailDescription": "…",
  "Specifications": [ { "Attribute": "…", "Values": ["…"] } ],
  "Links": [ { "Key": "Price|Image|2-D DWG|3-D STEP|SuggestedProduct", "Value": "…" } ],
  "SuggestedProductDifferences": [
    { "Attribute": "Material", "DiscontinuedProductValue": "…", "SuggestedProductValue": "…" }
  ]
}
```
⭐ 三个可直接借鉴的字段设计：
- `Specifications` 是 **属性名 → 值数组**（而非固定列），可容纳任意零件族的异构属性。
- `SuggestedProduct` + `SuggestedProductDifferences` = **「替代件 + 差异清单」的结构化表达**。
- `ProductStatus` 显式建模**生命周期状态**（`Active` / `Discontinued`）—— 🔶 推论：规则引擎应当能对 `Discontinued` 的零件发出告警。

### B.6 标准号即 schema 命名空间（🔶 推论，但事实基础 ✅）

从 FreeCAD Fasteners 支持清单与 Misumi/ISO 命名可以看到一个稳定模式：
- 零件身份 = **标准号 + 规格串**（`ISO 4762 M5×20`、`DIN 933 M6×25`、`ASME B18.2.1.6 1/4-20×1`）。
- 🔶 推论：**标准号天然是接口语义的命名空间**，可以直接作为规则条件的匹配键（等价于 KiCad 条件里的 `A.Library_Link`）。

---

## C. 标准件配套数据的现实可得性（诚实评估）

### C.1 逐项判定

| 他们要的检查 | 能否用**公开标准/数据集**支撑？ | 结论与理由 |
|---|---|---|
| **螺钉 ↔ 螺母：螺纹规格一致（M5 配 M5）** | ✅ **可由公开标准推导**（ISO 261 一般用途米制螺纹·优选系列；ISO 262 螺钉/螺母/螺栓选用；ISO 68-1 螺纹基本牙型；ASME B1.1 统一英制螺纹） | 螺纹**规格串本身**（`M5×0.8`）就是判定键。**问题不在标准，在于缺一个权威的机器可读数据集** —— 需要自己从标准的尺寸表誊写。见 C.2。 |
| **螺距匹配（粗牙/细牙）** | ✅ 标准有；❌ 数据集无 | M5 粗牙 0.8 mm、细牙 0.5 mm 是标准值。**必须自己建表**，或复用开源实现（BOLTS / FreeCAD Fasteners）里的参数表——⚠️ 但那是**开源实现的数据**，**不是标准原文**，需自行核校。 |
| **啮合长度充分** | ✅ 标准/手册有指导值；❌ 数据集无 | 啮合长度下限通常是**工程经验值**（常见说法是 ≥ 1×d 或 1.5×d，随材料变化）。⚠️ **我这次没有取得权威一手来源来给出具体倍数，故不写具体数字。** 团队须自定阈值（这正好适合放进「工程参数变量」，参照 KiCad 的 `${hv_clearance}`）。 |
| **型材 ↔ 角码：2020 vs 4040 系列匹配** | 🔶 **部分可编码，但必须自建表** | item24 **公开了** Line ↔ 模数 ↔ 槽宽 ↔ 螺纹尺寸的对应叙述（Line 10 → 10 mm 槽 → M10；Line X 复用 Line 8 槽型）。但**没有机器可读表**。80/20、Bosch Rexroth、Misumi 的对应关系**我未能验证**。⇒ **必须人工誊写；跨厂商更是必须自建。** |
| **槽宽 6 mm vs 8 mm 匹配** | 🔶 同上 | 槽宽是**几何量**，可从自己建的型材零件模型中直接测量/声明 ⇒ **不依赖外部数据**。这是好消息。 |
| **轴承 ↔ 轴/座（ISO 286 配合，H7/g6 等）** | ✅ 标准存在（ISO 286-1 术语与公差等级、ISO 286-2 孔轴极限偏差表）；❌ 开放数据集未找到 | ⚠️ 我**没有**找到权威的机器可读 ISO 286 数据集。搜索引擎命中的多为 ГОСТ 25346/25347（ISO 286 的俄标等同采用）网页版表格，**非权威一手、非机器可读**。⇒ **需自建**，但从标准表格誊写是机械工作。 |
| **轴承 ↔ 轴承座/轴（ISO 15 边界尺寸）** | ⚠️ **未验证** | 我只看到轴承厂商目录 PDF（如 RKB Bearing Catalogue）被索引，**没有**找到开放数据集或 API。**不做断言。** |
| **「part A mates with part B」的开放数据集** | ❌ **未找到，判断为不存在** | 🔶 **这是本次调研最重要的 gap**：电子侧有 SnapEDA / Ultra Librarian 这类「符号 + 封装 + 引脚映射」库，机械侧**没有对应物**。McMaster-Carr 与 TraceParts 的 API 都**只给属性 + 几何**，不给配对关系。**这意味着他们的「配套性表」是原创资产，也是护城河。** |

### C.2 关于「机器可读的螺纹/配合数据」的诚实结论

- ✅ **标准本身是公开可买的**：ISO 261 / ISO 262 / ISO 68-1 / ISO 286-1 / ISO 286-2 / ASME B1.1 **确实存在**。
  ⚠️ **但它们的正文是付费标准**，且**我没有验证**任何官方机构发布过 JSON/CSV 形式的机器可读版本。
- 🔶 **推论**：**「用公开标准」和「有现成数据集」是两件不同的事**。前者的意思是「数据是客观的、可核校的、无版权争议的事实性数值」；后者的意思是「有人已经誊好并持续维护」。**机械领域基本只有前者。**
- ⚠️ **法律/工程提醒**（🔶 推论）：从付费标准里誊写数值到自己的数据集，通常属于**使用事实性数据**；但**分发标准全文的复制件**是另一回事。请团队自行确认合规边界——**这不是我的专业领域，我未做任何法律核查。**
- ✅ **可复用的开源来源（非标准原文）**：
  - [BOLTS](https://github.com/boltsparts/BOLTS_archive) —— 自述为 "an open library of technical specifications"
  - [FreeCAD Fasteners Workbench](https://wiki.freecad.org/Fasteners_Workbench) —— 覆盖 ISO/DIN/EN/ASME/GOST 大量紧固件标准，可作为**规格串与尺寸的对照源**
  - ⚠️ **使用前必须自行核校准确性** —— 开源实现的数值可能有误，且可能不覆盖他们需要的全部规格。

### C.3 结论：哪些能靠公开数据，哪些必须自建

**能靠公开标准/资料（但仍需自己誊写成表）：**
1. 螺纹规格与螺距（ISO 261/262、ISO 68-1、ASME B1.1）
2. 孔轴配合公差带（ISO 286-1/2）
3. 型材系列 ↔ 槽宽 ↔ 螺纹尺寸（厂商公开资料，item24 已部分验证）
4. 紧固件几何尺寸（各标准；开源实现可作对照）

**必须完全自建的原创资产：**
1. ⭐ **「接口类别 × 接口类别」的兼容矩阵**（螺钉↔螺母、型材↔角码、轴承↔座…）
2. ⭐ **「什么算充分」的阈值**（啮合长度下限、槽内可承受载荷、跨系列适配的例外）
3. ⭐ **跨厂商等价性**（item 的 Line 8 与 Bosch Rexroth 的某系列是否互通？——**没有任何一方会公开承认或担保这个**）
4. ⭐ **每个标准件的「接口清单（port manifest）」本身** —— 把几何模型翻译成「我有哪几个接口、各是什么类别、参数是什么」。**这是整件事的地基，且没有现成数据。**

---

## D. 设计模式总结（指导他们实现）

### D.1 贯穿所有先例的四个不变式

**① 语义模型与几何模型分离** ✅（来自 KiCad 与 NX 的双重证据）
- KiCad：`.kicad_sch`（原理图/网表/netclass）↔ `.kicad_pcb`（几何/铜层）。DRC **同时**检查几何规则与「schematic ↔ PCB parity」。
- NX：checker 逻辑（`.dfa`）↔ 规则参数（XML）↔ 模型几何。
- 🔶 **对他们**：`part.py`（build123d 几何）与 `part.meta.yaml`（接口清单 + 规则）**必须是两个文件**，且 meta **可以在没有几何的情况下被独立校验**。

**② 规则是数据，不是代码** ✅
- KiCad：`.kicad_dru`，纯文本，进版本控制，有语法检查门禁。
- NX：checker 逻辑与 XML 参数分离；profile 打包规则集。
- Altium：`.rul` 可导入导出。
- 🔶 **对他们**：**绝不允许 LLM 在生成的 Python 里内联断言来充当规则**。模型应该**只**声明「我在 A 和 B 之间建立了一个 `threaded_hole(M5)` ↔ `screw(M5×20)` 的连接」，**由外部规则文件决定这算不算通过**。

**③ 检查器对着「图」求值，而不是对着坐标求值** ✅
- KiCad DRC 对着 connectivity graph 逐对对象求值；条件语言里的 A/B 就是图中相邻的两个对象。
- ERC 对着 net 求值（"per-net ERC markers"）。
- 🔶 **对他们**：核心中间表示是**装配接口图（assembly interface graph）**——节点是零件实例的接口，边是「这两个接口被装配在一起」的声明。规则在边上求值。

**④ 输出是机器可读报告 + 可持久化的豁免** ✅
- KiCad：纯文本报告文件；exclusion（含 comment）+ ignore，**跨多次运行被记住**。
- 🔶 **对他们**：CI 要能消费这个报告；豁免必须**带理由、带责任人、带到期**，否则规则表会被豁免淹没。

### D.2 建议的落地架构（🔶 推论 —— 这是我基于上述事实的构造，不是任何来源的说法）

```
标准件库 (packages/parts/)
├── iso4762_m5x20/
│   ├── part.py            # build123d 几何，纯几何，无断言
│   └── interface.yaml     # ★ 接口清单：声明式、可独立校验
│       part_id: iso4762_m5x20
│       revision: 3
│       family: socket_head_cap_screw
│       standards: [ISO 4762]
│       ports:
│         - id: thread
│           kind: external_thread
│           spec: { system: ISO_metric, diameter_mm: 5, pitch_mm: 0.8, class: "6g" }
│           axis: [0,0,1]          # 语义坐标系，不是几何顶点
│           length_mm: 20
│         - id: bearing_face
│           kind: planar_face
│           normal: [0,0,-1]
│       mass_g: 4.2
│       lifecycle: active
│
├── iso4032_m5_nut/…       # 同理，ports: [{kind: internal_thread, spec: {…, class: "6H"}}]
├── item_line8_40x40/…     # ports: [{kind: slot, slot_width_mm: 8, series: "8"}, …]
└── item_line8_corner/…    # ports: [{kind: slot_grip, accepts_slot_width_mm: 8}, …]

规则 (rules/)
├── compatibility.dru      # ★ 兼容矩阵 / 配对规则，版本化，进 git
├── engagement.dru         # 啮合长度、旋入深度
├── frame.dru              # 型材框架：系列一致性、槽宽一致性、装配方向
└── hygiene.dru            # 元数据卫生：未登记的零件、缺失的必需接口、引用了不存在的系列

检查器 (cadcheck/)
└── 读 interface.yaml → 构建装配接口图 → 加载 rules/*.dru → 求值 → 报告
```

**四层产出，对齐他们现有的 L1–L4：**

| 他们的层 | 建议新增/强化 |
|---|---|
| L1 API 速查 | 不变 |
| L2 Checkpoint 渲染（多模态看图） | 不变 —— **语义规则不能替代看图**，两者互补 |
| L3 数值断言（体积/实体数/bbox） | 保留，但**从「模型自证」降级为「几何自洽性底线」** |
| **L4（新）接口语义规则检查** | **本报告的重点**：图 + 规则 + 报告，像编译器一样 pass/fail |

### D.3 具体的迁移建议（🔶 推论）

1. **把「模型自证」换成「模型声明意图 + 检查器裁决」**。模型的产物从 `assert volume == 28274` 变成 `connect(part_a.port_thread, part_b.port_thread)`，由规则文件决定 M5 配 M6 是否 error。
2. **给规则文件加版本头 + 语法门禁**（照抄 `.kicad_dru`）。
3. **定死规则优先级语义**（照抄 KiCad 的「后来居上、首命中即停」，或显式定义一个优先级数）。
4. **用矩阵表达兼容性**（照抄 Pin Conflicts Map），值域含 `warning`。
5. **规则里只用「接口语义标识符」，绝不引用拓扑实体名**（如 `Face17`）。KiCad 规则只认 `Net`/`NetClass`/`Reference`，**不认边的 ID**——这是它能在编辑后仍然有效的原因。这一点**极其重要**：他们现在用 `Checkpoint.expect_faces(count)` 这类拓扑断言，在参数化模型里是**脆弱**的（拓扑命名问题）。
6. **规则要能引用工程参数变量**（啮合长度下限、最小壁厚…），而不是硬编码。
7. **豁免机制先于规则上线**：带理由、可持久化、可审计。
8. **报告机器可读**，接进 CI；规则文件坏了就**整体拒绝跑检查**。

---

## E. 风险与陷阱

### E.1 已被先例明确暴露的失败模式

| 陷阱 | 证据 | 后果 |
|---|---|---|
| **元数据质量决定引擎上限** | ✅ KiCad 原文："If symbols are designed incorrectly, ERC will not report accurate information." | 库里的接口标注错一个，整条检查链失效。**必须先有元数据评审流程，再谈规则。** |
| **规则被静默禁用** | ✅ KiCad 原文警告：severity 设为 `ignore` **并不停用规则**，规则仍被求值且**仍能覆盖更早的规则** | 一个 `ignore` 会连带改变后续规则的生效范围 —— **反直觉，易出错**。 |
| **规则求值顺序反直觉** | ✅ KiCad："Rules are evaluated in **reverse order** … the last rule in the file is checked first" | 新人写规则会放错位置，导致「明明写了规则却不生效」。需要 lint 或显式优先级。 |
| **豁免堆积** | ✅ KiCad 提供了三层豁免（单条 exclude / 带 comment / 整类 ignore）且**跨运行记忆** | 🔶 推论：豁免机制太方便 = 规则表逐渐失去意义。**需要配额/到期/审计。** |
| **对偶规则（required vs approved）容易只做一半** | ✅ NX 演讲稿把二者并列（"required attribute names missing" vs "unapproved attribute names present"） | 只做「该有的必须有」会漏掉「不该有的不许出现」（例如有人从库里手搓了一个没登记的零件）。 |
| **规则检查会掩盖需要人看的问题** | 🔶 推论 + ✅ 他们的 L2 渲染实践 | 规则通过 ≠ 设计正确。**规则是必要条件，不是充分条件。** 保持 L2 人工/多模态审查。 |

### E.2 该类系统历史上变得不可维护的原因（🔶 推论，基于上述事实外推）

1. **规则绑定了脆弱标识符**（拓扑实体名、面 ID）。参数化模型一改，规则全废。→ **只在语义标识符上写规则。**
2. **规则与几何耦合在同一份代码里**，导致改几何必须改规则、改规则必须重跑几何。
3. **没有版本化规则**：KiCad 有 `(version 1)` 头正是为了避免这个。
4. **兼容性绑在商品名/系列名上**，而非几何接口特征上。（item24 的 `Line X uses the Line 8 profile groove` 是反例的正确做法：**兼容性属于槽型，不属于系列名**。）
5. **跨厂商等价性被当成已知事实**：没有任何厂商会担保自己的型材与竞品互通。🔶 **推论**：这类规则必须标注**来源与置信度**，或干脆限定在单厂商生态内。
6. **阈值无处可调**：啮合长度、最小壁厚这类数值会随材料/工艺/供应商变化。**必须外置为参数。**
7. **规则集没有 profile/打包概念**：NX 用 profile 把「一套完整检查」打包；🞂 散装规则无法回答「这次检查覆盖了什么」。
8. **性能**：NX 的 assembly freeze 与 FreeCAD Assembly3 的 freeze 都是为了绕过求解器性能上限。🔶 **推论**：接口图检查通常比几何求解便宜得多 —— 这是他们的方案相对 Assembly3 路线的一个**结构性优势**，值得在设计文档里明说。

### E.3 LLM 特有的风险（🔶 推论 —— 这部分是我的分析，无来源）

1. **LLM 会「绕过规则」而不是「修正模型」**：如果规则能被模型改写，它迟早会改规则。→ **规则文件必须对模型只读。**
2. **LLM 会编造标准号与规格串**。→ 接口清单里的 `standards:` 字段应**对照白名单校验**（这正是 NX 的 "approved categories/attribute names" 对偶规则）。
3. **LLM 会产出「看起来通过」的元数据**：把 `spec: {diameter_mm: 5}` 写进一个实际上是 M6 的零件。→ 需要**几何-语义交叉校验**：从几何测量螺纹大径/槽宽，与 `interface.yaml` 的声明比对。⚠️ 这一条我**没有找到现成先例**（FreeCAD Fasteners 是由几何反推选型，方向相反）。🔶 **这可能是他们需要原创的部分。**

---

## 附录 A：最有价值的 10 个链接（按优先级）

1. ⭐ [KiCad PCB Editor 手册 · Custom design rules](https://docs.kicad.org/master/en/pcbnew/pcbnew.html)（文档源：<https://gitlab.com/kicad/services/kicad-doc/-/raw/master/src/pcbnew/pcbnew_advanced.adoc>）—— `.kicad_dru` 完整语法、约束类型表、对象属性表
2. ⭐ [KiCad 手册 · Electrical rules checking](https://docs.kicad.org/master/en/eeschema/eeschema.html)（源：<https://gitlab.com/kicad/services/kicad-doc/-/raw/master/src/eeschema/eeschema_inspecting_a_schematic.adoc>）—— ERC 检查项清单、Pin Conflicts Map
3. ⭐ [KiCad 手册 · Pin electrical types](https://docs.kicad.org/master/en/eeschema/eeschema.html)（源：<https://gitlab.com/kicad/services/kicad-doc/-/raw/master/src/eeschema/eeschema_symbols_and_libraries.adoc>）—— 12 种引脚类型及其冲突语义
4. ⭐ [NX Check-Mate 定制演讲稿（UGS/Siemens 官方）](https://ww3.cad.de/foren/ubb/uploads/schulze/NXCK2-Anderson.pdf) —— checker / profile / KF `.dfa` 架构
5. ⭐ [FreeCAD Fasteners Workbench](https://wiki.freecad.org/Fasteners_Workbench) —— tap hole vs pass hole 匹配机制（最接近的开源实现）
6. ⭐ [McMaster-Carr Product Information API](https://www.mcmaster.com/help/api/) —— 零件结构化属性 schema
7. ⭐ [item24 · Aluminium profile types](https://blog.item24.com/en/item-world/aluminium-profile-types-an-overview-of-the-differences/) —— Line 5/6/8/10/12 ↔ 模数 ↔ 槽宽 ↔ 螺纹
8. [Altium KB · Import or export Design Rules](https://www.altium.com/documentation/knowledge-base/altium-designer/import-or-export-design-rules) —— `.rul`
9. [DFMA® · What Is Design for Assembly](https://www.dfma.com/design-for-assembly.asp) —— 最小零件判据三问、DFA checklist
10. [BOLTS 开放技术规格库](https://github.com/boltsparts/BOLTS_archive) + [FreeCAD Thread for Screw Tutorial](https://wiki.freecad.org/Thread_for_Screw_Tutorial)（含 BOLTSFC / ThreadProfile 工作台）

---

## 附录 B：⚠️ 未验证清单（请勿引用为事实）

**A. 取得失败的一手来源（需用可访问网络重新取证）**
- SolidWorks 官方帮助全站（`help.solidworks.com`，JS 渲染 + 超时；`my.solidworks.com` 403）：DFMXpress、Design Checker、TolAnalyst、DimXpert 的**全部功能细节**
- Siemens NX Check-Mate 官方产品简介 PDF（`plm.automation.siemens.com/cz_cz/Images/fs_checkmate_quickcheck_tcm841-11882.pdf`，301 跳首页）
- Siemens *NX Checker* PDF（`plm.automation.siemens.com/de_de/Images/checker_tcm73-62406.pdf`，返回 `application/pdf` 但抓取失败）
- NXOpen .NET Reference · Package `NXOpen.Validate`（跨域重定向到 `scredirect.docs.sws.siemens.com`）
- Siemens Teamcenter **ClearanceDB** 管理员指南正文（仅确认其存在）
- Teamcenter *Lifecycle visualization mockup* PDF
- PTC Creo ModelCHECK 配置格式
- CATIA Knowledgeware User Guide（`bndtechsource.ucoz.com/.../kwxug2.pdf`，TLS 错误）— **EKL 语法完全未验证**
- DFMPro 白皮书（`dfmpro.geometricglobal.com/.../Whitepaper-The-other-side-of-design-for-assembly.pdf`）
- aPriori 文档（`docs.apriori.com`，403）
- **80/20 Inc** 官方手册 PDF（已下载 16 MB，**pypdf 解析失败：`PdfReadError: Invalid object in /Pages`**）
- Bosch Rexroth 铝型材选型 PDF（未取得）
- Misumi 官方目录 PDF（仅见标题片段）
- Bossard 下载中心（仅见页面）
- CadQuery 构建与测试文档（仅见第三方 DeepWiki 镜像）
- FreeCAD Assembly4 技术手册（`github.com/chennes/FreeCAD_Assembly4-1/blob/master/TECHMANUAL.md`，未读）
- eCAADe 2008 *Liaison Graph* 论文正文（仅验证标题与 PDF 入口）

**B. 明确无法确认的断言**
- Altium 规则类别完整清单、Query Language 具体语法、`.rul` 内部格式
- OrCAD/Allegro Constraint Manager 的任何细节
- Eagle `.dru` 的任何细节
- ISO 10303-242 (AP242) PMI 语义的具体表达方式
- 是否存在权威的机器可读 ISO 261/262/286/68-1 数据集（**我倾向认为不存在，但这是推论，不是验证结果**）
- BOLTS 的数据文件格式与是否含 mating 语义
- 轴承行业（ISO 15 边界尺寸）的开放数据集
- 「CAD CI / CAD linter / assembly lint」领域是否存在成熟开源项目（**我只确认了「搜索没找到好结果」，这不等于不存在**）
- Teamcenter / Windchill / 3DEXPERIENCE 的装配验证机制细节

**C. 我未做的核查**
- 任何法律/合规核查（标准数值誊写的版权边界）
- 任何具体数值的正确性核查（螺纹啮合长度倍数、型材承载值等，我均未给出具体数字）
