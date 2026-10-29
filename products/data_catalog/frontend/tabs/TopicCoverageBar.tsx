import { useMemo } from 'react'

import { ProportionBar } from '@posthog/quill-charts'
import type { Series } from '@posthog/quill-charts'

import { useChartTheme } from 'lib/charts/hooks'
import { getColorVar } from 'lib/colors'
import { pluralize } from 'lib/utils/strings'

import type { TopicCoverageApi } from '../generated/api.schemas'
import { TOPIC_COVERAGE_PARTS } from './topicCoverageParts'

function sessions(value: number): string {
    return pluralize(value, 'session')
}

export function TopicCoverageBar({ coverage }: { coverage: TopicCoverageApi }): JSX.Element {
    const theme = useChartTheme()
    const series = useMemo<Series[]>(
        () =>
            TOPIC_COVERAGE_PARTS.map(({ key, label, colorVar }) => ({
                key,
                label,
                data: [coverage[key]],
                color: getColorVar(colorVar),
            })),
        [coverage]
    )

    if (coverage.metric + coverage.table + coverage.nothing === 0) {
        return <span className="text-secondary text-xs">No session asked for a metric</span>
    }

    return (
        <div className="flex h-7 min-w-32 flex-col justify-center">
            <ProportionBar
                series={series}
                theme={theme}
                valueFormatter={sessions}
                config={{ barHeight: 12, barCornerRadius: 3, legend: { show: false } }}
            />
        </div>
    )
}
