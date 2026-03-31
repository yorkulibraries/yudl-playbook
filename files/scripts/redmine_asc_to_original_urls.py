#!/usr/bin/env python3
"""Post York TIFF URLs back to Redmine issues based on ASC IDs in descriptions."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from netrc import NetrcParseError, netrc
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm, Request, build_opener, urlopen


DEFAULT_REDMINE_URL = "https://redmine.library.yorku.ca/"
DEFAULT_YORK_URL = "https://digital.library.yorku.ca/"
ASC_PATTERN = re.compile(r"\bASC\d+\b", re.IGNORECASE)


class SafeIssueError(RuntimeError):
    """An error with a message that is safe to write back into Redmine."""

    def __init__(self, public_message: str, debug_message: str | None = None) -> None:
        super().__init__(debug_message or public_message)
        self.public_message = public_message


class LinkExtractor(HTMLParser):
    """Extract the first anchor href from a small HTML fragment."""

    def __init__(self) -> None:
        super().__init__()
        self.href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.href or tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.href = value
                return


@dataclass(frozen=True)
class Issue:
    issue_id: int
    description: str
    journal_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IssueSummary:
    issue_id: int
    category_name: str | None
    status_name: str | None


@dataclass(frozen=True)
class IssueStatus:
    status_id: int
    name: str


class RedmineClient:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = ensure_trailing_slash(base_url)
        self.api_key = api_key
        self.timeout = timeout
        self._status_ids_by_name: dict[str, int] | None = None

    def get_issue(self, issue_id: int) -> Issue:
        payload = self._request_json(
            "GET",
            f"{self.base_url}issues/{issue_id}.json?include=journals",
        )
        issue_data = payload.get("issue", {})
        description = issue_data.get("description") or ""
        journals = issue_data.get("journals", [])
        journal_notes: list[str] = []
        if isinstance(journals, list):
            for journal in journals:
                if not isinstance(journal, dict):
                    continue
                notes = journal.get("notes")
                if isinstance(notes, str) and notes:
                    journal_notes.append(notes)
        return Issue(
            issue_id=issue_id,
            description=description,
            journal_notes=tuple(journal_notes),
        )

    def update_issue(self, issue_id: int, *, note: str | None = None, status_id: int | None = None) -> None:
        issue_data: dict[str, object] = {}
        if note is not None:
            issue_data["notes"] = note
        if status_id is not None:
            issue_data["status_id"] = status_id
        if not issue_data:
            return

        self._request_json(
            "PUT",
            f"{self.base_url}issues/{issue_id}.json",
            {"issue": issue_data},
            expect_json=False,
        )

    def get_status_id(self, status_name: str) -> int:
        if self._status_ids_by_name is None:
            self._status_ids_by_name = {}
            payload = self._request_json(
                "GET",
                f"{self.base_url}issue_statuses.json",
            )
            statuses = payload.get("issue_statuses", [])
            if isinstance(statuses, list):
                for item in statuses:
                    if not isinstance(item, dict):
                        continue
                    status_id = item.get("id")
                    name = item.get("name")
                    if isinstance(status_id, int) and isinstance(name, str):
                        self._status_ids_by_name[name.casefold()] = status_id

        status_id = self._status_ids_by_name.get(status_name.casefold()) if self._status_ids_by_name else None
        if status_id is None:
            raise SafeIssueError(
                "unable to resolve automatically",
                f"Redmine status {status_name!r} was not found in /issue_statuses.json",
            )
        return status_id

    def find_issue_ids(self, *, category_name: str, status_name: str) -> list[int]:
        normalized_category = category_name.casefold()
        normalized_status = status_name.casefold()
        ticket_ids: list[int] = []

        for issue in self.iter_issues():
            if issue.category_name is None or issue.status_name is None:
                continue
            if issue.category_name.casefold() != normalized_category:
                continue
            if issue.status_name.casefold() != normalized_status:
                continue
            ticket_ids.append(issue.issue_id)

        return ticket_ids

    def iter_issues(self, *, page_size: int = 100) -> Iterable[IssueSummary]:
        offset = 0

        while True:
            query = urlencode(
                {
                    "status_id": "*",
                    "limit": page_size,
                    "offset": offset,
                }
            )
            payload = self._request_json(
                "GET",
                f"{self.base_url}issues.json?{query}",
            )
            issues_data = payload.get("issues", [])
            if not isinstance(issues_data, list) or not issues_data:
                return

            for issue_data in issues_data:
                if not isinstance(issue_data, dict):
                    continue

                issue_id = issue_data.get("id")
                if not isinstance(issue_id, int):
                    continue

                category = issue_data.get("category")
                status = issue_data.get("status")
                category_name = category.get("name") if isinstance(category, dict) else None
                status_name = status.get("name") if isinstance(status, dict) else None
                yield IssueSummary(
                    issue_id=issue_id,
                    category_name=category_name if isinstance(category_name, str) else None,
                    status_name=status_name if isinstance(status_name, str) else None,
                )

            total_count = payload.get("total_count")
            if not isinstance(total_count, int):
                if len(issues_data) < page_size:
                    return
                offset += len(issues_data)
                continue

            offset += len(issues_data)
            if offset >= total_count:
                return

    def _request_json(
        self,
        method: str,
        url: str,
        body: dict[str, object] | None = None,
        *,
        expect_json: bool = True,
    ) -> Any:
        headers = {
            "X-Redmine-API-Key": self.api_key,
            "Accept": "application/json",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        request = Request(url, data=data, headers=headers, method=method)
        return load_json_response(request, timeout=self.timeout, expect_json=expect_json)


class YorkClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: float) -> None:
        self.base_url = ensure_trailing_slash(base_url)
        self.timeout = timeout
        password_mgr = HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, self.base_url, username, password)
        self.opener = build_opener(HTTPBasicAuthHandler(password_mgr))

    def get_original_file_url(self, asc_id: str) -> str:
        request = Request(
            urljoin(self.base_url, f"api/asc-to-original-file/{asc_id}"),
            headers={"Accept": "application/json"},
            method="GET",
        )
        payload = load_json_response(request, opener=self.opener, timeout=self.timeout)
        href = extract_href_from_payload(payload)
        if not href:
            raise ValueError(f"No TIFF href found in York response for {asc_id}.")
        return urljoin(self.base_url, href)


def ensure_trailing_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def load_json_response(
    request: Request,
    *,
    opener=None,
    timeout: float,
    expect_json: bool = True,
) -> Any:
    handler = opener.open if opener else None
    try:
        response = handler(request, timeout=timeout) if handler else urlopen(request, timeout=timeout)
        with response as raw:
            if not expect_json:
                return {}
            charset = raw.headers.get_content_charset() or "utf-8"
            body = raw.read().decode(charset)
            return json.loads(body)
    except HTTPError as exc:
        message = f"{request.method} {request.full_url} failed with HTTP {exc.code}"
        raise SafeIssueError("unable to resolve automatically", message) from exc
    except URLError as exc:
        debug_message = f"{request.method} {request.full_url} failed: {exc.reason}"
        raise SafeIssueError("unable to resolve automatically", debug_message) from exc
    except json.JSONDecodeError as exc:
        debug_message = f"{request.method} {request.full_url} returned invalid JSON"
        raise SafeIssueError("unable to resolve automatically", debug_message) from exc


def extract_href_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, list) or not payload:
        return None

    first_item = payload[0]
    if not isinstance(first_item, dict):
        return None

    html_fragment = first_item.get("field_media_file")
    if not isinstance(html_fragment, str):
        return None

    parser = LinkExtractor()
    parser.feed(html_fragment)
    href = parser.href
    if not href:
        return None
    return href.strip()


def extract_asc_ids(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in ASC_PATTERN.findall(text):
        normalized = match.upper()
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def read_password_from_file(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8").strip()


def load_password_from_netrc(machine: str) -> str | None:
    try:
        auth = netrc().authenticators(machine)
    except (FileNotFoundError, NetrcParseError):
        return None
    if not auth:
        return None
    _login, _account, password = auth
    return password


def resolve_york_password(args: argparse.Namespace) -> str:
    if args.york_password:
        return args.york_password

    env_password = os.getenv("YORK_API_PASSWORD")
    if env_password:
        return env_password

    password_file = args.york_password_file or os.getenv("YORK_API_PASSWORD_FILE")
    if password_file:
        return read_password_from_file(password_file)

    machine = args.york_netrc_machine or os.getenv("YORK_NETRC_MACHINE") or "digital.library.yorku.ca"
    netrc_password = load_password_from_netrc(machine)
    if netrc_password:
        return netrc_password

    return getpass.getpass(f"Password for {args.york_user}: ")


def parse_ticket_ids(values: Iterable[str]) -> list[int]:
    ticket_ids: list[int] = []
    seen: set[int] = set()
    for value in values:
        for chunk in value.split(","):
            candidate = chunk.strip()
            if not candidate:
                continue
            try:
                ticket_id = int(candidate)
            except ValueError as exc:
                raise argparse.ArgumentTypeError(f"Invalid ticket ID: {candidate}") from exc
            if ticket_id not in seen:
                seen.add(ticket_id)
                ticket_ids.append(ticket_id)
    if not ticket_ids:
        raise argparse.ArgumentTypeError("At least one Redmine ticket ID is required.")
    return ticket_ids


def build_comment(asc_results: list[tuple[str, str | None, str | None]]) -> str:
    lines: list[str] = []
    for asc_id, resolved_url, error in asc_results:
        if resolved_url:
            lines.append(f"{asc_id} -> {resolved_url}")
        else:
            lines.append(f"{asc_id} -> ERROR: {error}")
    return "\n".join(lines)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read Redmine issue descriptions, resolve ASC IDs to original TIFF URLs, "
            "and add one aggregated Redmine comment per ticket."
        )
    )
    parser.add_argument(
        "ticket_ids",
        nargs="*",
        help="Optional Redmine issue IDs. Comma-separated values are also accepted.",
    )
    parser.add_argument(
        "--redmine-url",
        default=os.getenv("REDMINE_URL", DEFAULT_REDMINE_URL),
        help=f"Redmine base URL. Default: {DEFAULT_REDMINE_URL}",
    )
    parser.add_argument(
        "--redmine-api-key",
        default=os.getenv("REDMINE_API_KEY"),
        help="Redmine API key. Defaults to REDMINE_API_KEY.",
    )
    parser.add_argument(
        "--york-url",
        default=os.getenv("YORK_API_URL", DEFAULT_YORK_URL),
        help=f"York Digital Library base URL. Default: {DEFAULT_YORK_URL}",
    )
    parser.add_argument(
        "--york-user",
        default=os.getenv("YORK_API_USER"),
        help="York API username. Defaults to YORK_API_USER.",
    )
    parser.add_argument(
        "--york-password",
        help="York API password. Prefer env vars or a prompt to avoid shell history.",
    )
    parser.add_argument(
        "--york-password-file",
        help="Read the York API password from a local file.",
    )
    parser.add_argument(
        "--york-netrc-machine",
        help="Optional ~/.netrc machine name to use for York API credentials.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds. Default: 30.",
    )
    parser.add_argument(
        "--category",
        default=os.getenv("REDMINE_CATEGORY", "ASC"),
        help="When no ticket IDs are provided, query Redmine for this category name. Default: ASC.",
    )
    parser.add_argument(
        "--status",
        default=os.getenv("REDMINE_STATUS", "New"),
        help="When no ticket IDs are provided, query Redmine for this status name. Default: New.",
    )
    parser.add_argument(
        "--post-status",
        default=os.getenv("REDMINE_POST_STATUS", "Feedback"),
        help="After posting a comment, update the issue to this status name. Default: Feedback.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated comment instead of updating Redmine.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    if not args.redmine_api_key:
        parser.error("A Redmine API key is required via --redmine-api-key or REDMINE_API_KEY.")
    if not args.york_user:
        parser.error("A York API username is required via --york-user or YORK_API_USER.")

    york_password = resolve_york_password(args)

    redmine = RedmineClient(args.redmine_url, args.redmine_api_key, args.timeout)
    york = YorkClient(args.york_url, args.york_user, york_password, args.timeout)
    post_status_id = redmine.get_status_id(args.post_status)

    if args.ticket_ids:
        ticket_ids = parse_ticket_ids(args.ticket_ids)
    else:
        logging.info(
            "No ticket IDs provided; querying Redmine for category %s with status %s",
            args.category,
            args.status,
        )
        ticket_ids = redmine.find_issue_ids(category_name=args.category, status_name=args.status)
        if not ticket_ids:
            logging.info(
                "No Redmine issues found for category %s with status %s",
                args.category,
                args.status,
            )
            return 0
        logging.info("Found %s Redmine issue(s) to process", len(ticket_ids))

    had_error = False

    for ticket_id in ticket_ids:
        logging.info("Processing Redmine issue %s", ticket_id)
        try:
            issue = redmine.get_issue(ticket_id)
            asc_ids = extract_asc_ids(issue.description)
            if not asc_ids:
                logging.warning("Issue %s has no ASC IDs in the description. Skipping.", ticket_id)
                continue

            asc_results: list[tuple[str, str | None, str | None]] = []
            for asc_id in asc_ids:
                try:
                    resolved_url = york.get_original_file_url(asc_id)
                    asc_results.append((asc_id, resolved_url, None))
                except Exception as exc:  # noqa: BLE001
                    logging.error("Failed to resolve %s for issue %s: %s", asc_id, ticket_id, exc)
                    public_error = exc.public_message if isinstance(exc, SafeIssueError) else "unable to resolve automatically"
                    asc_results.append((asc_id, None, public_error))
                    had_error = True

            note = build_comment(asc_results)
            if note in issue.journal_notes:
                logging.info("Issue %s already has the generated comment. Skipping.", ticket_id)
                continue
            if args.dry_run:
                print(f"Issue {ticket_id}\n{note}\nStatus update: {args.post_status}\n")
            else:
                redmine.update_issue(ticket_id, note=note, status_id=post_status_id)
                logging.info("Added one comment to issue %s and updated status to %s", ticket_id, args.post_status)
        except Exception as exc:  # noqa: BLE001
            logging.error("Issue %s failed: %s", ticket_id, exc)
            had_error = True

    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
