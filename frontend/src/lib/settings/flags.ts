import { browser } from '$app/environment';

export const STREAM_INTO_BUILDER_KEY = 'lectio:stream-into-builder';

export function getStreamIntoBuilder(): boolean {
	return browser && localStorage.getItem(STREAM_INTO_BUILDER_KEY) === 'true';
}

export function setStreamIntoBuilder(value: boolean): void {
	if (browser) localStorage.setItem(STREAM_INTO_BUILDER_KEY, String(value));
}
