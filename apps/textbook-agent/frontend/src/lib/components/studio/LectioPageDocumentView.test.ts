import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render } from '@testing-library/svelte';
import LectioPageDocumentView from '$lib/components/studio/LectioPageDocumentView.svelte';
import type { LectioDocument } from '@lectio/page';

const fixture = JSON.parse(
	readFileSync(
		join(
			process.cwd(),
			'..',
			'backend',
			'tests',
			'fixtures',
			'lectio-page',
			'valid-document.json'
		),
		'utf8'
	)
) as LectioDocument;

describe('LectioPageDocumentView', () => {
	it('renders v2 section title and ordered block ids without reordering', () => {
		const { container } = render(LectioPageDocumentView, {
			props: { document: fixture, edition: 'teacher' }
		});
		expect(container.querySelector('[data-document-version="2"]')).toBeTruthy();
		const title = container.querySelector('.lectio-section-title, h2');
		expect(title?.textContent ?? '').toMatch(/light|What/i);
		const blockIds = [...container.querySelectorAll('[data-block-id]')].map((el) =>
			el.getAttribute('data-block-id')
		);
		if (blockIds.length) {
			expect(blockIds).toEqual([...blockIds].sort((a, b) => {
				const ai = fixture.sections[0].blocks.findIndex((block) => block.id === a);
				const bi = fixture.sections[0].blocks.findIndex((block) => block.id === b);
				return ai - bi;
			}));
		}
	});
});
