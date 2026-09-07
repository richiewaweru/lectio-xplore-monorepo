import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'itemized',
	itemSelector: '.timeline-print-event',
	preferredWidth: 'full',
	hasMedia: false,
	requiresColorReset: false,
	fallback: 'Vertical event list'
} satisfies LectioPrintSpec;
