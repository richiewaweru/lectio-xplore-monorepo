import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	GOOGLE_BUTTON_CONFIGURATION,
	buildGoogleIdConfiguration,
	mountGoogleSignIn
} from './google';

describe('google identity configuration', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('uses the standard client id and callback configuration', () => {
		const callback = vi.fn();

		const config = buildGoogleIdConfiguration('client-id', callback);

		expect(config).toEqual({
			client_id: 'client-id',
			callback
		});
	});

	it('renders the standard google sign-in button configuration', () => {
		expect(GOOGLE_BUTTON_CONFIGURATION).toEqual({
			theme: 'outline',
			size: 'large',
			width: 320,
			text: 'signin_with'
		});
	});

	it('initializes google identity services and renders the button', async () => {
		const initialize = vi.fn();
		const renderButton = vi.fn();

		vi.stubGlobal('window', {
			google: {
				accounts: {
					id: {
						initialize,
						renderButton
					}
				}
			}
		});
		vi.stubGlobal('document', {});

		const buttonElement = {
			replaceChildren: vi.fn()
		} as unknown as HTMLElement;
		const callback = vi.fn();

		await mountGoogleSignIn({
			clientId: 'standard-client-id',
			buttonElement,
			onCredential: callback
		});

		expect(initialize).toHaveBeenCalledTimes(1);
		expect(initialize).toHaveBeenCalledWith({
			client_id: 'standard-client-id',
			callback: expect.any(Function)
		});
		expect(buttonElement.replaceChildren).toHaveBeenCalledTimes(1);
		expect(renderButton).toHaveBeenCalledWith(buttonElement, GOOGLE_BUTTON_CONFIGURATION);
	});
});
