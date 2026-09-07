import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'atomic',
	preferredWidth: 'full',
	hasMedia: true,
	mediaConstraint: 'constrain-width',
	requiresColorReset: false,
	fallback: 'Static image from embedded data'
} satisfies LectioPrintSpec;
