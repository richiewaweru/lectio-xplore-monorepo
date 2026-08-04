import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const generateBlock = vi.hoisted(() => vi.fn());

vi.mock('$lib/builder/api/ai-client', () => ({ generateBlock }));
vi.mock('$lib/builder/stores/connectivity.svelte', () => ({
	connectivityStore: { online: true }
}));
vi.mock('$lib/builder/utils/ai-rate-limit', () => ({
	tryBeginAiCall: () => ({ ok: true, finish: vi.fn() })
}));
vi.mock('lectio', () => ({
	getEmptyContent: () => ({ body: '' })
}));

import AiBlockAssist from './AiBlockAssist.svelte';
import { NEW_AI_BLOCK_ASSIST_KEY } from '$lib/settings/flags';

function renderAssist(overrides: Record<string, unknown> = {}) {
	return render(AiBlockAssist, {
		props: {
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: '' }, position: 0 },
			lessonId: 'lesson-1',
			sectionId: 'section-1',
			subject: 'Science',
			gradeBand: 'secondary',
			contextBlocks: [],
			token: 'token',
			apiConfigured: true,
			ongenerated: vi.fn(),
			...overrides
		}
	});
}

describe('AiBlockAssist', () => {
	beforeEach(() => {
		localStorage.clear();
		generateBlock.mockReset();
		generateBlock.mockResolvedValue({ content: { body: 'Generated' } });
	});

	it('sends fill with FAST by default', async () => {
		renderAssist();
		expect(screen.getByTestId('ai-assist-trigger').getAttribute('title')).toBe('Generate content');
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'fill',
				model_tier: 'FAST',
				existing_content: undefined,
				teacher_note: undefined
			}),
			'token'
		));
	});

	it('sends an empty block with an instruction as custom without existing content', async () => {
		renderAssist();
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		await fireEvent.input(screen.getByLabelText('Instruction'), {
			target: { value: 'Add a concise explanation.' }
		});
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'custom',
				teacher_note: 'Add a concise explanation.',
				existing_content: undefined
			}),
			'token'
		));
	});

	it('sends populated improve requests with current content and STANDARD tier', async () => {
		renderAssist({
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: 'Existing' }, position: 0 }
		});
		expect(screen.getByTestId('ai-assist-trigger').getAttribute('title')).toBe('Edit with AI');
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		expect(
			(screen.getByRole('checkbox', {
				name: 'Keep existing content as basis'
			}) as HTMLInputElement).checked
		).toBe(true);
		await fireEvent.click(screen.getByRole('checkbox', { name: 'Higher quality (slower)' }));
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'improve', model_tier: 'STANDARD', existing_content: { body: 'Existing' }
			}),
			'token'
		));
	});

	it('keeps a populated block as improve when an optional instruction is supplied', async () => {
		renderAssist({
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: 'Existing' }, position: 0 }
		});
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		await fireEvent.input(screen.getByLabelText('Instruction'), {
			target: { value: 'Use shorter sentences.' }
		});
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'improve',
				teacher_note: 'Use shorter sentences.',
				existing_content: { body: 'Existing' }
			}),
			'token'
		));
	});

	it('rewrites a populated block statelessly when the basis toggle is off', async () => {
		const onRepairApplied = vi.fn();
		renderAssist({
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: 'Existing' }, position: 0 },
			onRepairApplied
		});
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		await fireEvent.click(screen.getByRole('checkbox', { name: 'Keep existing content as basis' }));
		await fireEvent.input(screen.getByLabelText('Instruction'), { target: { value: 'Make it clearer.' } });
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'custom', teacher_note: 'Make it clearer.', existing_content: undefined
			}),
			'token'
		));
		expect(onRepairApplied).not.toHaveBeenCalled();
	});

	it('retains the legacy radio UI when the feature flag is false', async () => {
		localStorage.setItem(NEW_AI_BLOCK_ASSIST_KEY, 'false');
		renderAssist({
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: 'Existing' }, position: 0 }
		});
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));

		expect(screen.getByRole('radio', { name: 'Fill' })).not.toBeNull();
		expect(screen.getByRole('radio', { name: 'Improve' })).not.toBeNull();
		expect(screen.getByRole('radio', { name: 'Custom' })).not.toBeNull();
		expect(screen.queryByRole('checkbox', { name: 'Keep existing content as basis' })).toBeNull();
	});

	it('opens a repair prefilled, editable, FAST, and sends no existing content', async () => {
		const onRepairApplied = vi.fn();
		const request = {
			requestKey: 'repair-1', issueId: 'issue-1', sectionId: 'section-1',
			targetBlockId: 'block-1', initialInstruction: 'Expected two questions.'
		};
		renderAssist({
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: 'Existing' }, position: 0 },
			repairRequest: request,
			onRepairApplied
		});

		const instruction = await screen.findByLabelText('Instruction');
		expect((instruction as HTMLTextAreaElement).value).toBe('Expected two questions.');
		await waitFor(() => expect(document.activeElement).toBe(instruction));
		await fireEvent.input(instruction, { target: { value: 'Add exactly two short questions.' } });
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'custom', model_tier: 'FAST',
				teacher_note: 'Add exactly two short questions.',
				existing_content: undefined
			}),
			'token'
		));
		expect(onRepairApplied).toHaveBeenCalledWith(request);
	});

	it('does not resolve a repair when generation fails', async () => {
		generateBlock.mockRejectedValueOnce(new Error('provider failed'));
		const onRepairApplied = vi.fn();
		renderAssist({
			repairRequest: {
				requestKey: 'repair-2', issueId: 'issue-2', sectionId: 'section-1',
				targetBlockId: 'block-1', initialInstruction: 'Repair this.'
			},
			onRepairApplied
		});
		await fireEvent.click(await screen.findByTestId('ai-assist-generate'));
		await screen.findByRole('alert');
		expect(onRepairApplied).not.toHaveBeenCalled();
	});
});
