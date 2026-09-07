import type { Component } from 'svelte';

import * as lectioComponents from '$lib/components/lectio';

import { componentRegistry } from './components';

export type RuntimeBlockComponent = Component<any>;

const componentsByRegistryKey = lectioComponents as Record<string, RuntimeBlockComponent>;

function buildComponentRenderMap(): Record<string, RuntimeBlockComponent> {
	const map: Record<string, RuntimeBlockComponent> = {};

	for (const [registryKey, meta] of Object.entries(componentRegistry)) {
		const component = componentsByRegistryKey[registryKey];
		if (!component) {
			throw new Error(
				`[Lectio] Missing runtime component for registry key "${registryKey}" (${meta.id}).`
			);
		}
		map[meta.id] = component;
	}

	return map;
}

export const componentRenderMap = buildComponentRenderMap();
