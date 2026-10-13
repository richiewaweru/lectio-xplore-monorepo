import { buildApiUrl } from '$lib/api/client';
import { storeLearner } from './learner-fetch';

export const RESUME_NOT_FOUND = "We couldn't find that code. Check it and try again.";
export const RESUME_RATE_LIMITED = 'Too many tries. Wait a minute and try again.';
export const RESUME_FAILED = 'Something went wrong. Try again.';

/** Exchange a learner return code for a session, store it, and return the learner id. */
export async function resumeWithCode(code: string): Promise<string> {
	const trimmed = code.trim();
	let response: Response;
	try {
		response = await fetch(buildApiUrl('/api/v1/learn/learners/resume'), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ code: trimmed })
		});
	} catch {
		throw new Error(RESUME_FAILED);
	}
	if (response.status === 404) throw new Error(RESUME_NOT_FOUND);
	if (response.status === 429) throw new Error(RESUME_RATE_LIMITED);
	if (!response.ok) throw new Error(RESUME_FAILED);
	const body = await response.json();
	storeLearner({
		token: body.token,
		learnerId: body.learner_id,
		displayName: body.display_name ?? '',
		code: trimmed.toUpperCase().replace(/\s+/g, '-')
	});
	return body.learner_id as string;
}
