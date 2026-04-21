#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


JSON_START = "__DRUPAL_UPDATE_JSON_START__"
JSON_END = "__DRUPAL_UPDATE_JSON_END__"


DRUSH_PHP = r'''use Drupal\update\UpdateFetcherInterface;
use Drupal\update\UpdateManagerInterface;

\Drupal::moduleHandler()->loadInclude('update', 'inc', 'update.compare');
update_refresh();
update_fetch_data();
\Drupal::keyValueExpirable('update')->delete('update_project_data');
$available = update_get_available(TRUE);
$projects = update_calculate_project_data($available);

$payload = [
  'generated_at' => date(DATE_ATOM),
  'site_name' => \Drupal::config('system.site')->get('name'),
  'projects' => [],
];

foreach ($projects as $name => $project) {
  if ($name === 'drupal') {
    $payload['core'] = [
      'existing_version' => $project['existing_version'] ?? NULL,
      'recommended' => $project['recommended'] ?? NULL,
      'latest_version' => $project['latest_version'] ?? NULL,
      'status' => $project['status'] ?? NULL,
      'reason' => $project['reason'] ?? NULL,
    ];
    continue;
  }

  $recommended_version = $project['recommended'] ?? NULL;
  $recommended_release = NULL;
  if ($recommended_version && !empty($project['releases'][$recommended_version])) {
    $recommended_release = $project['releases'][$recommended_version];
  }

  $also = [];
  if (!empty($project['also'])) {
    foreach ($project['also'] as $major => $version) {
      $release = $project['releases'][$version] ?? ['version' => $version];
      $also[] = [
        'major' => $major,
        'version' => $version,
        'core_compatible' => $release['core_compatible'] ?? NULL,
        'core_compatibility' => $release['core_compatibility'] ?? NULL,
        'core_compatibility_message' => $release['core_compatibility_message'] ?? NULL,
      ];
    }
  }

  $security_updates = [];
  if (!empty($project['security updates'])) {
    foreach ($project['security updates'] as $security_update) {
      $security_updates[] = [
        'version' => $security_update['version'] ?? NULL,
        'core_compatible' => $security_update['core_compatible'] ?? NULL,
        'core_compatibility' => $security_update['core_compatibility'] ?? NULL,
        'core_compatibility_message' => $security_update['core_compatibility_message'] ?? NULL,
      ];
    }
  }

  $extra = [];
  if (!empty($project['extra'])) {
    foreach ($project['extra'] as $item) {
      $extra[] = [
        'label' => $item['label'] ?? NULL,
        'data' => isset($item['data']) ? (string) $item['data'] : NULL,
      ];
    }
  }

  $payload['projects'][$name] = [
    'name' => $name,
    'title' => $project['title'] ?? $name,
    'existing_version' => $project['existing_version'] ?? NULL,
    'recommended' => $recommended_version,
    'latest_version' => $project['latest_version'] ?? NULL,
    'status' => $project['status'] ?? NULL,
    'reason' => $project['reason'] ?? NULL,
    'recommended_release' => $recommended_release ? [
      'version' => $recommended_release['version'] ?? $recommended_version,
      'core_compatible' => $recommended_release['core_compatible'] ?? NULL,
      'core_compatibility' => $recommended_release['core_compatibility'] ?? NULL,
      'core_compatibility_message' => $recommended_release['core_compatibility_message'] ?? NULL,
    ] : NULL,
    'also' => $also,
    'security_updates' => $security_updates,
    'extra' => $extra,
  ];
}

print("''' + JSON_START + r'''");
print(json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
print("''' + JSON_END + r'''");
'''


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Check Drupal Update Manager data through Drush, keep only updates "
            "compatible with the current Drupal core, and optionally create a "
            "Redmine issue."
        )
    )
    parser.add_argument("--drupal-root", required=True, help="Composer project root for the Drupal site")
    parser.add_argument("--site-uri", default="http://localhost", help="Drupal site URI for Drush")
    parser.add_argument("--drush", default="drush", help="Drush executable")
    parser.add_argument("--site-label", help="Friendly site label used in the Redmine ticket subject")
    parser.add_argument("--subject-prefix", default="Drupal compatible updates available", help="Redmine issue subject prefix")
    parser.add_argument(
        "--only-module",
        help="Only process a single project name, for example devel or drupal for Drupal core",
    )
    parser.add_argument("--redmine-url", help="Redmine base URL, for example https://redmine.example.com")
    parser.add_argument("--redmine-project-id", help="Redmine project id or identifier")
    parser.add_argument("--redmine-assignee-id", type=int, help="Redmine assignee user id")
    parser.add_argument("--redmine-parent-issue-id", type=int, help="Optional Redmine parent issue id for subtask creation")
    parser.add_argument("--redmine-tracker-id", type=int, help="Optional Redmine tracker id")
    parser.add_argument("--redmine-tracker-name", help="Optional Redmine tracker name, for example Support")
    parser.add_argument("--redmine-priority-id", type=int, help="Optional Redmine priority id")
    parser.add_argument("--redmine-api-key-env", default="REDMINE_API_KEY", help="Environment variable that stores the Redmine API key")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without creating a ticket")
    return parser.parse_args()


