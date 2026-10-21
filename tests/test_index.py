from pathlib import Path
import tempfile
import unittest

from gdc_index.build import build, render_session
from gdc_index.cli import main
from gdc_index.model import event_key, load_json, merge_resources, save_json, validate_dataset, youtube_id
from gdc_index.recordings import load_recordings, total_recordings
from gdc_index.vault import parse_catalog, parse_detail

ROOT = Path(__file__).resolve().parent.parent
TRACKS = load_json(ROOT / "config/tracks.json")


def temp_workspace():
    directory = (ROOT / ".cache/test-runs").resolve()
    if not directory.is_relative_to(ROOT.resolve()):
        raise ValueError("Test temporary files must stay inside this workspace")
    directory.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=directory)


def card(resource_id="123", title="Full title", access="public", kind="video"):
    target = f'href="/play/{resource_id}/"' if access == "public" else f'onclick="popup(\'/play/{resource_id}/title\')" title="{title}"'
    member = '<img class="members" />' if access == "members" else ""
    return f'''<a class="session_item" {target}>{member}
    <div class="media_type_image {kind}"></div><div class="conference_info"><p>
    <span class="conference_name">Game Developers Conference 2026</span><br>
    <strong>{title}</strong><br><span><em>by</em> A Developer <strong>(A Studio)</strong></span>
    <span class="track_name">Programming</span></p></div></a>'''


def video_detail(title="Full title", overview="An original overview."):
    return f'''<dl class="player-info"><dt>Session Name:</dt><dd>{title}</dd>
    <dt>Speaker(s):</dt><dd>A Developer, B Developer</dd><dt>Company Name(s):</dt><dd>Studio A, Studio B</dd>
    <dt>Track / Format:</dt><dd>Programming</dd></dl>
    <dl class="overview-section"><dt>Overview:</dt><dd>{overview}</dd></dl>
    <ul id="tags"><li>Game Developers Conference 2026</li><li>Programming</li></ul>
    <a href="https://www.youtube.com/channel/UC-example">Global footer</a>'''


def resource(resource_id="123", title="Full title", overview="An original overview."):
    data = parse_catalog(card(resource_id, title), 2026)[0]
    data.update({key: value for key, value in parse_detail(video_detail(title, overview), 2026).items() if not key.startswith("embedded_")})
    return data


def dataset(resources=None, previous=None):
    return merge_resources(resources or [resource()], previous, 2026, "2026-10-21", TRACKS)


class VaultTests(unittest.TestCase):
    def test_catalog_access_and_full_member_title(self):
        items = parse_catalog(card() + card("124", "Long complete title", "members") + card("125", "Sponsor", "registration"), 2026)
        self.assertEqual([item["access"] for item in items], ["public", "members", "registration"])
        self.assertEqual(items[1]["title"], "Long complete title")
        self.assertEqual(items[0]["speakers"], ["A Developer"])
        self.assertEqual(items[0]["companies"], ["A Studio"])

    def test_wrong_year_and_empty_catalog_rejected(self):
        for source in ("<h1>Nothing</h1>", card().replace("2026", "2027")):
            with self.assertRaises(ValueError):
                parse_catalog(source, 2026)

    def test_unescaped_title_quotes_use_complete_visible_text(self):
        for title in ['Build "Living Games" with AI', 'Turning a "Dead" Genre into a Breakout Hit']:
            with self.subTest(title=title):
                self.assertEqual(parse_catalog(card(title=title, access="members"), 2026)[0]["title"], title)
        source = card(title="Complete title", access="members").replace("<strong>Complete title</strong>", "<strong>Complete...</strong>")
        self.assertEqual(parse_catalog(source, 2026)[0]["title"], "Complete title")

    def test_video_detail_extracts_all_speakers(self):
        data = parse_detail(video_detail(), 2026)
        self.assertEqual(data["speakers"], ["A Developer", "B Developer"])
        self.assertEqual(data["overview"], "An original overview.")
        self.assertIsNone(youtube_id(data["embedded_youtube_urls"][0]))

    def test_slide_layout_and_encoded_file_url(self):
        source = '''<table><tr><td>Session Name:</td><td>Slide talk</td></tr>
        <tr><td>Speaker(s):</td><td>Speaker</td></tr><tr><td>Track / Format:</td><td>Design</td></tr>
        <tr><td>Overview:</td><td>Public overview.</td></tr></table>
        <div id="tags"><p>Game Developers Conference 2026</p><p></p></div>
        <iframe src="https://view.officeapps.live.com/op/embed.aspx?src=https%3A%2F%2Fmedia.gdcvault.com%2Fgdc2026%2FSlides%2FSome%20Talk.pptx"></iframe>'''
        data = parse_detail(source, 2026)
        self.assertEqual(data["title"], "Slide talk")
        self.assertEqual(data["overview"], "Public overview.")
        self.assertEqual(len(data["tags"]), 1)
        self.assertIn("Some%20Talk.pptx", data["embedded_articles"][0]["url"])

    def test_login_page_is_not_a_detail(self):
        with self.assertRaises(ValueError):
            parse_detail("<h1>Login</h1>", 2026)

    def test_historical_summer_and_showcase_detail_names(self):
        for tag in ("GDC 2020", "GDC Summer 2020", "Summer 2020", "Showcase 2020", "GDC Showcase 2020"):
            source = video_detail().replace("Game Developers Conference 2026", tag)
            self.assertEqual(parse_detail(source, 2020)["event"], tag)
        self.assertEqual(event_key("Summer 2020"), event_key("GDC Summer 2020"))
        self.assertNotEqual(event_key("GDC 2020"), event_key("Summer 2020"))


