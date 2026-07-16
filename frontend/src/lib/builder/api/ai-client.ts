import type { GradeBand } from 'lectio';
import { apiBaseUrl } from './public-env';

export type BlockGenerateModelTier = 'FAST' | 'STANDARD';

export interface BlockGenerateContextBlock {
	component_id: string;
	content: Record<string, unknown>;
}

export interface BlockGenerateRequest {
	lesson_id?: string;
	section_id?: string;
	component_id: string;
	mode?: 'fill' | 'improve' | 'custom';
	subject: string;
	focus: string;
	grade_band: GradeBand;
	context_blocks?: BlockGenerateContextBlock[];
	teacher_note?: string;
	existing_content?: Record<string, unknown>;
	model_tier?: BlockGenerateModelTier;
}

export interface BlockGenerateResponse {
	content: Record<string, unknown>;
}

export async function generateBlock(
	request: BlockGenerateRequest,
	token: string
): Promise<BlockGenerateResponse> {
	const base = apiBaseUrl();
	if (!base) {
		throw new Error('API URL is not configured (PUBLIC_API_URL).');
	}

	const response = await fetch(`${base}/api/v1/blocks/generate`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(request)
	});

	if (!response.ok) {
		let detail: string | undefined;
		try {
			const body = (await response.json()) as { detail?: unknown };
			if (typeof body?.detail === 'string') {
				detail = body.detail;
			} else if (Array.isArray(body?.detail)) {
				detail = JSON.stringify(body.detail);
			}
		} catch {
			/* ignore */
		}
		throw new Error(detail || `Generation failed (${response.status})`);
	}

	return response.json() as Promise<BlockGenerateResponse>;
}
