/**
 * Explicit Print / Learn path generation copy for Units preparation UI.
 * Paths are independent after the shared Teaching Plan — never converted.
 */

export const PATH_INDEPENDENCE_COPY =
	'Print and Learn are generated independently from the Teaching Plan.';

export type NativePathKind = 'print' | 'learn';

export function generatePathLabel(path: NativePathKind): string {
	return path === 'print' ? 'Generate Print' : 'Generate Learn';
}

export function openPathLabel(path: NativePathKind): string {
	return path === 'print' ? 'Open Print' : 'Open Learn';
}

export function pathHasRealization(
	status: {
		print_open_href?: string | null;
		learn_open_href?: string | null;
		print_output_id?: string | null;
		learn_output_id?: string | null;
		print_realization_id?: string | null;
		learn_realization_id?: string | null;
	} | null,
	path: NativePathKind
): boolean {
	if (!status) return false;
	if (path === 'print') {
		return Boolean(
			status.print_open_href || status.print_output_id || status.print_realization_id
		);
	}
	return Boolean(status.learn_open_href || status.learn_output_id || status.learn_realization_id);
}