def run_drush_update_report(args):
    command = [
        args.drush,
        "--root",
        args.drupal_root,
        "--uri",
        args.site_uri,
        "php:eval",
        DRUSH_PHP,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        message = stderr or stdout or "Unknown drush failure"
        raise RuntimeError(f"Drush update check failed: {message}")

    stdout = result.stdout
    start = stdout.find(JSON_START)
    end = stdout.find(JSON_END)
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("Could not find JSON payload in drush output")

    payload = stdout[start + len(JSON_START):end].strip()
    return json.loads(payload)


def classify_projects(report):
    actionable = []
    blocked = []

    core = report.get("core") or {}
    core_existing = core.get("existing_version")
    core_recommended = core.get("recommended")
    if core_recommended and core_recommended != core_existing:
        actionable.append(
            {
                "name": "drupal",
                "title": "Drupal core",
                "kind": "core",
                "existing_version": core_existing,
                "recommended": core_recommended,
                "latest_version": core.get("latest_version"),
                "security_update": False,
                "compatibility_message": core.get("reason"),
            }
        )

    for project in sorted(report.get("projects", {}).values(), key=lambda item: item["name"]):
        existing = project.get("existing_version")
        recommended = project.get("recommended")
        recommended_release = project.get("recommended_release") or {}
        core_compatible = recommended_release.get("core_compatible")
        compatibility_message = recommended_release.get("core_compatibility_message")

        if not recommended or recommended == existing:
            continue

        entry = {
            "name": project["name"],
            "title": project.get("title") or project["name"],
            "kind": "project",
            "existing_version": existing,
            "recommended": recommended,
            "latest_version": project.get("latest_version"),
            "security_update": bool(project.get("security_updates")),
            "compatibility_message": compatibility_message,
        }

        if core_compatible is False:
            blocked.append(entry)
        else:
            actionable.append(entry)

    return actionable, blocked


def build_subject(prefix, site_label):
    iso = dt.date.today().isocalendar()
    return f"{prefix}: {site_label} ({iso.year}-W{iso.week:02d})"


def build_module_subject(item):
    title = item.get("title") or item["name"]
    subject = f"Update {title}"
    if item["security_update"]:
        subject += " (security update)"
    return subject


def build_description(report, actionable, blocked, args):
    site_name = report.get("site_name") or args.site_label or args.site_uri
    core_version = ((report.get("core") or {}).get("existing_version")) or "unknown"
    lines = [
        f"Drupal update check for {site_name}.",
        "",
        f"Site URI: {args.site_uri}",
        f"Drupal core: {core_version}",
        f"Generated at: {report.get('generated_at', 'unknown')}",
        "",
        "Compatible updates:",
    ]

    for item in actionable:
        security_note = " [security]" if item["security_update"] else ""
        message = f" ({item['compatibility_message']})" if item.get("compatibility_message") else ""
        lines.append(f"- {item['name']}: {item['existing_version']} -> {item['recommended']}{security_note}{message}")

    if blocked:
        lines.extend(["", "Skipped because they require a Drupal core upgrade:"])
        for item in blocked:
            message = f" ({item['compatibility_message']})" if item.get("compatibility_message") else ""
            lines.append(f"- {item['name']}: {item['existing_version']} -> {item['recommended']}{message}")

    lines.extend(
        [
            "",
            "This ticket was created automatically from Drupal Update Manager data via Drush.",
        ]
    )
    return "\n".join(lines)


def build_module_description(report, item, blocked, args):
    site_name = report.get("site_name") or args.site_label or args.site_uri
    core_version = ((report.get("core") or {}).get("existing_version")) or "unknown"
    item_label = "Drupal core" if item.get("kind") == "core" else "Module"
    lines = [
        f"Drupal update check for {site_name}.",
        "",
        f"{item_label}: {item['title']}",
        f"Current version: {item['existing_version']}",
        f"Recommended version: {item['recommended']}",
        f"Site URI: {args.site_uri}",
        f"Drupal core: {core_version}",
        f"Generated at: {report.get('generated_at', 'unknown')}",
    ]
    if item.get("compatibility_message"):
        lines.append(item["compatibility_message"])
    if item["security_update"]:
        lines.append("Security update available.")
    if blocked:
        lines.extend(["", "Other updates skipped because they require a Drupal core upgrade:"])
        for blocked_item in blocked:
            message = f" ({blocked_item['compatibility_message']})" if blocked_item.get("compatibility_message") else ""
            lines.append(f"- {blocked_item['name']}: {blocked_item['existing_version']} -> {blocked_item['recommended']}{message}")
    lines.extend(["", "This ticket was created automatically from Drupal Update Manager data via Drush."])
    return "\n".join(lines)


def redmine_request(base_url, api_key, method, path, data=None):
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    body = None
    headers = {
        "X-Redmine-API-Key": api_key,
        "Content-Type": "application/json",
    }
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Redmine API error {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Redmine: {exc}") from exc


def resolve_tracker_id(base_url, api_key, args):
    if args.redmine_tracker_id is not None:
        return args.redmine_tracker_id
    if not args.redmine_tracker_name:
        return None
    data = redmine_request(base_url, api_key, "GET", "trackers.json")
    for tracker in data.get("trackers", []):
        if tracker.get("name", "").lower() == args.redmine_tracker_name.lower():
            return tracker.get("id")
    raise RuntimeError(f"Redmine tracker not found: {args.redmine_tracker_name}")


def open_issue_exists(base_url, api_key, project_id, subject):
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "project_id": project_id,
                "status_id": "open",
                "limit": 100,
                "offset": offset,
                "sort": "created_on:desc",
            }
        )
        data = redmine_request(base_url, api_key, "GET", f"issues.json?{query}")
        issues = data.get("issues", [])
        for issue in issues:
            if issue.get("subject") == subject:
                return issue
        total = data.get("total_count", 0)
        offset += len(issues)
        if offset >= total or not issues:
            return None


