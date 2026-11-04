from datetime import UTC, datetime

import pytest
from unittest.mock import MagicMock

from products.stamphog.backend.facade.contracts import StamphogGitHubError
from products.stamphog.backend.logic.attestations import (
    ANNOTATION_TITLE_PREFIX,
    ActionsAttestation,
    actions_attestation_results,
    actions_attestations,
)

_WORKFLOW = ".github/workflows/dependency-proof.yml"
_RULE = ActionsAttestation(name="Dependency proof", workflow=_WORKFLOW, job="prove")
_PR = {
    "number": 7,
    "head": {"sha": "head1", "repo": {"full_name": "PostHog/posthog"}},
    "base": {"ref": "master", "repo": {"default_branch": "master"}},
}
_MARKER = '<!-- stamphog:v1 ["pnpm-lock.yaml"] -->'


def _run(run_id: int, created_at: str, **changes: object) -> dict:
    return {
        "id": run_id,
        "created_at": created_at,
        "path": _WORKFLOW,
        "event": "pull_request",
        "head_sha": "head1",
        "status": "completed",
        "pull_requests": [{"number": 7}],
        **changes,
    }


def _job(job_id: int, **changes: object) -> dict:
    return {"id": job_id, "name": "prove", "status": "completed", "conclusion": "success", **changes}


def _annotation(title: str = ANNOTATION_TITLE_PREFIX + "master", level: str = "notice") -> dict:
    return {"annotation_level": level, "title": title, "message": _MARKER}


class _FakeClient:
    def __init__(
        self,
        runs: list[dict],
        jobs: dict[int, list[dict]],
        annotations: dict[int, list[dict]],
        base_changed_at: datetime | None = None,
    ) -> None:
        self.runs, self.jobs, self.annotations, self.base_changed_at = runs, jobs, annotations, base_changed_at

    def get_last_base_change_at(self, repo: str, pr_number: int) -> datetime | None:
        return self.base_changed_at

    def get_pull_request_workflow_runs(self, repo: str, head_sha: str) -> list[dict]:
        return self.runs

    def get_workflow_run_jobs(self, repo: str, run_id: int) -> list[dict]:
        return self.jobs[run_id]

    def get_check_run_annotations(self, repo: str, check_run_id: int) -> list[dict]:
        return self.annotations.get(check_run_id, [])


_PASSED = {"completed": True, "conclusion": "success", "files": ["pnpm-lock.yaml"]}
_NO_RUN = {"completed": False}


@pytest.mark.parametrize(
    "runs, jobs, annotations, expected",
    [
        pytest.param(
            [_run(1, "t1")],
            {1: [_job(11)]},
            {11: [_annotation()]},
            _PASSED,
            id="passed",
        ),
        pytest.param([_run(1, "t1", path=".github/workflows/other.yml")], {}, {}, _NO_RUN, id="other-workflow"),
        pytest.param([_run(1, "t1", event="push")], {}, {}, _NO_RUN, id="other-event"),
        pytest.param([_run(1, "t1", head_sha="head0")], {}, {}, _NO_RUN, id="other-head"),
        pytest.param([_run(1, "t1", pull_requests=[{"number": 8}])], {}, {}, _NO_RUN, id="other-pr"),
        pytest.param([_run(1, "t1", status="in_progress")], {1: []}, {}, _NO_RUN, id="running"),
        pytest.param(
            [_run(1, "t1", status="in_progress")],
            {1: [_job(11, status="in_progress", conclusion=None)]},
            {},
            _NO_RUN,
            id="job-running",
        ),
        pytest.param(
            [_run(1, "t1", status="in_progress")],
            {1: [_job(11)]},
            {11: [_annotation()]},
            _PASSED,
            id="job-finished-while-its-workflow-runs",
        ),
        pytest.param(
            [_run(1, "t1"), _run(2, "t2")],
            {
                1: [_job(11)],
                2: [_job(21, conclusion="skipped")],
            },
            {11: [_annotation()]},
            _PASSED,
            id="skipped-newer-run-keeps-older-proof",
        ),
        pytest.param(
            [_run(1, "t1"), _run(2, "t2")],
            {
                1: [_job(11)],
                2: [_job(21, conclusion="failure")],
            },
            {11: [_annotation()]},
            {"completed": True, "conclusion": "failure"},
            id="newest-run-failed",
        ),
        pytest.param(
            [_run(1, "t1")],
            {1: [_job(11)]},
            {11: [_annotation(title=ANNOTATION_TITLE_PREFIX + "release")]},
            {"completed": True, "conclusion": "success", "files": []},
            id="proved-against-another-base",
        ),
        pytest.param(
            [_run(1, "t1")],
            {1: [_job(11)]},
            {11: [_annotation(level="warning")]},
            {"completed": True, "conclusion": "success", "files": []},
            id="not-a-notice",
        ),
        pytest.param(
            [_run(1, "t1")],
            {1: [_job(11)]},
            {11: [_annotation(), _annotation()]},
            {"completed": True, "conclusion": "success", "files": []},
            id="injected-second-marker",
        ),
        pytest.param(
            [_run(1, "t1")],
            {1: [_job(11)]},
            {11: [_annotation(), _annotation(title=ANNOTATION_TITLE_PREFIX + "release")]},
            {"completed": True, "conclusion": "success", "files": []},
            id="injected-marker-for-another-base",
        ),
        pytest.param(
            [_run(1, "t1"), _run(2, "t2")],
            {1: [_job(11, conclusion="skipped")], 2: [_job(21, conclusion="skipped")]},
            {},
            {"completed": True, "conclusion": "skipped"},
            id="every-run-skipped",
        ),
        pytest.param(
            [_run(1, "t1")],
            {1: [_job(11, name="build")]},
            {},
            {"completed": True, "conclusion": "missing_job"},
            id="job-not-found",
        ),
    ],
)
def test_actions_attestation_trusts_only_the_declared_run(
    runs: list[dict], jobs: dict[int, list[dict]], annotations: dict[int, list[dict]], expected: dict
) -> None:
    client = _FakeClient(runs, jobs, annotations)

    assert actions_attestation_results(client, "posthog/posthog", _PR, [_RULE]) == {"Dependency proof": expected}  # type: ignore[arg-type]


