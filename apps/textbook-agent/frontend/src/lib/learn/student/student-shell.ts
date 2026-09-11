/** Clamp a stage index into [0, length-1]. Kept for StudentStageNav tests. */
export function clampStageIndex(index: number, length: number): number {
	if (length <= 0) return 0;
	return Math.max(0, Math.min(index, length - 1));
}
