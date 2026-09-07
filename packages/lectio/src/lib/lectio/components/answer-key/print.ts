import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'itemized',
	itemSelector: '.answer-key-entry',
	preferredWidth: 'full',
	hasMedia: false,
	requiresColorReset: true,
	fallback: 'Diagnostic answer list with grouped misconception evidence',
	notes: 'Starts on a fresh page; each question and its diagnostic rows stay together.'
} satisfies LectioPrintSpec;
