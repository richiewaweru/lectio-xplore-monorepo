import { getContext, setContext } from 'svelte';

import type { DocumentStore } from '$lib/builder/stores/document.svelte';

const DOCUMENT_STORE_KEY = Symbol('lessonBuilderDocumentStore');

export function setDocumentStoreContext(store: DocumentStore): void {
	setContext(DOCUMENT_STORE_KEY, store);
}

export function getDocumentStoreContext(): DocumentStore | undefined {
	return getContext<DocumentStore>(DOCUMENT_STORE_KEY);
}
