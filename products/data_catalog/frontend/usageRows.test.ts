import type { AdjustedRunApi, UsageSnapshotPayloadApi } from './generated/api.schemas'
import { buildSourceRows } from './usageRows'

function adjusted(metricId: string, outcome: AdjustedRunApi['fetch_outcome'], isScout: boolean): AdjustedRunApi {
    return {
        metric_id: metricId,
        fetch_outcome: outcome,
        relation: 'serves',
        intent: 'weekly signups',
        sql: 'select count() from events',
        reasoning: 'Same measure.',
        occurred_at: '2026-10-20T12:00:00Z',
        session_id: null,
        is_scout: isScout,
    }
}

const PAYLOAD: UsageSnapshotPayloadApi = {
    metric_runs: [
        {
            metric_id: 'm1',
            direct_runs: { web: 3, mcp: 5 },
            direct_people: 4,
            scout_runs: 120,
            source_insight_dashboard_runs: 0,
            source_insight_insight_runs: 0,
        },
    ],
    adjusted_runs: [adjusted('m1', 'adapted', false), adjusted('m2', 'missed', false)],
    unchecked_queries: 0,
    topics: null,
    topic_sessions: null,
    table_sources: [{ name: 'revenue_daily', sessions: 2, people: 5 }],
    uncovered: null,
    proposed_metrics: null,
    failed_sections: [],
}

describe('buildSourceRows', () => {
    it.each([
        [
            false,
            8,
            [
                ['mcp', 5],
                ['web', 3],
            ],
        ],
        [
            true,
            128,
            [
                ['scouts', 120],
                ['mcp', 5],
                ['web', 3],
            ],
        ],
    ])(
        'ranks tables and metrics by people, and leaves out metrics with no run (scouts %s)',
        (includeScouts, uses, surfaces) => {
            const rows = buildSourceRows(PAYLOAD, { m1: 'Signups' }, includeScouts as boolean)

            expect(rows).toEqual([
                { key: 'table-revenue_daily', kind: 'table', name: 'revenue_daily', uses: 2, people: 5, surfaces: [] },
                { key: 'metric-m1', kind: 'metric', name: 'Signups', uses, people: 4, surfaces },
            ])
        }
    )

    it('keeps the top tables ahead of metrics that reach more people', () => {
        const metricRun = (
            index: number
        ): UsageSnapshotPayloadApi['metric_runs'] extends (infer T)[] | null ? T : never => ({
            ...PAYLOAD.metric_runs![0],
            metric_id: `m${index}`,
            direct_people: 50 - index,
        })
        const rows = buildSourceRows(
            {
                ...PAYLOAD,
                metric_runs: [1, 2, 3, 4, 5].map(metricRun),
                table_sources: [
                    { name: 'small_a', sessions: 2, people: 2 },
                    { name: 'small_b', sessions: 1, people: 1 },
                ],
            },
            {},
            false
        )

        expect(rows.slice(0, 5).map((row) => row.name)).toEqual(['m1', 'm2', 'm3', 'small_a', 'small_b'])
        expect(rows.slice(5).map((row) => row.name)).toEqual(['m4', 'm5'])
    })
})
