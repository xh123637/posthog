import type { UncoveredGroupApi, UsageSnapshotPayloadApi } from './generated/api.schemas'
import { buildProposedRows, proposedRowPrefill } from './proposedRows'

function group(digest: string, overrides: Partial<UncoveredGroupApi> = {}): UncoveredGroupApi {
    return {
        fingerprint_digest: digest,
        measure: `measure ${digest}`,
        outcome: 'uncovered',
        matched_metric_id: null,
        matched_metric_status: null,
        distinct_people: 2,
        views: 0,
        active_days: 3,
        built: 4,
        scout_runs: 0,
        sample_sql: `SELECT ${digest}`,
        draft_name: null,
        draft_description: null,
        draft_definition: null,
        ...overrides,
    }
}

const PROPOSAL = {
    name: 'user_signups',
    description: 'Counts signups.',
    definition: 'SELECT count() FROM events',
    measures: 2,
    people: 9,
    views: 12,
    active_days: 5,
    built: 40,
    charts: [],
    other_charts: 0,
    surfaces: [],
    agents: null,
}

const PAYLOAD: UsageSnapshotPayloadApi = {
    metric_runs: null,
    adjusted_runs: null,
    unchecked_queries: 0,
    topics: null,
    topic_sessions: null,
    table_sources: null,
    uncovered: [
        group('a', { draft_name: 'user_signups', scout_runs: 7 }),
        group('b', { draft_name: 'user_signups', scout_runs: 3 }),
        group('c', { distinct_people: 20 }),
        group('d', { distinct_people: 0, built: 0, scout_runs: 50 }),
        group('e', { draft_name: 'orphan_draft', draft_definition: 'SELECT orphan', distinct_people: 1 }),
        group('f', { outcome: 'covered', distinct_people: 30 }),
        group('g', { outcome: 'slice', matched_metric_id: 'metric-1', distinct_people: 15 }),
        group('h', { distinct_people: 0, views: 5, built: 1 }),
    ],
    proposed_metrics: [PROPOSAL],
    failed_sections: [],
}

describe('proposedRows', () => {
    it('merges drafted measures into their proposal, leaves out covered measures and ranks by people', () => {
        const rows = buildProposedRows(PAYLOAD, false)

        expect(rows.map((row) => [row.name ?? row.measure, row.people, row.built, row.viewed])).toEqual([
            ['measure c', 20, 4, 0],
            ['measure g', 15, 4, 0],
            ['user_signups', 9, 40, 12],
            ['orphan_draft', 1, 4, 0],
            ['measure h', 0, 1, 5],
        ])
        expect(rows.find((row) => row.measure === 'measure g')?.matchedMetricId).toBe('metric-1')
    })

    it('adds scout runs and scout-only measures only when scouts are on', () => {
        const rows = buildProposedRows(PAYLOAD, true)

        const signups = rows.find((row) => row.name === 'user_signups')
        const scoutOnly = rows.find((row) => row.measure === 'measure d')
        expect([signups?.built, signups?.viewed]).toEqual([47, 19])
        expect([scoutOnly?.built, scoutOnly?.viewed]).toEqual([50, 50])
    })

    it('shows the rows from an older scan that has no proposals section', () => {
        const rows = buildProposedRows({ ...PAYLOAD, proposed_metrics: null }, false)

        expect(rows.map((row) => row.name ?? row.measure)).toEqual([
            'measure c',
            'measure g',
            'user_signups',
            'user_signups',
            'orphan_draft',
            'measure h',
        ])
    })

    it.each([
        [
            'a draft fills the whole form',
            { ...buildProposedRows(PAYLOAD, false)[2] },
            {
                display_name: 'User signups',
                name: 'user_signups',
                description: 'Counts signups.',
                sql: 'SELECT count() FROM events',
            },
        ],
        [
            'a measure with no draft fills only the query',
            { ...buildProposedRows(PAYLOAD, false)[0] },
            { display_name: '', name: '', description: '', sql: 'SELECT c' },
        ],
    ])('prefills the new metric form: %s', (_name, row, expected) => {
        expect(proposedRowPrefill(row)).toEqual(expected)
    })
})
