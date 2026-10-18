import json
import os
import tempfile
import unittest
from datetime import date, timezone
from unittest import mock

from print_heatmap import archive, cli, demo, gist, stats, svg, text


def task(id, start, end, status=2, weight=10.0, color="FF671FFF", title="Clip"):
    return {
        "id": id, "startTime": start, "endTime": end, "status": status, "weight": weight, "title": title,
        "deviceId": "SERIAL", "deviceModel": "P2S", "cover": "https://example.com/c.png",
        "amsDetailMapping": [{"sourceColor": color, "filamentType": "PLA", "weight": weight}],
    }


class ArchiveTests(unittest.TestCase):
    def test_slim_keeps_only_chart_fields(self):
        r = archive.slim(task(1, "2026-10-01T10:00:00Z", "2026-10-01T12:00:00Z"))
        self.assertEqual(r["filaments"], [{"color": "#FF671F", "type": "PLA", "grams": 10.0}])
        self.assertEqual(r["status"], "finished")
        self.assertNotIn("deviceId", r)
        self.assertNotIn("cover", r)

    def test_slim_skips_running_print(self):
        self.assertIsNone(archive.slim(task(1, "2026-10-01T10:00:00Z", "2026-10-01T10:00:30Z")))

    def test_slim_without_titles(self):
        self.assertNotIn("title", archive.slim(task(1, "2026-10-01T10:00:00Z", "2026-10-01T12:00:00Z"), titles=False))

    def test_merge_keeps_old_and_updates_by_id(self):
        old = [archive.slim(task(1, "2026-07-01T10:00:00Z", "2026-07-01T11:00:00Z"))]
        new = [archive.slim(task(2, "2026-10-01T10:00:00Z", "2026-10-01T11:00:00Z")),
               archive.slim(task(1, "2026-07-01T10:00:00Z", "2026-07-01T11:00:00Z", status=3))]
        merged = archive.merge(old, new)
        self.assertEqual([r["id"] for r in merged], [2, 1])
        self.assertEqual(merged[1]["status"], "failed")

    def test_load_raw_api_response(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tasks.json")
            with open(path, "w") as f:
                json.dump({"total": 1, "hits": [task(1, "2026-10-01T10:00:00Z", "2026-10-01T12:00:00Z")]}, f)
            self.assertEqual(len(archive.load(path)), 1)

    def test_save_load_round_trip(self):
        records = demo.records(date(2026, 10, 18))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out", "prints.json")
            archive.save(path, records)
            self.assertEqual(archive.load(path), records)


class StatsTests(unittest.TestCase):
    def test_failed_prints_add_no_hours(self):
        records = [archive.slim(task(1, "2026-10-01T10:00:00Z", "2026-10-01T12:00:00Z")),
                   archive.slim(task(2, "2026-10-01T13:00:00Z", "2026-10-01T14:00:00Z", status=3))]
        day = stats.aggregate(records, timezone.utc)[date(2026, 10, 1)]
        self.assertEqual((day.prints, day.failed, day.hours, day.grams), (1, 1, 2.0, 10.0))

    def test_days_follow_time_zone(self):
        from zoneinfo import ZoneInfo

        records = [archive.slim(task(1, "2026-10-01T23:30:00Z", "2026-10-02T01:00:00Z"))]
        self.assertIn(date(2026, 10, 2), stats.aggregate(records, ZoneInfo("Europe/Moscow")))


class StreakTests(unittest.TestCase):
    def days(self, *dates):
        return {d: stats.Day(prints=1) for d in dates}

    def test_empty_today_keeps_current_streak(self):
        days = self.days(date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 17))
        self.assertEqual(stats.streaks(days, date(2026, 10, 1), date(2026, 10, 18)), (3, 3))

    def test_empty_yesterday_breaks_it(self):
        days = self.days(date(2026, 10, 15), date(2026, 10, 16))
        self.assertEqual(stats.streaks(days, date(2026, 10, 1), date(2026, 10, 18)), (2, 0))


