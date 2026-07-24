import { browser } from '$app/environment';

export const STREAM_INTO_BUILDER_KEY = 'lectio:stream-into-builder';
export const NEW_AI_BLOCK_ASSIST_KEY = 'lectio:new-ai-block-assist';

export function getStreamIntoBuilder(): boolean {
	return browser && localStorage.getItem(STREAM_INTO_BUILDER_KEY) === 'true';
}

export function setStreamIntoBuilder(value: boolean): void {
	if (browser) localStorage.setItem(STREAM_INTO_BUILDER_KEY, String(value));
}

export function getNewAiBlockAssist(): boolean {
	return !browser || localStorage.getItem(NEW_AI_BLOCK_ASSIST_KEY) !== 'false';
}

export function setNewAiBlockAssist(value: boolean): void {
	if (browser) localStorage.setItem(NEW_AI_BLOCK_ASSIST_KEY, String(value));
}
