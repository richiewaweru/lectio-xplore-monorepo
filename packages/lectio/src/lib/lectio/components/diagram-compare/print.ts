import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'atomic',
	preferredWidth: 'full',
	hasMedia: true,
	mediaConstraint: 'constrain-width',
	requiresColorReset: false,
	fallback: 'Both diagrams shown side by side'
} satisfies LectioPrintSpec;
