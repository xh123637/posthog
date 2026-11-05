import { ok } from '~/ingestion/framework/results'
import { ProcessingStep } from '~/ingestion/framework/steps'
import { PluginEvent } from '~/plugin-scaffold'

const AI_EVENT_BYTES_PROPERTY = '$ai_event_bytes'

type StampAiEventBytesInput = {
    normalizedEvent: PluginEvent
    eventBytes: number
}

/**
 * Size pricing bills from `$ai_event_bytes`, so it must be the size we measured, never a value the
 * client or a Hog transformation set. Keep it after the Hog transformation: no later step writes
 * arbitrary property keys.
 */
export function createStampAiEventBytesStep<TInput extends StampAiEventBytesInput>(): ProcessingStep<TInput, TInput> {
    return function stampAiEventBytesStep(input) {
        const { normalizedEvent, eventBytes } = input
        return Promise.resolve(
            ok({
                ...input,
                normalizedEvent: {
                    ...normalizedEvent,
                    properties: { ...normalizedEvent.properties, [AI_EVENT_BYTES_PROPERTY]: eventBytes },
                },
            })
        )
    }
}