class MergeTests(unittest.TestCase):
    def test_video_and_slides_merge_without_losing_sources(self):
        first, second = resource("123"), resource("124")
        second["type"] = "slides"
        data = dataset([second, first])
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(data["sessions"][0]["id"], "gdc-2026-123")
        self.assertEqual(len(data["sessions"][0]["sources"]), 2)

    def test_ambiguous_truncation_does_not_merge_distinct_sessions(self):
        abbreviated = parse_catalog(card("125", "Common prefix..."), 2026)[0]
        data = dataset([resource("123", "Common prefix one"), resource("124", "Common prefix two"), abbreviated])
        self.assertEqual(len(data["sessions"]), 3)

    def test_unique_truncation_merges(self):
        abbreviated = parse_catalog(card("125", "Common prefix..."), 2026)[0]
        data = dataset([resource("123", "Common prefix expanded"), abbreviated])
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(data["sessions"][0]["title"], "Common prefix expanded")

    def test_editorial_work_preserved_and_changes_mark_stale(self):
        old = dataset()
        item = old["sessions"][0]
        item["title_zh"] = "已整理标题"
        item["summary"] = {"en": "Reading note.", "zh": "导读。", "status": "reviewed", "basis": "official-overview", "source_hash": item["source_hash"]}
        item["links"]["articles"] = [{"title": "Notes", "url": "https://example.org/notes"}]
        new = dataset([resource(overview="The source changed.")], old)["sessions"][0]
        self.assertEqual(new["summary"]["status"], "stale")
        self.assertEqual(new["summary"]["zh"], "导读。")
        self.assertEqual(new["title_zh"], "已整理标题")
        self.assertEqual(new["links"], item["links"])

    def test_catalog_refresh_does_not_erase_verified_details(self):
        old = dataset()
        new = dataset(parse_catalog(card(), 2026), old)
        self.assertEqual(new["sessions"][0]["source_hash"], old["sessions"][0]["source_hash"])
        self.assertEqual(new["sessions"][0]["speakers"], ["A Developer", "B Developer"])

    def test_disappearing_sessions_are_retained(self):
        old = dataset([resource("123"), resource("124", "Another talk")])
        new = dataset([resource("123")], old)
        self.assertEqual(len(new["sessions"]), 2)
        missing = next(item for item in new["sessions"] if item["id"].endswith("124"))
        self.assertEqual(missing["catalog_status"], "not_in_latest_catalog")

    def test_sync_is_idempotent(self):
        old = dataset()
        self.assertEqual(dataset(previous=old), old)

    def test_unmapped_track_is_rejected(self):
        data = dataset()
        data["sessions"][0]["source_tracks"] = ["Unseen new official track"]
        self.assertTrue(any("unmapped" in error for error in validate_dataset(data, TRACKS)))

    def test_two_curated_records_are_never_silently_combined(self):
        old = dataset([resource("123", "First"), resource("124", "Second")])
        for item in old["sessions"]:
            item["title_zh"] = "已整理的独立条目"
        with self.assertRaises(ValueError):
            dataset([resource("123", "Same now"), resource("124", "Same now")], old)

    def test_uncurated_catalog_duplicates_can_merge_after_title_resolution(self):
        old = dataset([resource("123", "First"), resource("124", "Second")])
        result = dataset([resource("123", "Same now"), resource("124", "Same now")], old)
        self.assertEqual(len(result["sessions"]), 1)
        self.assertEqual(len(result["sessions"][0]["sources"]), 2)

    def test_same_title_in_different_events_is_not_merged(self):
        first, second = resource("123"), resource("124")
        second["event"] = "Showcase 2026"
        result = dataset([first, second])
        self.assertEqual(len(result["sessions"]), 2)

    def test_title_prefix_resolution_stays_within_event(self):
        first = resource("123", "Shared prefix complete")
        second = parse_catalog(card("124", "Shared prefix..."), 2026)[0]
        second["event"] = "Showcase 2026"
        result = dataset([first, second])
        self.assertEqual(len(result["sessions"]), 2)
        self.assertIn("Shared prefix...", [item["title"] for item in result["sessions"]])

    def test_catalog_only_refresh_keeps_resolved_resource_groups(self):
        first = resource("123", "Full resolved title")
        second = resource("124", "Full resolved title")
        old = dataset([first, second])
        raw = parse_catalog(card("123", "Full...") + card("124", "Full resolved title"), 2026)
        result = dataset(raw, old)
        self.assertEqual(len(result["sessions"]), 1)
        self.assertEqual(result["sessions"][0]["source_hash"], old["sessions"][0]["source_hash"])


