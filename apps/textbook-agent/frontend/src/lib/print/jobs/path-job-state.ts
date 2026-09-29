/**
 * Print-path generation operation state (domain-owned).
 * Must not import Learn or Unit store internals.
 * State is derived from the lesson-status DTO (`workspace.print`) only.
 */

import { createPathJobLane, type PathJobLane } from '$lib/reliability/path-job-lane';

export type PrintPathJobState = PathJobLane;

export function createPrintPathJobState(): PrintPathJobState {
	return createPathJobLane('Generating Print…');
}
