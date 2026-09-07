import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'itemized',
	itemSelector: '.worked-step-print',
	preferredWidth: 'full',
	hasMedia: false,
	requiresColorReset: false,
	fallback: 'Bordered card with numbered step indicators, all steps expanded'
} satisfies LectioPrintSpec;
