# 数据字典

规范数据为`data/*.jsonl`：UTF-8，每行一个JSON对象，保留数组、布尔值、数值和`null`类型。所有表带`dataset_snapshot_version`，来源身份使用`source_snapshot_id`（差异表为`local_source_snapshot_id`）。本版为`2026-11-02-g11-public-v1`。

## 表及关联

| 表 | 行数 | 身份与用途 |
|---|---:|---|
| `words.jsonl` | 11,000 | 一条来源词条一行；`word_key`与`vocab_id`唯一 |
| `stages.jsonl` | 11,105 | `stage_id`唯一；以`word_key`关联词条；含11,000基础与105扩展阶段 |
| `relations.jsonl` | 11,384 | `relation_id`唯一；`word_key`、`theme_id`、`class_id`连接词、主题和子类 |
| `themes.jsonl` | 35 | `theme_id`唯一，`name`为主题名称 |
| `taxonomy.jsonl` | 6,085 | `class_id`为规范子类身份；保留别名、范围及成员 |
| `source_notes.jsonl` | 26 | `note_id`唯一；涉及25词的来源疑点及项目解释 |
| `classification_dispositions.jsonl` | 89 | `issue_id`唯一；涉及86词的已处理分歧及限定范围 |
| `source_differences.jsonl` | 6 | `comparison_id`唯一；保存版与官网核验版的词汇字段差异 |

同形词不能按文字去重。`word_key`由来源快照与`vocab_id`组成，`relation_key`由来源快照与关系ID组成。名称相同或相近也不能自动合并子类；以`class_id`为准，`aliases`保存旧标识。

## 词条与等级

`written_form`保留来源词形及同形标识，`written_form_base`供文字检索，`homograph_index`为来源同形序号。`pinyin_source`、`pos_source`保存原标注；495条原词性为空，未补猜。`source_sequence`、`source_pdf_page`、`source_printed_page`等定位字段只适用于固定研究保存版，详见[SOURCES.md](SOURCES.md)。

`source_level_raw`保存来源等级写法，`base_level_band`为基础等级带，`base_level_min/max`为数值边界。`stages`里的`stage_kind`区分`base`与`extension`，`stage_order`保存阶段顺序，`pos_segment_source`保存该阶段词性段。7—9级保持一个等级带，不能拆成三个逐级结论。扩展阶段不是新增词条。`stage_ids`、`source_note_ids`、`classification_disposition_ids`为关联索引。

## 分类关系

`selected_meaning`是本关系所采用的意义；`scene`与`use`分别为场景和用途数组；`restriction`为使用条件。使用词表时应一起保留这些字段。`classification_rationale`说明归类理由；`relation_strength`及其理由表示关系强度，`classification_confidence`及其理由表示项目分类判断的确定程度，两者不能互换。5条置信度缺失保持`null`，`missing_fields`说明缺项；大小写及原标签不强行统一。

`research_pos`与官方原词性分开；`source_sense_level_status`不将研究义项当作官方分义等级。`evidence_ids`为研究参考定位码，`evidence_resolution`表示该记录的证据解析状态，不保证仓库提供对应参考全文。

`current_research_state=accepted_local_research`表示当前项目已接受的研究关系，不是官方认可。794条关系在研究历史中曾带待审原始状态，但已成为当前有效关系，本版完整保留。`all_senses_complete=false`表示没有穷尽词的全部义项。`scope_notes`保存额外语义范围，不应因它不是单一标签而丢弃。

## 目录与边界

`taxonomy.name`是现有可用名称，部分精细身份仍以ID显示。13类原记录没有独立完整定义，本版保留现有标签、主题边界及成员意义条件，并标明状态，不补造定义。`scope_kind`、`definition_status`区分范围描述类型；`scope_components`保存完整范围的分层原子，含`role`、`original_field`及`value`。其中`original_field`是源JSON字段导航，不是文件路径。`approved_member_relation_ids`及`approved_member_vocab_ids`列本版成员；`future_automatic_admission=false`表示不能把新词自动收入该类。

`source_notes`区分`source_question`、`adopted_project_interpretation`、`external_evidence_limit`、`official_source_corrected`和`source_anomaly_officially_resolved`。项目采纳解释不等于已解决官方来源疑点。

`classification_dispositions`中的`current_disposition`为当前项目处理结果；`branches`、`scope_components`保存问题、采用解释和原先问题范围。标为`previous_question_context_not_current_relation`的值是原问题语境，不是当前有效分类。历史状态字符串也不覆盖当前结果。`no_global_word_ban`、`other_senses_not_closed`和`scope_not_closed`等字段防止把一次限定不收录理解为永久禁用整词。当前分类仍以`relations`为准。

来源差异表的`local_value_json`与`website_value_json`本身为JSON字符串；`matching_state`记录匹配状态，`adoption_state=observed_not_adopted`表示已观察但未替换原研究值。

## CSV与Excel

`downloads/classified-vocabulary.csv`是一条关系一行的便用视图，附词形、拼音、基础/扩展等级和关系条件；其余8张CSV对应8张规范表。CSV使用带BOM的UTF-8，嵌套数组/对象与布尔值编码为JSON文本，`null`显示空单元格。疑似公式起始字符会加单引号作为表格显示保护；需要类型无歧义的程序处理请使用JSONL。导出时已逐单元格读回比较。目录CSV有超过131,072字符的完整范围单元格；Python读取时需先设足够的`csv.field_size_limit`（例如`100_000_000`），其他表格软件也可能有单格上限，不能据显示长度判断原数据完整性。

Excel是由公开数据新生成的便用副本，包含筛选、冻结表头及来源/许可说明。超过Excel单格上限的完整JSON分成有序的连续列，必须按列顺序连接后解析；不截断语义内容。以工作簿说明页标明的列名和分段规则为准。Excel与CSV不取代JSONL规范数据。

## 清单与离线读取

`data/manifest.json`列每张规范表的行数、字节数和SHA-256；`files[].path`相对该清单目录，下载条目的路径相对仓库根目录。来源快照、研究快照哈希和公开转换数量也在清单中。`query.py`读取前核验八表，输出原始关系、条件与相关说明；它不会访问网络或修改数据。同类/同主题表示主题关联，不表示近义、可互换或覆盖所有用法。
