import { dev } from '$app/environment';
import { error, json } from '@sveltejs/kit';
import golden from '$lib/learn/document/dev-fixtures/golden.json';
import legacy from '$lib/learn/document/dev-fixtures/legacy.json';
import overlong from '$lib/learn/document/dev-fixtures/overlong.json';
import g3Photosynthesis from '$lib/learn/document/dev-fixtures/g3-photosynthesis.json';
import g3Formula from '$lib/learn/document/dev-fixtures/g3-formula.json';
import g3Comparison from '$lib/learn/document/dev-fixtures/g3-comparison.json';

const FIXTURES = {
	golden,
	legacy,
	overlong,
	'g3-photosynthesis': g3Photosynthesis,
	'g3-formula': g3Formula,
	'g3-comparison': g3Comparison
} as const;

export function GET({ params }) {
	if (!dev) error(404, 'Development fixture previews are disabled.');
	const document = FIXTURES[params.fixture as keyof typeof FIXTURES];
	if (!document) error(404, 'Unknown shared lesson fixture.');
	return json(document);
}
