import copy
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace only after serialization succeeds. Always emit UTF-8 and LF.
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8", newline="\n")
    temp.replace(path)


def key(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().casefold()


def event_key(name: str) -> str:
    """Vault uses 'Summer 2020' in cards and 'GDC Summer 2020' in tags."""
    match = re.fullmatch(r"(?:Game Developers Conference|GDC)\s+(\d{4})", name)
    if match:
        return "gdc-" + match[1]
    match = re.fullmatch(r"(?:GDC\s+)?(Summer|Showcase)\s+(\d{4})", name)
    if match:
        return f"gdc-{match[1].lower()}-{match[2]}"
    return key(name)


def source_hash(metadata: dict) -> str:
    content = {name: metadata.get(name, []) if name != "overview" else metadata.get(name, "")
               for name in ("title", "speakers", "source_tracks", "overview")}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def categories_for(item: dict, tracks: list[dict]) -> list[str]:
    result = []
    for track in tracks:
        if set(item["source_tracks"]) & set(track["source_tracks"]) or set(item.get("tags", [])) & set(track.get("tags", [])):
            result.append(track["slug"])
    # VR/AR is a cross-cutting topic in 2026, rather than a standalone Vault track.
    if re.search(r"\b(?:VR|AR|XR|mixed reality|virtual reality|augmented reality|Quest|Horizon OS)\b", item["title"], re.I):
        if "vr-ar" not in result:
            result.append("vr-ar")
    return result


def merge_resources(resources: list[dict], previous: dict | None, year: int, as_of: str, tracks: list[dict]) -> dict:
    previous = previous or {"sessions": []}
    old_by_resource = {source["id"]: session for session in previous["sessions"] for source in session["sources"]}
    groups = defaultdict(list)
    # Prefer exact, unabridged titles from public detail pages. Catalog truncation
    # can be resolved only when exactly one complete title matches the prefix.
    complete = defaultdict(set)
    for resource in resources:
        if not re.search(r"\.{3}|…", resource["title"]):
            complete[event_key(resource.get("event", ""))].add(key(resource["title"]))
    for resource in resources:
        event_group = event_key(resource.get("event", ""))
        name = key(resource["title"])
        old_resource = old_by_resource.get(resource["id"])
        if resource["metadata_source"] == "catalog" and old_resource and old_resource["metadata_source"] == "detail":
            name = key(old_resource["title"])
        if re.search(r"\.{3}|…", name):
            prefix = re.split(r"\.{3}|…", name)[0].rstrip()
            candidates = [full for full in complete[event_group] if full.startswith(prefix)]
            if len(candidates) == 1:
                name = candidates[0]
        groups[(event_group, name)].append(resource)
    sessions = []
    for _, items in sorted(groups.items()):
        items.sort(key=lambda item: (item["metadata_source"] != "detail", bool(re.search(r"\.{3}|…", item["title"])), -len(item["title"]), int(item["id"])))
        best = items[0]
        old_matches = {old_by_resource[item["id"]]["id"]: old_by_resource[item["id"]]
                       for item in items if item["id"] in old_by_resource}
        edited = [item for item in old_matches.values() if item.get("title_zh") or item["summary"]["en"] or item["summary"]["zh"] or any(item["links"].values())]
        if len(edited) > 1:
            raise ValueError(f"Source now merges multiple curated sessions: {best['title']}; resolve editorial data manually")
        old = edited[0] if edited else min(old_matches.values(), key=lambda item: int(item["id"].rsplit("-", 1)[1]), default=None)
        # A catalog-only refresh must not replace previously verified detail data.
        if old and best["metadata_source"] == "catalog" and old["metadata_source"] == "detail":
            metadata = {field: old[field] for field in ("title", "speakers", "companies", "source_tracks", "tags", "metadata_source")}
            fingerprint = old["source_hash"]
        else:
            metadata = {field: best[field] for field in ("title", "speakers", "companies", "source_tracks", "tags", "metadata_source")}
            fingerprint = source_hash(best)
        if best.get("event"):
            metadata["event"] = best["event"]
        summary = copy.deepcopy(old["summary"]) if old else {"en": "", "zh": "", "status": "missing", "basis": "", "source_hash": ""}
        if summary["status"] != "missing" and summary.get("source_hash") != fingerprint:
            summary["status"] = "stale"
        sources = [{field: item[field] for field in ("id", "type", "url", "access", "event") if field in item} for item in sorted(items, key=lambda item: int(item["id"]))]
        item = {
            "id": old["id"] if old else f"gdc-{year}-{min(int(item['id']) for item in items)}",
            "year": year, **metadata,
            "title_zh": old.get("title_zh", "") if old else "",
            "categories": categories_for(metadata, tracks),
            "sources": sources, "source_hash": fingerprint,
            "summary": summary,
            "links": copy.deepcopy(old["links"]) if old else {"articles": [], "youtube": []},
        }
        sessions.append(item)
    # Never silently remove a curated session when the upstream page shrinks.
    seen = {source["id"] for session in sessions for source in session["sources"]}
    retained = []
    for old in previous["sessions"]:
        if not any(source["id"] in seen for source in old["sources"]):
            item = copy.deepcopy(old)
            item["catalog_status"] = "not_in_latest_catalog"
            retained.append(item)
    sessions.extend(retained)
    sessions.sort(key=lambda item: (key(item["title"]), item["id"]))
    return {
        "schema_version": 1, "year": year,
        "source": f"https://gdcvault.com/browse/gdc-{year % 100:02d}/",
        "checked_at": as_of, "sessions": sessions,
    }


def youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "www.youtube-nocookie.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/", "/live/")):
            candidate = parsed.path.split("/")[2]
        else:
            return None
    else:
        return None
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None


