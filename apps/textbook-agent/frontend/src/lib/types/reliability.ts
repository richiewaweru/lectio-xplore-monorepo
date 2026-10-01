/**
 * Frontend contracts for unit-workspace edit protection.
 * Realization status comes from the lesson-status DTO, not a separate endpoint.
 */

export interface ReliabilityConflictState {
	message: string;
	local_revision: number | null;
	server_revision: number | null;
	/** Local editor draft preserved across the conflict. */
	local_draft: {
		title: string;
		objective: string;
		must_establish: string;
		exclusions: string;
	};
}
