export type StorageEstimateResult = { used: number; quota: number };

/**
 * Returns persisted storage usage and quota when the Storage API is available.
 */
export async function getStorageEstimate(): Promise<StorageEstimateResult | null> {
	if (typeof navigator === 'undefined' || !navigator.storage?.estimate) return null;
	const { usage, quota } = await navigator.storage.estimate();
	return { used: usage ?? 0, quota: quota ?? 0 };
}
