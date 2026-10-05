import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ParagraphNode from './ParagraphNode.svelte';
import EquationNode from './EquationNode.svelte';
import CalloutNode from './CalloutNode.svelte';
import FigureNode from './FigureNode.svelte';
import DocumentNodeRenderer from './DocumentNodeRenderer.svelte';
import type { DocumentNode } from '../types';

afterEach(() => cleanup());

describe('Learn document renderers', () => {
	it('splits paragraphs and renders every inline token', () => {
		const { container } = render(ParagraphNode, {
			node: { id: 'p', kind: 'paragraph', text: '**Bold**\n\n*em* ~sub~ ^sup^' }
		});
		expect(container.querySelectorAll('p')).toHaveLength(2);
		expect(container.querySelector('strong')?.textContent).toBe('Bold');
		expect(container.querySelector('em')?.textContent).toBe('em');
		expect(container.querySelector('sub')?.textContent).toBe('sub');
		expect(container.querySelector('sup')?.textContent).toBe('sup');
	});

	it('keeps all equation outputs and authored callout titles', () => {
		const equation = render(EquationNode, {
			node: { id: 'eq', kind: 'equation', inputs: ['water'], outputs: ['sugar', 'oxygen'], condition: 'light' }
		});
		expect(equation.container.textContent).toContain('sugar');
		expect(equation.container.textContent).toContain('oxygen');
		equation.unmount();

		const callout = render(CalloutNode, {
			node: { id: 'c', kind: 'callout', tone: 'note', title: 'Notice two things', body: 'Keep this detail.' }
		});
		expect(callout.container.textContent).toContain('Notice two things');
	});

	it('omits figures without a resolved asset and warns once per unknown kind', () => {
		const figure = render(FigureNode, {
			node: { id: 'f', kind: 'figure', asset_id: 'missing', caption: 'Hidden' },
			assets: {}
		});
		expect(figure.container.querySelector('[data-testid="figure-node"]')).toBeNull();
		figure.unmount();

		const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
		const unknown = { id: 'u', kind: 'future-block', text: 'First\n\nSecond', extra: 'hidden' } as unknown as DocumentNode;
		const first = render(DocumentNodeRenderer, { node: unknown });
		const second = render(DocumentNodeRenderer, { node: { ...unknown, id: 'u2' } as DocumentNode });
		expect(first.container.querySelectorAll('.unknown-fallback')).toHaveLength(2);
		expect(first.container.textContent).toContain('First');
		expect(first.container.textContent).toContain('Second');
		expect(first.container.textContent).not.toContain('future-block');
		expect(warn.mock.calls.filter(([message]) => String(message).includes('future-block'))).toHaveLength(1);
		first.unmount();
		second.unmount();
		warn.mockRestore();
	});
});
