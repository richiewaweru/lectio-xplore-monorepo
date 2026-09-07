import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'InsightStrip',
	id: 'insight-strip',
	name: 'InsightStrip',
	phase: 2,

	role: "Side-by-side comparison of 2-3 related values or concepts",

	cognitiveJob: "Compare values simultaneously",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"cellsMax":3,"cellsMin":2,"cellLinesMax":2},

	teachingIntent: 'explain',
	status: 'stable',
	sectionField: 'insight_strip',
	shadcnPrimitive: "CSS Grid"
} satisfies LectioComponentPublicMetadata;

