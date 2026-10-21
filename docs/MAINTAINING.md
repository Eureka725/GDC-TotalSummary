# 维护指南

## 更新一个年份

2020、2021、2023 年的主会及 Summer／Showcase 归档已配置在 `config/archives.json`。`sync --year` 会采集该年份配置的全部活动，并分别保留活动名称；2022 年使用主会归档。旧年份的 Summit／Workshop 方向由 `config/tracks.json` 统一映射，原始名称不会丢弃。

在仓库根目录执行：

```bash
python -m gdc_index sync --year 2026 --details --refresh
python -m gdc_index validate
python -m gdc_index build
python -m unittest discover -s tests -v
python -m gdc_index build --check
```

不带 `--refresh` 时复用一周内的 HTML 缓存；不带 `--details` 时只更新目录。公开详情有助于补齐完整标题、多位讲者和官方简介；需会员或注册的页面仅保留目录元数据与访问标记。官方目录本身可能存在分类、讲者信息错误，来自目录而未经详情核对的记录会明确标注。

目录中长标题较多时，也可用 `python -m gdc_index sync --year 2023 --resolve-titles` 只请求被截断标题的公开详情。该选项不代表已读取全部演讲简介。完整简介可继续用 `--details` 获取；已有本地简介缓存与人工编辑内容会保留。

缓存、原始 HTML 与官方简介存放在被 Git 忽略的 `.cache/`。当前提交的 JSON 只保存索引元数据、原创双语导读与核实过的链接，不存视频、完整演讲、完整官方简介或第三方文章。

采集失败的详情写入 `.cache/vault/errors-2026.json`，不阻止其余公开元数据更新。年度目录为空、年份不符、新方向尚未映射或资源量下降超过 20% 时，中止更新并保留原数据。修改结构前先检查官方页面是否发生变化。

## 整理中英文摘要

```bash
python -m gdc_index export --year 2026 --missing-only --output .cache/queue-2026.json
```

队列包含公开简介及来源指纹，可手动编辑，或交给你选择的翻译／写作工具。仓库不绑定收费模型，也不会自行发送数据到外部 AI 服务。若本地缓存中没有简介，请打开原始资料核对，不能仅凭标题编造内容。

每个 `items` 条目可以编辑 `title_zh`、`summary` 和 `links`。保留 `id` 与 `source_hash`。新摘要应同时提供英文导读和中文导读，表达相同信息；`basis` 填写 `official-overview`、`talk` 或 `speaker-article`，`status` 初始为 `draft`，人工校对后为 `reviewed`。读过简介只能形成简介导读，不应声称观看了完整演讲。

```bash
python -m gdc_index import .cache/queue-2026.json
python -m gdc_index validate
python -m gdc_index build
```

导入时会检查 ID、来源指纹、摘要状态和视频链接，全部校验通过才写入数据。如果来源已变，重新导出队列后复核旧稿。请勿提交带有完整官方简介的本地队列。

也可直接编辑 `data/2026/sessions.json`；摘要的 `source_hash` 必须等于记录的当前 `source_hash`。直接编辑时同样需要执行 `validate` 和 `build`。

## 补充文章与 YouTube

文章记录保存在 `links.articles`，格式为：

```json
{"title": "讲者文章：主题与语言说明", "url": "https://example.org/talk-notes"}
```

视频记录保存在 `links.youtube`，格式为：

```json
{
  "title": "与演讲对应的实际视频标题",
  "url": "https://www.youtube.com/watch?v=XxvLyd4lKZM",
  "channel": "GDC Festival of Gaming",
  "checked_at": "2026-10-21",
  "evidence_url": "https://www.youtube.com/watch?v=XxvLyd4lKZM"
}
```

核对演讲题目、讲者、举办年份和发布者。YouTube 上传年份可能与演讲年份不同，不能只按上传时间判断。演讲可能在 YouTube 使用不同标题，需要通过官方活动页、讲者说明或视频简介确认对应关系。优先收录官方／讲者发布的完整演讲，剪辑、访谈或预告不能冒充完整演讲。

`evidence_url` 指向支持对应关系的官方页面或视频详情；`checked_at` 是核对日期，不是发布日期。频道页面、播放列表和搜索结果不属于直接视频 URL，校验器会拒绝把它们当成演讲视频。未找到视频时保留空数组，阅读页面会自动给出明确标注的搜索入口。

官方活动页链接的发布方还可能发布 Vault 年度目录未收录的演讲。此类资料写入 `data/2026/recordings.json`，使用 `article_url` 保留官方 GDC 活动页，用 `evidence_url` 记录能核对大会年份和发布关系的依据；不要猜测其 Vault ID。`build` 会生成单独的 `2026/youtube.md`，将这部分与已关联的归档条目分开显示。

采集器自动保留官方页公开提供的直接幻灯片链接；其他文章和 YouTube 链接通过核对后录入。代码不会把全局页脚的 YouTube 频道当成某一场演讲。

## 增加下一年或新增方向

```bash
python -m gdc_index sync --year 2027 --details
python -m gdc_index build
```

工具使用指定年份的 GDC Vault 归档，不根据会滚动改为下一年的日程首页推断年份。如果新年度尚未公开或解析失败，会保留已有数据。若官方出现新方向，在 `config/tracks.json` 明确添加映射，然后重跑采集与生成；未知方向不会被静默丢弃。

## 离线复现与自动检查

有 HTML 快照时可以完全离线复现采集：

```bash
python -m gdc_index sync --year 2026 --catalog-file .cache/catalog-2026.html --detail-dir .cache/public-pages --as-of 2026-10-21
```

`--as-of` 应填写快照真实核对日期。常规网络更新不需要指定，由工具记录当前 UTC 日期。该日期表示资料核对日期，不是大会日期。

一个年份配置了多个活动时，按 `config/archives.json` 的顺序重复提供 `--catalog-file`。例如 2020 年需同时提供主会与 Summer 的快照；缺少快照时中止，避免误把部分活动当作全年目录：

```bash
python -m gdc_index sync --year 2020 --catalog-file .cache/gdc-20.html --catalog-file .cache/gdc-summer-20.html --detail-dir .cache/public-pages --as-of 2026-10-21
```

每次 Push／PR 的 GitHub Actions 检查数据、单元测试与生成文件一致性。`Collect public metadata` 工作流可手动输入年份采集，结果以 artifact 下载；它不自动提交更改，也不设置定时任务。下载结果后审阅差异，补译并运行本地检查，再提交。

## 发布到自己的 GitHub

在 GitHub 创建一个空仓库，例如 `GDC-Community-Index`，将本目录作为 Git 工作区，按 GitHub 页面提示添加自己的远程地址并推送。仓库名和账号不写死在数据或脚本中。推送前执行本页第一组检查；不要提交 `.cache/`、`.env` 或个人凭据。
