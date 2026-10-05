import type { LectioDocument } from '$lib/contract/document';
import photosynthesis from '../../fixtures/photosynthesis-ref.json';
import empty from '../../fixtures/empty-document.json';
import marginStress from '../../fixtures/margin-stress.json';
import sharedLessonLegacy from '../../fixtures/shared-lesson-legacy.json';
import sharedLessonGolden from '../../fixtures/shared-lesson-golden.json';
import oversizedStress from '../../fixtures/oversized-stress.json';
import sharedLessonOverlong from '../../fixtures/shared-lesson-overlong.json';
import trackCPhotosynthesis from '../../fixtures/track-c-photosynthesis-print.json';
import trackCFormula from '../../fixtures/track-c-formula-print.json';
import trackCComparison from '../../fixtures/track-c-comparison-print.json';
import phase5Photosynthesis from '../../fixtures/phase5-photosynthesis-print.json';

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
	},
	{
		id: 'shared-lesson-overlong',
		title: 'Doc36 frozen overlong shared lesson',
		description: 'Frozen overlong shared lesson fixture for print continuation checks.'
	},
	{
		id: 'track-c-photosynthesis-print',
		title: 'Track C photosynthesis Print projection',
		description: 'Accepted Track C shared document projected through the Print adapter.'
	},
	{
		id: 'track-c-formula-print',
		title: 'Track C formula Print projection',
		description: 'Accepted Track C formula document projected through the Print adapter.'
	},
	{
		id: 'track-c-comparison-print',
		title: 'Track C comparison Print projection',
		description: 'Accepted Track C comparison document projected through the Print adapter.'
	},
	{
		id: 'phase5-photosynthesis-print',
		title: 'Phase 5 photosynthesis Print projection',
		description: 'Phase 5 integration run draft projected through the Print adapter (figure image unavailable).'
	}
] as const;

export type FixtureId = (typeof fixtureIndex)[number]['id'];

export function loadFixture(id: string): LectioDocument | null {
	if (id === 'photosynthesis-ref') return photosynthesis as unknown as LectioDocument;
	if (id === 'empty-document') return empty as unknown as LectioDocument;
	if (id === 'margin-stress') return marginStress as unknown as LectioDocument;
	if (id === 'shared-lesson-legacy') return sharedLessonLegacy as unknown as LectioDocument;
	if (id === 'shared-lesson-golden') return sharedLessonGolden as unknown as LectioDocument;
	if (id === 'oversized-stress') return oversizedStress as unknown as LectioDocument;
	if (id === 'shared-lesson-overlong') return sharedLessonOverlong as unknown as LectioDocument;
	if (id === 'track-c-photosynthesis-print') return trackCPhotosynthesis as unknown as LectioDocument;
	if (id === 'track-c-formula-print') return trackCFormula as unknown as LectioDocument;
	if (id === 'track-c-comparison-print') return trackCComparison as unknown as LectioDocument;
	if (id === 'phase5-photosynthesis-print') return phase5Photosynthesis as unknown as LectioDocument;
	return null;
}

