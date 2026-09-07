import type { ComponentMeta, TeachingIntent } from '$lib/schema/component-meta';

import { componentRegistry } from './components';

export type { LectioComponentModuleList, LectioContentModuleList } from './components';
export {
	lectioContentModules,
	lectioComponentModules,
	lectioComponents,
	componentRegistry
} from './components';

export {
	buildLegacyComponentRegistryFromModules,
	applyGenerationHintNormalization,
	defaultGenerationHint
} from './build-legacy-registry';

export { getComponentFieldMap } from './field-map';
export type { PaletteGroup } from './palette-groups';
export { PALETTE_GROUPS } from './palette-groups';

export type { LectioManifestV3 } from './manifest';
export { buildLectioManifest } from './manifest';

/** Components ready to use (stable + beta) */
export function getStableComponents(): ComponentMeta[] {
	return Object.values(componentRegistry).filter(
		(component) => component.status === 'stable' || component.status === 'beta'
	);
}

export function getComponentsByGroup(group: number): ComponentMeta[] {
	return Object.values(componentRegistry).filter((component) => component.group === group);
}

export function getComponentsForSubject(subject: string): ComponentMeta[] {
	return Object.values(componentRegistry).filter(
		(component) => component.subjects.includes('universal') || component.subjects.includes(subject)
	);
}

export function getComponentsByIntent(intent: TeachingIntent): ComponentMeta[] {
	return Object.values(componentRegistry).filter((component) => component.teachingIntent === intent);
}

export function getComponentById(componentId: string): ComponentMeta | undefined {
	return Object.values(componentRegistry).find((component) => component.id === componentId);
}