def valid_url(url: str) -> bool:
    if not isinstance(url, str) or re.search(r"[\s<>\"\\]", url):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def validate_dataset(data: dict, tracks: list[dict]) -> list[str]:
    errors = []
    if data.get("schema_version") != 1:
        errors.append("Unsupported schema_version")
    year = data.get("year")
    if type(year) is not int or not 2000 <= year <= 2099:
        errors.append("Invalid year")
    try:
        date.fromisoformat(data.get("checked_at", ""))
    except (TypeError, ValueError):
        errors.append("Invalid checked_at")
    sessions = data.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        return errors + ["sessions must be a non-empty list"]
    slugs = {track["slug"] for track in tracks}
    mapped = {name for track in tracks for name in track["source_tracks"]}
    seen_ids, seen_sources = set(), set()
    archives = data.get("catalogs", [])
    event_names = set()
    for archive in archives:
        if not re.search(rf"\b{year}\b", archive.get("name", "")) or not valid_url(archive.get("url", "")):
            errors.append("Invalid annual archive name/URL")
        event_names.add(event_key(archive.get("name", "")))
    for item in sessions:
        name = item.get("id", "<missing id>")
        if name in seen_ids or not re.fullmatch(rf"gdc-{year}-\d+", name):
            errors.append(f"{name}: invalid or duplicate session ID")
        seen_ids.add(name)
        if item.get("year") != year:
            errors.append(f"{name}: wrong year")
        if event_names and event_key(item.get("event", "")) not in event_names:
            errors.append(f"{name}: event is missing or not part of annual archives")
        for field in ("title", "source_hash", "metadata_source"):
            if not isinstance(item.get(field), str) or not item[field]:
                errors.append(f"{name}: missing {field}")
        if not re.fullmatch(r"[a-f0-9]{64}", item.get("source_hash", "")):
            errors.append(f"{name}: invalid source_hash")
        if item.get("metadata_source") not in {"catalog", "detail"}:
            errors.append(f"{name}: invalid metadata_source")
        if not isinstance(item.get("title_zh"), str):
            errors.append(f"{name}: title_zh must be text")
        for field in ("speakers", "companies", "source_tracks", "tags", "categories"):
            values = item.get(field)
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                errors.append(f"{name}: invalid {field}")
        categories = item.get("categories", [])
        if not categories or any(category not in slugs for category in categories):
            errors.append(f"{name}: missing or unknown category")
        unknown = set(item.get("source_tracks", [])) - mapped
        if unknown:
            errors.append(f"{name}: unmapped source track {', '.join(sorted(unknown))}")
        summary = item.get("summary", {})
        status = summary.get("status")
        if status not in {"missing", "draft", "reviewed", "stale"}:
            errors.append(f"{name}: invalid summary status")
        for language in ("en", "zh"):
            if not isinstance(summary.get(language), str):
                errors.append(f"{name}: summary.{language} must be text")
        if status in {"draft", "reviewed", "stale"}:
            if not summary.get("en") or not summary.get("zh"):
                errors.append(f"{name}: bilingual summaries require both en and zh")
            if summary.get("basis") not in {"official-overview", "talk", "speaker-article"}:
                errors.append(f"{name}: invalid summary basis")
            if status != "stale" and summary.get("source_hash") != item.get("source_hash"):
                errors.append(f"{name}: summary does not match source hash")
        elif status == "missing" and (summary.get("en") or summary.get("zh")):
            errors.append(f"{name}: a nonempty summary cannot have missing status")
        evidence = summary.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, dict):
                errors.append(f"{name}: summary evidence must be an object")
            else:
                if not valid_url(evidence.get("url", "")):
                    errors.append(f"{name}: invalid summary evidence URL")
                if evidence.get("access") not in {"public", "indexed-history"}:
                    errors.append(f"{name}: invalid summary evidence access")
                fingerprint = evidence.get("content_hash", "")
                if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
                    errors.append(f"{name}: invalid summary evidence content hash")
                if not isinstance(evidence.get("note", ""), str):
                    errors.append(f"{name}: summary evidence note must be text")
                try:
                    date.fromisoformat(evidence.get("checked_at", ""))
                except (TypeError, ValueError):
                    errors.append(f"{name}: invalid summary evidence checked_at")
        sources = item.get("sources", [])
        if not sources:
            errors.append(f"{name}: missing official sources")
        for source in sources:
            resource_id = source.get("id", "")
            if resource_id in seen_sources or not re.fullmatch(r"\d+", resource_id):
                errors.append(f"{name}: duplicate or invalid resource ID {resource_id}")
            seen_sources.add(resource_id)
            if source.get("url") != f"https://gdcvault.com/play/{resource_id}/":
                errors.append(f"{name}: unexpected Vault URL")
            if source.get("type") not in {"video", "slides", "audio", "other"} or source.get("access") not in {"public", "members", "registration"}:
                errors.append(f"{name}: invalid resource type/access")
        links = item.get("links", {})
        for article in links.get("articles", []):
            if not valid_url(article.get("url", "")) or not article.get("title"):
                errors.append(f"{name}: invalid article")
        for video in links.get("youtube", []):
            video_id = youtube_id(video.get("url", ""))
            if not video_id or not video.get("title") or not video.get("channel"):
                errors.append(f"{name}: expected a direct YouTube video URL, title and channel")
            if not valid_url(video.get("evidence_url", "")):
                errors.append(f"{name}: missing YouTube verification evidence")
            if not isinstance(video.get("note", ""), str):
                errors.append(f"{name}: YouTube version note must be text")
            try:
                date.fromisoformat(video.get("checked_at", ""))
            except (TypeError, ValueError):
                errors.append(f"{name}: invalid YouTube checked_at")
    return errors
