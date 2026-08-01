// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	getLessonShape: vi.fn(), requestShapeDeviation: vi.fn(), decideShapeDeviation: vi.fn()
}));

vi.mock('$lib/api/units', () => mocks);

import LessonShapePanel from './LessonShapePanel.svelte';

const slot = (slot_id: string, locked = false) => ({
	slot_id, role: slot_id, purpose: slot_id, allowed_components: ['text'], locked, visual_required: false
});

const canonical = {
	group_profile: 'core' as const, support_level: 'medium',
	slots: [slot('orient'), slot('explain'), slot('check', true)],
	toggles_applied: [], warnings: [], structural_diff: [], blocking_issues: []
};

const shape = {
	path_lesson_id: 'lesson-1', lesson_revision: 1, objective: 'Explain plant food.',
	objective_hash: 'hash', concept_id: 'concept-1', scope_exclusions: ['Respiration'],
	lesson_mode: 'first_exposure' as const, misconception_count: 1,
	skeleton_id: 'conceptual-core', skeleton_version: 1, canonical,
	variants: [
		{
			...canonical, group_profile: 'support' as const, support_level: 'high',
			structural_diff: [{ operation: 'replace' as const, slot_id: 'explain', replacement_slot: 'model', toggle_id: 'support.use_model', explanation: 'Use a worked model for high support.' }]
		},
		canonical,
		{ ...canonical, group_profile: 'extension' as const, support_level: 'low' }
	],
	deviations: [], available_slots: ['orient', 'explain', 'model', 'check'],
	blocking_issues: [{ code: 'skeleton_conflict' as const, message: 'Six-slot limit would be exceeded.', toggle_id: 'extension.add_apply', group_profile: 'extension' as const }],
	can_prepare: false
};

const path = { id: 'path-1', revision: 2 } as never;
const lesson = { id: 'lesson-1', revision: 1 } as never;

afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe('LessonShapePanel', () => {
	it('shows canonical and declared variants with exact explanations and blocking issues', () => {
		render(LessonShapePanel, {
			props: { unitId: 'unit-1', path, lesson, shape, lessonMode: 'first_exposure', misconceptionCount: 1, onsettings: vi.fn(), onshape: vi.fn(), onrevision: vi.fn() }
		});
		expect(screen.getByText('Canonical')).toBeTruthy();
		expect(screen.getByText('Support')).toBeTruthy();
		expect(screen.getByText('Extension')).toBeTruthy();
		expect(screen.getByText('Use a worked model for high support.')).toBeTruthy();
		expect(screen.getByText('support.use_model')).toBeTruthy();
		expect(screen.getByRole('alert').textContent).toContain('Six-slot limit would be exceeded.');
	});

	it('requests and separately approves a teacher deviation', async () => {
		const pending = {
			id: 'dev-1', skeleton_id: 'conceptual-core', skeleton_version: 1,
			lesson_mode: 'first_exposure', operation: 'remove', target_slot: 'orient', replacement_slot: null,
			reason: 'Make room for the extension application.', requested_by: 'teacher', status: 'pending_teacher',
			requested_at: '2026-08-01T00:00:00Z', decided_at: null, decided_by: null
		} as const;
		mocks.requestShapeDeviation.mockResolvedValue(pending);
		mocks.getLessonShape.mockResolvedValue({ ...shape, deviations: [pending] });
		mocks.decideShapeDeviation.mockResolvedValue({ ...pending, status: 'approved', lesson_revision: 2 });
		const onshape = vi.fn();
		const onrevision = vi.fn();
		render(LessonShapePanel, {
			props: { unitId: 'unit-1', path, lesson, shape, lessonMode: 'first_exposure', misconceptionCount: 1, onsettings: vi.fn(), onshape, onrevision }
		});
		await fireEvent.change(screen.getByLabelText('Operation'), { target: { value: 'remove' } });
		await fireEvent.change(screen.getByLabelText('Target slot'), { target: { value: 'orient' } });
		await fireEvent.input(screen.getByLabelText('Pedagogical reason'), { target: { value: pending.reason } });
		await fireEvent.click(screen.getByRole('button', { name: 'Request deviation' }));
		expect(mocks.requestShapeDeviation).toHaveBeenCalledWith('unit-1', path, lesson, expect.objectContaining({ operation: 'remove', target_slot: 'orient', replacement_slot: null }));
		expect(onshape).toHaveBeenCalled();

		cleanup();
		render(LessonShapePanel, {
			props: { unitId: 'unit-1', path, lesson, shape: { ...shape, deviations: [pending] }, lessonMode: 'first_exposure', misconceptionCount: 1, onsettings: vi.fn(), onshape, onrevision }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Approve deviation' }));
		expect(mocks.decideShapeDeviation).toHaveBeenCalledWith('unit-1', path, lesson, 'dev-1', 'approve');
		expect(onrevision).toHaveBeenCalledWith(2);
	});
});
