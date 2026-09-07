import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'SectionHeader',
	id: 'section-header',
	name: 'SectionHeader',
	phase: 1,

	role: "Opens a section with title, subject, objective, and level indicators",

	cognitiveJob: "Orient the learner",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"titleMaxWords":12,"subtitleMaxWords":20,"objectiveMaxWords":30},

	teachingIntent: 'structure',
	status: 'stable',
	sectionField: 'header',
	shadcnPrimitive: "Badge (for level pills)"
} satisfies LectioComponentPublicMetadata;

