import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';
import type { BehaviourMode } from '$lib/schema/types';

export const metadata = {
	registryKey: 'DiagramSeries',
	id: 'diagram-series',
	name: 'DiagramSeries',
	phase: 6,

	role: "A progression of diagrams that tells a sequence",

	cognitiveJob: "Follow a visual progression",
	subjects: ["universal"],
	behaviourModes: ['step-reveal', 'static'] as const satisfies readonly BehaviourMode[],

	capabilities: {"acceptsMedia":false,"acceptsQuestions":false,"producesAnswerKey":false,"interactive":false,"isMedia":true},
	capacity: {"diagramsMax":4},

	teachingIntent: 'visualize',
	status: 'stable',
	sectionField: 'diagram_series',
	shadcnPrimitive: "Tabs or step nav",
	generationHint: "Write a series title that describes the full progression shown across all steps, and a caption for each step that names the specific state of the diagram at that moment ΓÇö what is drawn, what has changed from the previous step, and what the student should be able to see. Use present tense throughout. Each step caption must stand alone as a description of that frame: someone reading it knows exactly what that step shows. Max 60 words per caption. Do not repeat the step label as the caption."
} satisfies LectioComponentPublicMetadata;

