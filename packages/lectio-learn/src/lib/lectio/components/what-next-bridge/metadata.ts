import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'WhatNextBridge',
	id: 'what-next-bridge',
	name: 'WhatNextBridge',
	phase: 1,

	role: "Connects the section forward to what the concept enables",

	cognitiveJob: "Connect forward",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":false},
	capacity: {"bodyMaxWords":50,"nextMaxWords":15,"previewMaxWords":30},

	teachingIntent: 'structure',
	status: 'stable',
	sectionField: 'what_next',
	shadcnPrimitive: "Card"
} satisfies LectioComponentPublicMetadata;

