import { render, fireEvent } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { DocumentSection } from '@lectio/learn';
import StudentStageNav from './StudentStageNav.svelte';
import type { StudentStage } from './student-shell';

function stage(partial: Partial<DocumentSection> & Pick<DocumentSection, 'id' | 'position' | 'title'>): StudentStage {
	const section: DocumentSection = {
		template_id: 'open-canvas',
		block_ids: [],
		...partial
	};
	return {
		section,
		index: partial.position,
		label: partial.learner_label ?? partial.title,
		assessment_mode: partial.assessment_mode ?? 'ungraded-info',
		required: true
	};
}

describe('StudentStageNav', () => {
	it('renders ordered stage tabs and compact phone nav', async () => {
		const stages = [
			stage({ id: 's1', position: 0, title: 'Orient', learner_label: 'Warm-up' }),
			stage({ id: 's2', position: 1, title: 'Practice', assessment_mode: 'practice' })
		];
		let current = 0;
		const { getByTestId, getAllByRole, rerender } = render(StudentStageNav, {
			props: {
				stages,
				currentIndex: current,
				onSelect: (index: number) => {
					current = index;
				}
			}
		});
		const tabs = getByTestId('stage-tabs');
		expect(tabs.textContent).toContain('Warm-up');
		expect(tabs.textContent).toContain('Practice');
		expect(getByTestId('stage-compact')).toBeTruthy();

		const practice = getAllByRole('button').find((b) => b.textContent?.includes('Practice'));
		expect(practice).toBeTruthy();
		await fireEvent.click(practice!);
		await rerender({
			stages,
			currentIndex: 1,
			onSelect: (index: number) => {
				current = index;
			}
		});
		expect(current).toBe(1);
		expect(getByTestId('stage-tabs').querySelector('button.active')?.textContent).toContain('Practice');
	});
});
