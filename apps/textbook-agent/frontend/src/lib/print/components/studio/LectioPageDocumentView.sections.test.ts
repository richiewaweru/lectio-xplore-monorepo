// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { LectioDocument } from '@lectio/page/contract';
import { findSectionElement } from '$lib/curriculum/lessons/section-focus';
import LectioPageDocumentView from './LectioPageDocumentView.svelte';

const fixture = JSON.parse(
	readFileSync(
		join(process.cwd(), '..', 'backend', 'tests', 'fixtures', 'lectio-page', 'valid-document.json'),
		'utf8'
	)
) as LectioDocument;

describe('LectioPageDocumentView section markers', () => {
	afterEach(() => cleanup());

	it('tags each rendered section so the "Go to section" link can find it', async () => {
		render(LectioPageDocumentView, { props: { document: fixture } });
		const sectionId = fixture.sections[0].id;
		await new Promise((resolve) => setTimeout(resolve, 0));
		const element = findSectionElement(sectionId);
		expect(element).toBeTruthy();
		expect(element?.getAttribute('data-section-id')).toBe(sectionId);
	});
});
