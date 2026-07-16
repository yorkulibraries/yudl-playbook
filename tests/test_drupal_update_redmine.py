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


if __name__ == "__main__":
    unittest.main()
