/**
 * Independent operation lanes — Print, Learn, plan, and save must not share
 * a single busy flag (G19/G20). Shared helper; domain stores own their lanes.
 */

export type UnitOperationLane =
	| 'plan'
	| 'save'
	| 'print'
	| 'learn'
	| 'approve'
	| 'regenerate'
	| 'merge'
	| 'restore'
	| 'chat';

export type OperationBusyMap = Record<UnitOperationLane, string | null>;

export function emptyBusyMap(): OperationBusyMap {
	return {
		plan: null,
		save: null,
		print: null,
		learn: null,
		approve: null,
		regenerate: null,
		merge: null,
		restore: null,
		chat: null
	};
}

export function isLaneBusy(busy: OperationBusyMap, lane: UnitOperationLane): boolean {
	return busy[lane] !== null;
}

/** True when any generation path job is active — for dual-path proofs. */
export function anyPathJobBusy(busy: OperationBusyMap): boolean {
	return busy.print !== null || busy.learn !== null;
}
