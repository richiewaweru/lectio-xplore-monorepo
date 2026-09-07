import { getDB } from './idb-store';

const STORE = 'sync-queue';

export interface SyncEntry {
	id: string;
	document_id: string;
	action: 'save' | 'delete';
	timestamp: string;
}

export type SyncResult = {
	synced: number;
	failed: number;
	errors: string[];
};

export type SyncAdapter = (entry: SyncEntry) => Promise<void>;

let adapter: SyncAdapter | null = null;

/** Register the Phase 7 (or test) handler; `null` clears. Without an adapter, `flushSyncQueue` does not send or remove entries. */
export function registerSyncAdapter(fn: SyncAdapter | null): void {
	adapter = fn;
}

export async function enqueueSync(entry: SyncEntry): Promise<void> {
	const db = await getDB();
	await db.put(STORE, entry);
}

export async function getSyncQueueSize(): Promise<number> {
	const db = await getDB();
	return db.count(STORE);
}

/**
 * Processes queued entries with the registered adapter and removes successful ones.
 * If no adapter is registered, returns zeros and leaves the queue unchanged.
 */
export async function flushSyncQueue(): Promise<SyncResult> {
	if (!adapter) {
		return { synced: 0, failed: 0, errors: [] };
	}
	const db = await getDB();
	const entries = await db.getAll(STORE) as SyncEntry[];
	let synced = 0;
	let failed = 0;
	const errors: string[] = [];
	for (const entry of entries) {
		try {
			await adapter(entry);
			await db.delete(STORE, entry.id);
			synced++;
		} catch (e) {
			failed++;
			errors.push(e instanceof Error ? e.message : String(e));
		}
	}
	return { synced, failed, errors };
}
