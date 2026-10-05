import { dev } from '$app/environment';
import { error, json } from '@sveltejs/kit';
import golden from '$lib/learn/document/dev-fixtures/golden.json';
import legacy from '$lib/learn/document/dev-fixtures/legacy.json';
import overlong from '$lib/learn/document/dev-fixtures/overlong.json';

const FIXTURES = { golden, legacy, overlong } as const;

export function GET({ params }) {
	if (!dev) error(404, 'Development fixture previews are disabled.');
	const document = FIXTURES[params.fixture as keyof typeof FIXTURES];
	if (!document) error(404, 'Unknown shared lesson fixture.');
	return json(document);
}
