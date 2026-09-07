import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'itemized',
	itemSelector: '.process-print-step',
	preferredWidth: 'full',
	hasMedia: false,
	requiresColorReset: false,
	fallback: 'All steps visible, checkbox squares for print'
} satisfies LectioPrintSpec;
