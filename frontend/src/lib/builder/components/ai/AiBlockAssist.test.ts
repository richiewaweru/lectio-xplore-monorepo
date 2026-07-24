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
		generateBlock.mockReset();
		generateBlock.mockResolvedValue({ content: { body: 'Generated' } });
	});

	it('sends fill with FAST by default', async () => {
		renderAssist();
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({ mode: 'fill', model_tier: 'FAST', existing_content: undefined }),
			'token'
		));
	});

	it('sends populated improve requests with current content and STANDARD tier', async () => {
		renderAssist({
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: 'Existing' }, position: 0 }
		});
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		await fireEvent.click(screen.getByRole('radio', { name: 'Improve' }));
		await fireEvent.click(screen.getByRole('checkbox', { name: 'Higher quality (slower)' }));
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'improve', model_tier: 'STANDARD', existing_content: { body: 'Existing' }
			}),
			'token'
		));
	});

	it('keeps ordinary custom requests stateless', async () => {
		renderAssist({
			block: { id: 'block-1', component_id: 'explanation-block', content: { body: 'Existing' }, position: 0 }
		});
		await fireEvent.click(screen.getByTestId('ai-assist-trigger'));
		await fireEvent.click(screen.getByRole('radio', { name: 'Custom' }));
		await fireEvent.input(screen.getByLabelText('Instruction'), { target: { value: 'Make it clearer.' } });
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() => expect(generateBlock).toHaveBeenCalledWith(
			expect.objectContaining({
				mode: 'custom', teacher_note: 'Make it clearer.', existing_content: undefined
			}),
			'token'
		));
	});

	it('opens a repair prefilled, editable, FAST, and sends existing content', async () => {
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
				existing_content: { body: 'Existing' }
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
