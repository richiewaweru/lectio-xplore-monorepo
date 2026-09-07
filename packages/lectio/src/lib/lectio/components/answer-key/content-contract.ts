import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		label: {
			format: 'plain_text_short',
			description: 'Optional heading; defaults to "Answer key".',
			renderBehavior: 'Plain text heading.'
		},
		note: {
			format: 'plain_text',
			description: 'Optional standing note beneath the heading.',
			renderBehavior: 'Defaults to the standard indicative-not-conclusive diagnostic note.'
		},
		'entries[].question_number': {
			format: 'number',
			description: 'Source question number used for ordered-list numbering.'
		},
		'entries[].question': {
			format: 'plain_text',
			description: 'Full question stem repeated for standalone use.',
			renderBehavior: 'Plain text that wraps without truncation.'
		},
		'entries[].correct_key': {
			format: 'plain_text_short',
			description: 'Optional source option key such as "a".'
		},
		'entries[].correct_answer': {
			format: 'plain_text',
			description: 'Correct option text.'
		},
		'entries[].diagnostics[].option_text': {
			format: 'plain_text',
			description: 'Incorrect option text selected by a learner.'
		},
		'entries[].diagnostics[].misconception_id': {
			format: 'plain_text_short',
			description: 'Caller-supplied misconception id; Lectio does not interpret it.'
		},
		'entries[].diagnostics[].misconception_label': {
			format: 'plain_text',
			description: 'Human-readable misconception hypothesis.'
		}
	},
	componentConstraints: [
		'Use evidence language: chose "{option_text}" → consistent with: {misconception_label}.',
		'Never describe a diagnostic tag as a confirmed learner belief.',
		'Do not deduplicate repeated misconception ids; consumers own aggregation.'
	]
} satisfies LectioContentContract;
