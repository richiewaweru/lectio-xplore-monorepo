import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'atomic',
	preferredWidth: 'full',
	hasMedia: false,
	requiresColorReset: false,
	fallback: 'Bordered warning box with icon and misconception/correction structure'
} satisfies LectioPrintSpec;
