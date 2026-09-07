import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'prose',
	preferredWidth: 'full',
	hasMedia: false,
	requiresColorReset: false,
	fallback: 'End card with next-lesson label and arrow'
} satisfies LectioPrintSpec;
