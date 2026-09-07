import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'SummaryBlock',
	id: 'summary-block',
	name: 'SummaryBlock',
	phase: 1,

	role: "Lists what this section covered ΓÇö key takeaways as bullets",

	cognitiveJob: "Consolidate and close",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"itemsMin":2,"itemsMax":5,"itemMaxWords":25,"closingMaxWords":30},

	teachingIntent: 'structure',
	status: 'stable',
	sectionField: 'summary',
	shadcnPrimitive: "Card"
} satisfies LectioComponentPublicMetadata;

