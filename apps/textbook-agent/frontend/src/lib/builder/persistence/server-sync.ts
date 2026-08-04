import type { LessonDocument } from 'lectio';
import { isApiError } from '$lib/api/errors';
import {
	deleteBuilderLesson,
	getBuilderLesson,
	updateBuilderLesson
} from '$lib/builder/api/lesson-crud';
import { getDocument, saveDocument } from './idb-store';
import {
	enqueueSync,
	flushSyncQueue,
	registerSyncAdapter,
	type SyncEntry,
	type SyncResult
} from './sync-queue';

const SAVE_QUEUE_KEY_PREFIX = 'builder-save:';
let adapterRegistered = false;

function _queueKey(documentId: string): string {
	return `${SAVE_QUEUE_KEY_PREFIX}${documentId}`;
}

function _isRetryableSyncError(error: unknown): boolean {
	if (!isApiError(error)) {
		return true;
	}
	return error.status >= 500;
}

async function _syncFromQueue(entry: SyncEntry): Promise<void> {
	if (entry.action === 'delete') {
		await deleteBuilderLesson(entry.document_id);
		return;
	}
	const cached = await getDocument(entry.document_id);
	if (!cached) {
		return;
	}
	await updateBuilderLesson(entry.document_id, {
		title: cached.title,
		document: cached
	});
}

export function ensureBuilderSyncAdapterRegistered(): void {
	if (adapterRegistered) {
		return;
	}
	registerSyncAdapter(_syncFromQueue);
	adapterRegistered = true;
}

export async function queueLessonSave(documentId: string): Promise<void> {
	await enqueueSync({
		id: _queueKey(documentId),
		document_id: documentId,
		action: 'save',
		timestamp: new Date().toISOString()
	});
}

export async function saveLessonToServer(document: LessonDocument): Promise<void> {
	ensureBuilderSyncAdapterRegistered();
	try {
		await updateBuilderLesson(document.id, {
			title: document.title,
			document
		});
	} catch (error) {
		if (_isRetryableSyncError(error)) {
			await queueLessonSave(document.id);
		}
		throw error;
	}
}

export async function flushBuilderSyncQueue(): Promise<SyncResult> {
	ensureBuilderSyncAdapterRegistered();
	return flushSyncQueue();
}

export async function loadBuilderLessonWithFallback(
	lessonId: string
): Promise<{ document: LessonDocument; source: 'server' | 'idb' }> {
	ensureBuilderSyncAdapterRegistered();
	try {
		const remote = await getBuilderLesson(lessonId);
		await saveDocument(remote.document);
		return { document: remote.document, source: 'server' };
	} catch (error) {
		if (!_isRetryableSyncError(error)) {
			throw error;
		}
		const cached = await getDocument(lessonId);
		if (!cached) {
			throw error;
		}
		return { document: cached, source: 'idb' };
	}
}