def test_actions_attestation_ignores_runs_from_before_the_last_base_change() -> None:
    # A run made while the PR targeted another branch ran that branch's copy of the workflow.
    runs = [_run(1, "2026-11-01T10:00:00Z"), _run(2, "2026-11-01T12:00:00Z")]
    jobs = {1: [_job(11)], 2: [_job(21, conclusion="skipped")]}
    retargeted_at = datetime(2026, 11, 1, 11, tzinfo=UTC)
    client = _FakeClient(runs, jobs, {11: [_annotation()]}, base_changed_at=retargeted_at)

    assert actions_attestation_results(client, "posthog/posthog", _PR, [_RULE]) == {  # type: ignore[arg-type]
        "Dependency proof": {"completed": True, "conclusion": "skipped"}
    }


@pytest.mark.parametrize(
    "head_repo, base_ref, runs_error",
    [
        pytest.param("someone/posthog", "master", None, id="fork"),
        # A repo writer can push a branch that is not the default one and change its copy of the workflow.
        pytest.param("PostHog/posthog", "author-branch", None, id="base-is-not-the-default-branch"),
        pytest.param(
            "PostHog/posthog", "master", StamphogGitHubError("forbidden", status_code=403), id="no-actions-read"
        ),
    ],
)
def test_actions_attestation_without_a_bindable_run_lifts_and_waits_for_nothing(
    head_repo: str, base_ref: str, runs_error: StamphogGitHubError | None
) -> None:
    pr = {
        **_PR,
        "head": {"sha": "head1", "repo": {"full_name": head_repo}},
        "base": {"ref": base_ref, "repo": {"default_branch": "master"}},
    }
    client = _FakeClient([_run(1, "t1")], {1: [_job(11)]}, {11: [_annotation()]})
    client.get_pull_request_workflow_runs = MagicMock(side_effect=runs_error, return_value=client.runs)  # type: ignore[method-assign]

    assert actions_attestation_results(client, "posthog/posthog", pr, [_RULE]) == {}  # type: ignore[arg-type]


def test_actions_attestations_reads_only_actions_entries_from_both_lists() -> None:
    policy = """
attestations:
  - {name: Migration risk, check: Migration risk, lifts: [migrations], paths: ['x']}
extend_attestations:
  - {name: Dependency proof, actions_workflow: .github/workflows/dependency-proof.yml, job: prove, lifts: [deps_toolchain], paths: ['y']}
"""

    assert actions_attestations(policy) == [_RULE]
