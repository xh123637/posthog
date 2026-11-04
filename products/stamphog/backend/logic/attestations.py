"""Find the GitHub Actions runs that the repository's policy trusts as attestations.

An attestation is a CI result that lifts named deny categories for the files it lists (the engine's
``attestations.py`` holds the model). The engine reads a check attestation from the head commit's
check runs. An Actions attestation needs its run found first, with a token the sandbox does not
hold, so the server finds it here and passes the result in the review context.

A run counts only when GitHub says it ran the declared workflow file on a ``pull_request`` event
for this head commit and this PR, and only the named job of its latest attempt is read. A check
with the right name from anywhere else, or a job that skipped, counts for nothing.

A run created before the PR's last base change counts for nothing, because it ran the old base's
copy of the workflow. GitHub fills a run's ``pull_requests`` field at read time from the PR's current
state, so the time of the base change comes from the PR's timeline. The job also titles its notice
with the base branch it proved against.
"""

import re
import json
from datetime import datetime

import yaml
import structlog

from posthog.dataclasses import frozen

from ..facade.contracts import StamphogGitHubError
from .github_client import StamphogGitHubClient

logger = structlog.get_logger(__name__)

ANNOTATION_TITLE_PREFIX = "stamphog attestation: "
_MARKER_RE = re.compile(r"<!--\s*stamphog:v1\s+(\[[^\]]*\])\s*-->")


@frozen
class ActionsAttestation:
    name: str
    workflow: str
    job: str


def actions_attestations(policy_text: str | None) -> list[ActionsAttestation]:
    """The Actions attestations a repository's default-branch policy declares.

    The engine validates the whole policy and fails the review on a malformed one, so an entry
    this cannot read is skipped here rather than reported twice.
    """
    try:
        raw = yaml.safe_load(policy_text or "")
    except yaml.YAMLError:
        return []
    if not isinstance(raw, dict):
        return []
    entries = [
        entry
        for key in ("attestations", "extend_attestations")
        if isinstance(listed := raw.get(key), list)
        for entry in listed
    ]
    return [
        ActionsAttestation(name=entry["name"], workflow=entry["actions_workflow"], job=entry["job"])
        for entry in entries
        if isinstance(entry, dict)
        and all(isinstance(entry.get(key), str) for key in ("name", "actions_workflow", "job"))
    ]


def _marker_files(annotations: list[dict], base_ref: str) -> list[str]:
    # A job that prints PR content can emit a workflow command too, so a second marker at any level
    # or for any base means the job's output was not its own, and the proof lifts nothing.
    markers = [
        (annotation, match.group(1))
        for annotation in annotations
        for match in _MARKER_RE.finditer(str(annotation.get("message") or ""))
    ]
    if len(markers) != 1:
        return []
    annotation, listed = markers[0]
    if annotation.get("annotation_level") != "notice" or annotation.get("title") != ANNOTATION_TITLE_PREFIX + base_ref:
        return []
    try:
        paths = json.loads(listed)
    except json.JSONDecodeError:
        return []
    return sorted({p for p in paths if isinstance(p, str)}) if isinstance(paths, list) else []


def _created_after(run: dict, base_changed_at: datetime | None) -> bool:
    if base_changed_at is None:
        return True
    try:
        return datetime.fromisoformat(str(run.get("created_at"))) > base_changed_at
    except ValueError:
        return False


def _result(
    client: StamphogGitHubClient,
    repo: str,
    pr: dict,
    rule: ActionsAttestation,
    runs: list[dict],
    jobs_by_run: dict[int, list[dict]],
    base_changed_at: datetime | None,
) -> dict:
    head_sha = (pr.get("head") or {}).get("sha")
    candidates = sorted(
        (
            run
            for run in runs
            if run.get("path") == rule.workflow
            and run.get("event") == "pull_request"
            and run.get("head_sha") == head_sha
            and any(item.get("number") == pr.get("number") for item in run.get("pull_requests") or [])
            and _created_after(run, base_changed_at)
        ),
        key=lambda run: (run.get("created_at") or "", run.get("id") or 0),
        reverse=True,
    )
    skipped = False
    for run in candidates:
        if run["id"] not in jobs_by_run:
            jobs_by_run[run["id"]] = client.get_workflow_run_jobs(repo, run["id"])
        jobs = [job for job in jobs_by_run[run["id"]] if job.get("name") == rule.job]
        if not jobs and run.get("status") != "completed":
            return {"completed": False}
        if len(jobs) != 1:
            return {"completed": True, "conclusion": "missing_job"}
        job = jobs[0]
        # The job's own check run wakes the review, and the rest of its workflow may still be
        # running then, so the job's status decides rather than the run's.
        if job.get("status") != "completed":
            return {"completed": False}
        # A run that skipped the job (an edit that changed nothing it proves) leaves the older proof standing.
        if job.get("conclusion") == "skipped":
            skipped = True
            continue
        if job.get("conclusion") != "success":
            return {"completed": True, "conclusion": job.get("conclusion") or "unknown"}
        base_ref = (pr.get("base") or {}).get("ref") or ""
        files = _marker_files(client.get_check_run_annotations(repo, job["id"]), base_ref)
        return {"completed": True, "conclusion": "success", "files": files}
    return {"completed": True, "conclusion": "skipped"} if skipped else {"completed": False}


def actions_attestation_results(
    client: StamphogGitHubClient, repo: str, pr: dict, rules: list[ActionsAttestation]
) -> dict[str, dict]:
    """Each Actions attestation's state at the PR head, keyed by name, in the engine's context shape.

    No run yet reads as not completed, so the engine waits for it when the PR changes a file the
    attestation judges. An attestation with no entry lifts nothing and waits for nothing. That is
    every attestation on a fork PR, because GitHub lists no PR on a fork's run, on a PR whose base
    is not the default branch, and on an installation without Actions read, which gets a 403.
    Other errors raise and the activity retries.
    """
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    if ((head.get("repo") or {}).get("full_name") or "").lower() != repo.lower():
        return {}
    # A repo writer can push a branch that is not the default one, and a run on a PR to it uses its copy of the workflow.
    if not base.get("ref") or base.get("ref") != (base.get("repo") or {}).get("default_branch"):
        return {}
    try:
        runs = client.get_pull_request_workflow_runs(repo, head.get("sha") or "")
        base_changed_at = client.get_last_base_change_at(repo, pr["number"]) if runs else None
        jobs_by_run: dict[int, list[dict]] = {}
        return {rule.name: _result(client, repo, pr, rule, runs, jobs_by_run, base_changed_at) for rule in rules}
    except StamphogGitHubError as e:
        if e.status_code != 403:
            raise
        logger.warning("stamphog_actions_attestations_forbidden", repository=repo)
        return {}
