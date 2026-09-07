import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'itemized',
	itemSelector: '.practice-print-problem',
	preferredWidth: 'full',
	hasMedia: false,
	requiresColorReset: false,
	fallback: 'All visible, write-in lines rendered; inline answers hidden by default'
} satisfies LectioPrintSpec;
