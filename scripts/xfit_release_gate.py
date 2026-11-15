#!/usr/bin/env python3
"""Wait for exact-commit WP publication before browser QA on a main push.

Uses only GitHub's read-only Actions/compare APIs and the two existing live
workflow path filters. Never reads WordPress credentials or makes a WP write.
"""

import fnmatch
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LIVE_WORKFLOWS = {
    "XFIT Creatine Advisor Live": ".github/workflows/xfit-creatine-live.yml",
    "XFIT Whey Advisor Live": ".github/workflows/xfit-whey-live.yml",
}
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class ReleaseGateError(ValueError):
    """Missing, late or unsuccessful same-commit publication evidence."""


def workflow_push_paths(source):
    """Read literal path filters from a tightly scoped existing workflow YAML."""
    in_push = False
    in_paths = False
    patterns = []
    for line in source.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line == "  push:":
            in_push = True
            continue
        if in_push and line.startswith("  ") and not line.startswith("    "):
            break
        if not in_push:
            continue
        if line == "    paths:":
            in_paths = True
            continue
        if in_paths:
            if not line.startswith("      - "):
                break
            raw = line.removeprefix("      - ").strip().strip("'\"")
            if not raw or raw.startswith("!"):
                raise ReleaseGateError("Invalid release path filter")
            patterns.append(raw)
    if not patterns:
        raise ReleaseGateError("Release workflow lacks a readable push path filter")
    return patterns


def expected_releases(changed, workflow_sources):
    if not isinstance(changed, set) or not all(isinstance(x, str) for x in changed):
        raise ReleaseGateError("Invalid changed file evidence")
    result = set()
    for name, source in workflow_sources.items():
        patterns = workflow_push_paths(source)
        if any(fnmatch.fnmatchcase(file, pattern) for file in changed for pattern in patterns):
            result.add(name)
    return result


def check_release_runs(expected, runs, sha):
    """Return True only when every required workflow has successful evidence."""
    if not expected:
        return True
    found = {}
    for run in runs:
        name = run.get("name")
        if name not in expected or run.get("event") != "push" or run.get("head_sha") != sha:
            continue
        if name not in found or run.get("id", 0) > found[name].get("id", 0):
            found[name] = run
    if set(found) != expected:
        return False
    for name, run in found.items():
        if run.get("status") != "completed":
            return False
        if run.get("conclusion") != "success":
            raise ReleaseGateError("Required live publication failed or was skipped: " + name)
    return True


def github_json(path, *, repo, token):
    req = Request("https://api.github.com/repos/" + repo + "/" + path,
                  headers={"Accept": "application/vnd.github+json",
                           "Authorization": "Bearer " + token,
                           "X-GitHub-Api-Version": "2022-11-28",
                           "User-Agent": "XfitMobileReleaseGate/1.0"})
    try:
        with urlopen(req, timeout=25) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise ReleaseGateError("GitHub read-only release evidence unavailable: " + type(exc).__name__) from exc


def changed_files(*, before, after, repo, token):
    if not SHA_RE.fullmatch(before) or not SHA_RE.fullmatch(after):
        raise ReleaseGateError("Missing exact before/after commit SHAs")
    compare = github_json("compare/" + before + "..." + after, repo=repo, token=token)
    files = compare.get("files")
    if not isinstance(files, list) or len(files) >= 300:
        raise ReleaseGateError("Commit file comparison missing or truncated")
    changed = set()
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise ReleaseGateError("Invalid changed file in GitHub comparison")
        changed.add(item["filename"])
        if isinstance(item.get("previous_filename"), str):
            changed.add(item["previous_filename"])
    return changed


def wait_for_releases(expected, *, sha, repo, token, timeout_seconds=840, interval_seconds=10):
    if not expected:
        print(json.dumps({"state": "NO_ADVISER_RELEASE_EXPECTED", "wp_writes": 0}))
        return
    deadline = time.monotonic() + timeout_seconds
    while True:
        data = github_json("actions/runs?head_sha=" + sha + "&event=push&per_page=100",
                           repo=repo, token=token)
        runs = data.get("workflow_runs")
        if not isinstance(runs, list):
            raise ReleaseGateError("GitHub Actions run list unavailable")
        if check_release_runs(expected, runs, sha):
            print(json.dumps({"state": "SAME_COMMIT_RELEASES_VERIFIED",
                              "workflow_names": sorted(expected), "wp_writes": 0}))
            return
        if time.monotonic() >= deadline:
            raise ReleaseGateError("Required live workflow did not finish within the QA gate window")
        time.sleep(interval_seconds)


def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    before = os.environ.get("GITHUB_EVENT_BEFORE", "")
    sha = os.environ.get("GITHUB_SHA", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not REPO_RE.fullmatch(repo) or not token:
        raise ReleaseGateError("Missing GitHub Actions read-only context")
    sources = {name: Path(path).read_text(encoding="utf-8")
               for name, path in LIVE_WORKFLOWS.items()}
    expected = expected_releases(changed_files(before=before, after=sha,
                                               repo=repo, token=token), sources)
    wait_for_releases(expected, sha=sha, repo=repo, token=token)


if __name__ == "__main__":
    try:
        main()
    except (ReleaseGateError, OSError) as exc:
        print("XFIT_RELEASE_GATE_ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)
