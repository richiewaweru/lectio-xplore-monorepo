import { getComponentsByGroup, type ComponentMeta } from 'lectio';

export interface PaletteOverlayGroup {
	group: {
		id: number;
		label: string;
		description: string;
		icon: string;
	};
	components: ComponentMeta[];
}

const GROUPS: PaletteOverlayGroup['group'][] = [
	{ id: 1, label: 'Structure', description: 'Orient and frame the lesson', icon: 'layout-list' },
	{ id: 2, label: 'Define', description: 'Introduce key terms and facts', icon: 'notebook-pen' },
	{ id: 3, label: 'Explain / Show how', description: 'Teach and model methods', icon: 'book-open' },
	{ id: 4, label: 'Practice', description: 'Give students a try', icon: 'pencil-ruler' },
	{ id: 5, label: 'Warn', description: 'Highlight common mistakes', icon: 'triangle-alert' },
	{ id: 6, label: 'Visualize', description: 'Use diagrams, media, and timelines', icon: 'image' },
	{ id: 7, label: 'Engage', description: 'Simulation and active exploration', icon: 'sparkles' }
];

function normalizeQuery(value: string): string {
	return value.trim().toLowerCase();
}

function matches(meta: ComponentMeta, normalizedQuery: string): boolean {
	if (!normalizedQuery) return true;
	return (
		meta.teacherLabel.toLowerCase().includes(normalizedQuery) ||
		meta.teacherDescription.toLowerCase().includes(normalizedQuery) ||
		meta.id.toLowerCase().includes(normalizedQuery)
	);
}

export function filterPaletteGroups(query: string): PaletteOverlayGroup[] {
	const normalizedQuery = normalizeQuery(query);
	return GROUPS.map((group) => ({
		group,
		components: getComponentsByGroup(group.id).filter((meta) => matches(meta, normalizedQuery))
	})).filter((entry) => entry.components.length > 0);
}
