export interface GoogleCredentialResponse {
	credential: string;
}

interface GoogleIdClient {
	initialize(config: GoogleIdConfiguration): void;
	renderButton(parent: HTMLElement, options: GoogleButtonConfiguration): void;
}

interface GoogleWindow extends Window {
	google?: {
		accounts?: {
			id?: GoogleIdClient;
		};
	};
}

interface GoogleIdConfiguration {
	client_id: string;
	callback: (response: GoogleCredentialResponse) => void;
}

interface GoogleButtonConfiguration {
	theme: 'outline';
	size: 'large';
	width: number;
	text: 'signin_with';
}

interface MountGoogleSignInOptions {
	clientId: string;
	buttonElement: HTMLElement;
	onCredential: (response: GoogleCredentialResponse) => void | Promise<void>;
}

const GOOGLE_SCRIPT_ID = 'google-identity-services';

let googleScriptPromise: Promise<GoogleIdClient> | null = null;
let initializedClientId: string | null = null;
let currentCredentialHandler:
	| ((response: GoogleCredentialResponse) => void | Promise<void>)
	| null = null;

function getGoogleIdClient(): GoogleIdClient | null {
	if (typeof window === 'undefined') {
		return null;
	}

	return (window as GoogleWindow).google?.accounts?.id ?? null;
}

export function buildGoogleIdConfiguration(
	clientId: string,
	callback: (response: GoogleCredentialResponse) => void
): GoogleIdConfiguration {
	return {
		client_id: clientId,
		callback
	};
}

export const GOOGLE_BUTTON_CONFIGURATION: GoogleButtonConfiguration = {
	theme: 'outline',
	size: 'large',
	width: 320,
	text: 'signin_with'
};

async function handleGoogleCredential(response: GoogleCredentialResponse): Promise<void> {
	await currentCredentialHandler?.(response);
}

function ensureGoogleScript(documentRef: Document): Promise<GoogleIdClient> {
	if (googleScriptPromise) {
		return googleScriptPromise;
	}

	googleScriptPromise = new Promise<GoogleIdClient>((resolve, reject) => {
		const existingClient = getGoogleIdClient();
		if (existingClient) {
			resolve(existingClient);
			return;
		}

		const existingScript = documentRef.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
		if (existingScript) {
			existingScript.addEventListener('load', () => {
				const loadedClient = getGoogleIdClient();
				if (loadedClient) {
					resolve(loadedClient);
					return;
				}
				googleScriptPromise = null;
				reject(new Error('Google Identity Services loaded without a usable client.'));
			});
			existingScript.addEventListener('error', () => {
				googleScriptPromise = null;
				reject(new Error('Failed to load Google Identity Services.'));
			});
			return;
		}

		const script = documentRef.createElement('script');
		script.id = GOOGLE_SCRIPT_ID;
		script.src = 'https://accounts.google.com/gsi/client';
		script.async = true;
		script.defer = true;
		script.onload = () => {
			const loadedClient = getGoogleIdClient();
			if (loadedClient) {
				resolve(loadedClient);
				return;
			}
			googleScriptPromise = null;
			reject(new Error('Google Identity Services loaded without a usable client.'));
		};
		script.onerror = () => {
			googleScriptPromise = null;
			reject(new Error('Failed to load Google Identity Services.'));
		};
		documentRef.head.appendChild(script);
	});

	return googleScriptPromise;
}

function initializeGoogleClient(googleId: GoogleIdClient, clientId: string) {
	if (initializedClientId === clientId) {
		return;
	}

	googleId.initialize(buildGoogleIdConfiguration(clientId, handleGoogleCredential));
	initializedClientId = clientId;
}

export async function mountGoogleSignIn({
	clientId,
	buttonElement,
	onCredential
}: MountGoogleSignInOptions): Promise<() => void> {
	currentCredentialHandler = onCredential;
	const googleId = await ensureGoogleScript(document);

	initializeGoogleClient(googleId, clientId);
	buttonElement.replaceChildren();
	googleId.renderButton(buttonElement, GOOGLE_BUTTON_CONFIGURATION);

	return () => undefined;
}
