import argparse
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "files" / "scripts" / "drupal_update_redmine.py"
SPEC = importlib.util.spec_from_file_location("drupal_update_redmine", SCRIPT)
drupal_update_redmine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drupal_update_redmine)


def priority_args(ordinary=2, security=4):
    return argparse.Namespace(
        redmine_priority_id=ordinary,
        redmine_security_priority_id=security,
    )


def main_args(parent_issue_id=4336):
    return argparse.Namespace(
        drupal_root="/var/www/html/drupal/web",
        site_uri="digital.library.yorku.ca",
        drush="/usr/local/bin/drush",
        site_label="YUDL",
        subject_prefix="Drupal compatible updates available",
        only_module=None,
        redmine_url="https://redmine.example.com",
        redmine_project_id="islandora",
        redmine_assignee_id=3,
        redmine_parent_issue_id=parent_issue_id,
        redmine_tracker_id=3,
        redmine_tracker_name=None,
        redmine_priority_id=2,
        redmine_security_priority_id=4,
        redmine_category_id=None,
        redmine_category_name="Maintenance",
        redmine_version_id=None,
        redmine_version_name="2026-2027 Workplan",
        redmine_api_key_env="REDMINE_API_KEY",
        dry_run=False,
    )


def update_item(name="webform", security=True):
    return {
        "name": name,
        "title": name.title(),
        "kind": "project",
        "existing_version": "1.0.0",
        "recommended": "1.0.1",
        "latest_version": "1.0.1",
        "security_update": security,
        "compatibility_message": None,
    }


def update_report():
    return {
        "site_name": "YUDL",
        "generated_at": "2026-07-16T08:00:00-04:00",
        "core": {"existing_version": "10.4.5"},
    }


class PrioritySelectionTests(unittest.TestCase):
    def test_parse_args_accepts_security_priority_id(self):
        argv = [
            "drupal_update_redmine.py",
            "--drupal-root",
            "/var/www/html/drupal/web",
            "--redmine-security-priority-id",
            "4",
        ]
        with mock.patch.object(sys, "argv", argv):
            args = drupal_update_redmine.parse_args()
        self.assertEqual(args.redmine_security_priority_id, 4)

    def test_security_update_uses_security_priority(self):
        updates = [{"security_update": True}]
        self.assertEqual(
            drupal_update_redmine.select_priority_id(priority_args(), updates),
            4,
        )

    def test_ordinary_update_uses_ordinary_priority(self):
        updates = [{"security_update": False}]
        self.assertEqual(
            drupal_update_redmine.select_priority_id(priority_args(), updates),
            2,
        )

    def test_security_update_falls_back_to_ordinary_priority(self):
        updates = [{"security_update": True}]
        self.assertEqual(
            drupal_update_redmine.select_priority_id(
                priority_args(security=None), updates
            ),
            2,
        )

    def test_aggregate_uses_security_priority_if_any_update_is_security(self):
        updates = [{"security_update": False}, {"security_update": True}]
        self.assertEqual(
            drupal_update_redmine.select_priority_id(priority_args(), updates),
            4,
        )

    def test_aggregate_uses_ordinary_priority_if_none_are_security(self):
        updates = [{"security_update": False}, {"security_update": False}]
        self.assertEqual(
            drupal_update_redmine.select_priority_id(priority_args(), updates),
            2,
        )


