import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'itemized',
	itemSelector: '.diagram-series-print-item',
	preferredWidth: 'full',
	hasMedia: true,
	mediaConstraint: 'constrain-height',
	requiresColorReset: false,
	fallback: 'All diagrams in sequence with step labels'
} satisfies LectioPrintSpec;
