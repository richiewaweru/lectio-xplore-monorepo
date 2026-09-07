/**
 * Teacher-facing labels for the lesson builder palette.
 * Every component id in the registry must have an entry.
 */
export const TEACHER_LOOKUP: Record<string, { teacherLabel: string; teacherDescription: string }> = {
	'section-header': {
		teacherLabel: 'Section Header',
		teacherDescription: 'Sets the title, subject, and learning objectives for a section.'
	},
	'hook-hero': {
		teacherLabel: 'Opening Hook',
		teacherDescription: 'Grabs attention with a question, quote, or fact before the lesson begins.'
	},
	'explanation-block': {
		teacherLabel: 'Core Explanation',
		teacherDescription: 'Main teaching prose that builds understanding step by step.'
	},
	'prerequisite-strip': {
		teacherLabel: 'Prerequisites',
		teacherDescription: 'Lists assumed knowledge with optional refresher notes.'
	},
	'what-next-bridge': {
		teacherLabel: 'What Next',
		teacherDescription: 'Connects this section to the concept or topic that follows.'
	},
	'interview-anchor': {
		teacherLabel: 'Explain Out Loud',
		teacherDescription: 'Prompts learners to rehearse explaining the idea in their own words.'
	},
	'callout-block': {
		teacherLabel: 'Callout',
		teacherDescription: 'Highlighted tip, warning, exam note, or remembered point.'
	},
	'summary-block': {
		teacherLabel: 'Summary',
		teacherDescription: 'Bullet takeaways that close what the section covered.'
	},
	'section-divider': {
		teacherLabel: 'Section Divider',
		teacherDescription: 'Named visual break between parts within a lesson.'
	},
	'definition-card': {
		teacherLabel: 'Key Term Definition',
		teacherDescription: 'Introduces a term with formal and everyday language side by side.'
	},
	'definition-family': {
		teacherLabel: 'Definition Family',
		teacherDescription: 'Groups related terms that belong together conceptually.'
	},
	'glossary-rail': {
		teacherLabel: 'Glossary Rail',
		teacherDescription: 'Sidebar vocabulary that stays visible while reading.'
	},
	'glossary-inline': {
		teacherLabel: 'Inline Glossary',
		teacherDescription: 'Short in-text definition pop-up on a key term.'
	},
	'insight-strip': {
		teacherLabel: 'Insight Strip',
		teacherDescription: 'Side-by-side comparison of a few values or ideas.'
	},
	'key-fact': {
		teacherLabel: 'Key Fact',
		teacherDescription: 'Prominent stat, formula, or date that anchors the section.'
	},
	'comparison-grid': {
		teacherLabel: 'Comparison Table',
		teacherDescription: 'Compares concepts across shared criteria in a grid.'
	},
	'worked-example-card': {
		teacherLabel: 'Worked Example',
		teacherDescription: 'Walks through a problem step by step with clear reasoning.'
	},
	'process-steps': {
		teacherLabel: 'Process Steps',
		teacherDescription: 'Ordered procedure learners should follow every time.'
	},
	'practice-stack': {
		teacherLabel: 'Practice Problems',
		teacherDescription: 'Problems at varied difficulty with progressive hints.'
	},
	'quiz-check': {
		teacherLabel: 'Quick Check Quiz',
		teacherDescription: 'Short check-for-understanding with immediate feedback.'
	},
	'answer-key': {
		teacherLabel: 'Diagnostic Answer Key',
		teacherDescription: 'Lists correct answers and the misconceptions each distractor may reveal.'
	},
	'reflection-prompt': {
		teacherLabel: 'Reflection Prompt',
		teacherDescription: 'Open pause that encourages deeper thinking or sharing.'
	},
	'student-textbox': {
		teacherLabel: 'Student Textbox',
		teacherDescription: 'Simple write-in space tied to a short prompt.'
	},
	'short-answer': {
		teacherLabel: 'Short Answer',
		teacherDescription: 'Open question with lines for a written response.'
	},
	'fill-in-blank': {
		teacherLabel: 'Fill in the Blank',
		teacherDescription: 'Cloze passage with blanks for recall, not recognition only.'
	},
	'pitfall-alert': {
		teacherLabel: 'Common Mistake Alert',
		teacherDescription: 'Names a misconception and explains the correct idea.'
	},
	'diagram-block': {
		teacherLabel: 'Diagram',
		teacherDescription: 'Labelled visual with optional annotation callouts.'
	},
	'diagram-compare': {
		teacherLabel: 'Before / After Diagram',
		teacherDescription: 'Compares two diagrams with an interactive or static slider.'
	},
	'diagram-series': {
		teacherLabel: 'Diagram Series',
		teacherDescription: 'Sequence of diagrams that tells a visual story.'
	},
	'video-embed': {
		teacherLabel: 'Video',
		teacherDescription: 'Embed a YouTube or Vimeo video with a caption.'
	},
	'image-block': {
		teacherLabel: 'Image',
		teacherDescription: 'Photo, screenshot, or illustration from an uploaded image.'
	},
	'timeline-block': {
		teacherLabel: 'Timeline',
		teacherDescription: 'Chronological events with summaries along a spine.'
	},
	'simulation-block': {
		teacherLabel: 'Interactive Simulation',
		teacherDescription: 'Manipulable widget where learners discover by experimenting.'
	}
};

export function teacherFor(componentId: string): { teacherLabel: string; teacherDescription: string } {
	const t = TEACHER_LOOKUP[componentId];
	if (!t) {
		throw new Error(`[Lectio] Missing teacher-facing metadata for component id "${componentId}"`);
	}
	return t;
}
