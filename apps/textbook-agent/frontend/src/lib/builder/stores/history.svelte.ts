import type { LessonDocument } from 'lectio';

function cloneDoc(doc: LessonDocument): LessonDocument {
	return JSON.parse(JSON.stringify(doc)) as LessonDocument;
}

/**
 * Undo/redo stack that stores LessonDocument snapshots.
 *
 * Design: snapshot-based, not command-based.
 * Each mutation pushes the *previous* document state onto the undo stack.
 * Undo pops from undo → pushes current to redo → restores popped.
 *
 * Max stack depth: 50 (configurable). Older entries are discarded.
 */
export function createHistoryStore(maxDepth = 50) {
	let undoStack = $state<LessonDocument[]>([]);
	let redoStack = $state<LessonDocument[]>([]);

	function pushBeforeMutation(snapshot: LessonDocument): void {
		const next = [...undoStack, cloneDoc(snapshot)];
		undoStack = next.length > maxDepth ? next.slice(-maxDepth) : next;
		redoStack = [];
	}

	function undo(current: LessonDocument): LessonDocument | null {
		if (undoStack.length === 0) return null;
		const prev = undoStack[undoStack.length - 1]!;
		undoStack = undoStack.slice(0, -1);
		redoStack = [...redoStack, cloneDoc(current)];
		return cloneDoc(prev);
	}

	function redo(current: LessonDocument): LessonDocument | null {
		if (redoStack.length === 0) return null;
		const next = redoStack[redoStack.length - 1]!;
		redoStack = redoStack.slice(0, -1);
		const u = [...undoStack, cloneDoc(current)];
		undoStack = u.length > maxDepth ? u.slice(-maxDepth) : u;
		return cloneDoc(next);
	}

	function clear(): void {
		undoStack = [];
		redoStack = [];
	}

	return {
		pushBeforeMutation,
		undo,
		redo,
		clear,
		get canUndo() {
			return undoStack.length > 0;
		},
		get canRedo() {
			return redoStack.length > 0;
		}
	};
}

export type HistoryStore = ReturnType<typeof createHistoryStore>;
