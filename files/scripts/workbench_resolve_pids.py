#!/usr/bin/env python3
"""Replace PIDs and term names with IDs in an Islandora Workbench CSV.

The Workbench CSVs in files/workbench/ reference parent nodes by PID (e.g.
yul:asc) and some terms by name (e.g. Open Seadragon) instead of ID, so they
keep working however many nodes and terms exist before Workbench runs. This
looks them up in Drupal and writes a copy of the CSV with IDs.

Term names need resolving here for paged content: Workbench copies the parent
row's field_display_hints onto each page node without resolving it.
"""

import argparse
import csv
import subprocess
import sys


# Columns that hold node references; values may be pipe-separated.
NODE_COLUMNS = ("field_member_of", "node_id")

# Term columns resolved by name, and the vocabulary each one uses.
TERM_COLUMNS = {
    "field_model": "islandora_models",
    "field_display_hints": "islandora_display",
    "field_resource_type": "resource_types",
}

PID_QUERY = "SELECT field_pid_value, entity_id FROM node__field_pid"
TERM_QUERY = (
    "SELECT vid, name, tid FROM taxonomy_term_field_data "
    "WHERE default_langcode = 1 AND vid IN ('islandora_models', 'islandora_display', 'resource_types')"
)


def sql_rows(drush, drupal_root, query):
    output = subprocess.run(
        [drush, f"--root={drupal_root}", "sql:query", query],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [[part.strip() for part in line.split("\t")] for line in output.splitlines() if line.strip()]


def fetch_pid_map(drush, drupal_root):
    return {
        row[0]: row[1]
        for row in sql_rows(drush, drupal_root, PID_QUERY)
        if len(row) == 2 and row[1].isdigit()
    }


def fetch_term_map(drush, drupal_root):
    """Map (vocabulary, name) to tid; names used twice in a vocabulary map to None."""
    term_map = {}
    for row in sql_rows(drush, drupal_root, TERM_QUERY):
        if len(row) == 3 and row[2].isdigit():
            key = (row[0], row[1])
            term_map[key] = None if key in term_map else row[2]
    return term_map


def resolve_value(value, lookup):
    resolved = []
    missing = []
    for part in value.split("|"):
        part = part.strip()
        if not part or part.isdigit():
            resolved.append(part)
        elif lookup.get(part):
            resolved.append(lookup[part])
        else:
            missing.append(part)
    return "|".join(resolved), missing


def resolve_rows(rows, pid_map, term_map):
    term_lookups = {
        column: {name: tid for (vid, name), tid in term_map.items() if vid == vocabulary}
        for column, vocabulary in TERM_COLUMNS.items()
    }
    lookups = {column: pid_map for column in NODE_COLUMNS}
    lookups.update(term_lookups)

    missing = []
    for line_number, row in enumerate(rows, start=2):
        for column, lookup in lookups.items():
            if row.get(column):
                row[column], not_found = resolve_value(row[column], lookup)
                missing.extend(f"line {line_number}: {column} {value}" for value in not_found)
    return rows, missing


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    parser.add_argument("--drush", default="/var/www/html/drupal/vendor/bin/drush")
    parser.add_argument("--drupal-root", default="/var/www/html/drupal/web")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    with open(args.input_csv, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)

    rows, missing = resolve_rows(
        rows,
        fetch_pid_map(args.drush, args.drupal_root),
        fetch_term_map(args.drush, args.drupal_root),
    )
    if missing:
        print(f"{args.input_csv}: not found (or ambiguous) in Drupal:", file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1

    with open(args.output_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
