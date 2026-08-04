import { error } from '@sveltejs/kit';
import { loadFixture, fixtureIndex } from '$lib/fixtures';
import { validateDocument } from '$lib/contract';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => {
	const doc = loadFixture(params.id);
	if (!doc) error(404, 'Fixture not found');
	const issues = validateDocument(doc);
	const meta = fixtureIndex.find((f) => f.id === params.id);
	return { doc, issues, meta };
};
