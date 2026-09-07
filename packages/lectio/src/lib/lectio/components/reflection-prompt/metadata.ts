import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'ReflectionPrompt',
	id: 'reflection-prompt',
	name: 'ReflectionPrompt',
	phase: 4,

	role: "Pauses forward motion and turns attention inward",

	cognitiveJob: "Pause and consolidate",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":true,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"promptMaxWords":40,"spaceMax":6},

	teachingIntent: 'reflect',
	status: 'stable',
	sectionField: 'reflection',
	shadcnPrimitive: "Card"
} satisfies LectioComponentPublicMetadata;

