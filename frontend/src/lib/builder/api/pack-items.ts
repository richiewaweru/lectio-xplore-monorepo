import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';
import type { ConceptCardMisconception } from '$lib/builder/api/concept-cards';

export type PackItemOption = {
	key: string;
	text: string;
	correct: boolean;
	diagnoses: string | null;
	teacher_edited: boolean;
};

export type PackItem = {
	id: string;
	question_id: string;
	prompt_text: string;
	options: PackItemOption[];
	stale: boolean;
	teacher_edited: boolean;
};

export type CardItemReview = {
	card_id: string;
	card_title: string;
	misconceptions: ConceptCardMisconception[];
	items: PackItem[];
	coverage: Record<string, number>;
	missing_misconceptions: string[];
	unmapped_options: number;
	stale: boolean;
};

export async function getPackItems(packId: string): Promise<CardItemReview[]> {
	const response = await apiFetch(`/api/v1/v3/packs/${encodeURIComponent(packId)}/items`);
	await ensureOk(response, 'Could not load the shared quiz.');
	return response.json() as Promise<CardItemReview[]>;
}

export async function updatePackItem(
	packId: string,
	item: Pick<PackItem, 'id' | 'prompt_text' | 'options'>
): Promise<CardItemReview> {
	const response = await apiFetch(
		`/api/v1/v3/packs/${encodeURIComponent(packId)}/items/${encodeURIComponent(item.id)}`,
		{
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				prompt_text: item.prompt_text,
				options: item.options
			})
		}
	);
	await ensureOk(response, 'Could not save this quiz item.');
	return response.json() as Promise<CardItemReview>;
}

export async function regenerateCardItems(
	packId: string,
	cardId: string
): Promise<CardItemReview> {
	const response = await apiFetch(
		`/api/v1/v3/packs/${encodeURIComponent(packId)}/cards/${encodeURIComponent(cardId)}/items/regenerate`,
		{ method: 'POST' }
	);
	await ensureOk(response, 'Could not regenerate this card’s quiz.');
	return response.json() as Promise<CardItemReview>;
}
