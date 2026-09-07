import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'CalloutBlock',
	id: 'callout-block',
	name: 'CalloutBlock',
	phase: 1,

	role: "Standalone highlighted callout ΓÇö tip, warning, info, or exam note",

	cognitiveJob: "Flag what matters",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"bodyMaxWords":60,"headingMaxWords":6},

	teachingIntent: 'explain',
	status: 'stable',
	sectionField: 'callout',
	shadcnPrimitive: "Alert"
} satisfies LectioComponentPublicMetadata;

