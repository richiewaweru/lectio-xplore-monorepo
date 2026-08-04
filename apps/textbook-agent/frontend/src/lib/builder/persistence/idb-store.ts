import { openDB, type IDBPDatabase } from 'idb';
import type { LessonDocument } from 'lectio';

const DB_NAME = 'lesson-builder';
const DB_VERSION = 3;
const STORE_NAME = 'documents';
const SYNC_QUEUE_STORE = 'sync-queue';
export const DOCUMENT_VERSIONS_STORE = 'document-versions';

/** Full lesson snapshot for version history (Phase 7). */
export interface DocumentVersion {
	id: string;
	document_id: string;
	snapshot: LessonDocument;
	label?: string;
	created_at: string;
}

export async function getDB(): Promise<IDBPDatabase> {
	return openDB(DB_NAME, DB_VERSION, {
		upgrade(db, oldVersion) {
			if (!db.objectStoreNames.contains(STORE_NAME)) {
				const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
				store.createIndex('updated_at', 'updated_at');
				store.createIndex('title', 'title');
			}
			if (oldVersion < 2 && !db.objectStoreNames.contains(SYNC_QUEUE_STORE)) {
				db.createObjectStore(SYNC_QUEUE_STORE, { keyPath: 'id' });
			}
			if (oldVersion < 3 && !db.objectStoreNames.contains(DOCUMENT_VERSIONS_STORE)) {
				const vStore = db.createObjectStore(DOCUMENT_VERSIONS_STORE, { keyPath: 'id' });
				vStore.createIndex('document_id', 'document_id');
			}
		}
	});
}

const MAX_VERSIONS_PER_DOCUMENT = 20;

function newVersionId(): string {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	return `v-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/** Persist a version snapshot; enforces at most `MAX_VERSIONS_PER_DOCUMENT` per document (oldest removed). */
export async function saveVersionSnapshot(
	documentId: string,
	snapshot: LessonDocument,
	label?: string,
	/** For tests or backdating; defaults to now. */
	createdAt?: string
): Promise<string> {
	const db = await getDB();
	const plain = JSON.parse(JSON.stringify(snapshot)) as LessonDocument;
	const id = newVersionId();
	const row: DocumentVersion = {
		id,
		document_id: documentId,
		snapshot: plain,
		label,
		created_at: createdAt ?? new Date().toISOString()
	};
	await db.put(DOCUMENT_VERSIONS_STORE, row);
	const list = await listVersions(documentId);
	const overflow = list.slice(MAX_VERSIONS_PER_DOCUMENT);
	for (const v of overflow) {
		await db.delete(DOCUMENT_VERSIONS_STORE, v.id);
	}
	return id;
}

export async function listVersions(documentId: string): Promise<DocumentVersion[]> {
	const db = await getDB();
	const tx = db.transaction(DOCUMENT_VERSIONS_STORE, 'readonly');
	const index = tx.store.index('document_id');
	const out: DocumentVersion[] = [];
	for await (const cursor of index.iterate(IDBKeyRange.only(documentId))) {
		out.push(cursor.value as DocumentVersion);
	}
	await tx.done;
	return out.sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export async function getVersion(versionId: string): Promise<DocumentVersion | undefined> {
	const db = await getDB();
	return db.get(DOCUMENT_VERSIONS_STORE, versionId) as Promise<DocumentVersion | undefined>;
}

export async function deleteVersion(versionId: string): Promise<void> {
	const db = await getDB();
	await db.delete(DOCUMENT_VERSIONS_STORE, versionId);
}

/**
 * Snapshot current document as a new version, then return the target snapshot for the caller to load.
 * Reversible: current state is preserved in history first.
 */
export async function restoreVersionWithBackup(
	current: LessonDocument,
	target: DocumentVersion
): Promise<LessonDocument> {
	if (current.id !== target.document_id) {
		throw new Error('Version does not belong to this document.');
	}
	await saveVersionSnapshot(current.id, current, 'Before restore');
	return JSON.parse(JSON.stringify(target.snapshot)) as LessonDocument;
}

export async function saveDocument(doc: LessonDocument): Promise<void> {
	const db = await getDB();
	/** JSON round-trip strips Svelte proxies and guarantees a plain tree for IDB (structuredClone can mis-handle proxies). */
	const row = JSON.parse(JSON.stringify(doc)) as LessonDocument;
	row.updated_at = new Date().toISOString();
	await db.put(STORE_NAME, row);
}

export async function getDocument(id: string): Promise<LessonDocument | undefined> {
	const db = await getDB();
	return db.get(STORE_NAME, id);
}

export async function listDocuments(): Promise<LessonDocument[]> {
	const db = await getDB();
	const all = await db.getAllFromIndex(STORE_NAME, 'updated_at');
	return all.reverse();
}

export async function deleteDocument(id: string): Promise<void> {
	const db = await getDB();
	await db.delete(STORE_NAME, id);
}
