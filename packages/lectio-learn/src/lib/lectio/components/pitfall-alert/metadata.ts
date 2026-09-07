import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'PitfallAlert',
	id: 'pitfall-alert',
	name: 'PitfallAlert',
	phase: 5,

	role: "Names a specific misconception before the learner makes it",

	cognitiveJob: "Inoculate against error",
	subjects: ["universal"],
	behaviourModes: ['static', 'hint-toggle'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"misconceptionMaxWords":20,"correctionMaxWords":80,"exampleMaxWords":40},

	teachingIntent: 'warn',
	status: 'stable',
	sectionField: 'pitfall',
	shadcnPrimitive: "Alert + Collapsible"
} satisfies LectioComponentPublicMetadata;