def create_issue(base_url, api_key, subject, description, args, tracker_id=None):
    issue = {
        "project_id": args.redmine_project_id,
        "subject": subject,
        "description": description,
    }
    if args.redmine_assignee_id is not None:
        issue["assigned_to_id"] = args.redmine_assignee_id
    if args.redmine_parent_issue_id is not None:
        issue["parent_issue_id"] = args.redmine_parent_issue_id
    if tracker_id is not None:
        issue["tracker_id"] = tracker_id
    if args.redmine_priority_id is not None:
        issue["priority_id"] = args.redmine_priority_id

    data = redmine_request(base_url, api_key, "POST", "issues.json", {"issue": issue})
    return data.get("issue", {})


def main():
    args = parse_args()
    report = run_drush_update_report(args)
    actionable, blocked = classify_projects(report)
    subject = None
    description = None

    if args.only_module:
        actionable = [item for item in actionable if item["name"] == args.only_module]
        blocked = [item for item in blocked if item["name"] == args.only_module]

    if not actionable:
        print("No compatible Drupal updates found.")
        if blocked:
            print(f"Skipped {len(blocked)} update(s) that require a Drupal core upgrade.")
        return 0

    site_label = args.site_label or report.get("site_name") or args.site_uri
    if args.redmine_parent_issue_id is not None:
        for item in actionable:
            subject = build_module_subject(item)
            description = build_module_description(report, item, blocked, args)
            print(subject)
            print()
            print(description)
            print()
    else:
        subject = build_subject(args.subject_prefix, site_label)
        description = build_description(report, actionable, blocked, args)
        print(subject)
        print()
        print(description)

    if args.dry_run:
        return 0

    required = {
        "--redmine-url": args.redmine_url,
        "--redmine-project-id": args.redmine_project_id,
    }
    missing = [flag for flag, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required Redmine options: {', '.join(missing)}")

    try:
        api_key = os.environ[args.redmine_api_key_env]
    except KeyError as exc:
        raise RuntimeError(
            f"Missing Redmine API key in environment variable {args.redmine_api_key_env}"
        ) from exc

    tracker_id = resolve_tracker_id(args.redmine_url, api_key, args)

    if args.redmine_parent_issue_id is not None:
        created = 0
        for item in actionable:
            subject = build_module_subject(item)
            existing = open_issue_exists(args.redmine_url, api_key, args.redmine_project_id, subject)
            if existing:
                print(f"Open Redmine issue already exists for {item['name']}: #{existing['id']}")
                continue
            description = build_module_description(report, item, blocked, args)
            issue = create_issue(args.redmine_url, api_key, subject, description, args, tracker_id)
            print(f"Created Redmine issue for {item['name']}: #{issue.get('id')}")
            created += 1
        if created == 0:
            print("No new Redmine subtasks created.")
    else:
        existing = open_issue_exists(args.redmine_url, api_key, args.redmine_project_id, subject)
        if existing:
            print()
            print(f"Open Redmine issue already exists: #{existing['id']}")
            return 0

        issue = create_issue(args.redmine_url, api_key, subject, description, args, tracker_id)
        print()
        print(f"Created Redmine issue #{issue.get('id')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
