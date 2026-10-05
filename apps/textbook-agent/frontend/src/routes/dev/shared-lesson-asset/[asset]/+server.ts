import { dev } from '$app/environment';
import { error } from '@sveltejs/kit';
import seedlings from '$lib/learn/document/dev-fixtures/seedlings.svg?raw';

export function GET({ params }) {
	if (!dev) error(404, 'Development fixture assets are disabled.');
	if (params.asset !== 'seedlings.svg') error(404, 'Unknown shared lesson fixture asset.');
	return new Response(seedlings, {
		headers: { 'content-type': 'image/svg+xml; charset=utf-8', 'cache-control': 'no-store' }
	});
}
