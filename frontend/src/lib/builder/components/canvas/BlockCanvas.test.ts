import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { LessonDocument } from 'lectio';

const generateBlock = vi.hoisted(() => vi.fn());

vi.mock('$lib/builder/api/ai-client', () => ({ generateBlock }));
vi.mock('$lib/stores/auth', () => ({ getToken: () => 'token' }));
vi.mock('$lib/builder/stores/connectivity.svelte', () => ({
	connectivityStore: { online: true }
}));
vi.mock('$lib/builder/utils/ai-rate-limit', () => ({
	tryBeginAiCall: () => ({ ok: true, finish: vi.fn() })
}));
vi.mock('$lib/builder/persistence/idb-store', () => ({
	saveDocument: vi.fn(async () => {}),
	saveVersionSnapshot: vi.fn(async () => {})
}));
vi.mock('$lib/builder/persistence/server-sync', () => ({
	ensureBuilderSyncAdapterRegistered: vi.fn(),
	flushBuilderSyncQueue: vi.fn(async () => ({ synced: 0, failed: 0, errors: [] })),
	saveLessonToServer: vi.fn(async () => {})
}));
vi.mock('svelte-dnd-action', () => ({
	dragHandle: () => ({}),
	dragHandleZone: () => ({})
}));

import BlockCanvas from './BlockCanvas.svelte';
import { createDocumentStore } from '$lib/builder/stores/document.svelte';
import type { IssueSection } from '$lib/builder/issues';

function regressionDocument(): LessonDocument {
	const fixture = JSON.parse(
		readFileSync(
			join(process.cwd(), 'src/lib/builder/fixtures/block-ai-regression.json'),
			'utf8'
		)
	) as { lesson: LessonDocument };
	const lesson = structuredClone(fixture.lesson);
	for (const block of Object.values(lesson.blocks)) {
		if (block.component_id === 'explanation-block' && !Array.isArray(block.content.emphasis)) {
			block.content.emphasis = [];
		}
	}
	return lesson;
}

describe('BlockCanvas AI repair integration', () => {
	beforeEach(() => {
		sessionStorage.setItem('lesson-builder-e2e-api-base', 'https://api.example.test');
		Element.prototype.scrollIntoView = vi.fn();
		generateBlock.mockReset();
		generateBlock.mockResolvedValue({
			content: {
				title: 'Check your understanding',
				problems: [{
					difficulty: 'warm',
					question: 'What does chlorophyll capture?',
					hints: [],
					answer: 'Light energy'
				}]
			}
		});
	});

	it('opens a fixture repair, sends edited current content, resolves it, and keeps advisory issues dismiss-only', async () => {
		const store = createDocumentStore();
		store.loadDocument(regressionDocument());
		render(BlockCanvas, { props: { store } });

		expect(screen.getAllByRole('button', { name: 'Fix with AI' })).toHaveLength(1);
		await fireEvent.click(screen.getByRole('button', { name: 'Fix with AI' }));

		const instruction = await screen.findByLabelText('Instruction');
		expect((instruction as HTMLTextAreaElement).value).toBe(
			'Fix this issue in the block: Expected 2 practice questions, found 0.'
		);
		await waitFor(() => expect(document.activeElement).toBe(instruction));
		await fireEvent.input(instruction, {
			target: { value: 'Add two short photosynthesis questions.' }
		});
		await fireEvent.click(screen.getByTestId('ai-assist-generate'));

		await waitFor(() =>
			expect(generateBlock).toHaveBeenCalledWith(
				expect.objectContaining({
					mode: 'custom',
					teacher_note: 'Add two short photosynthesis questions.',
					existing_content: {
						title: 'Check your understanding',
						problems: []
					}
				}),
				'token'
			)
		);
		await waitFor(() => {
			const section = store.document?.sections[0] as IssueSection | undefined;
			const repaired = section?.meta?.issues?.find((issue) => issue.id === 'repair-practice');
			expect(repaired?.resolved).toBe(true);
		});

		const section = store.document?.sections[0] as IssueSection;
		const advisory = section.meta?.issues?.find((issue) => issue.id === 'advisory-anchor');
		expect(advisory?.resolved).toBe(false);
		expect(screen.queryByText('The section anchor needs whole-section review.')).not.toBeNull();
		expect(screen.queryAllByRole('button', { name: 'Fix with AI' })).toHaveLength(0);
	});
});
