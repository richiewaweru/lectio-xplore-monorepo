import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'GlossaryRail',
	id: 'glossary-rail',
	name: 'GlossaryRail',
	phase: 2,

	role: "Vocabulary visible in peripheral field, updates by section",

	cognitiveJob: "Retrieve meaning without losing place",
	subjects: ["universal"],
	behaviourModes: ['sticky', 'drawer', 'inline-strip'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"termsMax":8,"termsWarning":6,"definitionMaxWords":30},

	teachingIntent: 'define',
	status: 'stable',
	sectionField: 'glossary',
	shadcnPrimitive: "Card + ScrollArea + Sheet"
} satisfies LectioComponentPublicMetadata;

