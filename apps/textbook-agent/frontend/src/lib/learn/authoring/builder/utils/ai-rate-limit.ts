/** Max one AI request start per block per this many ms. */
export const AI_PER_BLOCK_COOLDOWN_MS = 3000;

/** Max concurrent AI requests across the document. */
export const AI_MAX_CONCURRENT = 5;

let inFlight = 0;
const lastStartByBlock = new Map<string, number>();

export type AiCallTicket =
	| { ok: true; finish: () => void }
	| { ok: false; waitMs: number; reason: 'cooldown' | 'concurrent' };

/**
 * Attempt to start an AI call for a block. If ok, call `finish()` in a finally block when done.
 */
export function tryBeginAiCall(blockId: string): AiCallTicket {
	const now = Date.now();
	const prev = lastStartByBlock.get(blockId);
	if (prev !== undefined && now - prev < AI_PER_BLOCK_COOLDOWN_MS) {
		return {
			ok: false,
			waitMs: AI_PER_BLOCK_COOLDOWN_MS - (now - prev),
			reason: 'cooldown'
		};
	}
	if (inFlight >= AI_MAX_CONCURRENT) {
		return { ok: false, waitMs: 0, reason: 'concurrent' };
	}
	inFlight += 1;
	lastStartByBlock.set(blockId, now);
	let finished = false;
	return {
		ok: true,
		finish: () => {
			if (finished) return;
			finished = true;
			inFlight -= 1;
		}
	};
}

/** Test helper: reset module state. */
export function resetAiRateLimitForTests(): void {
	inFlight = 0;
	lastStartByBlock.clear();
}
