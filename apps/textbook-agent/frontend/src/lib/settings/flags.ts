import { browser } from '$app/environment';

export const NEW_AI_BLOCK_ASSIST_KEY = 'lectio:new-ai-block-assist';

export function getNewAiBlockAssist(): boolean {
	return !browser || localStorage.getItem(NEW_AI_BLOCK_ASSIST_KEY) !== 'false';
}

export function setNewAiBlockAssist(value: boolean): void {
	if (browser) localStorage.setItem(NEW_AI_BLOCK_ASSIST_KEY, String(value));
}
