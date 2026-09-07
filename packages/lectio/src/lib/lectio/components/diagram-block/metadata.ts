import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'DiagramBlock',
	id: 'diagram-block',
	name: 'DiagramBlock',
	phase: 6,

	role: "Makes spatial or relational structure visible",

	cognitiveJob: "See the structure",
	subjects: ["universal"],
	behaviourModes: ['static', 'zoom', 'hint-toggle'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":true},
	capacity: {"calloutsMax":6,"captionMaxWords":60},

	teachingIntent: 'visualize',
	status: 'stable',
	sectionField: 'diagram',
	shadcnPrimitive: "Card + Dialog",
	generationHint:
		'Show a labelled diagram or image. Use description for extended figure text and figure_ref for sequential numbering (e.g. Figure 2.1).'
} satisfies LectioComponentPublicMetadata;

