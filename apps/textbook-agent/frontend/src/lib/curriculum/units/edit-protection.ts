/**
 * Dirty edit protection: progress refresh must not clobber local drafts;
 * 409 conflicts preserve edits and expose reload/resolve (G21).
 */

import type { ReliabilityConflictState } from '$lib/types/reliability';

export interface LessonEditorDraft {
	title: string;
	objective: string;
	must_establish: string;
	exclusions: string;
}

export interface LessonServerSnapshot {
	title: string;
	objective: string;
	must_establish: string;
	exclusions: string;
	revision: number;
}

export function draftsEqual(a: LessonEditorDraft, b: LessonEditorDraft): boolean {
	return (
		a.title === b.title &&
		a.objective === b.objective &&
		a.must_establish === b.must_establish &&
		a.exclusions === b.exclusions
	);
}

export function snapshotToDraft(snapshot: LessonServerSnapshot): LessonEditorDraft {
	return {
		title: snapshot.title,
		objective: snapshot.objective,
		must_establish: snapshot.must_establish,
		exclusions: snapshot.exclusions
	};
}

export function isEditorDirty(draft: LessonEditorDraft, baseline: LessonEditorDraft | null): boolean {
	if (!baseline) return false;
	return !draftsEqual(draft, baseline);
}

/**
 * Apply a progress/status refresh. When the editor is dirty, keep the draft
 * and only return metadata that is safe to update (revision from server is
 * recorded but draft fields are unchanged).
 */
export function applyProgressRefreshWhileEditing(args: {
	dirty: boolean;
	draft: LessonEditorDraft;
	incoming: LessonServerSnapshot;
}): { draft: LessonEditorDraft; baseline: LessonEditorDraft | null; preserved: boolean } {
	if (args.dirty) {
		return { draft: args.draft, baseline: null, preserved: true };
	}
	const next = snapshotToDraft(args.incoming);
	return { draft: next, baseline: next, preserved: false };
}

export function conflictFrom409(args: {
	message: string;
	draft: LessonEditorDraft;
	localRevision: number | null;
	serverRevision: number | null;
}): ReliabilityConflictState {
	return {
		message: args.message,
		local_revision: args.localRevision,
		server_revision: args.serverRevision,
		local_draft: { ...args.draft }
	};
}

export type ConflictResolution = 'keep_editing' | 'reload_server';

export function resolveConflict(
	conflict: ReliabilityConflictState,
	choice: ConflictResolution,
	serverSnapshot: LessonServerSnapshot | null
): { draft: LessonEditorDraft; baseline: LessonEditorDraft | null; conflict: null } {
	if (choice === 'keep_editing') {
		return {
			draft: { ...conflict.local_draft },
			baseline: null,
			conflict: null
		};
	}
	if (serverSnapshot) {
		const next = snapshotToDraft(serverSnapshot);
		return { draft: next, baseline: next, conflict: null };
	}
	return {
		draft: { ...conflict.local_draft },
		baseline: null,
		conflict: null
	};
}
