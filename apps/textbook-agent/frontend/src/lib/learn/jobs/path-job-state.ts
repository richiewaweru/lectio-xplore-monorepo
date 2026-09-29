/**
 * Learn-path generation operation state (domain-owned).
 * Must not import Print or Unit store internals.
 * State is derived from the lesson-status DTO (`workspace.learn`) only.
 */

import { createPathJobLane, type PathJobLane } from '$lib/reliability/path-job-lane';

export type LearnPathJobState = PathJobLane;

export function createLearnPathJobState(): LearnPathJobState {
	return createPathJobLane('Generating Learn…');
}
