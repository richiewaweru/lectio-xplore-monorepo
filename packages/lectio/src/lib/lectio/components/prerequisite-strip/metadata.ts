import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'PrerequisiteStrip',
	id: 'prerequisite-strip',
	name: 'PrerequisiteStrip',
	phase: 1,

	role: "Lists assumed knowledge with optional refresher pop-ups",

	cognitiveJob: "Activate prior knowledge",
	subjects: ["universal"],
	behaviourModes: ['static', 'hint-toggle'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"itemsMax":4},

	teachingIntent: 'structure',
	status: 'stable',
	sectionField: 'prerequisites',
	shadcnPrimitive: "Popover"
} satisfies LectioComponentPublicMetadata;

