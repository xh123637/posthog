import { getColorVar } from 'lib/colors'

import { TOPIC_COVERAGE_PARTS } from './topicCoverageParts'

export function TopicCoverageLegend(): JSX.Element {
    return (
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {TOPIC_COVERAGE_PARTS.map(({ key, label, colorVar }) => (
                <span key={key} className="inline-flex items-center gap-1.5">
                    <span
                        aria-hidden
                        className="inline-block size-2.5 shrink-0 rounded-sm"
                        // eslint-disable-next-line react/forbid-dom-props
                        style={{ backgroundColor: getColorVar(colorVar) }}
                    />
                    {label}
                </span>
            ))}
        </div>
    )
}
