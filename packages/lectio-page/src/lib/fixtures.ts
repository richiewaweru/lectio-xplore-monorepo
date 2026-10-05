import type { LectioDocument } from '$lib/contract/document';
import photosynthesis from '../../fixtures/photosynthesis-ref.json';
import empty from '../../fixtures/empty-document.json';
import marginStress from '../../fixtures/margin-stress.json';
import sharedLessonLegacy from '../../fixtures/shared-lesson-legacy.json';
import sharedLessonGolden from '../../fixtures/shared-lesson-golden.json';
import oversizedStress from '../../fixtures/oversized-stress.json';

export const fixtureIndex = [
	{
		id: 'photosynthesis-ref',
		title: 'Photosynthesis reference pages',
		description: 'Hand-authored three-section rebuild using all ten page objects.'
	},
	{
		id: 'empty-document',
		title: 'Empty valid shell',
		description: 'Minimal document for contract smoke checks.'
	},
	{
		id: 'margin-stress',
		title: 'Margin placement stress cases',
		description: 'Adjacent asides and an aside positioned near a page break.'
	},
	{
		id: 'shared-lesson-legacy',
		title: 'Legacy shared lesson',
		description: 'Production shared lesson export used for the doc36 compatibility PDF proof.'
	},
	{
		id: 'shared-lesson-golden',
		title: 'Doc36 golden shared lesson',
		description: 'All Doc36 ordinary blocks, inline markup, and teacher answers.'
	},
	{
		id: 'oversized-stress',
		title: 'Doc36 oversized pagination stress',
		description: 'Test-only tall prose, table, comparison, and misconception blocks.'
	}
] as const;

export type FixtureId = (typeof fixtureIndex)[number]['id'];

export function loadFixture(id: string): LectioDocument | null {
	if (id === 'photosynthesis-ref') return photosynthesis as LectioDocument;
	if (id === 'empty-document') return empty as LectioDocument;
	if (id === 'margin-stress') return marginStress as LectioDocument;
	if (id === 'shared-lesson-legacy') return sharedLessonLegacy as LectioDocument;
	if (id === 'shared-lesson-golden') return sharedLessonGolden as LectioDocument;
	if (id === 'oversized-stress') return oversizedStress as LectioDocument;
	return null;
}
