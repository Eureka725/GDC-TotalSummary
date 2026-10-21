"""Parse public GDC Vault pages. Never fetch player streams or gated resources."""

import re
from urllib.parse import parse_qs, quote, urlparse

from .html import Document, definition_list

BASE = "https://gdcvault.com"


def catalog_url(year: int) -> str:
    if not 2000 <= year <= 2099:
        raise ValueError("Year must be between 2000 and 2099")
    return f"{BASE}/browse/gdc-{year % 100:02d}/"


def parse_catalog(source: str, year: int) -> list[dict]:
    root = Document(source).root
    resources = []
    for card in root.find_all("a", "session_item"):
        conference = card.first(css_class="conference_name")
        if conference is None or not re.search(rf"\b{year}\b", conference.text()):
            raise ValueError(f"Catalog contains a session outside GDC {year}")
        attrs = card.attrs
        target = attrs.get("href", "")
        match = re.search(r"/play/(\d+)", target + " " + attrs.get("onclick", ""))
        if not match:
            raise ValueError("Catalog session has no readable resource ID")
        info = card.first(css_class="conference_info")
        title_node = info.first("strong") if info else None
        title = (attrs.get("title") or "").strip()
        visible_title = title_node.text() if title_node else ""
        # Some upstream title attributes contain unescaped quotation marks.
        # Recover the full visible title when it extends the broken prefix;
        # retain a full attribute when the visible card title is abbreviated.
        if not title or (visible_title.startswith(title) and len(visible_title) > len(title)
                         and not re.search(r"\.{3}|…", visible_title)):
            title = visible_title
        if not title:
            raise ValueError("Catalog session has no title")
        track = card.first(css_class="track_name")
        media = card.first(css_class="media_type_image")
        kinds = set(media.attrs.get("class", "").split()) - {"media_type_image"} if media else set()
        kind = next((kind for kind in ("video", "slides", "audio") if kind in kinds), "other")
        members = card.first(css_class="members") is not None
        access = "members" if members else ("public" if target.startswith("/play/") else "registration")
        speakers, companies = [], []
        if info:
            for span in info.find_all("span"):
                if span.first("em") and span.first("em").text() == "by":
                    company = span.first("strong")
                    company_text = company.text() if company else ""
                    name = span.text().removeprefix("by").strip()
                    if company_text and name.endswith(company_text):
                        name = name[:-len(company_text)].strip()
                    if name:
                        speakers = [name]
                    if company_text:
                        companies = [company_text[1:-1] if company_text.startswith("(") and company_text.endswith(")") else company_text]
                    break
        resources.append({
            "id": match[1], "type": kind, "url": f"{BASE}/play/{match[1]}/",
            "access": access, "title": title, "speakers": speakers,
            "companies": companies, "source_tracks": [track.text()] if track else [],
            "tags": [], "overview": "", "metadata_source": "catalog",
            "event": conference.text(),
        })
    if not resources:
        raise ValueError(f"No GDC {year} sessions found; refusing to replace local data")
    if len({item["id"] for item in resources}) != len(resources):
        raise ValueError("Catalog contains duplicate resource IDs; inspect source layout")
    return resources


def parse_detail(source: str, year: int) -> dict:
    root = Document(source).root
    tags_node = next((node for node in root.find_all() if node.attrs.get("id") == "tags"), None)
    tags = [node.text() for node in tags_node.children if hasattr(node, "tag") and node.tag in {"li", "p"} and node.text()] if tags_node else []
    event = next((tag for tag in tags if re.fullmatch(rf"(?:Game Developers Conference|GDC(?: Summer| Showcase)?|Summer|Showcase)\s+{year}", tag)), None)
    if event is None:
        raise ValueError(f"Detail page is not a public GDC {year} session")
    metadata = definition_list(root.first("dl", "player-info"))
    overview = definition_list(root.first("dl", "overview-section"))
    # Slide resources use a legacy table layout instead of the video layout.
    if not metadata:
        for row in root.find_all("tr"):
            cells = list(row.find_all("td"))
            if len(cells) == 2:
                label = cells[0].text().rstrip(":").strip()
                if label in {"Session Name", "Speaker(s)", "Company Name(s)", "Track / Format", "Overview"}:
                    metadata[label] = cells[1].text()
    title = metadata.get("Session Name") or overview.get("Session Name")
    if not title:
        raise ValueError("Public detail page has no session title")
    urls, articles = [], []
    for node in root.find_all():
        # Only direct links embedded by the official page; never infer video IDs.
        for attr in ("href", "src"):
            target = node.attrs.get(attr, "").strip()
            if target and urlparse(target).hostname in {"youtube.com", "www.youtube.com", "youtu.be", "www.youtube-nocookie.com"}:
                urls.append(target)
            parsed = urlparse(target)
            if parsed.hostname in {"view.officeapps.live.com", "docs.google.com"}:
                target = parse_qs(parsed.query).get("src", [target])[0]
                parsed = urlparse(target)
            if parsed.scheme == "https" and parsed.hostname == "media.gdcvault.com" and parsed.path.lower().endswith((".pdf", ".ppt", ".pptx")):
                articles.append({"title": "官方幻灯片", "url": quote(target, safe=":/?=&%#@+,-._~")})
    return {
        "title": title,
        "speakers": split_values(metadata.get("Speaker(s)", "")),
        "companies": split_values(metadata.get("Company Name(s)", "")),
        "source_tracks": split_values(metadata.get("Track / Format", "")),
        "tags": tags,
        "overview": re.sub(r"(?<=[.!?])n{2,}(?=[A-Z])", " ", overview.get("Overview", metadata.get("Overview", ""))),
        "metadata_source": "detail",
        "event": event,
        "embedded_youtube_urls": list(dict.fromkeys(urls)),
        "embedded_articles": list({item["url"]: item for item in articles}.values()),
    }


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
