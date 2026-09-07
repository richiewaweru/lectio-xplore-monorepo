import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';
import type { V3ChunkedPlanState } from '$lib/types/v3';

export type ConceptCardMisconception = {
	id: string;
	description: string;
	source: 'drafted' | 'teacher';
};

export type ConceptCard = {
	id: string;
	pack_id: string;
	title: string;
	objective: string;
	prereqs: string[];
	misconceptions: ConceptCardMisconception[];
	no_known_misconceptions: boolean;
	teacher_edited: boolean;
	source_card_id?: string | null;
	source_pack_id?: string | null;
};

export type CardLibraryItem = {
	card_id: string;
	pack_id: string;
	slug: string;
	title: string;
	objective: string;
	prereqs: string[];
	misconceptions: ConceptCardMisconception[];
	created_at: string | null;
};

export async function getConceptCards(packId: string): Promise<ConceptCard[]> {
	const response = await apiFetch(`/api/v1/v3/packs/${encodeURIComponent(packId)}/cards`);
	await ensureOk(response, 'Could not load concept cards.');
	return response.json() as Promise<ConceptCard[]>;
}

export async function updateConceptCard(
	packId: string,
	card: Pick<ConceptCard, 'id' | 'title' | 'objective' | 'misconceptions'>
): Promise<ConceptCard> {
	const response = await apiFetch(
		`/api/v1/v3/packs/${encodeURIComponent(packId)}/cards/${encodeURIComponent(card.id)}`,
		{
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				title: card.title,
				objective: card.objective,
				misconceptions: card.misconceptions
			})
		}
	);
	await ensureOk(response, 'Could not save this concept card.');
	return response.json() as Promise<ConceptCard>;
}

export async function approveConceptCards(packId: string): Promise<V3ChunkedPlanState> {
	const response = await apiFetch(
		`/api/v1/v3/packs/${encodeURIComponent(packId)}/cards/approve`,
		{ method: 'POST' }
	);
	await ensureOk(response, 'Could not approve concept cards.');
	return response.json() as Promise<V3ChunkedPlanState>;
}

export async function searchConceptCards(search = ''): Promise<CardLibraryItem[]> {
	const response = await apiFetch(
		`/api/v1/v3/cards?search=${encodeURIComponent(search)}&limit=40`
	);
	await ensureOk(response, 'Could not search your concept-card library.');
	return response.json() as Promise<CardLibraryItem[]>;
}

export async function reuseConceptCard(
	packId: string,
	sourceCardId: string,
	targetCardId: string
): Promise<ConceptCard> {
	const response = await apiFetch(
		`/api/v1/v3/packs/${encodeURIComponent(packId)}/cards/reuse`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				source_card_id: sourceCardId,
				target_card_id: targetCardId
			})
		}
	);
	await ensureOk(response, 'Could not reuse this concept card.');
	return response.json() as Promise<ConceptCard>;
}
