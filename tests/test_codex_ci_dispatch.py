"""CI contract: bot-created pull requests receive non-privileged checks automatically.

Static assertions defend the important invariant: invoking CI via
workflow_dispatch is NOT permission to auto-merge or publish to WordPress.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CodexReadOnlyDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = (ROOT / ".github/workflows/xfit-codex-lane.yml").read_text(encoding="utf-8")
        cls.caller = (ROOT / ".github/workflows/xfit-codex-parallel.yml").read_text(encoding="utf-8")
        cls.checks = (ROOT / ".github/workflows/xfit-checks.yml").read_text(encoding="utf-8")

    def test_dispatch_is_bounded_to_agent_owned_branch_and_read_only_workflow(self):
        self.assertIn("gh workflow run xfit-checks.yml", self.agent)
        self.assertIn("if: steps.open_pr.outputs.branch != ''", self.agent)
        self.assertIn("^xfit/codex-(ux|archive|editor|revenue)-[0-9]+-[0-9]+$", self.agent)
        self.assertIn('PR_BRANCH: ${{ steps.open_pr.outputs.branch }}', self.agent)
        self.assertIn("actions: write  # workflow_dispatch only", self.agent)

    def test_reusable_caller_scopes_match_child_job_before_actions_start(self):
        # GitHub validates permissions across reusable workflow boundaries
        # BEFORE scheduling jobs. Missing actions:write previously caused
        # startup_failure with zero jobs and zero usable logs.
        caller = self.caller.split("  parallel-lanes:", 1)[1]
        call_permissions = caller.split("    permissions:", 1)[1].split("    strategy:", 1)[0]
        for required in ("actions: write", "contents: write",
                         "pull-requests: write"):
            self.assertIn(required, call_permissions)
        self.assertIn("uses: ./.github/workflows/xfit-codex-lane.yml", caller)
        self.assertIn("actions: write  # workflow_dispatch only", self.agent)
        # Do not give actions:write to preflight, which needs read only.
        gate = self.caller.split("  permission-gate:", 1)[1].split(
            "  parallel-lanes:", 1)[0]
        self.assertIn("actions: read", gate)
        self.assertNotIn("actions: write", gate)
        # Only edits to this orchestration file should launch an extra wave.
        self.assertIn("paths: ['.github/workflows/xfit-codex-parallel.yml']",
                      self.caller)

    def test_code_checks_is_unprivileged_and_requires_explicit_dispatch(self):
        self.assertIn("workflow_dispatch:", self.checks)
        self.assertIn("permissions:\n  contents: read\n", self.checks)
        self.assertNotIn("secrets.WP_APP_PASSWORD", self.checks)
        self.assertNotIn("scripts/wp_publish.py --publish", self.checks)
        self.assertNotIn("gh pr merge", self.checks)

    def test_agent_does_not_automerge_or_deploy(self):
        self.assertNotIn("gh pr merge", self.agent)
        self.assertNotIn("scripts/wp_publish.py --publish", self.agent)
        self.assertIn("Human review and explicit merge decision still required.", self.agent)


if __name__ == "__main__":
    unittest.main()
