import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'ImageBlock',
	id: 'image-block',
	name: 'ImageBlock',
	phase: 6,

	role: "Uploaded raster image with caption and layout options",

	cognitiveJob: "Illustrate with photos or screenshots",
	subjects: ["universal"],
	behaviourModes: ['static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":true},
	capacity: {"captionMaxWords":40,"altMaxWords":80},

	teachingIntent: 'visualize',
	status: 'stable',
	sectionField: 'image_block',
	shadcnPrimitive: "Card + img"
} satisfies LectioComponentPublicMetadata;

