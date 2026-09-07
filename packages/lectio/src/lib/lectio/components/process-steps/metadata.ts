import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'ProcessSteps',
	id: 'process-steps',
	name: 'ProcessSteps',
	phase: 3,

	role: "A repeatable procedure where order is non-negotiable",

	cognitiveJob: "Follow a procedure",
	subjects: ["universal"],
	behaviourModes: ['static', 'step-reveal'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"stepsMax":8,"actionMaxWords":15,"detailMaxWords":60},

	teachingIntent: 'show-how',
	status: 'stable',
	sectionField: 'process',
	shadcnPrimitive: "Card + Separator"
} satisfies LectioComponentPublicMetadata;

