import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'atomic',
	preferredWidth: 'full',
	hasMedia: true,
	mediaConstraint: 'constrain-height',
	requiresColorReset: true,
	fallback:
		'Image above headline when present; pull quote block with left border when text-only'
} satisfies LectioPrintSpec;
