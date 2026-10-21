"""Additional publisher-hosted recordings may not be present in the Vault catalog."""

from pathlib import Path
from datetime import date

from .model import load_json, valid_url, youtube_id


def load_recordings(root: Path, year: int) -> list[dict]:
    path = root / "data" / str(year) / "recordings.json"
    if not path.exists():
        return []
    data = load_json(path)
    if data.get("schema_version") != 1 or data.get("year") != year or not isinstance(data.get("videos"), list):
        raise ValueError(f"{path}: invalid supplementary recording dataset")
    seen = set()
    for video in data["videos"]:
        video_id = youtube_id(video.get("url", ""))
        if not video_id or video_id in seen:
            raise ValueError(f"{path}: invalid or duplicate direct video URL")
        seen.add(video_id)
        if not all(isinstance(video.get(field), str) and video[field] for field in ("title", "title_zh", "channel")):
            raise ValueError(f"{path}: video title, translated title and channel are required")
        if not valid_url(video.get("article_url", "")) or not valid_url(video.get("evidence_url", "")):
            raise ValueError(f"{path}: official article and verification URLs are required")
        date.fromisoformat(video.get("checked_at", ""))
    return data["videos"]


def total_recordings(sessions: list[dict], extra: list[dict]) -> int:
    return len({youtube_id(video["url"]) for item in sessions for video in item["links"]["youtube"]} | {youtube_id(video["url"]) for video in extra})
