import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'GlossaryInline',
	id: 'glossary-inline',
	name: 'GlossaryInline',
	phase: 2,

	role: "In-text definition pop-up on a defined term",

	cognitiveJob: "Retrieve meaning in context",
	subjects: ["universal"],
	behaviourModes: ['hint-toggle'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"definitionMaxWords":30},

	teachingIntent: 'define',
	status: 'stable',
	sectionField: null,
	shadcnPrimitive: "Popover"
} satisfies LectioComponentPublicMetadata;

