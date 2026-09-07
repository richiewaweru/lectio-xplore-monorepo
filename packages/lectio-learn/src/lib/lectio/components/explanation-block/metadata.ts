import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'ExplanationBlock',
	id: 'explanation-block',
	name: 'ExplanationBlock',
	phase: 1,

	role: "Sustained prose that builds a mental model",

	cognitiveJob: "Build understanding",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"bodyMaxWords":350,"emphasisMax":3},

	teachingIntent: 'explain',
	status: 'stable',
	sectionField: 'explanation',
	shadcnPrimitive: "Typography"
} satisfies LectioComponentPublicMetadata;

