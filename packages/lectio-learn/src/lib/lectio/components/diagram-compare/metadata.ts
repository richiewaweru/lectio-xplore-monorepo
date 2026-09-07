import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'DiagramCompare',
	id: 'diagram-compare',
	name: 'DiagramCompare',
	phase: 6,

	role: "Before and after comparison with a drag slider",

	cognitiveJob: "See transformation",
	subjects: ["history","science","mathematics","geography"],
	behaviourModes: ['compare'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":true},
	capacity: {"captionMaxWords":60},

	teachingIntent: 'visualize',
	status: 'stable',
	sectionField: 'diagram_compare',
	shadcnPrimitive: "Slider",
	generationHint: "Write a caption that precisely names what is being compared, what is visible in each state, and exactly what changes between them ΓÇö name the specific element that transforms, not just that a change occurs. Use present tense. Max 60 words. The caption must describe both images as if the student cannot see the labels: name the before state, name the after state, name the difference."
} satisfies LectioComponentPublicMetadata;