class RenderTests(unittest.TestCase):
    end = date(2026, 10, 18)

    def test_svg_has_a_cell_per_day(self):
        days = stats.aggregate(demo.records(self.end), timezone.utc)
        out = svg.render(days, self.end)
        cells = out.count('class="c l')
        self.assertEqual(cells, (self.end - stats.year_start(self.end)).days + 1 + 5)  # + legend

    def test_svg_empty_and_themes(self):
        for theme in ("auto", "light", "dark"):
            out = svg.render({}, self.end, colors="filament", theme=theme)
            self.assertIn("of printing in the last year", out)
            self.assertEqual("prefers-color-scheme" in out, theme == "auto")

    def test_months_fit_a_pinned_gist(self):
        out = text.render(stats.aggregate(demo.records(self.end), timezone.utc), self.end)
        lines = out.splitlines()
        self.assertEqual(len(lines), 5)  # a pinned gist shows 5 lines
        self.assertTrue(all(len(line) <= text.WIDTH for line in lines), lines)
        self.assertEqual(lines[1], "")
        self.assertEqual([line[:3] for line in lines[2:5]], ["Aug", "Sep", "Oct"])
        self.assertEqual(len(lines[4].split()[1]), self.end.day)  # one character per day so far

    def test_grid_layout(self):
        records = demo.records(self.end)
        out = text.render(stats.aggregate(records, timezone.utc), self.end, layout="grid")
        lines = out.splitlines()
        self.assertEqual(len(lines), 9)  # summary, months, 7 weekdays
        self.assertTrue(all(len(line) <= text.WIDTH for line in lines), lines)
        self.assertEqual(len(lines[2].split()), text.WEEKS)  # Sunday row: one cell per week

    def test_text_cells_match_svg_levels(self):
        days = {date(2026, 10, 12): stats.Day(prints=1, hours=5.0), date(2026, 10, 13): stats.Day(prints=1, hours=1.0)}
        rows = text.render(days, date(2026, 10, 17), layout="grid").splitlines()[2:]
        th = stats.quartiles(d.hours for d in days.values())
        self.assertEqual(rows[1].split()[-1], text.SHADES[stats.level(5.0, th)])  # Monday, Oct 12
        self.assertEqual(rows[2].split()[-1], text.SHADES[stats.level(1.0, th)])  # Tuesday, Oct 13
        self.assertEqual(rows[3].split()[-1], text.SHADES[0])  # Wednesday, nothing printed

    def test_color_name(self):
        self.assertEqual(text.color_name("#FF671F"), "Orange")
        self.assertEqual(text.color_name("#0A0A0A"), "Black")


class CliTests(unittest.TestCase):
    def test_update_fetches_merges_and_renders(self):
        hits = [task(5, "2026-10-17T05:58:04Z", "2026-10-17T06:36:06Z")]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"BAMBU_TOKEN": "t"}), \
                mock.patch("print_heatmap.cloud.fetch_tasks", return_value=hits):
            archive.save(f"{d}/prints.json", [archive.slim(task(1, "2026-06-01T10:00:00Z", "2026-06-01T11:00:00Z"))])
            cli.main(["update", "--archive", f"{d}/prints.json", "--svg", f"{d}/h.svg", "--text", f"{d}/s.txt",
                      "--timezone", "UTC", "--end", "2026-10-18"])
            self.assertEqual(len(archive.load(f"{d}/prints.json")), 2)
            for name in ("h.svg", "h-light.svg", "h-dark.svg", "s.txt"):
                self.assertTrue(os.path.exists(f"{d}/{name}"), name)

    def test_gist_renames_first_file(self):
        calls = []

        def fake(method, url, token, data=None):
            calls.append((method, data))
            return {"files": {"placeholder.md": {}}}

        with mock.patch("print_heatmap.gist._call", side_effect=fake):
            gist.update("abc", "t", "Title", "body")
        self.assertEqual(calls[1], ("PATCH", {"files": {"placeholder.md": {"filename": "Title", "content": "body"}}}))


if __name__ == "__main__":
    unittest.main()
