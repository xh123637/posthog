import { IconClock, IconTrends } from '@posthog/icons'
import {
    AlertDialog,
    AlertDialogClose,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
    Badge,
    Button,
    Card,
    CardContent,
    Text,
    Tooltip,
    TooltipContent,
    TooltipTrigger,
    cn,
} from '@posthog/quill'

import { quillBadgeVariant } from './quillBadgeVariant'
import { ReportCheckRowData } from './reportCheckPresentation'
import { reportCheckStopConfirmation } from './reportCheckStopConfirmation'
import { ReportCheckTiming } from './ReportCheckTiming'

/**
 * The quill sibling of `ReportCheckRow`. Stop confirms first, because a cancelled check is terminal.
 * It shows on hover with a fine pointer, and stays visible on touch so it has a tap path.
 */
export function QuillReportCheckRow({
    row,
    cancelling,
    onCancel,
}: {
    row: ReportCheckRowData
    cancelling: boolean
    onCancel: (checkId: string) => void
}): JSX.Element {
    const { check, reportStatus, tag, detail, cancelled, cancellable } = row
    const confirmation = reportCheckStopConfirmation(check)

    const title = (
        <Text
            size="xs"
            render={<span />}
            className={cn('min-w-0 flex-1 basis-32 leading-snug line-clamp-2', cancelled && 'line-through')}
        >
            {check.title}
        </Text>
    )

    return (
        <Card size="sm" className={cn('group', cancelled && 'opacity-60')}>
            <CardContent className="flex flex-col gap-1">
                <div className="flex min-w-0 flex-wrap items-start gap-2">
                    <span className="mt-0.5 shrink-0 text-subtle-foreground [&_svg]:size-3.5">
                        {check.kind === 'agent' ? <IconClock /> : <IconTrends />}
                    </span>
                    {check.rationale ? (
                        <Tooltip>
                            <TooltipTrigger render={title} />
                            <TooltipContent className="max-w-80">{check.rationale}</TooltipContent>
                        </Tooltip>
                    ) : (
                        title
                    )}
                    <Badge variant={quillBadgeVariant(tag.type)}>{tag.label}</Badge>
                </div>
                <div className="flex min-w-0 items-end gap-2 ps-5.5">
                    <Text size="xs" render={<span />} className="min-w-0 flex-1 leading-snug text-subtle-foreground">
                        <ReportCheckTiming check={check} reportStatus={reportStatus} detail={detail} />
                    </Text>
                    {cancellable && (
                        <AlertDialog>
                            <AlertDialogTrigger
                                render={
                                    <Button
                                        variant="destructive-outline"
                                        loading={cancelling}
                                        disabledReason={cancelling ? 'Stopping this check' : undefined}
                                        data-attr="signals-report-check-stop"
                                        className="shrink-0 transition-opacity pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100 pointer-fine:focus-visible:opacity-100"
                                    />
                                }
                            >
                                Stop
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                                <AlertDialogHeader>
                                    <AlertDialogTitle>{confirmation.title}</AlertDialogTitle>
                                    <AlertDialogDescription>{confirmation.description}</AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                    <AlertDialogClose render={<Button variant="outline" />}>
                                        {confirmation.dismissLabel}
                                    </AlertDialogClose>
                                    <AlertDialogClose
                                        render={<Button variant="destructive-outline" />}
                                        onClick={() => onCancel(check.id)}
                                    >
                                        {confirmation.confirmLabel}
                                    </AlertDialogClose>
                                </AlertDialogFooter>
                            </AlertDialogContent>
                        </AlertDialog>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
