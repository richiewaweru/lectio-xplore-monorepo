import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'TimelineBlock',
	id: 'timeline-block',
	name: 'TimelineBlock',
	phase: 6,

	role: "Turns chronology into a readable instructional spine",

	cognitiveJob: "Follow cause and sequence over time",
	subjects: ["history","science","universal"],
	behaviourModes: ['static', 'timeline-scrubber'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":true},
	capacity: {"eventsMin":3,"eventsMax":8,"titleMaxWords":10,"summaryMaxWords":50},

	teachingIntent: 'visualize',
	status: 'stable',
	sectionField: 'timeline',
	shadcnPrimitive: "Card + Button"
} satisfies LectioComponentPublicMetadata;

