import { useActions, useValues } from 'kea'

import { IconCalendar } from '@posthog/icons'
import { LemonSelect } from '@posthog/lemon-ui'

import { INBOX_CREATED_WINDOW_OPTIONS, INBOX_PRIORITY_OPTIONS, inboxPriorityFilterLabel } from '../../filterOptions'
import { InboxCreatedWindow, inboxFiltersLogic } from '../../logics/inboxFiltersLogic'
import { SignalReportPriority } from '../../types'
import { InboxPriorityDot } from './InboxPriorityDot'
import { InboxSourceFilter } from './InboxSourceFilter'
import { InboxStateFilter } from './InboxStateFilter'
import { INBOX_ANY_TIME_LABEL, inboxCreatedWindowLabel, inboxPriorityOptionLabel } from './inboxToolbarOptions'

const ALL_PRIORITIES = null

const PRIORITY_SELECT_OPTIONS = [
    { value: ALL_PRIORITIES, label: inboxPriorityFilterLabel([]) },
    ...INBOX_PRIORITY_OPTIONS.map((priority) => ({
        value: priority,
        label: inboxPriorityOptionLabel(priority),
        icon: <InboxPriorityDot priority={priority} />,
    })),
]

const ANY_TIME = null
const CREATED_WINDOW_SELECT_OPTIONS: { value: InboxCreatedWindow | null; label: string }[] = [
    { value: ANY_TIME, label: INBOX_ANY_TIME_LABEL },
    ...INBOX_CREATED_WINDOW_OPTIONS.map(({ value, label }) => ({ value, label })),
]

function PanelField({ label, children }: { label: string; children: JSX.Element }): JSX.Element {
    return (
        <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-secondary">{label}</span>
            {children}
        </div>
    )
}

/**
 * What narrows the report list: report state, then priority, then the created-in window, then source.
 * Filter state is persisted via `inboxFiltersLogic`, and the list reloads on change.
 *
 * Source goes last because its label grows with the selected scout name. Anywhere earlier, a long name
 * pushes the controls after it to the right.
 *
 * Sort and reviewer scope are deliberately not here. Sort orders the list rather than narrowing it,
 * and scope picks whose inbox this is, so both sit after a divider at the end of the row.
 */
export function InboxReportFilters({ layout = 'row' }: { layout?: 'row' | 'panel' }): JSX.Element {
    const { priorityFilter, timeWindowAvailable, createdWindow, sourceFilterAvailable } = useValues(inboxFiltersLogic)
    const { setPriorityFilter, setCreatedWindow } = useActions(inboxFiltersLogic)
    const panel = layout === 'panel'
    const field = (label: string, control: JSX.Element): JSX.Element =>
        panel ? <PanelField label={label}>{control}</PanelField> : control

    return (
        <div className={panel ? 'flex flex-col gap-2' : 'flex flex-wrap items-center gap-2'}>
            {field('Status', <InboxStateFilter />)}
            {field(
                'Priority',
                <LemonSelect
                    size="small"
                    value={priorityFilter.length === 1 ? priorityFilter[0] : ALL_PRIORITIES}
                    onChange={(priority) => setPriorityFilter(priority ? [priority as SignalReportPriority] : [])}
                    options={PRIORITY_SELECT_OPTIONS}
                    // A shared link can carry several priorities, which no single option represents.
                    // Read the selection out of the filter itself so the button never understates it.
                    renderButtonContent={() => inboxPriorityFilterLabel(priorityFilter)}
                    data-attr="inbox-filter-priority"
                />
            )}
            {timeWindowAvailable &&
                field(
                    'Created',
                    <LemonSelect
                        size="small"
                        value={createdWindow}
                        onChange={(window) => setCreatedWindow(window)}
                        options={CREATED_WINDOW_SELECT_OPTIONS}
                        icon={<IconCalendar />}
                        tooltip={panel ? undefined : `Created: ${inboxCreatedWindowLabel(createdWindow)}`}
                        // The window value ("7d") doubles as the short label in a narrow container.
                        renderButtonContent={(leaf) =>
                            panel ? (
                                (leaf?.label ?? INBOX_ANY_TIME_LABEL)
                            ) : (
                                <>
                                    <span className="@2xl:hidden">{leaf?.value ?? INBOX_ANY_TIME_LABEL}</span>
                                    <span className="hidden @2xl:inline">{leaf?.label ?? INBOX_ANY_TIME_LABEL}</span>
                                </>
                            )
                        }
                        data-attr="inbox-filter-created-window"
                    />
                )}
            {sourceFilterAvailable && field('Source', <InboxSourceFilter />)}
        </div>
    )
}
