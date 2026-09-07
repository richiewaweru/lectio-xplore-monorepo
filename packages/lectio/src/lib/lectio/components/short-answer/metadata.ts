import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'ShortAnswerQuestion',
	id: 'short-answer',
	name: 'ShortAnswerQuestion',
	phase: 4,

	role: "Open question with write-in space and optional mark scheme",

	cognitiveJob: "Recall and explain in own words",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":true,"acceptsQuestions":true,"producesAnswerKey":true,"interactive":false,"isMedia":false},
	capacity: {"questionMaxWords":60,"linesMax":10,"marksMax":10},

	teachingIntent: 'practice',
	status: 'stable',
	sectionField: 'short_answer',
	shadcnPrimitive: "Card + Collapsible (mark scheme)"
} satisfies LectioComponentPublicMetadata;

