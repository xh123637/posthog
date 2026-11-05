import json
from datetime import datetime

from django.db import migrations, transaction

BATCH_SIZE = 500
PRIORITIES = ["P0", "P1", "P2", "P3", "P4"]
PUBLIC_HEADS = {
    "open": ("ranking_open_score", "ranking_open_lift"),
    "action": ("ranking_action_score", "ranking_action_lift"),
    "fixed": ("ranking_fix_score", "ranking_fix_lift"),
}
RANKING_FIELDS = ["ranking_scores", *[field for fields in PUBLIC_HEADS.values() for field in fields]]


def _parse_datetime(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _numbers(value):
    if not isinstance(value, dict):
        return {}
    return {
        key: float(number)
        for key, number in value.items()
        if isinstance(key, str) and isinstance(number, (int, float)) and not isinstance(number, bool)
    }


def _ranking_values(content, latest_edit_at):
    values = dict.fromkeys(RANKING_FIELDS)
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return values
    if not isinstance(parsed, dict):
        return values
    read_at_value = parsed.get("embedding_inserted_at")
    if read_at_value is None:
        read_at_value = parsed.get("scored_at")
    read_at = _parse_datetime(read_at_value)
    if read_at is not None and latest_edit_at is not None and latest_edit_at > read_at:
        return values
    served_key = parsed.get("served_key")
    results = parsed.get("results")
    served = results.get(served_key) if isinstance(results, dict) and isinstance(served_key, str) else None
    if not isinstance(served, dict):
        return values
    scores = _numbers(served.get("scores"))
    lifts = _numbers(served.get("lifts"))
    values["ranking_scores"] = scores or None
    for head, (score_field, lift_field) in PUBLIC_HEADS.items():
        values[score_field] = scores.get(head)
        values[lift_field] = lifts.get(head)
    return values


def backfill_signalreport_inbox_sort_cache(apps, schema_editor):
    SignalReport = apps.get_model("signals", "SignalReport")
    SignalReportArtefact = apps.get_model("signals", "SignalReportArtefact")
    cursor = None
    while True:
        with transaction.atomic():
            # A concurrent receiver waits for this lock, then writes the newest cache after this batch commits.
            page = SignalReport.objects.select_for_update(no_key=True).order_by("id")
            if cursor is not None:
                page = page.filter(id__gt=cursor)
            reports = list(page[:BATCH_SIZE])
            if not reports:
                return
            cursor = reports[-1].id
            report_ids = [report.id for report in reports]
            latest_by_type = {
                (report_id, artefact_type): content
                for report_id, content, artefact_type in SignalReportArtefact.objects.filter(
                    report_id__in=report_ids, type__in=["priority_judgment", "ranking_score"]
                )
                .order_by("report_id", "type", "-created_at", "-id")
                .distinct("report_id", "type")
                .values_list("report_id", "content", "type")
            }
            latest_edit_ats = dict(
                SignalReportArtefact.objects.filter(
                    report_id__in=report_ids, type__in=["title_change", "summary_change"]
                )
                .order_by("report_id", "-created_at", "-id")
                .distinct("report_id")
                .values_list("report_id", "created_at")
            )
            for report in reports:
                priority_content = latest_by_type.get((report.id, "priority_judgment"))
                priority = None
                if priority_content is not None:
                    try:
                        priority_data = json.loads(priority_content)
                        priority = priority_data.get("priority") if isinstance(priority_data, dict) else None
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                report.priority_sort_rank = PRIORITIES.index(priority) if priority in PRIORITIES else len(PRIORITIES)
                ranking = _ranking_values(
                    latest_by_type.get((report.id, "ranking_score")), latest_edit_ats.get(report.id)
                )
                for field, value in ranking.items():
                    setattr(report, field, value)
            SignalReport.objects.bulk_update(reports, ["priority_sort_rank", *RANKING_FIELDS], batch_size=BATCH_SIZE)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("signals", "0235_signalreport_priority_sort_rank_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_signalreport_inbox_sort_cache, migrations.RunPython.noop, elidable=True),
    ]
