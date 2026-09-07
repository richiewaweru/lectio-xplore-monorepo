import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'SectionDivider',
	id: 'section-divider',
	name: 'SectionDivider',
	phase: 1,

	role: "Named visual break between parts within a section",

	cognitiveJob: "Signal a phase change",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"labelMaxWords":4},

	teachingIntent: 'structure',
	status: 'stable',
	sectionField: 'divider',
	shadcnPrimitive: "Separator"
} satisfies LectioComponentPublicMetadata;

