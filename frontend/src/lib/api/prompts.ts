import { apiFetch } from './client';

export type PromptListItem = {
	id: string;
	stage_label: string;
	editable: boolean;
	modified: boolean;
	version: number;
};

export type PromptDetail = PromptListItem & {
	text: string;
};

export async function listPrompts(): Promise<PromptListItem[]> {
	const response = await apiFetch('/api/v1/prompts');
	if (!response.ok) {
		throw new Error('Failed to load prompts.');
	}
	return response.json();
}

export async function getPrompt(promptId: string): Promise<PromptDetail> {
	const response = await apiFetch(`/api/v1/prompts/${encodeURIComponent(promptId)}`);
	if (!response.ok) {
		throw new Error('Failed to load prompt.');
	}
	return response.json();
}

export async function savePrompt(promptId: string, text: string): Promise<PromptDetail> {
	const response = await apiFetch(`/api/v1/prompts/${encodeURIComponent(promptId)}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ text })
	});
	if (!response.ok) {
		const detail = await response.text();
		throw new Error(detail || 'Failed to save prompt.');
	}
	return response.json();
}

export async function resetPrompt(promptId: string): Promise<PromptDetail> {
	const response = await apiFetch(`/api/v1/prompts/${encodeURIComponent(promptId)}`, {
		method: 'DELETE'
	});
	if (!response.ok) {
		throw new Error('Failed to reset prompt.');
	}
	return response.json();
}
