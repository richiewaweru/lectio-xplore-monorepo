import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'DefinitionCard',
	id: 'definition-card',
	name: 'DefinitionCard',
	phase: 2,

	role: "Anchors a formal term with formal and plain versions",

	cognitiveJob: "Anchor formal knowledge",
	subjects: ["universal"],
	behaviourModes: ['static', 'plain-formal-toggle'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"formalMaxWords":80,"plainMaxWords":60,"relatedTermsMax":3},

	teachingIntent: 'define',
	status: 'stable',
	sectionField: 'definition',
	shadcnPrimitive: "Card + Collapsible"
} satisfies LectioComponentPublicMetadata;

