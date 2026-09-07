import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'atomic',
	preferredWidth: 'aside',
	hasMedia: false,
	requiresColorReset: true,
	fallback: 'Bordered box; floats as aside when adjacent to explanation, full-width otherwise'
} satisfies LectioPrintSpec;
