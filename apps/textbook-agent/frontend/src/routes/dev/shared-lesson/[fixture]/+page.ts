import { dev } from '$app/environment';
import { error } from '@sveltejs/kit';

const FIXTURES = new Set(['golden', 'legacy', 'overlong']);

export const load = async ({ fetch, params }) => {
	if (!dev) error(404, 'Development fixture previews are disabled.');
	if (!FIXTURES.has(params.fixture)) error(404, 'Unknown shared lesson fixture.');
	const response = await fetch(`/dev/shared-lesson/${params.fixture}`);
	if (!response.ok) error(404, 'Shared lesson fixture is unavailable.');
	return { document: await response.json() };
};
