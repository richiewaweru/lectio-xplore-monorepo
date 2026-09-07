import type { LectioPrintSpec } from '$lib/lectio/core/types';

export const print = {
	breakBehavior: 'prose',
	preferredWidth: 'content-fit',
	hasMedia: false,
	requiresColorReset: false,
	fallback: 'Term underlined, definition in footnote'
} satisfies LectioPrintSpec;
