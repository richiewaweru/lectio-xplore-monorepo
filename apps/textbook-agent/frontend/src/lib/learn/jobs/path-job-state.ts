/**
 * Learn-path generation operation state (domain-owned).
 * Must not import Print or Unit store internals.
 */

import type { PathJobLane } from '$lib/reliability/path-job-lane';
import type { ReliabilityAllowedAction, ReliabilityRunStatus } from '$lib/types/reliability';

export type LearnPathJobState = PathJobLane;

export function createLearnPathJobState(): LearnPathJobState {
	let busyLabel: string | null = null;
	let runStatus: ReliabilityRunStatus | null = null;
	let allowed = new Set<ReliabilityAllowedAction>();

	return {
		get busyLabel() {
			return busyLabel;
		},
		get runStatus() {
			return runStatus;
		},
		get allowedActions() {
			return allowed;
		},
		begin(label = 'Generating Learn…') {
			if (busyLabel !== null) return false;
			busyLabel = label;
			return true;
		},
		end() {
			busyLabel = null;
		},
		applyStatus(status) {
			runStatus = status;
			allowed = new Set(status?.allowed_actions ?? []);
		},
		canPrepare(pathApproved, lessonSkipped) {
			if (busyLabel !== null) return false;
			if (!pathApproved || lessonSkipped) return false;
			if (allowed.size === 0) return true;
			return allowed.has('prepare_learn');
		}
	};
}
