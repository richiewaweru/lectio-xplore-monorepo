/**
 * Isolated preview attempt store (P06-L04).
 *
 * Preview uses the same evaluator semantics as production but never persists
 * LearnerAttempt / evidence rows. Draft edits stay on the editable lesson and
 * do not mutate published release snapshots.
 */

import {
	createAttemptState,
	evaluateInteraction,
	type EvaluationResult,
	type InteractionAttemptState,
	type LearnInteractionContract
} from '../learn/interaction-contract';

export interface PreviewAttemptRecord {
	interaction_id: string;
	result: EvaluationResult;
	response: unknown;
	created_at: string;
}

export interface PreviewAttemptStore {
	readonly mode: 'preview';
	readonly persists_production_attempts: false;
	getState(interactionId: string): InteractionAttemptState;
	submit(contract: LearnInteractionContract, response: unknown): EvaluationResult;
	list(): PreviewAttemptRecord[];
	clear(): void;
}

export function createPreviewAttemptStore(): PreviewAttemptStore {
	const states = new Map<string, InteractionAttemptState>();
	const records: PreviewAttemptRecord[] = [];

	return {
		mode: 'preview',
		persists_production_attempts: false,
		getState(interactionId: string) {
			let state = states.get(interactionId);
			if (!state) {
				state = createAttemptState(interactionId);
				states.set(interactionId, state);
			}
			return state;
		},
		submit(contract: LearnInteractionContract, response: unknown) {
			const state = this.getState(contract.id);
			const result = evaluateInteraction(contract, response, state);
			state.attempt_count += 1;
			state.last_result = result;
			state.responses.push(response);
			if (result.outcome === 'correct' || contract.completion.type === 'submitted') {
				state.completed = true;
			}
			records.push({
				interaction_id: contract.id,
				result,
				response,
				created_at: new Date().toISOString()
			});
			return result;
		},
		list() {
			return [...records];
		},
		clear() {
			states.clear();
			records.length = 0;
		}
	};
}
