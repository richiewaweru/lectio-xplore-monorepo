import type { GradeBand } from '@lectio/learn';

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

/** D3: /api/v1/blocks/generate retired. */
export async function generateBlock(
	_request: BlockGenerateRequest,
	_token: string
): Promise<BlockGenerateResponse> {
	throw new Error('Block AI assist was retired with the non-Unit blocks/generate API (D3).');
}
