import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .build import build
from .fetch import Fetcher
from .model import event_key, key, load_json, merge_resources, save_json, validate_dataset
from .vault import catalog_url, parse_catalog, parse_detail
from .recordings import load_recordings, total_recordings


def sync(args) -> int:
    root = args.root.resolve()
    tracks = load_json(root / "config/tracks.json")
    fetcher = Fetcher(root / ".cache/vault", refresh=args.refresh)
    archive_config = root / "config/archives.json"
    archives = load_json(archive_config).get(str(args.year), []) if archive_config.exists() else []
    archives = archives or [{"slug": f"gdc-{args.year % 100:02d}", "name": f"Game Developers Conference {args.year}", "url": catalog_url(args.year)}]
    if args.catalog_file and len(args.catalog_file) != len(archives):
        raise ValueError(f"Expected {len(archives)} --catalog-file snapshots, in configured archive order")
    resources = []
    for index, archive in enumerate(archives):
        source = args.catalog_file[index].read_text(encoding="utf-8") if args.catalog_file else fetcher.get(archive["url"], f"catalog-{archive['slug']}.html")
        entries = parse_catalog(source, args.year)
        if len(archives) > 1 and any(entry["event"] != archive["name"] for entry in entries):
            raise ValueError(f"Archive event does not match {archive['name']}")
        resources.extend(entries)
    detail_cache = root / ".cache/vault" / f"overviews-{args.year}.json"
    details = load_json(detail_cache) if detail_cache.exists() else {}
    failures = []
    if args.details or args.detail_dir or args.resolve_titles:
        # One public resource per title is enough for the metadata. Other media
        # of the same session inherit the same verified description and speakers.
        candidates = {}
        for resource in resources:
            if resource["access"] == "public":
                candidates.setdefault((resource.get("event", ""), key(resource["title"])), resource)
        if args.resolve_titles and not args.details and not args.detail_dir:
            import re
            candidates = {name: resource for name, resource in candidates.items() if re.search(r"\.{3}|…", resource["title"])}
        for index, resource in enumerate(candidates.values(), 1):
            try:
                if args.detail_dir:
                    path = args.detail_dir / (resource["id"] + ".html")
                    if not path.exists():
                        failures.append({"id": resource["id"], "error": "No offline snapshot"})
                        continue
                    content = path.read_text(encoding="utf-8")
                else:
                    content = fetcher.get(resource["url"], resource["id"] + ".html")
                detail = parse_detail(content, args.year)
                if event_key(detail["event"]) != event_key(resource["event"]):
                    raise ValueError("Public detail belongs to a different GDC event")
                detail["event"] = resource["event"]
                details[resource["id"]] = detail
                original_key = key(resource["title"])
                for target in resources:
                    if target["event"] == resource["event"] and key(target["title"]) == original_key:
                        target.update({name: value for name, value in detail.items() if name not in {"embedded_youtube_urls", "embedded_articles"}})
                if index % 20 == 0:
                    print(f"Public details: {index}/{len(candidates)}", flush=True)
            except (OSError, ValueError) as error:
                failures.append({"id": resource["id"], "error": str(error)})
    save_json(detail_cache, details)
    save_json(root / ".cache/vault" / f"errors-{args.year}.json", failures)
    target = root / "data" / str(args.year) / "sessions.json"
    previous = load_json(target) if target.exists() else None
    if previous and len(resources) < len({source["id"] for item in previous["sessions"] for source in item["sources"]}) * 0.8:
        raise ValueError("Catalog shrank by over 20%; local dataset was preserved. Inspect the upstream source before updating.")
    as_of = args.as_of or datetime.now(timezone.utc).date().isoformat()
    data = merge_resources(resources, previous, args.year, as_of, tracks)
    if str(args.year) in (load_json(archive_config) if archive_config.exists() else {}):
        data["catalogs"] = archives
    # Preserve manually curated articles; append direct official slide links.
    for item in data["sessions"]:
        known = {article["url"] for article in item["links"]["articles"]}
        for resource in item["sources"]:
            for article in details.get(resource["id"], {}).get("embedded_articles", []):
                if article["url"] not in known:
                    item["links"]["articles"].append(article)
                    known.add(article["url"])
    errors = validate_dataset(data, tracks)
    if errors:
        raise ValueError("Validation failed; local dataset was preserved:\n" + "\n".join(errors))
    save_json(target, data)
    print(f"GDC {args.year}: {len(resources)} resources -> {len(data['sessions'])} sessions; {len(details)} public details; {len(failures)} details unavailable.")
    print(f"Dataset: {target}")
    if failures:
        print(f"Details log: {root / '.cache/vault' / f'errors-{args.year}.json'}")
    return 0


def datasets(root: Path, year: int | None = None):
    paths = [root / "data" / str(year) / "sessions.json"] if year else sorted((root / "data").glob("[0-9][0-9][0-9][0-9]/sessions.json"))
    if not paths:
        raise ValueError("No datasets found")
    return [(path, load_json(path)) for path in paths]


