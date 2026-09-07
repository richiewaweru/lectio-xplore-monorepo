import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'DefinitionFamily',
	id: 'definition-family',
	name: 'DefinitionFamily',
	phase: 2,

	role: "Groups related terms that belong together conceptually",

	cognitiveJob: "Distinguish related concepts",
	subjects: ["universal"],
	behaviourModes: ['static', 'accordion'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"definitionsMax":4,"introMaxWords":40},

	teachingIntent: 'define',
	status: 'stable',
	sectionField: 'definition_family',
	shadcnPrimitive: "Card + Accordion"
} satisfies LectioComponentPublicMetadata;

