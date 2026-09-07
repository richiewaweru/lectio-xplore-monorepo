import { getComponentById, getComponentFieldMap } from '../schema/registry';

export type FieldInputType =
	| 'text'
	| 'textarea'
	| 'richtext'
	| 'number'
	| 'select'
	| 'list'
	| 'object-list'
	| 'boolean'
	| 'media'
	| 'svg'
	| 'hidden';

export interface FieldSchema {
	field: string;
	label: string;
	input: FieldInputType;
	required: boolean;
	placeholder?: string;
	maxWords?: number;
	maxItems?: number;
	options?: Array<{ value: string; label: string }>;
	itemSchema?: FieldSchema[];
	help?: string;
}

export interface EditSchema {
	component_id: string;
	fields: FieldSchema[];
}

function maxWordsFromCapacity(capacity: Record<string, number | string>, key: string): number | undefined {
	const v = capacity[key];
	return typeof v === 'number' ? v : undefined;
}

const hookHeroSchema: EditSchema = {
	component_id: 'hook-hero',
	fields: [
		{
			field: 'type',
			label: 'Hook style',
			input: 'select',
			required: true,
			options: [
				{ value: 'prose', label: 'Prose' },
				{ value: 'quote', label: 'Quote' },
				{ value: 'question', label: 'Question' },
				{ value: 'data-point', label: 'Data point' }
			]
		},
		{
			field: 'headline',
			label: 'Headline',
			input: 'text',
			required: true,
			placeholder: 'Short attention-grabbing headline',
			maxWords: 12
		},
		{
			field: 'body',
			label: 'Body',
			input: 'textarea',
			required: true,
			placeholder: 'Hook content',
			maxWords: 80
		},
		{
			field: 'anchor',
			label: 'Anchor concept',
			input: 'text',
			required: true,
			placeholder: 'Core concept this hook connects to'
		},
		{
			field: 'quote_attribution',
			label: 'Quote attribution',
			input: 'text',
			required: false,
			placeholder: 'Who said this (quote type only)'
		}
	]
};

const practiceStackSchema: EditSchema = {
	component_id: 'practice-stack',
	fields: [
		{
			field: 'problems',
			label: 'Problems',
			input: 'object-list',
			required: true,
			maxItems: 6,
			itemSchema: [
				{
					field: 'difficulty',
					label: 'Difficulty',
					input: 'select',
					required: true,
					options: [
						{ value: 'warm', label: 'Warm-up' },
						{ value: 'medium', label: 'Medium' },
						{ value: 'cold', label: 'Challenge' },
						{ value: 'extension', label: 'Extension' }
					]
				},
				{
					field: 'question',
					label: 'Question',
					input: 'textarea',
					required: true,
					placeholder: 'Problem statement',
					maxWords: 100
				},
				{
					field: 'hints',
					label: 'Hints',
					input: 'object-list',
					required: false,
					maxItems: 3,
					itemSchema: [
						{
							field: 'level',
							label: 'Level',
							input: 'select',
							required: true,
							options: [
								{ value: '1', label: 'Nudge' },
								{ value: '2', label: 'Guidance' },
								{ value: '3', label: 'Walkthrough' }
							]
						},
						{
							field: 'text',
							label: 'Hint text',
							input: 'textarea',
							required: true,
							maxWords: 60
						}
					]
				}
			]
		}
	]
};

