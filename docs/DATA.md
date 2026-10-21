# 数据与分类说明

## 唯一数据源

`data/<年份>/sessions.json` 是可编辑数据；`<年份>/README.md` 和各方向 Markdown 是生成产物。顶层包含 `schema_version`、`year`、官方 `source`、`checked_at` 和 `sessions`。

官方发布方提供、但尚未在年度 Vault 目录中匹配到的公开视频另存于 `data/<年份>/recordings.json`。每条包含真实视频标题、参考译名、直接播放 URL、发布频道、核验日期、官方活动页和核验依据；这些视频在年度 YouTube 索引中单独列出，不计入 Vault 演讲数量。

| 字段 | 含义 |
| --- | --- |
| `id` | 首次收录时依据官方资源 ID 创建的稳定锚点；后续合并优先保留已有 ID |
| `year` | 大会年份，从指定年度归档核对 |
| `event` | 具体活动；历史年份区分主会、Summer、Showcase |
| `title` / `title_zh` | 官方英文题目／参考中文译名 |
| `speakers` / `companies` | 来源中列出的讲者和机构；不推断两者一一对应 |
| `source_tracks` | 官方原始方向名称 |
| `categories` | 本项目阅读分类的 slug；允许跨方向 |
| `tags` | 官方详情页标签，辅助分类 |
| `metadata_source` | `detail` 为已读公开详情页，`catalog` 为仅从目录获取 |
| `sources` | 本场演讲对应的全部 Vault 视频、音频或幻灯片资料页 |
| `source_hash` | 标题、讲者、官方方向与公开简介的指纹 |
| `summary` | 原创中英文导读、依据、进度和所对应的来源指纹 |
| `links.articles` | 经核实的官方幻灯片、讲者文章或相关阅读 |
| `links.youtube` | 直接视频 URL、实际视频标题、发布频道、核验日期与核验依据 |
| `catalog_status` | 仅在旧记录不再出现在最新目录时保留 `not_in_latest_catalog`，等待复核 |

## 摘要状态

| 状态 | 阅读页显示 | 统计计入双语摘要 |
| --- | --- | --- |
| `missing` | 待整理 | 否 |
| `draft` | AI 辅助初稿，待校对 | 是 |
| `reviewed` | 已校对 | 是 |
| `stale` | 来源已变更，待复核 | 否 |

简介导读不是演讲全文翻译。英文和中文均由本项目依据标注来源归纳；未取得可靠简介的条目保留“待整理”。`reviewed` 仅用于确实经过人工校对的条目。中文译名也属于参考译名。

导读可附 `summary.evidence`，保存实际使用的 `url`、核对日期 `checked_at`、本地来源文本的 SHA-256 `content_hash`、访问方式 `access` 与可选的范围说明 `note`。`public` 表示直接读取公开资料；`indexed-history` 表示依据检索服务保留的历史页面内容，原页面可能已经变更或失效。该指纹针对本地采用的来源文本或摘录，不是整张网页的文件校验值。

`official-overview` 用于官方演讲简介；`speaker-article` 也包含发布方相关文章与大会报道；`talk` 可用于已读的公开演讲资料。若使用同一讲者在其他活动中的相关说明，必须用 `note` 写明版本边界，不能声称资料或视频就是 GDC 现场版本。新增导读均保留出处和初稿状态。

## 方向映射

延续原项目九个常用方向，同时为 2026 年归档中其他方向提供入口。映射统一存放在 `config/tracks.json`，官方原名始终保留在条目中。

2020—2023 年的 Summit／Workshop 映射也在同一配置中：音频峰会归音频，AI／机器学习／数学／在线技术／工具峰会归程序，动画／艺术指导／技术美术／特效峰会归视觉艺术，叙事峰会归叙事，关卡／UX／桌游峰会归设计，独立游戏峰会归独立游戏，教育峰会归教育，职业及学生项目归职业发展。旧版制作与团队管理归制作方向；社区、免费游戏和电竞峰会归商业与市场；Fair Play 与气候工作坊归文化与可持续发展；Future Realities 与 Entertainment VR/AR 归 VR/AR。

年度数据可包含 `catalogs`，列出 `config/archives.json` 配置的多个官方归档。2020 年同时收录 GDC 2020 与 Summer 2020；2021、2023 年分别同时收录主会与 Showcase。活动名称在资料页和标签中的别名会先标准化，再核对；例如 `Summer 2020` 与 `GDC Summer 2020` 指向同一活动。

| 阅读方向 | 2026 年官方方向或判据 |
| --- | --- |
| Audio | Audio |
| Business & Marketing | Business Strategy、Discovery & Marketing、Product Management |
| Design | Design |
| Game Narrative | Narrative & Performance |
| Independent Games | Independent Development |
| Production & Team Leadership | Production、Team Leadership |
| Programming | Game & Production Technology |
| Visual Arts | Visual Development |
| VR / AR | 官方 VR/AR 标签，或标题明确出现 VR、AR、XR、Quest、Horizon OS 等相关词 |
| Culture & Sustainability | Culture & Sustainability |
| Educators | Educators |
| Career | Career |
| Luminaries Speaker Series | Luminaries Speaker Series |
| Special Events | Special Event |

VR/AR 在当前归档中是跨方向话题，因此可能与程序、美术或制作方向重叠。标题规则只影响浏览分类，不生成内容摘要。

## 去重与保留

合并前先按具体活动分组。即使年份和标题相同，主会与 Summer／Showcase 的记录也分别保留。尚无人工编辑的目录重复项可在标题补全后自动合并；已有两份人工整理内容时仍中止并要求核对。

同一年、完整标题一致的多个资源合并为一条演讲，保留每个原始资源链接。目录有时截断标题：只有当截断前缀唯一对应到一个完整标题时才合并；存在歧义时保留分开的记录供复核。首次收录优先使用数值最小的官方资源 ID，后续更新保留原锚点。

只更新目录时不会覆盖以前从详情核对的元数据或来源指纹。相同资源的简介变化会将旧导读标为 `stale`；来源缺失时保留历史条目。若官方变化导致两个已经整理的条目需要合并，工具中止并要求手动核对，避免静默丢失笔记或文章。

## 覆盖边界

官方 Vault 归档与完整大会日程并不等价；未上传资料的圆桌、现场活动等可能不在目录中。访问权限也可能变化。年度目录列出的是此次可验证的归档范围，不能当作全大会的完整覆盖率。

已核实 YouTube 表示元数据和演讲对应关系得到来源支持，不表示自动检测过所有地区的实际播放能力。工具校验 URL 格式和核验记录，人工或独立来源核对视频内容对应关系。
