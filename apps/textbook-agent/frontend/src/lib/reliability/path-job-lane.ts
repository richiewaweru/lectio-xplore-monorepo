/**
 * Shared path-job lane contract. Print/Learn implement this; Unit composes it
 * without importing sibling domain modules.
 */

import type { ReliabilityAllowedAction, ReliabilityRunStatus } from '$lib/types/reliability';

export interface PathJobLane {
	readonly busyLabel: string | null;
	readonly runStatus: ReliabilityRunStatus | null;
	readonly allowedActions: ReadonlySet<ReliabilityAllowedAction>;
	begin(label?: string): boolean;
	end(): void;
	applyStatus(status: ReliabilityRunStatus | null): void;
	canPrepare(pathApproved: boolean, lessonSkipped: boolean): boolean;
}
