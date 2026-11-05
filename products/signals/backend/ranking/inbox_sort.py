"""Resolve the `recommended` inbox sort to an arm, and give each row a merge key.

A multivariate flag keyed by the requesting user picks the arm. An arm is a ranker and a pill setting:

| Variant        | Ranker   | Pill |
|----------------|----------|------|
| `control`      | priority | no   |
| `pills`        | priority | yes  |
| `action_pills` | action   | yes  |

An unknown variant, or a flag that is off or fails to evaluate, gives `control`.

A head ranker sorts by the served score of its outcome, highest first, then in priority order. Unscored and stale
reports come after every scored report, in priority order. The merge key follows the same order, so a client can merge
rows from different state requests: `1 - score` for a scored report, `2 + priority rank` for an unscored report, and
the priority rank alone for the priority ranker.
"""

from typing import Literal, get_args

import structlog
import posthoganalytics

from posthog.dataclasses import frozen
from posthog.models.team import Team
from posthog.models.user import User

from products.signals.backend.models import AutonomyPriority
from products.signals.backend.ranking.public_outcomes import PublicOutcomeName

logger = structlog.get_logger(__name__)

RECOMMENDED_INBOX_SORT_FLAG = "signals-inbox-ranking-pills"

HeadRanker = PublicOutcomeName
InboxRanker = Literal["priority", HeadRanker]

HEAD_RANKERS: tuple[HeadRanker, ...] = get_args(HeadRanker)

PRIORITY_ORDERING = "priority,status,-updated_at"
RANKER_ORDERINGS: dict[InboxRanker, str] = {
    "priority": PRIORITY_ORDERING,
    **{head: f"-ranking_{head},{PRIORITY_ORDERING}" for head in HEAD_RANKERS},
}

_PRIORITY_SLOTS = len(AutonomyPriority.values) + 1
_UNSCORED_MERGE_KEY_BASE = 2.0


@frozen
class RecommendedArm:
    ranker: InboxRanker
    ranking_pill: bool


CONTROL_ARM = RecommendedArm(ranker="priority", ranking_pill=False)
RECOMMENDED_ARMS: dict[str, RecommendedArm] = {
    "control": CONTROL_ARM,
    "pills": RecommendedArm(ranker="priority", ranking_pill=True),
    "action_pills": RecommendedArm(ranker="action", ranking_pill=True),
}


def resolve_recommended_arm(team: Team, user: User, *, send_feature_flag_events: bool = True) -> RecommendedArm:
    """`send_feature_flag_events=False` reads the variant without an exposure, for a caller that does not show the inbox."""
    if not user.distinct_id:
        return CONTROL_ARM
    try:
        variant = posthoganalytics.get_feature_flag(
            RECOMMENDED_INBOX_SORT_FLAG,
            # Keyed by user so the exposure joins to the user's inbox events in the experiment.
            user.distinct_id,
            # The web and desktop clients register the project group by uuid, so all clients get the same variant.
            groups={"project": str(team.uuid)},
            group_properties={"project": {"id": team.id, "uuid": str(team.uuid)}},
            send_feature_flag_events=send_feature_flag_events,
        )
    except Exception:
        logger.exception("signals.inbox_sort.flag_failed", team_id=team.id, user_id=user.id)
        return CONTROL_ARM
    return RECOMMENDED_ARMS.get(variant, CONTROL_ARM) if isinstance(variant, str) else CONTROL_ARM


def _clamped_priority_rank(priority_rank: int | None) -> int:
    return _PRIORITY_SLOTS - 1 if priority_rank is None else min(max(priority_rank, 0), _PRIORITY_SLOTS - 1)


def inbox_merge_key(ranker: InboxRanker, score: float | None, priority_rank: int | None) -> float:
    """Lower keys rank first. For a head ranker, a report without a score sorts after every scored report."""
    priority = _clamped_priority_rank(priority_rank)
    if ranker == "priority":
        return float(priority)
    if score is None:
        return _UNSCORED_MERGE_KEY_BASE + priority
    return 1.0 - min(max(score, 0.0), 1.0)
