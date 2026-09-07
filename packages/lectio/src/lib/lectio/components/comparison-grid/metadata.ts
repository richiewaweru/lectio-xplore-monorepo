import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'ComparisonGrid',
	id: 'comparison-grid',
	name: 'ComparisonGrid',
	phase: 2,

	role: "Holds multiple concepts in view so distinctions become structural",

	cognitiveJob: "Compare and classify in parallel",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"columnsMin":2,"columnsMax":4,"rowsMax":6,"criterionMaxWords":8,"valueMaxWords":20},

	teachingIntent: 'engage',
	status: 'stable',
	sectionField: 'comparison_grid',
	shadcnPrimitive: "CSS Grid + Card"
} satisfies LectioComponentPublicMetadata;

