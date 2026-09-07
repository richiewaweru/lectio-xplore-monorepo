const DIAGRAM_COMPONENT_IDS = new Set(['diagram-block', 'diagram-compare', 'diagram-series']);

export function isDiagramComponentId(componentId: string): boolean {
	return DIAGRAM_COMPONENT_IDS.has(componentId);
}

export function svgFieldFor(componentId: string, mediaField: string): string | null {
	if (componentId === 'diagram-compare') {
		if (mediaField === 'before_media_id') return 'before_svg';
		if (mediaField === 'after_media_id') return 'after_svg';
		return null;
	}
	if (componentId === 'diagram-block' || componentId === 'diagram-series') {
		return 'svg_content';
	}
	return null;
}
