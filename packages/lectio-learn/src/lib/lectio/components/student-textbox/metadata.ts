import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'StudentTextbox',
	id: 'student-textbox',
	name: 'StudentTextbox',
	phase: 4,

	role: "Simple write-in box for student responses ΓÇö no framing beyond a prompt",

	cognitiveJob: "Record thinking",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":true,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"promptMaxWords":40,"linesMax":10},

	teachingIntent: 'reflect',
	status: 'stable',
	sectionField: 'student_textbox',
	shadcnPrimitive: "Textarea (print: lined box)"
} satisfies LectioComponentPublicMetadata;