class RedminePayloadTests(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(
            redmine_project_id="islandora",
            redmine_assignee_id=3,
            redmine_parent_issue_id=4336,
        )

    def test_create_issue_uses_explicit_priority(self):
        with mock.patch.object(
            drupal_update_redmine,
            "redmine_request",
            return_value={"issue": {"id": 99}},
        ) as request:
            drupal_update_redmine.create_issue(
                "https://redmine.example.com",
                "key",
                "subject",
                "description",
                self.args,
                tracker_id=3,
                priority_id=4,
            )
        payload = request.call_args.args[4]
        self.assertEqual(payload["issue"]["priority_id"], 4)

    def test_create_issue_omits_absent_priority(self):
        with mock.patch.object(
            drupal_update_redmine,
            "redmine_request",
            return_value={"issue": {"id": 99}},
        ) as request:
            drupal_update_redmine.create_issue(
                "https://redmine.example.com",
                "key",
                "subject",
                "description",
                self.args,
                tracker_id=3,
                priority_id=None,
            )
        payload = request.call_args.args[4]
        self.assertNotIn("priority_id", payload["issue"])
        self.assertNotIn("category_id", payload["issue"])
        self.assertNotIn("fixed_version_id", payload["issue"])

    def test_create_issue_sets_category_and_version(self):
        with mock.patch.object(
            drupal_update_redmine,
            "redmine_request",
            return_value={"issue": {"id": 99}},
        ) as request:
            drupal_update_redmine.create_issue(
                "https://redmine.example.com",
                "key",
                "subject",
                "description",
                self.args,
                tracker_id=3,
                priority_id=4,
                category_id=7,
                version_id=21,
            )
        payload = request.call_args.args[4]
        self.assertEqual(payload["issue"]["category_id"], 7)
        self.assertEqual(payload["issue"]["fixed_version_id"], 21)


def lookup_args(**overrides):
    values = {
        "redmine_project_id": "islandora",
        "redmine_category_id": None,
        "redmine_category_name": None,
        "redmine_version_id": None,
        "redmine_version_name": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CategoryVersionLookupTests(unittest.TestCase):
    def test_parse_args_accepts_category_and_version_names(self):
        argv = [
            "drupal_update_redmine.py",
            "--drupal-root",
            "/var/www/html/drupal/web",
            "--redmine-category-name",
            "Maintenance",
            "--redmine-version-name",
            "2026-2027 Workplan",
        ]
        with mock.patch.object(sys, "argv", argv):
            args = drupal_update_redmine.parse_args()
        self.assertEqual(args.redmine_category_name, "Maintenance")
        self.assertEqual(args.redmine_version_name, "2026-2027 Workplan")

    def test_explicit_ids_skip_lookup(self):
        args = lookup_args(redmine_category_id=7, redmine_version_id=21)
        with mock.patch.object(drupal_update_redmine, "redmine_request") as request:
            self.assertEqual(drupal_update_redmine.resolve_category_id("u", "k", args), 7)
            self.assertEqual(drupal_update_redmine.resolve_version_id("u", "k", args), 21)
        request.assert_not_called()

    def test_unset_returns_none(self):
        args = lookup_args()
        with mock.patch.object(drupal_update_redmine, "redmine_request") as request:
            self.assertIsNone(drupal_update_redmine.resolve_category_id("u", "k", args))
            self.assertIsNone(drupal_update_redmine.resolve_version_id("u", "k", args))
        request.assert_not_called()

    def test_category_name_lookup_is_case_insensitive(self):
        args = lookup_args(redmine_category_name="maintenance")
        data = {"issue_categories": [{"id": 5, "name": "Bug"}, {"id": 7, "name": "Maintenance"}]}
        with mock.patch.object(
            drupal_update_redmine, "redmine_request", return_value=data
        ) as request:
            self.assertEqual(drupal_update_redmine.resolve_category_id("u", "k", args), 7)
        self.assertEqual(request.call_args.args[3], "projects/islandora/issue_categories.json")

    def test_missing_category_raises(self):
        args = lookup_args(redmine_category_name="Maintenance")
        with mock.patch.object(
            drupal_update_redmine, "redmine_request", return_value={"issue_categories": []}
        ):
            with self.assertRaises(RuntimeError):
                drupal_update_redmine.resolve_category_id("u", "k", args)

    def test_version_name_lookup(self):
        args = lookup_args(redmine_version_name="2026-2027 Workplan")
        data = {
            "versions": [
                {"id": 20, "name": "2025-2026 Workplan", "status": "closed"},
                {"id": 21, "name": "2026-2027 Workplan", "status": "open"},
            ]
        }
        with mock.patch.object(
            drupal_update_redmine, "redmine_request", return_value=data
        ) as request:
            self.assertEqual(drupal_update_redmine.resolve_version_id("u", "k", args), 21)
        self.assertEqual(request.call_args.args[3], "projects/islandora/versions.json")

    def test_closed_version_raises(self):
        args = lookup_args(redmine_version_name="2026-2027 Workplan")
        data = {"versions": [{"id": 21, "name": "2026-2027 Workplan", "status": "locked"}]}
        with mock.patch.object(drupal_update_redmine, "redmine_request", return_value=data):
            with self.assertRaises(RuntimeError):
                drupal_update_redmine.resolve_version_id("u", "k", args)

    def test_missing_version_raises(self):
        args = lookup_args(redmine_version_name="2026-2027 Workplan")
        with mock.patch.object(
            drupal_update_redmine, "redmine_request", return_value={"versions": []}
        ):
            with self.assertRaises(RuntimeError):
                drupal_update_redmine.resolve_version_id("u", "k", args)


class ClassificationTests(unittest.TestCase):
    def test_core_security_metadata_marks_core_update_as_security(self):
        report = {
            "core": {
                "existing_version": "10.4.5",
                "recommended": "10.4.6",
                "latest_version": "10.4.6",
                "security_updates": [{"version": "10.4.6"}],
            },
            "projects": {},
        }
        actionable, blocked = drupal_update_redmine.classify_projects(report)
        self.assertEqual(blocked, [])
        self.assertEqual(len(actionable), 1)
        self.assertTrue(actionable[0]["security_update"])


class ModuleDescriptionTests(unittest.TestCase):
    def test_core_description_has_single_drupal_core_line(self):
        item = update_item(name="drupal", security=False)
        item.update({"title": "Drupal core", "kind": "core"})
        description = drupal_update_redmine.build_module_description(
            update_report(), item, [], main_args()
        )
        self.assertNotIn("Drupal core: Drupal core", description)
        self.assertEqual(description.count("Drupal core:"), 1)

    def test_module_description_names_module(self):
        description = drupal_update_redmine.build_module_description(
            update_report(), update_item(), [], main_args()
        )
        self.assertIn("Module: Webform", description)


class MainFlowTests(unittest.TestCase):
    def run_main(self, args, actionable, existing=None):
        with mock.patch.object(
            drupal_update_redmine, "parse_args", return_value=args
        ), mock.patch.object(
            drupal_update_redmine,
            "run_drush_update_report",
            return_value=update_report(),
        ), mock.patch.object(
            drupal_update_redmine,
            "classify_projects",
            return_value=(actionable, []),
        ), mock.patch.object(
            drupal_update_redmine, "resolve_tracker_id", return_value=3
        ), mock.patch.object(
            drupal_update_redmine, "resolve_category_id", return_value=7
        ), mock.patch.object(
            drupal_update_redmine, "resolve_version_id", return_value=21
        ), mock.patch.object(
            drupal_update_redmine, "open_issue_exists", return_value=existing
        ), mock.patch.object(
            drupal_update_redmine,
            "create_issue",
            return_value={"id": 99},
        ) as create_issue, mock.patch.dict(
            drupal_update_redmine.os.environ,
            {"REDMINE_API_KEY": "key"},
            clear=False,
        ):
            result = drupal_update_redmine.main()
        return result, create_issue

    def test_parent_mode_passes_security_priority_for_security_update(self):
        result, create_issue = self.run_main(main_args(), [update_item()])
        self.assertEqual(result, 0)
        self.assertEqual(create_issue.call_args.args[-1], 4)

    def test_aggregate_mode_uses_security_priority_if_any_update_is_security(self):
        actionable = [
            update_item(name="token", security=False),
            update_item(name="webform", security=True),
        ]
        result, create_issue = self.run_main(
            main_args(parent_issue_id=None), actionable
        )
        self.assertEqual(result, 0)
        self.assertEqual(create_issue.call_args.args[-1], 4)

    def test_category_and_version_are_passed_to_create_issue(self):
        for parent_issue_id in (4336, None):
            result, create_issue = self.run_main(
                main_args(parent_issue_id=parent_issue_id), [update_item()]
            )
            self.assertEqual(result, 0)
            self.assertEqual(create_issue.call_args.kwargs["category_id"], 7)
            self.assertEqual(create_issue.call_args.kwargs["version_id"], 21)

    def test_existing_parent_issue_is_not_modified_or_recreated(self):
        result, create_issue = self.run_main(
            main_args(), [update_item()], existing={"id": 88}
        )
        self.assertEqual(result, 0)
        create_issue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
