import { apiBaseUrl } from './public-env';

export async function regenerateGenerationVisual(
	generationId: string,
	visualId: string,
	teacherHint: string,
	token: string
): Promise<Record<string, unknown>> {
	const response = await fetch(`${apiBaseUrl()}/api/v1/v3/generations/${generationId}/visuals/${visualId}/regenerate`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
		body: JSON.stringify({ teacher_hint: teacherHint.trim() || undefined })
	});
	if (!response.ok) throw new Error(`Visual regeneration failed (${response.status})`);
	return response.json() as Promise<Record<string, unknown>>;
}