const schemasById: Record<string, EditSchema> = {
	'section-header': {
		component_id: 'section-header',
		fields: [
			{ field: 'title', label: 'Title', input: 'text', required: true, maxWords: 12 },
			{ field: 'subtitle', label: 'Subtitle', input: 'text', required: false, maxWords: 20 },
			{ field: 'subject', label: 'Subject', input: 'text', required: true },
			{
				field: 'grade_band',
				label: 'Grade band',
				input: 'select',
				required: true,
				options: [
					{ value: 'primary', label: 'Primary' },
					{ value: 'secondary', label: 'Secondary' },
					{ value: 'advanced', label: 'Advanced' }
				]
			},
			{ field: 'objectives', label: 'Objectives', input: 'list', required: false, maxItems: 4 }
		]
	},
	'hook-hero': hookHeroSchema,
	'explanation-block': {
		component_id: 'explanation-block',
		fields: [
			{
				field: 'body',
				label: 'Body',
				input: 'textarea',
				required: true,
				maxWords: 350
			},
			{ field: 'emphasis', label: 'Key phrases', input: 'list', required: true, maxItems: 3 }
		]
	},
	'prerequisite-strip': {
		component_id: 'prerequisite-strip',
		fields: [
			{
				field: 'items',
				label: 'Prerequisites',
				input: 'object-list',
				required: true,
				maxItems: 4,
				itemSchema: [
					{ field: 'concept', label: 'Concept', input: 'text', required: true, maxWords: 8 },
					{ field: 'refresher', label: 'Refresher', input: 'textarea', required: false, maxWords: 60 }
				]
			}
		]
	},
	'what-next-bridge': {
		component_id: 'what-next-bridge',
		fields: [
			{ field: 'body', label: 'Body', input: 'textarea', required: true, maxWords: 50 },
			{ field: 'next', label: 'Next concept', input: 'text', required: true, maxWords: 15 },
			{ field: 'preview', label: 'Preview', input: 'textarea', required: false, maxWords: 30 }
		]
	},
	'interview-anchor': {
		component_id: 'interview-anchor',
		fields: [
			{ field: 'prompt', label: 'Prompt', input: 'textarea', required: true, maxWords: 35 },
			{ field: 'audience', label: 'Audience', input: 'text', required: true, maxWords: 10 },
			{ field: 'follow_up', label: 'Follow-up', input: 'textarea', required: false, maxWords: 25 }
		]
	},
	'callout-block': {
		component_id: 'callout-block',
		fields: [
			{
				field: 'variant',
				label: 'Variant',
				input: 'select',
				required: true,
				options: [
					{ value: 'info', label: 'Info' },
					{ value: 'tip', label: 'Tip' },
					{ value: 'warning', label: 'Warning' },
					{ value: 'exam-tip', label: 'Exam tip' },
					{ value: 'remember', label: 'Remember' }
				]
			},
			{ field: 'heading', label: 'Heading', input: 'text', required: false, maxWords: 6 },
			{ field: 'body', label: 'Body', input: 'textarea', required: true, maxWords: 60 }
		]
	},
	'summary-block': {
		component_id: 'summary-block',
		fields: [
			{ field: 'heading', label: 'Heading', input: 'text', required: false },
			{
				field: 'items',
				label: 'Takeaways',
				input: 'object-list',
				required: true,
				maxItems: 5,
				itemSchema: [{ field: 'text', label: 'Point', input: 'text', required: true, maxWords: 25 }]
			},
			{ field: 'closing', label: 'Closing', input: 'textarea', required: false, maxWords: 30 }
		]
	},
	'section-divider': {
		component_id: 'section-divider',
		fields: [{ field: 'label', label: 'Label', input: 'text', required: true, maxWords: 4 }]
	},
	'definition-card': {
		component_id: 'definition-card',
		fields: [
			{ field: 'term', label: 'Term', input: 'text', required: true },
			{ field: 'formal', label: 'Formal definition', input: 'textarea', required: true, maxWords: 80 },
			{ field: 'plain', label: 'Plain language', input: 'textarea', required: true, maxWords: 60 }
		]
	},
	'definition-family': {
		component_id: 'definition-family',
		fields: [
			{ field: 'family_title', label: 'Family title', input: 'text', required: true, maxWords: 10 },
			{ field: 'family_intro', label: 'Introduction', input: 'textarea', required: false, maxWords: 40 },
			{
				field: 'definitions',
				label: 'Definitions',
				input: 'object-list',
				required: true,
				maxItems: 6,
				itemSchema: [
					{ field: 'term', label: 'Term', input: 'text', required: true },
					{ field: 'formal', label: 'Formal definition', input: 'textarea', required: true, maxWords: 60 },
					{ field: 'plain', label: 'Plain language', input: 'textarea', required: true, maxWords: 40 }
				]
			}
		]
	},
	'glossary-rail': {
		component_id: 'glossary-rail',
		fields: [
			{
				field: 'terms',
				label: 'Terms',
				input: 'object-list',
				required: true,
				maxItems: 8,
				itemSchema: [
					{ field: 'term', label: 'Term', input: 'text', required: true },
					{ field: 'definition', label: 'Definition', input: 'textarea', required: true, maxWords: 30 }
				]
			}
		]
	},
	'insight-strip': {
		component_id: 'insight-strip',
		fields: [
			{
				field: 'cells',
				label: 'Cells',
				input: 'object-list',
				required: true,
				maxItems: 3,
				itemSchema: [
					{ field: 'label', label: 'Label', input: 'text', required: true, maxWords: 6 },
					{ field: 'value', label: 'Value', input: 'textarea', required: true },
					{ field: 'note', label: 'Note', input: 'textarea', required: false, maxWords: 20 }
				]
			}
		]
	},
	'key-fact': {
		component_id: 'key-fact',
		fields: [
			{ field: 'fact', label: 'Fact', input: 'text', required: true, maxWords: 20 },
			{ field: 'context', label: 'Context', input: 'textarea', required: false, maxWords: 30 }
		]
	},
	'comparison-grid': {
		component_id: 'comparison-grid',
		fields: [
			{ field: 'title', label: 'Title', input: 'text', required: true, maxWords: 10 },
			{ field: 'intro', label: 'Introduction', input: 'textarea', required: false, maxWords: 60 },
			{
				field: 'columns',
				label: 'Columns',
				input: 'object-list',
				required: true,
				maxItems: 5,
				itemSchema: [
					{ field: 'id', label: 'ID', input: 'text', required: true },
					{ field: 'title', label: 'Column heading', input: 'text', required: true, maxWords: 6 },
					{ field: 'summary', label: 'Summary', input: 'textarea', required: false, maxWords: 30 }
				]
			},
			{
				field: 'rows',
				label: 'Rows',
				input: 'object-list',
				required: true,
				maxItems: 8,
				itemSchema: [
					{ field: 'criterion', label: 'Row label', input: 'text', required: true, maxWords: 8 },
					{
						field: 'values',
						label: 'Cell values (one per column, in order)',
						input: 'object-list',
						required: true,
						itemSchema: [{ field: 'text', label: 'Value', input: 'text', required: true, maxWords: 20 }]
					},
					{ field: 'takeaway', label: 'Takeaway', input: 'text', required: false, maxWords: 15 }
				]
			},
			{ field: 'apply_prompt', label: 'Apply prompt', input: 'textarea', required: false, maxWords: 40 }
		]
	},
	'worked-example-card': {
		component_id: 'worked-example-card',
		fields: [
			{ field: 'title', label: 'Title', input: 'text', required: true },
			{ field: 'setup', label: 'Setup', input: 'textarea', required: true, maxWords: 60 },
			{
				field: 'steps',
				label: 'Steps',
				input: 'object-list',
				required: true,
				maxItems: 6,
				itemSchema: [
					{ field: 'label', label: 'Label', input: 'text', required: true, maxWords: 12 },
					{ field: 'content', label: 'Content', input: 'textarea', required: true, maxWords: 80 }
				]
			},
			{ field: 'conclusion', label: 'Conclusion', input: 'textarea', required: true, maxWords: 40 }
		]
	},
	'process-steps': {
		component_id: 'process-steps',
		fields: [
			{ field: 'title', label: 'Title', input: 'text', required: true },
			{
				field: 'steps',
				label: 'Steps',
				input: 'object-list',
				required: true,
				maxItems: 8,
				itemSchema: [
					{ field: 'number', label: 'Number', input: 'number', required: true },
					{ field: 'action', label: 'Action', input: 'text', required: true, maxWords: 15 },
					{ field: 'detail', label: 'Detail', input: 'textarea', required: true, maxWords: 60 }
				]
			}
		]
	},
	'practice-stack': practiceStackSchema,
	'quiz-check': {
		component_id: 'quiz-check',
		fields: [
			{ field: 'question', label: 'Question', input: 'textarea', required: true, maxWords: 60 },
			{
				field: 'options',
				label: 'Options',
				input: 'object-list',
				required: true,
				maxItems: 4,
				itemSchema: [
					{ field: 'text', label: 'Text', input: 'text', required: true, maxWords: 20 },
					{ field: 'correct', label: 'Correct', input: 'boolean', required: true },
					{ field: 'explanation', label: 'Explanation', input: 'textarea', required: true, maxWords: 40 }
				]
			},
			{ field: 'feedback_correct', label: 'Correct feedback', input: 'textarea', required: true, maxWords: 30 },
			{ field: 'feedback_incorrect', label: 'Incorrect feedback', input: 'textarea', required: true, maxWords: 30 }
		]
	},
	'answer-key': {
		component_id: 'answer-key',
		fields: [
			{ field: 'label', label: 'Label', input: 'text', required: false },
			{ field: 'note', label: 'Standing note', input: 'textarea', required: false },
			{
				field: 'entries',
				label: 'Questions',
				input: 'object-list',
				required: true,
				itemSchema: [
					{ field: 'question_number', label: 'Number', input: 'number', required: true },
					{ field: 'question', label: 'Question', input: 'textarea', required: true },
					{ field: 'correct_key', label: 'Correct option key', input: 'text', required: false },
					{ field: 'correct_answer', label: 'Correct answer', input: 'textarea', required: true },
					{
						field: 'diagnostics',
						label: 'Diagnostic distractors',
						input: 'object-list',
						required: false,
						itemSchema: [
							{ field: 'option_key', label: 'Option key', input: 'text', required: false },
							{ field: 'option_text', label: 'Option text', input: 'textarea', required: true },
							{
								field: 'misconception_id',
								label: 'Misconception id',
								input: 'text',
								required: true
							},
							{
								field: 'misconception_label',
								label: 'Misconception label',
								input: 'textarea',
								required: true
							}
						]
					}
				]
			}
		]
	},
	'reflection-prompt': {
		component_id: 'reflection-prompt',
		fields: [
			{ field: 'prompt', label: 'Prompt', input: 'textarea', required: true, maxWords: 40 },
			{
				field: 'type',
				label: 'Type',
				input: 'select',
				required: true,
				options: [
					{ value: 'open', label: 'Open' },
					{ value: 'pair-share', label: 'Pair share' },
					{ value: 'sentence-stem', label: 'Sentence stem' },
					{ value: 'timed', label: 'Timed' },
					{ value: 'connect', label: 'Connect' },
					{ value: 'predict', label: 'Predict' },
					{ value: 'transfer', label: 'Transfer' }
				]
			}
		]
	},
	'student-textbox': {
		component_id: 'student-textbox',
		fields: [
			{ field: 'prompt', label: 'Prompt', input: 'textarea', required: true, maxWords: 40 }
		]
	},
	'short-answer': {
		component_id: 'short-answer',
		fields: [
			{ field: 'question', label: 'Question', input: 'textarea', required: true, maxWords: 60 },
			{ field: 'marks', label: 'Marks', input: 'number', required: false }
		]
	},
	'fill-in-blank': {
		component_id: 'fill-in-blank',
		fields: [
			{
				field: 'instruction',
				label: 'Instruction to student',
				input: 'textarea',
				required: false,
				maxWords: 30
			},
			{
				field: 'segments',
				label: 'Sentence parts (alternate between text and blanks)',
				input: 'object-list',
				required: true,
				maxItems: 12,
				itemSchema: [
					{ field: 'text', label: 'Text (leave empty for blanks)', input: 'text', required: false },
					{ field: 'is_blank', label: 'This is a blank (student fills in)', input: 'boolean', required: true },
					{ field: 'answer', label: 'Correct answer (if blank)', input: 'text', required: false }
				]
			},
			{
				field: 'word_bank',
				label: 'Word bank (optional - shown to student as hints)',
				input: 'object-list',
				required: false,
				maxItems: 8,
				itemSchema: [
					{ field: 'word', label: 'Word', input: 'text', required: true }
				]
			}
		]
	},
	'pitfall-alert': {
		component_id: 'pitfall-alert',
		fields: [
			{ field: 'misconception', label: 'Misconception', input: 'text', required: true, maxWords: 20 },
			{ field: 'correction', label: 'Correction', input: 'textarea', required: true, maxWords: 80 },
			{ field: 'example', label: 'Example', input: 'textarea', required: false, maxWords: 40 }
		]
	},
	'diagram-block': {
		component_id: 'diagram-block',
		fields: [
			{ field: 'media_id', label: 'Image', input: 'media', required: false },
			{ field: 'image_url', label: 'Image URL (if no upload)', input: 'text', required: false },
			{ field: 'svg_content', label: 'SVG markup (advanced)', input: 'svg', required: false },
			{ field: 'caption', label: 'Caption', input: 'textarea', required: true, maxWords: 60 },
			{ field: 'alt_text', label: 'Alt text', input: 'textarea', required: true, maxWords: 80 },
			{
				field: 'width',
				label: 'Width',
				input: 'select',
				required: false,
				options: [
					{ value: 'full', label: 'Full width' },
					{ value: 'half', label: 'Half width' },
					{ value: 'third', label: 'Third width' }
				]
			}
		]
	},
	'diagram-compare': {
		component_id: 'diagram-compare',
		fields: [
			{ field: 'before_media_id', label: 'Before image', input: 'media', required: false },
			{ field: 'before_image_url', label: 'Before image URL', input: 'text', required: false },
			{ field: 'before_svg', label: 'Before SVG (advanced)', input: 'svg', required: false },
			{ field: 'before_label', label: 'Before label', input: 'text', required: true, maxWords: 6 },
			{ field: 'after_media_id', label: 'After image', input: 'media', required: false },
			{ field: 'after_image_url', label: 'After image URL', input: 'text', required: false },
			{ field: 'after_svg', label: 'After SVG (advanced)', input: 'svg', required: false },
			{ field: 'after_label', label: 'After label', input: 'text', required: true, maxWords: 6 },
			{ field: 'caption', label: 'Caption', input: 'textarea', required: true, maxWords: 60 },
			{ field: 'alt_text', label: 'Alt text', input: 'textarea', required: true }
		]
	},
	'diagram-series': {
		component_id: 'diagram-series',
		fields: [
			{ field: 'title', label: 'Title', input: 'text', required: true, maxWords: 10 },
			{
				field: 'diagrams',
				label: 'Diagrams',
				input: 'object-list',
				required: true,
				maxItems: 4,
				itemSchema: [
					{ field: 'media_id', label: 'Image', input: 'media', required: false },
					{ field: 'image_url', label: 'Image URL (if no upload)', input: 'text', required: false },
					{ field: 'svg_content', label: 'SVG markup (advanced)', input: 'svg', required: false },
					{ field: 'step_label', label: 'Step label', input: 'text', required: true, maxWords: 8 },
					{ field: 'caption', label: 'Caption', input: 'textarea', required: true, maxWords: 40 }
				]
			}
		]
	},
	'video-embed': {
		component_id: 'video-embed',
		fields: [
			{ field: 'media_id', label: 'Video', input: 'media', required: true, help: 'YouTube or Vimeo URL' },
			{ field: 'caption', label: 'Caption', input: 'textarea', required: false, maxWords: 40 },
			{ field: 'start_time', label: 'Start time (seconds)', input: 'number', required: false },
			{ field: 'end_time', label: 'End time (seconds)', input: 'number', required: false },
			{
				field: 'print_fallback',
				label: 'Print fallback',
				input: 'select',
				required: true,
				options: [
					{ value: 'thumbnail', label: 'Thumbnail' },
					{ value: 'qr-link', label: 'QR link' },
					{ value: 'hide', label: 'Hide' }
				]
			}
		]
	},
	'image-block': {
		component_id: 'image-block',
		fields: [
			{
				field: 'media_id',
				label: 'Image',
				input: 'media',
				required: true,
				help: 'Upload PNG, JPEG, WebP, or GIF (max 2 MB)'
			},
			{
				field: 'alt_text',
				label: 'Alt text (accessibility)',
				input: 'textarea',
				required: true,
				maxWords: 80,
				help: 'Describe the image for screen readers and learners who cannot see it.'
			},
			{ field: 'caption', label: 'Caption', input: 'textarea', required: false, maxWords: 40 },
			{
				field: 'width',
				label: 'Width',
				input: 'select',
				required: false,
				options: [
					{ value: 'full', label: 'Full width' },
					{ value: 'half', label: 'Half width' },
					{ value: 'third', label: 'Third width' }
				]
			},
			{
				field: 'alignment',
				label: 'Alignment',
				input: 'select',
				required: false,
				options: [
					{ value: 'left', label: 'Left' },
					{ value: 'center', label: 'Center' },
					{ value: 'right', label: 'Right' }
				]
			}
		]
	},
	'timeline-block': {
		component_id: 'timeline-block',
		fields: [
			{ field: 'title', label: 'Title', input: 'text', required: true, maxWords: 10 },
			{
				field: 'events',
				label: 'Events',
				input: 'object-list',
				required: true,
				maxItems: 8,
				itemSchema: [
					{ field: 'year', label: 'Year', input: 'text', required: true },
					{ field: 'title', label: 'Title', input: 'text', required: true, maxWords: 10 },
					{ field: 'summary', label: 'Summary', input: 'textarea', required: true, maxWords: 50 }
				]
			}
		]
	},
	'simulation-block': {
		component_id: 'simulation-block',
		fields: [
			{ field: 'spec', label: 'Interaction spec', input: 'hidden', required: true },
			{ field: 'html_content', label: 'HTML content', input: 'textarea', required: false },
			{ field: 'explanation', label: 'Explanation', input: 'textarea', required: false, maxWords: 60 }
		]
	}
};

/**
 * Merge registry capacity limits into schema maxWords where applicable.
 */
function enrichWithCapacity(schema: EditSchema): EditSchema {
	const meta = getComponentById(schema.component_id);
	if (!meta) return schema;
	const cap = meta.capacity;
	const fields = schema.fields.map((f) => {
		const wKey = `${f.field}MaxWords`;
		const mw = maxWordsFromCapacity(cap, wKey);
		if (mw !== undefined && f.maxWords === undefined) {
			return { ...f, maxWords: mw };
		}
		return f;
	});
	return { ...schema, fields };
}

/**
 * Edit schema for builder forms. Null when the component has no block field (e.g. glossary-inline).
 */
export function getEditSchema(componentId: string): EditSchema | null {
	const fieldMap = getComponentFieldMap();
	if (!fieldMap[componentId]) {
		return null;
	}
	const base = schemasById[componentId];
	if (!base) {
		return null;
	}
	return enrichWithCapacity(base);
}