class EditorialTests(unittest.TestCase):
    def test_multi_archive_offline_sync_and_incomplete_snapshot_rejection(self):
        with temp_workspace() as temporary:
            root = Path(temporary)
            save_json(root / "config/tracks.json", TRACKS)
            archives = [
                {"slug": "gdc-20", "name": "GDC 2020", "url": "https://gdcvault.com/browse/gdc-20/"},
                {"slug": "gdc-summer-20", "name": "Summer 2020", "url": "https://gdcvault.com/browse/gdc-summer-20/"},
            ]
            save_json(root / "config/archives.json", {"2020": archives})
            first, second = root / "main.html", root / "summer.html"
            first.write_text(card("123").replace("Game Developers Conference 2026", "GDC 2020"), encoding="utf-8")
            second.write_text(card("124").replace("Game Developers Conference 2026", "Summer 2020"), encoding="utf-8")
            args = ["--root", str(root), "sync", "--year", "2020", "--catalog-file", str(first), "--catalog-file", str(second), "--as-of", "2026-10-21"]
            self.assertEqual(main(args), 0)
            path = root / "data/2020/sessions.json"
            before = path.read_bytes()
            self.assertEqual(len(load_json(path)["sessions"]), 2)
            self.assertEqual(main(["--root", str(root), "sync", "--year", "2020", "--catalog-file", str(first)]), 1)
            self.assertEqual(path.read_bytes(), before)

    def test_catalog_only_sync_preserves_local_overview_cache(self):
        with temp_workspace() as temporary:
            root = Path(temporary)
            save_json(root / "config/tracks.json", TRACKS)
            source = root / "catalog.html"
            source.write_text(card(), encoding="utf-8")
            cached = root / ".cache/vault/overviews-2026.json"
            save_json(cached, {"123": {"overview": "A previously verified public overview."}})
            self.assertEqual(main(["--root", str(root), "sync", "--year", "2026", "--catalog-file", str(source)]), 0)
            self.assertEqual(load_json(cached)["123"]["overview"], "A previously verified public overview.")

    def test_youtube_requires_real_video_url_not_channel_or_search(self):
        for url in ["https://www.youtube.com/results?search_query=talk", "https://www.youtube.com/playlist?list=abc", "https://youtube.com.evil.example/watch?v=XxvLyd4lKZM", "https://www.youtube.com/@channel"]:
            self.assertIsNone(youtube_id(url), url)
        self.assertEqual(youtube_id("https://www.youtube.com/watch?v=XxvLyd4lKZM"), "XxvLyd4lKZM")
        self.assertEqual(youtube_id("https://youtu.be/XxvLyd4lKZM?t=10"), "XxvLyd4lKZM")

    def test_bilingual_summary_requires_matching_source(self):
        data = dataset()
        data["sessions"][0]["summary"] = {"en": "Note.", "zh": "导读。", "status": "draft", "basis": "official-overview", "source_hash": "wrong"}
        self.assertTrue(any("source hash" in error for error in validate_dataset(data, TRACKS)))

    def test_failed_import_is_atomic(self):
        with temp_workspace() as temporary:
            root = Path(temporary)
            save_json(root / "config/tracks.json", TRACKS)
            original = dataset()
            path = root / "data/2026/sessions.json"
            save_json(path, original)
            update = root / "edits.json"
            save_json(update, {"year": 2026, "items": [{"id": original["sessions"][0]["id"], "source_hash": "changed", "title_zh": "不应写入"}]})
            self.assertEqual(main(["--root", str(root), "import", str(update)]), 1)
            self.assertEqual(load_json(path), original)

    def test_import_and_export_roundtrip(self):
        with temp_workspace() as temporary:
            root = Path(temporary)
            save_json(root / "config/tracks.json", TRACKS)
            save_json(root / "data/2026/sessions.json", dataset())
            queue = root / "queue.json"
            self.assertEqual(main(["--root", str(root), "export", "--year", "2026", "--output", str(queue)]), 0)
            data = load_json(queue)
            data["items"][0]["summary"].update({"en": "Note.", "zh": "导读。", "status": "draft", "basis": "official-overview"})
            save_json(queue, data)
            self.assertEqual(main(["--root", str(root), "import", str(queue)]), 0)
            self.assertEqual(load_json(root / "data/2026/sessions.json")["sessions"][0]["summary"]["zh"], "导读。")

    def test_render_marks_search_as_search(self):
        output = render_session(dataset()["sessions"][0], 2026)
        self.assertIn("（搜索入口）", output)
        self.assertIn("尚未收录已核实", output)
        self.assertIn("官方资料与相关文章", output)

    def test_summary_evidence_is_validated_and_rendered_with_scope(self):
        data = dataset()
        item = data["sessions"][0]
        item["summary"] = {"en": "A source-based note.", "zh": "依据来源的导读。", "status": "draft", "basis": "speaker-article", "source_hash": item["source_hash"],
                           "evidence": {"url": "https://example.org/archive", "access": "indexed-history", "checked_at": "2026-10-21", "content_hash": "a" * 64, "note": "相关资料，不能认定为相同演讲版本。"}}
        self.assertEqual(validate_dataset(data, TRACKS), [])
        output = render_session(item, 2026)
        self.assertIn("依据讲者／发布方相关文章或大会报道", output)
        self.assertIn("历史页面索引", output)
        self.assertIn("https://example.org/archive", output)
        self.assertIn("不能认定为相同演讲版本", output)
        item["summary"]["evidence"]["url"] = "file:///private/source.html"
        self.assertTrue(any("evidence URL" in error for error in validate_dataset(data, TRACKS)))

    def test_summary_evidence_requires_fingerprint_date_and_access(self):
        data = dataset()
        data["sessions"][0]["summary"]["evidence"] = {"url": "https://example.org/source", "access": "unknown", "checked_at": "not-a-date", "content_hash": "invalid"}
        errors = validate_dataset(data, TRACKS)
        self.assertTrue(any("evidence access" in error for error in errors))
        self.assertTrue(any("evidence content hash" in error for error in errors))
        self.assertTrue(any("evidence checked_at" in error for error in errors))
        data["sessions"][0]["summary"]["evidence"]["content_hash"] = None
        self.assertTrue(any("evidence content hash" in error for error in validate_dataset(data, TRACKS)))

    def test_youtube_version_note_is_visible_and_validated(self):
        data = dataset()
        item = data["sessions"][0]
        item["links"]["youtube"] = [{"title": "Official talk", "url": "https://youtu.be/XxvLyd4lKZM", "channel": "Publisher", "evidence_url": "https://example.org/gdc-2026", "checked_at": "2026-10-21", "note": "发布方标明的重新演绎版本"}]
        self.assertEqual(validate_dataset(data, TRACKS), [])
        self.assertIn("版本说明：发布方标明的重新演绎版本", render_session(item, 2026))
        item["links"]["youtube"][0]["note"] = 123
        self.assertTrue(any("version note" in error for error in validate_dataset(data, TRACKS)))

    def test_generated_files_are_reproducible_and_check_is_read_only(self):
        with temp_workspace() as temporary:
            root = Path(temporary)
            save_json(root / "config/tracks.json", TRACKS)
            save_json(root / "data/2026/sessions.json", dataset())
            readme = root / "README.md"
            readme.write_text("<!-- generated:years:start -->\n<!-- generated:years:end -->\n", encoding="utf-8")
            self.assertTrue(build(root))
            self.assertEqual(build(root, check=True), [])
            annual = root / "2026/programming.md"
            annual.write_text("Out of date\n", encoding="utf-8")
            self.assertIn(annual, build(root, check=True))
            self.assertEqual(annual.read_text(encoding="utf-8"), "Out of date\n")

    def test_supplementary_video_requires_official_source(self):
        with temp_workspace() as temporary:
            root = Path(temporary)
            path = root / "data/2026/recordings.json"
            video = {"title": "Recorded talk", "title_zh": "演讲录像", "url": "https://youtu.be/XxvLyd4lKZM", "channel": "Official", "checked_at": "2026-10-21", "article_url": "https://example.org/gdc-2026", "evidence_url": "https://example.org/recordings"}
            save_json(path, {"schema_version": 1, "year": 2026, "videos": [video]})
            self.assertEqual(len(load_recordings(root, 2026)), 1)
            video["url"] = "https://www.youtube.com/results?search_query=recorded"
            save_json(path, {"schema_version": 1, "year": 2026, "videos": [video]})
            with self.assertRaises(ValueError):
                load_recordings(root, 2026)

    def test_supplementary_video_does_not_inflate_unique_count(self):
        data = dataset()
        video = {"url": "https://youtu.be/XxvLyd4lKZM"}
        data["sessions"][0]["links"]["youtube"] = [video]
        self.assertEqual(total_recordings(data["sessions"], [video]), 1)


if __name__ == "__main__":
    unittest.main()
