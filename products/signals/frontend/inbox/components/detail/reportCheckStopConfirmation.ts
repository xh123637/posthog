import type { SignalReportCheckApi } from 'products/signals/frontend/generated/api.schemas'

export interface ReportCheckStopConfirmation {
    title: string
    description: string
    confirmLabel: string
    dismissLabel: string
}

/** The confirmation that `ReportCheckRow` and its quill sibling show before a check is stopped. */
export function reportCheckStopConfirmation(check: Pick<SignalReportCheckApi, 'title'>): ReportCheckStopConfirmation {
    return {
        title: 'Stop this check?',
        description: `"${check.title}" will not run, and nothing will report back on it. Results it already recorded stay on this report.`,
        confirmLabel: 'Stop check',
        dismissLabel: 'Keep it',
    }
}
