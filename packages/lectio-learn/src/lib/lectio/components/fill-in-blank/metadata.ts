import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'FillInTheBlank',
	id: 'fill-in-blank',
	name: 'FillInTheBlank',
	phase: 4,

	role: "Cloze passage with student-completed blanks ΓÇö tests recall not recognition",

	cognitiveJob: "Retrieve and complete",
	subjects: ["universal"],
	behaviourModes: ['static', 'hint-toggle'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":true,"acceptsQuestions":true,"producesAnswerKey":true,"interactive":false,"isMedia":false},
	capacity: {"segmentsMax":60,"blanksMax":10,"wordBankMax":15},

	teachingIntent: 'practice',
	status: 'stable',
	sectionField: 'fill_in_blank',
	shadcnPrimitive: "Input inline"
} satisfies LectioComponentPublicMetadata;

