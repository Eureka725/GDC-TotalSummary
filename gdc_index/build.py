import html
import re
from pathlib import Path
from urllib.parse import quote, urlencode

from .model import load_json, validate_dataset
from .recordings import load_recordings, total_recordings

STATUS = {"missing": "待整理", "draft": "AI 辅助初稿，待校对", "reviewed": "已校对", "stale": "来源已变更，待复核"}
ACCESS = {"public": "公开页面", "members": "需会员", "registration": "需注册"}
KIND = {"video": "视频资料页", "slides": "幻灯片资料页", "audio": "音频资料页", "other": "资料页"}


def text(value: str) -> str:
    return html.escape(re.sub(r"\s+", " ", value), quote=False).replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")


def link(label: str, url: str) -> str:
    return f"[{text(label)}](<{quote(url, safe=':/?=&%#@+,-._~') }>)"


def counts(sessions: list[dict]) -> tuple[int, int]:
    summaries = sum(item["summary"]["status"] in {"draft", "reviewed"} for item in sessions)
    videos = sum(bool(item["links"]["youtube"]) for item in sessions)
    return summaries, videos


def table(data: dict, tracks: list[dict], prefix: str = "") -> str:
    rows = ["| 方向 | 演讲数 | 双语摘要 | YouTube 已核实 |", "| --- | ---: | ---: | ---: |"]
    for track in tracks:
        items = [item for item in data["sessions"] if track["slug"] in item["categories"]]
        summary_count, video_count = counts(items)
        label = f"{track['en']} · {track['zh']}"
        rows.append(f"| {link(label, prefix + track['slug'] + '.md')} | {len(items)} | {summary_count} | {video_count} |")
    return "\n".join(rows)


def render_session(item: dict, year: int) -> str:
    parts = [f'<a id="{item["id"]}"></a>', "", f'## {text(item["title"])}', ""]
    if item["title_zh"]:
        parts.extend([f'**{text(item["title_zh"])}**', ""])
    if item.get("event"):
        parts.extend([f"活动：{text(item['event'])}", ""])
    parts.extend([
        f"讲者：{text(' / '.join(item['speakers'])) if item['speakers'] else '官方目录未提供'}  ",
        f"机构：{text(' / '.join(dict.fromkeys(item['companies'])))}  " if item["companies"] else "机构：官方目录未提供  ",
    ])
    # Companies and speakers are independent lists: the source does not reliably
    # associate each name with a company, so do not invent those relationships.
    parts.extend([
        f"官方方向：{text(' / '.join(item['source_tracks']))}  ",
        f"元数据：{'已核对公开详情页' if item['metadata_source'] == 'detail' else '来自官方目录，讲者等信息待详情复核'}",
        "", "**官方资料与相关文章**", "",
    ])
    for source in item["sources"]:
        parts.append(f"- {link('GDC Vault · ' + KIND[source['type']], source['url'])}（{ACCESS[source['access']]}）")
    for article in item["links"]["articles"]:
        parts.append(f"- {link(article['title'], article['url'])}")
    parts.extend(["", "**YouTube 演讲**", ""])
    for video in item["links"]["youtube"]:
        note = f" · 版本说明：{text(video['note'])}" if video.get("note") else ""
        parts.append(f"- {link(video['title'], video['url'])} · {text(video['channel'])} · {video['checked_at']} 核验{note}")
    if not item["links"]["youtube"]:
        search = "https://www.youtube.com/results?" + urlencode({"search_query": f"GDC {year} {item['title']}"})
        parts.append(f"- 尚未收录已核实的视频链接。{link('按演讲名搜索 YouTube', search)}（搜索入口）")
    summary = item["summary"]
    parts.extend(["", f"**双语摘要 · {STATUS[summary['status']]}**", ""])
    if summary["en"] or summary["zh"]:
        if summary["basis"] == "official-overview":
            parts.extend(["依据官方公开简介整理的导读；未声称覆盖完整演讲。", ""])
        elif summary["basis"] == "speaker-article":
            parts.extend(["依据讲者／发布方相关文章或大会报道整理的导读；资料范围以出处说明为准。", ""])
        elif summary["basis"] == "talk":
            parts.extend(["依据公开演讲资料整理的导读；不代表演讲全文翻译。", ""])
        evidence = summary.get("evidence")
        if evidence:
            historical = " · 历史页面索引，原页面可能已变更或失效" if evidence["access"] == "indexed-history" else ""
            parts.extend([f"{link('导读依据', evidence['url'])} · {evidence['checked_at']} 核对{historical}", ""])
            if evidence.get("note"):
                parts.extend([f"> 出处说明：{text(evidence['note'])}", ""])
        parts.extend([f"**EN** {text(summary['en'])}", "", f"**中文** {text(summary['zh'])}", ""])
    else:
        parts.extend(["待依据官方公开简介、演讲或讲者文章整理。", ""])
    if item.get("catalog_status") == "not_in_latest_catalog":
        parts.extend(["> 本条未出现在最近一次官方目录中，保留历史资料，待复核。", ""])
    return "\n".join(parts)


