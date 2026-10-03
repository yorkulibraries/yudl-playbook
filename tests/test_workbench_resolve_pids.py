import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "files" / "scripts" / "workbench_resolve_pids.py"
SPEC = importlib.util.spec_from_file_location("workbench_resolve_pids", SCRIPT)
workbench_resolve_pids = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workbench_resolve_pids)


PID_MAP = {"yul:asc": "4", "yul:smil": "12"}
TERM_MAP = {
    ("islandora_models", "Collection"): "12",
    ("islandora_models", "Paged Content"): "16",
    ("islandora_display", "Open Seadragon"): "22",
    ("resource_types", "Collection"): "24",
    ("resource_types", "Text"): "34",
}


class ResolveValueTest(unittest.TestCase):
    def test_resolves_pid(self):
        self.assertEqual(workbench_resolve_pids.resolve_value("yul:asc", PID_MAP), ("4", []))

    def test_resolves_pipe_separated_and_keeps_node_ids(self):
        self.assertEqual(
            workbench_resolve_pids.resolve_value("yul:asc|7|yul:smil", PID_MAP),
            ("4|7|12", []),
        )

    def test_reports_missing_pid(self):
        self.assertEqual(
            workbench_resolve_pids.resolve_value("yul:nope", PID_MAP),
            ("", ["yul:nope"]),
        )


class FetchPidMapTest(unittest.TestCase):
    def test_parses_drush_output(self):
        completed = mock.Mock(stdout="yul:asc\t4\nyul:smil\t12\n\n")
        with mock.patch.object(workbench_resolve_pids.subprocess, "run", return_value=completed) as run:
            pid_map = workbench_resolve_pids.fetch_pid_map("drush", "/web")
        self.assertEqual(pid_map, PID_MAP)
        self.assertIn("sql:query", run.call_args.args[0])


class FetchTermMapTest(unittest.TestCase):
    def test_marks_duplicate_names_ambiguous(self):
        completed = mock.Mock(stdout="resource_types\tText\t34\nresource_types\tText\t99\nislandora_models\tPage\t17\n")
        with mock.patch.object(workbench_resolve_pids.subprocess, "run", return_value=completed):
            term_map = workbench_resolve_pids.fetch_term_map("drush", "/web")
        self.assertIsNone(term_map[("resource_types", "Text")])
        self.assertEqual(term_map[("islandora_models", "Page")], "17")


class ResolveRowsTest(unittest.TestCase):
    def test_resolves_terms_within_their_vocabulary(self):
        rows, missing = workbench_resolve_pids.resolve_rows(
            [{"field_model": "Collection", "field_resource_type": "Collection", "field_display_hints": "Open Seadragon"}],
            PID_MAP,
            TERM_MAP,
        )
        self.assertEqual(missing, [])
        self.assertEqual(rows[0], {"field_model": "12", "field_resource_type": "24", "field_display_hints": "22"})

    def test_reports_unknown_and_ambiguous_terms(self):
        term_map = {**TERM_MAP, ("resource_types", "Text"): None}
        _, missing = workbench_resolve_pids.resolve_rows(
            [{"field_model": "Nope", "field_resource_type": "Text"}], PID_MAP, term_map
        )
        self.assertEqual(missing, ["line 2: field_model Nope", "line 2: field_resource_type Text"])


class MainTest(unittest.TestCase):
    def run_main(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.csv"
            dest = Path(tmp) / "out.csv"
            with open(src, "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            with mock.patch.object(workbench_resolve_pids, "fetch_pid_map", return_value=PID_MAP), \
                    mock.patch.object(workbench_resolve_pids, "fetch_term_map", return_value=TERM_MAP):
                code = workbench_resolve_pids.main([str(src), str(dest)])
            output = None
            if dest.exists():
                with open(dest, newline="") as handle:
                    output = list(csv.DictReader(handle))
        return code, output

    def test_writes_resolved_csv(self):
        code, output = self.run_main([
            {"id": "yul:F0005", "field_member_of": "yul:asc", "field_model": "Collection", "title": "Glendon College fonds"},
            {"id": "yul:os", "field_member_of": "", "field_model": "Paged Content", "title": "Open Scholarship"},
        ])
        self.assertEqual(code, 0)
        self.assertEqual([r["field_member_of"] for r in output], ["4", ""])
        self.assertEqual([r["field_model"] for r in output], ["12", "16"])
        self.assertEqual(output[0]["title"], "Glendon College fonds")

    def test_fails_without_writing_when_pid_missing(self):
        code, output = self.run_main([{"node_id": "yul:missing", "file": "x.jpg"}])
        self.assertEqual(code, 1)
        self.assertIsNone(output)


if __name__ == "__main__":
    unittest.main()
