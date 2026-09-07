/** D3: /api/v1/packs retired. */

export async function getPackStatus(_packId: string): Promise<never> {
	throw new Error('packs API retired (D3)');
}

export async function listPacks(): Promise<never> {
	throw new Error('packs API retired (D3)');
}

export async function getPack(_packId: string): Promise<never> {
	throw new Error('packs API retired (D3)');
}

/* original exports retired; see git history for pre-D3 client */