def rendered_files(root: Path) -> dict[Path, str]:
    tracks = load_json(root / "config/tracks.json")
    datasets = [load_json(path) for path in sorted((root / "data").glob("[0-9][0-9][0-9][0-9]/sessions.json"), reverse=True)]
    if not datasets:
        raise ValueError("No annual datasets found")
    output = {}
    year_rows = ["| 年份 | 独立演讲 | 双语摘要 | YouTube 已核实 | 来源核对日期 |", "| --- | ---: | ---: | ---: | --- |"]
    for data in datasets:
        errors = validate_dataset(data, tracks)
        if errors:
            raise ValueError("\n".join(errors))
        year = data["year"]
        items = data["sessions"]
        extra = load_recordings(root, year)
        all_video_count = total_recordings(items, extra)
        summary_count, video_count = counts(items)
        year_rows.append(f"| [{year}]({year}/README.md) | {len(items)} | {summary_count} | [{all_video_count}]({year}/youtube.md) | {data['checked_at']} |")
        intro = [
            f"# GDC {year} 中英文资料索引", "",
            "[返回首页](../README.md) · [维护说明](../docs/MAINTAINING.md) · [结构化数据](../data/" + str(year) + "/sessions.json)", "",
            f"依据 {link('GDC Vault 年度归档', data['source'])} 整理；来源核对日期：{data['checked_at']}。", "",
            f"共 **{len(items)}** 场独立演讲／活动，**{sum(len(item['sources']) for item in items)}** 个资料页；双语摘要 **{summary_count}** 条，已核实 YouTube 视频的演讲 **{video_count}** 场。", "",
            f"[YouTube 公开视频索引](youtube.md)：共 **{all_video_count}** 个已核实播放链接，包含归档内视频及 **{len(extra)}** 个官方发布方补充视频。索引同时提供官方资料／活动页。", "",
            "这是当前 Vault 归档的索引，不能据此认定已覆盖大会所有活动。视频与幻灯片按演讲合并，跨方向条目会同时出现；各方向数量不可直接相加。", "",
            "中文标题为便于检索的参考译名；“AI 辅助初稿”尚待人工校对。已核实视频使用播放页链接，搜索入口有独立标记。访问状态记录的是核对时的页面状态。", "",
            table(data, tracks), "",
            "跨年份方向与阅读分类的对应关系见 [分类说明](../docs/DATA.md#方向映射)。", "",
            "<!-- Generated by python -m gdc_index build; edit data, not this file. -->", "",
        ]
        output[root / str(year) / "README.md"] = "\n".join(intro)
        if data.get("catalogs"):
            archive_lines = ["## 本年度收录的官方活动", ""]
            for archive in data["catalogs"]:
                selected = [item for item in items if item.get("event") == archive["name"]]
                archive_lines.append(f"- {link(archive['name'], archive['url'])}：{len(selected)} 场演讲／活动。")
            archive_lines.extend(["", "相同标题只在同一活动内合并；不同活动的同名演讲分别保留。", ""])
            output[root / str(year) / "README.md"] += "\n".join(archive_lines)
        videos = [f"# GDC {year} · YouTube 公开视频索引", "", "[年度目录](README.md) · [项目首页](../README.md)", "",
                  "每项同时列出官方资料／文章入口与实际视频播放页。视频标题可能与大会原题不同，核验依据保留在结构化数据中。", "",
                  "## 已关联归档条目", "", "| 演讲／活动 | 官方资料／文章 | YouTube 视频 | 发布频道 | 核验日期 |", "| --- | --- | --- | --- | --- |"]
        for item in items:
            for video in item["links"]["youtube"]:
                sources = [link("GDC Vault", source["url"]) for source in item["sources"]]
                sources += [link(article["title"], article["url"]) for article in item["links"]["articles"]]
                note = f" · 版本说明：{text(video['note'])}" if video.get("note") else ""
                videos.append(f"| {text(item['title'])} | {' / '.join(sources)} | {link(video['title'], video['url'])}{note} | {text(video['channel'])} | {video['checked_at']} |")
        videos.extend(["", "## 官方发布方补充演讲", "",
                       "以下视频由官方 GDC 活动页链接的发布方提供，当前年度 Vault 目录中尚未匹配到对应条目，因此单独列出，不计入 Vault 演讲数量。中文标题为参考译名。", "",
                       "| 演讲／参考译名 | 官方资料／文章 | YouTube 视频 | 发布频道 | 核验日期 |", "| --- | --- | --- | --- | --- |"])
        for video in extra:
            videos.append(f"| {text(video['title_zh'])} | {link('官方 GDC 资料页', video['article_url'])} | {link(video['title'], video['url'])} | {text(video['channel'])} | {video['checked_at']} |")
        videos.extend(["", "核验支持演讲对应关系与发布来源；未测试所有地区的实际播放能力。未收录的演讲可在方向页面使用明确标注的 YouTube 搜索入口。", "", "<!-- Generated by python -m gdc_index build. -->", ""])
        output[root / str(year) / "youtube.md"] = "\n".join(videos)
        for track in tracks:
            selected = [item for item in items if track["slug"] in item["categories"]]
            lines = [f"# GDC {year} · {track['en']} · {track['zh']}", "", "[年度目录](README.md) · [项目首页](../README.md)", "",
                     f"共 {len(selected)} 场。资料来源核对日期：{data['checked_at']}。", "",
                     "> 本文件由结构化数据生成。摘要是基于所标注来源的中英文导读；初稿待校对。", ""]
            if selected:
                lines.extend(["## 目录", ""])
                lines.extend(f"- [{text(item['title'])}](#{item['id']})" for item in selected)
                lines.extend(["", "---", ""])
                lines.extend(render_session(item, year) for item in selected)
            else:
                lines.extend(["当前官方归档中尚未匹配到本方向的条目。", ""])
            lines.extend(["", "<!-- Generated by python -m gdc_index build. -->", ""])
            output[root / str(year) / (track["slug"] + ".md")] = "\n".join(lines)
    readme = root / "README.md"
    if readme.exists():
        original = readme.read_text(encoding="utf-8")
        pattern = r"(<!-- generated:years:start -->).*?(<!-- generated:years:end -->)"
        replacement = re.sub(pattern, lambda match: match[1] + "\n" + "\n".join(year_rows) + "\n" + match[2], original, flags=re.S)
        if replacement == original and not re.search(pattern, original, flags=re.S):
            raise ValueError("README is missing the generated year table markers")
        output[readme] = replacement
    return output


def build(root: Path, check: bool = False) -> list[Path]:
    changed = []
    for path, content in rendered_files(root).items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            changed.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    return changed
