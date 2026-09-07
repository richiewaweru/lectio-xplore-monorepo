// @vitest-environment node

/**
 * Content capability records are a projection, not a second catalogue.
 *
 * These tests exist to stop the projection drifting away from the thing it
 * projects: if the export policy says a component is not selectable, the
 * catalogue may not say it is, and vice versa.
 */

import { describe, expect, it } from 'vitest';

import { isInstructionalIntentId, isLearnerActionId } from '@lectio/contracts';
import { CONTENT_CONTRACT_COMPONENT_IDS } from '$lib/lectio/export-policy';
import { lectioContentModules } from '$lib/lectio/registry/components';
import { contentCapabilities } from './content';
import { isSelectable } from './views';

describe('content capability projection', () => {
	it('projects exactly one record per registered component', () => {
		expect(contentCapabilities.map((record) => record.id)).toEqual(
			lectioContentModules.map((module) => module.metadata.id)
		);
	});

	it('agrees with the export policy about who is selectable', () => {
		const eligible = new Set<string>(CONTENT_CONTRACT_COMPONENT_IDS);
		for (const record of contentCapabilities) {
			if (!eligible.has(record.id)) {
				expect(isSelectable(record), `${record.id} is selectable but not contract-eligible`).toBe(
					false
				);
			}
			expect(record.readiness_evidence.contract_export, record.id).toBe(eligible.has(record.id));
			expect(record.readiness_evidence.consumer_selection_support, record.id).toBe(
				eligible.has(record.id)
			);
		}
	});

	it('keeps teacher-attached media out of generation without hiding it', () => {
		for (const id of ['image-block', 'video-embed']) {
			const record = contentCapabilities.find((entry) => entry.id === id);
			expect(record, id).toBeDefined();
			expect(record!.readiness, id).toBe('manual-only');
			expect(isSelectable(record!), id).toBe(false);
			expect(record!.blocking_reasons.length, id).toBeGreaterThan(0);
		}
	});

	it('marks the beta and excluded components incomplete rather than ready', () => {
		const simulation = contentCapabilities.find((entry) => entry.id === 'simulation-block');
		expect(simulation?.readiness).not.toBe('generation-ready');
		expect(simulation?.availability).toBe('incomplete');

		const glossary = contentCapabilities.find((entry) => entry.id === 'glossary-inline');
		expect(glossary?.availability).toBe('unavailable');
		expect(glossary?.blocking_reasons.join(' ')).toMatch(/export policy|section field/i);
	});

	it('describes every component in canonical shared vocabulary', () => {
		for (const record of contentCapabilities) {
			expect(record.supported_intents.length, record.id).toBeGreaterThan(0);
			for (const intent of record.supported_intents) {
				expect(isInstructionalIntentId(intent), `${record.id}: ${intent}`).toBe(true);
			}
			for (const action of record.supported_actions) {
				expect(isLearnerActionId(action), `${record.id}: ${action}`).toBe(true);
			}
		}
	});

	it('claims auto-scoring only where a shared evaluator backs it', () => {
		for (const record of contentCapabilities) {
			if (record.evaluation.mode !== 'auto-score') continue;
			expect(record.id, 'unexpected auto-scored content component').toMatch(
				/^(quiz-check|fill-in-blank)$/
			);
			expect(record.evaluation.contract_ref, record.id).toMatch(/interaction-contract\.ts#/);
			expect(record.response_schema, record.id).not.toBeNull();
		}
	});
});
