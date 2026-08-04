export class ApiError extends Error {
	status: number;
	detail: string;
	errorType: string | null;

	constructor(status: number, detail: string, errorType: string | null = null) {
		super(detail);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
		this.errorType = errorType;
	}
}

interface ApiErrorPayload {
	detail?: string | Record<string, unknown>;
	error_type?: string;
}

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

async function readErrorPayload(response: Response): Promise<ApiErrorPayload | null> {
	const contentType = response.headers.get('content-type') ?? '';

	if (contentType.includes('application/json')) {
		try {
			const payload = (await response.json()) as unknown;
			if (isObject(payload)) {
				const d = payload.detail;
				let detail: string | Record<string, unknown> | undefined;
				if (typeof d === 'string') {
					detail = d;
				} else if (isObject(d) && !Array.isArray(d)) {
					detail = d;
				}
				return {
					detail,
					error_type: typeof payload.error_type === 'string' ? payload.error_type : undefined
				};
			}
		} catch {
			return null;
		}
		return null;
	}

	try {
		const text = (await response.text()).trim();
		return text ? { detail: text } : null;
	} catch {
		return null;
	}
}

function formatStructuredDetail(
	raw: Record<string, unknown>,
	fallbackMessage: string
): string {
	const msg =
		typeof raw.message === 'string' && raw.message.length > 0 ? raw.message : fallbackMessage;
	const dbg = raw.debug;
	const suffix =
		dbg !== undefined && dbg !== null
			? `\n\nDebug:\n${JSON.stringify(dbg, null, 2)}`
			: '';
	return `${msg}${suffix}`;
}

export async function ensureOk(response: Response, fallbackMessage: string): Promise<Response> {
	if (response.ok) {
		return response;
	}

	const payload = await readErrorPayload(response);
	const raw = payload?.detail;

	if (response.status === 429) {
		const msg =
			typeof raw === 'string'
				? raw
				: 'You already have the maximum number of active generations. Please wait for one to finish before starting another.';
		throw new ApiError(response.status, msg, payload?.error_type ?? null);
	}

	if (isObject(raw) && !Array.isArray(raw) && ('message' in raw || 'debug' in raw)) {
		throw new ApiError(
			response.status,
			formatStructuredDetail(raw, fallbackMessage),
			payload?.error_type ?? null
		);
	}

	const detail =
		typeof raw === 'string' ? raw : (response.statusText || fallbackMessage);
	throw new ApiError(response.status, detail, payload?.error_type ?? null);
}

export function isApiError(error: unknown): error is ApiError {
	return error instanceof ApiError;
}
