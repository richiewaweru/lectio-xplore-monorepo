import type { TeachingIntent } from '$lib/schema/component-meta';

import { componentRegistry } from './components';

export interface PaletteGroup {
	id: TeachingIntent;
	label: string;
	description: string;
	icon: string;
	componentIds: string[];
}

const GROUP_DEFINITIONS: Array<Omit<PaletteGroup, 'componentIds'>> = [
	{ id: 'explain', label: 'Explain', description: 'Teach concepts clearly', icon: 'book-open' },
	{ id: 'define', label: 'Define', description: 'Introduce key terms', icon: 'notebook-pen' },
	{ id: 'show-how', label: 'Show how', description: 'Demonstrate a method', icon: 'list-checks' },
	{ id: 'practice', label: 'Practice', description: 'Give students a try', icon: 'pencil-ruler' },
	{ id: 'reflect', label: 'Reflect', description: 'Prompt student thinking', icon: 'message-circle' },
	{ id: 'warn', label: 'Warn', description: 'Highlight common mistakes', icon: 'triangle-alert' },
	{
		id: 'visualize',
		label: 'Visualize',
		description: 'Use diagrams, media, and timelines',
		icon: 'image'
	},
	{ id: 'structure', label: 'Structure', description: 'Organize lesson flow', icon: 'layout-list' },
	{ id: 'engage', label: 'Engage', description: 'Hook and energize learners', icon: 'sparkles' }
];

const allComponents = Object.values(componentRegistry);

export const PALETTE_GROUPS: PaletteGroup[] = GROUP_DEFINITIONS.map((group) => ({
	...group,
	componentIds: allComponents
		.filter((component) => component.teachingIntent === group.id && component.sectionField !== null)
		.map((component) => component.id)
}));

