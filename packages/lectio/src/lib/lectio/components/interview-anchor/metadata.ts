import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'InterviewAnchor',
	id: 'interview-anchor',
	name: 'InterviewAnchor',
	phase: 1,

	role: "Makes knowledge speakable - rehearse explaining the concept",

	cognitiveJob: "Make knowledge speakable",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"promptMaxWords":35,"audienceMaxWords":10,"followUpMaxWords":25},

	teachingIntent: 'reflect',
	status: 'stable',
	sectionField: 'interview',
	shadcnPrimitive: "Card"
} satisfies LectioComponentPublicMetadata;

