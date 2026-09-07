import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'KeyFact',
	id: 'key-fact',
	name: 'KeyFact',
	phase: 2,

	role: "Visually prominent stat, formula, or date that anchors the section",

	cognitiveJob: "Anchor a critical fact",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"factMaxWords":20,"contextMaxWords":30},

	teachingIntent: 'explain',
	status: 'stable',
	sectionField: 'key_fact',
	shadcnPrimitive: "Card",
	generationHint:
		'Anchor a critical fact, formula, or equation. Use the formula field for any LaTeX expression that should be visually prominent.'
} satisfies LectioComponentPublicMetadata;