def validate(args) -> int:
    tracks = load_json(args.root / "config/tracks.json")
    errors = []
    for path, data in datasets(args.root, args.year):
        issues = validate_dataset(data, tracks)
        load_recordings(args.root, data["year"])
        errors.extend(f"{path}: {issue}" for issue in issues)
        if not issues:
            print(f"OK {data['year']}: {len(data['sessions'])} sessions")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


def report(args) -> int:
    for _, data in datasets(args.root, args.year):
        items = data["sessions"]
        status = Counter(item["summary"]["status"] for item in items)
        print(f"GDC {data['year']}: {len(items)} sessions, {sum(len(item['sources']) for item in items)} resources")
        print(f"  summaries: {dict(status)}")
        print(f"  YouTube: {sum(bool(item['links']['youtube']) for item in items)} verified, {sum(not item['links']['youtube'] for item in items)} pending")
        extra = load_recordings(args.root, data["year"])
        print(f"  additional publisher videos: {len(extra)}; total unique verified video links: {total_recordings(items, extra)}")
        print(f"  source checked: {data['checked_at']}")
    return 0


def export_queue(args) -> int:
    queue = []
    cache_file = args.root / ".cache/vault" / f"overviews-{args.year}.json"
    details = load_json(cache_file) if cache_file.exists() else {}
    for _, data in datasets(args.root, args.year):
        for item in data["sessions"]:
            if args.missing_only and item["summary"]["status"] not in {"missing", "stale"}:
                continue
            overview = next((details[source["id"]].get("overview", "") for source in item["sources"] if source["id"] in details), "")
            queue.append({"id": item["id"], "title": item["title"], "source_hash": item["source_hash"], "official_overview": overview,
                          "title_zh": item["title_zh"], "summary": item["summary"], "links": item["links"]})
    save_json(args.output, {"year": args.year, "items": queue})
    print(f"Exported {len(queue)} items to {args.output}. Source excerpts stay in the local queue; do not commit this file.")
    return 0


def import_edits(args) -> int:
    payload = load_json(args.file)
    path = args.root / "data" / str(payload["year"]) / "sessions.json"
    data = load_json(path)
    by_id = {item["id"]: item for item in data["sessions"]}
    edited = set()
    for update in payload["items"]:
        session_id = update["id"]
        if session_id in edited:
            raise ValueError(f"Duplicate editorial update: {session_id}")
        edited.add(session_id)
        if session_id not in by_id:
            raise ValueError(f"Unknown session ID: {session_id}")
        item = by_id[session_id]
        if update.get("source_hash") != item["source_hash"]:
            raise ValueError(f"Source has changed for {session_id}; re-export the queue")
        for field in ("title_zh", "links"):
            if field in update:
                item[field] = update[field]
        if "summary" in update:
            item["summary"] = update["summary"]
            item["summary"]["source_hash"] = item["source_hash"] if item["summary"]["status"] != "missing" else ""
    errors = validate_dataset(data, load_json(args.root / "config/tracks.json"))
    if errors:
        raise ValueError("Invalid editorial updates; dataset was preserved:\n" + "\n".join(errors))
    save_json(path, data)
    print(f"Imported {len(edited)} editorial updates")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Maintain the bilingual GDC Community Index")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("sync", help="Collect public annual Vault metadata")
    command.add_argument("--year", type=int, required=True)
    command.add_argument("--details", action="store_true", help="Also read public detail pages (slower)")
    command.add_argument("--resolve-titles", action="store_true", help="Read public details for truncated catalog titles")
    command.add_argument("--refresh", action="store_true", help="Ignore the one-week HTML cache")
    command.add_argument("--catalog-file", type=Path, action="append", help="Use local catalog snapshots; repeat in configured archive order")
    command.add_argument("--detail-dir", type=Path, help="Use local public-detail HTML snapshots")
    command.add_argument("--as-of", help="Source snapshot date, YYYY-MM-DD")
    command.set_defaults(handler=sync)
    command = commands.add_parser("validate", help="Validate data, editorial state and video links")
    command.add_argument("--year", type=int)
    command.set_defaults(handler=validate)
    command = commands.add_parser("build", help="Generate annual/category Markdown")
    command.add_argument("--check", action="store_true", help="Fail if generated files need updating")
    command.set_defaults(handler=lambda args: run_build(args))
    command = commands.add_parser("report", help="Show coverage and pending work")
    command.add_argument("--year", type=int)
    command.set_defaults(handler=report)
    command = commands.add_parser("export", help="Export an editorial queue with local source overviews")
    command.add_argument("--year", type=int, required=True)
    command.add_argument("--missing-only", action="store_true")
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=export_queue)
    command = commands.add_parser("import", help="Validate and import bilingual summaries and verified links")
    command.add_argument("file", type=Path)
    command.set_defaults(handler=import_edits)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


def run_build(args) -> int:
    changed = build(args.root, args.check)
    if args.check and changed:
        print("Generated files are stale:\n" + "\n".join(str(path) for path in changed), file=sys.stderr)
        return 1
    print(f"{'Checked' if args.check else 'Generated'} Markdown; {len(changed)} files {'need updates' if args.check else 'updated'}")
    return 0
