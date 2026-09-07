import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'SimulationBlock',
	id: 'simulation-block',
	name: 'SimulationBlock',
	phase: 7,

	role: "Manipulate a variable and discover the concept through observation",

	cognitiveJob: "Manipulate and discover",
	subjects: ["mathematics","physics","chemistry","statistics"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":true,"isMedia":true},
	capacity: {"countGuidance":"template-defined"},

	teachingIntent: 'engage',
	status: 'beta',
	sectionField: 'simulation',
	shadcnPrimitive: "iframe sandbox"
} satisfies LectioComponentPublicMetadata;

