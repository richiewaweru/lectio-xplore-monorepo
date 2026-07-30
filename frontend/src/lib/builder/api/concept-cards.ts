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
