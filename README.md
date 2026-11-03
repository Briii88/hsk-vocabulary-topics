# HSK 3.0 词汇主题分类表

**把已经分好类的词表提供给中文教师、学习者和材料编写者使用。** 下载表格，按词语、等级、主题或子类筛选，查看相关词及其具体意义和使用条件，用于编写练习、课文和口语材料。

An independently curated topical vocabulary dataset based on the HSK 3.0 syllabus: 11,000 source entries and 11,384 research classification relationships. Downloadable tables, an offline query tool, and an issue template are included. This is an independent research resource, not an official HSK classification or endorsement.

## 下载和使用

- [Excel分类词表](downloads/hsk-vocabulary-topics.xlsx)：直接打开筛选，包含词条、分类关系、阶段和边界说明。
- [分类词表CSV](downloads/classified-vocabulary.csv)：一条分类关系一行，附词形、等级和使用条件，适合导入其他工具。
- [其他CSV表](downloads/)：词条、等级阶段、目录、来源判断及分歧边界分别保存。
- [JSONL规范数据](data/)及[数据清单](data/manifest.json)：适合程序读取，文件带版本和校验值。
- 下载整个仓库：点击GitHub页面的 **Code → Download ZIP**，解压后即可离线使用。

第一次使用，建议先按词语搜索，再看所选意义和条件，最后筛选同一主题中的其他词。一个词可能对应多个主题；同形词也可能有不同来源身份。

例如，“医院”在医疗机构与人员相关分类中可关联医生、药店、病人、大夫、护士等；它也有公共服务主题关系。**同主题或同类不等于近义词，也不保证可以互换。**

## 本版内容

数据快照：`2026-11-02-g11-public-v1`。

| 内容 | 数量 |
|---|---:|
| 来源词条 | 11,000 |
| 当前有效分类关系 | 11,384 |
| 主题 | 35 |
| 规范子类身份 | 6,085 |
| 等级阶段 | 11,105（含105个扩展阶段） |
| 来源与项目判断说明 | 26条，涉及25词 |
| 已处理分类分歧的边界说明 | 89项，涉及86词 |

词表保留分类意义、场景、用途、理由、使用条件和关系强度。7—9级保持原合并粒度。原词性空值保留，不补猜；来源词条等级也不自动证明某个研究义项属于同一等级。

每个词的所有义项并未穷尽。部分子类当前只有一个词；工具会区分“同子类”与“同主题扩展”，不会为了凑相关词合并类别。已处理特定分歧不表示所有来源疑点或外部证据缺口都已消失。

## 离线查询

需要Python 3.10或更高版本，只使用标准库，无需API、账号或第三方依赖。在仓库根目录运行：

```sh
python3 query.py word --word 医院
python3 query.py related --word 医院 --scope class
python3 query.py related --word 医院 --scope theme --limit 20
python3 query.py filter --level 4 --mode cumulative --limit 20
python3 query.py themes
python3 -m unittest discover -s tests -v
```

`base`选择基础等级，`cumulative`选择该级及以下的基础词条，`extension`选择指定级别的扩展阶段。输出同时保留完整阶段信息，不把扩展阶段计成新词。

结果为JSON。`--limit`最多100，`--offset`翻页；无条件的`filter`默认空，显式`--all`才遍历全部词。程序只读本地数据，并核对清单中的哈希，不会修改数据、访问网络或自动更新研究结论。完整字段说明见[DATA_DICTIONARY.md](DATA_DICTIONARY.md)。

## 来源与版本

原始词条依据中外语言交流合作中心发布的《中文水平考试 HSK考试大纲》，封面载2025年11月发布、2026年7月实施。[官方公开入口](https://www.chinesetest.cn/)直接链接[大纲PDF](https://hsk.cn-bj.ufileos.com/3.0/%E6%96%B0%E7%89%88HSK%E8%80%83%E8%AF%95%E5%A4%A7%E7%BA%B21219.pdf)。文档日期不等同于各考点实际切换日期。

本版分类基于研究时保存的固定来源。2026年11月3日核验的官网文件与保存副本：词形及等级集合一致，但排序、部分页码和6词的拼音或词性标注不同。详见[SOURCES.md](SOURCES.md)及[来源差异表](downloads/source_differences.csv)。本版保留研究ID和原标注，另列观察到的官网差异，不自动将其当作官方勘误或改写分类。

主题、子类和说明是本项目的研究整理，含AI辅助工作与人工复核、裁决；不是官方逐词分类。38条材料依据型理由在公开版中采用保义改写。原PDF、教材或试题长文、原工作簿及内部审核档案不包含在仓库中。

## 提出修改建议

发现错分、漏分、需要新增分类或说明不清，可[提交词表修改建议](https://github.com/Briii88/hsk-vocabulary-topics/issues/new?template=vocabulary-feedback.md)。请填写数据版本、词语、`vocab_id`和已有的`relation_id`，说明建议与理由。找不到ID时，词语及当前主题也可以。

反馈先作为建议，由维护者审核后决定是否采纳。采纳的修改进入新版本并记录变更；不会自动改写当前词表或冻结研究。详见[CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可

- 本项目有权许可的原创分类、目录和研究说明：**CC BY 4.0**，允许复制、改编和商用，须署名并说明修改。[数据许可](LICENSE-DATA.md)
- 查询程序和测试代码：**MIT**。[代码许可](LICENSE-CODE)
- 官方来源字段单独注明出处；本项目不替第三方授予额外权利，不声称官方认证。[范围说明](LICENSE.md)

建议引用：`Briii88, HSK 3.0词汇主题分类表, 2026-11-02-g11-public-v1, https://github.com/Briii88/hsk-vocabulary-topics`。修改后请保留原来源，并说明自己的改动。
