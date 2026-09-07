export type { ComponentMeta, TeachingIntent } from './component-meta';

export {
	applyGenerationHintNormalization,
	buildLegacyComponentRegistryFromModules,
	buildLectioManifest,
	componentRegistry,
	defaultGenerationHint,
	PALETTE_GROUPS,
	getComponentById,
	getComponentFieldMap,
	getComponentsByGroup,
	getComponentsByIntent,
	getComponentsForSubject,
	getStableComponents,
	lectioComponentModules,
	lectioComponents,
	lectioContentModules
} from '$lib/lectio/registry';
export type { PaletteGroup } from '$lib/lectio/registry';
