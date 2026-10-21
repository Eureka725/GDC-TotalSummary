# GDC Community Index

从 **2026 年**开始持续整理 GDC 演讲的中英文资料索引，并补充 **2020—2023 年**历史归档：按年份、方向查找演讲，同时查看官方资料、相关文章与已核实的 YouTube 视频。

A community-maintained English/Chinese GDC index with historical archives for 2020–2023 and ongoing coverage beginning in 2026, including source references, bilingual reading notes, and verified YouTube recordings.

本项目受到 [Zilize/GDC-Index](https://github.com/Zilize/GDC-Index) 的启发，延续其按年、按方向阅读中英文摘要的形式。2024、2025 年资料请访问原仓库；本仓库独立采集官方元数据，新增来源核对、视频链接与可复现的维护工具。

## 年度索引

<!-- generated:years:start -->
| 年份 | 独立演讲 | 双语摘要 | YouTube 已核实 | 来源核对日期 |
| --- | ---: | ---: | ---: | --- |
| [2026](2026/README.md) | 374 | 374 | [19](2026/youtube.md) | 2026-10-21 |
| [2023](2023/README.md) | 568 | 568 | [14](2023/youtube.md) | 2026-10-21 |
| [2022](2022/README.md) | 488 | 488 | [36](2022/youtube.md) | 2026-10-21 |
| [2021](2021/README.md) | 434 | 434 | [23](2021/youtube.md) | 2026-10-21 |
| [2020](2020/README.md) | 209 | 209 | [22](2020/youtube.md) | 2026-10-21 |
<!-- generated:years:end -->

“独立演讲”按官方年度归档中的视频与幻灯片合并统计，可能包含颁奖等活动。双语摘要数量只计来源未变更的初稿和已校对条目；YouTube 数量统计已记录核验依据的播放链接，包含另列的官方发布方补充演讲。**这不是大会所有议程的完整清单。**

2026-10-21 整理批次已补齐当前归档原有的 **1,536 条**导读空缺；全部条目仍为待人工校对的双语初稿。逐年数量、来源范围及核验记录见[整理说明](docs/COVERAGE.md)。

## 如何阅读

进入年度目录后，选择方向。每条记录包含英文题目、可用的中文译名、讲者、官方方向、官方资料／相关文章、YouTube 视频和双语摘要。

- **官方资料／文章**：GDC Vault 资料页、公开幻灯片、讲者文章及其他已核实的相关阅读。
- **YouTube 演讲**：直接播放链接带频道和核验日期；尚未收录的视频附带明确标注的搜索入口。
- **双语摘要**：依据官方简介、公开演讲资料、讲者／发布方文章或大会报道整理，并列出具体出处与版本边界；AI 辅助初稿待人工校对。
- **访问状态**：公开页面、需注册、需会员按核对时的官方页面记录；公开资料页不等于所有视频均可免费观看。

## 本地维护

需要 **Python 3.11 或更新版本**。全部工具使用标准库，无需安装依赖或配置 API 密钥。

```bash
# 核验当前仓库并重建阅读页面（无需联网）
python -m gdc_index validate
python -m gdc_index build
python -m gdc_index report

# 更新年度官方目录和可公开读取的简介
python -m gdc_index sync --year 2026 --details --refresh
python -m gdc_index build

# 开始下一年；官方归档尚未发布时会保留现有数据并报错
python -m gdc_index sync --year 2027 --details
```

采集器只读取公开 HTML 元数据。它会限速、缓存、遵守 robots.txt，并保留人工摘要、相关文章和已核实视频；来源变更时将已有摘要标记为待复核。不会自动生成或猜测 YouTube 视频 ID。

详见 [维护指南](docs/MAINTAINING.md)、[数据与分类说明](docs/DATA.md)、[贡献指南](CONTRIBUTING.md)。

## 参与整理

欢迎通过 Issue 或 Pull Request 补充视频、文章、译名、摘要或纠错。请提供可核实来源，优先使用大会官方、讲者或所属工作室发布的内容。

数据源在 `data/<年份>/sessions.json`，阅读页面由脚本生成；修改数据后运行 `validate` 与 `build`。仓库内置 CI、资料提报模板和翻译队列导出／导入工具，详见贡献指南。

## 致谢与许可

感谢 [Zilize/GDC-Index](https://github.com/Zilize/GDC-Index) 对 GDC 中英文资料整理的启发，也感谢 [GDC Vault](https://gdcvault.com/) 与分享资料的讲者。

本仓库的原创代码和原创导读采用 [MIT License](LICENSE)。演讲、官方简介、视频、幻灯片及第三方文章的权利属于各自权利人；收录链接不改变其许可或访问条件。来源与整理范围见 [NOTICE](NOTICE.md)。
