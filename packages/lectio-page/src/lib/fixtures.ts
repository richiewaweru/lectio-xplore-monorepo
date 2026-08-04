import type { LectioDocument } from '$lib/contract/document';
import photosynthesis from '../../fixtures/photosynthesis-ref.json';
import empty from '../../fixtures/empty-document.json';

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
	}
] as const;

export type FixtureId = (typeof fixtureIndex)[number]['id'];

export function loadFixture(id: string): LectioDocument | null {
	if (id === 'photosynthesis-ref') return photosynthesis as LectioDocument;
	if (id === 'empty-document') return empty as LectioDocument;
	return null;
}
