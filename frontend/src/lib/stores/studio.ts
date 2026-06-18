import { writable } from 'svelte/store';

import type { GenerationAccepted, GenerationDocument } from '$lib/types';

type StudioGenerationState = {
	accepted: GenerationAccepted | null;
	document: GenerationDocument | null;
	connectionBanner: string | null;
};

export const generationState = writable<StudioGenerationState>({
	accepted: null,
	document: null,
	connectionBanner: null
});

export function resetGenerationState(): void {
	generationState.set({
		accepted: null,
		document: null,
		connectionBanner: null
	});
}

export function setGenerationAccepted(accepted: StudioGenerationState['accepted']): void {
	generationState.update((state) => ({
		...state,
		accepted
	}));
}

export function setGenerationDocument(document: StudioGenerationState['document']): void {
	generationState.update((state) => ({
		...state,
		document
	}));
}

export function setGenerationBanner(message: string | null): void {
	generationState.update((state) => ({
		...state,
		connectionBanner: message
	}));
}
