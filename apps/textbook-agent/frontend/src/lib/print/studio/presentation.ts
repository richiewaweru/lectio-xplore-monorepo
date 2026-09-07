import type { SectionRole, VisualPolicy } from '$lib/types';

const ROLE_LABELS: Record<SectionRole, string> = {
	intro: 'Intro',
	explain: 'Explain',
	practice: 'Practice',
	summary: 'Summary',
	process: 'Process',
	compare: 'Compare',
	timeline: 'Timeline',
	visual: 'Visual',
	discover: 'Discover'
};

const ROLE_TONES: Record<SectionRole, 'intro' | 'explain' | 'practice' | 'summary' | 'neutral'> = {
	intro: 'intro',
	explain: 'explain',
	practice: 'practice',
	summary: 'summary',
	process: 'explain',
	compare: 'practice',
	timeline: 'summary',
	visual: 'intro',
	discover: 'neutral'
};

const HEAVY_COMPONENTS = new Set([
	'diagram-block',
	'diagram-series',
	'diagram-compare',
	'simulation-block',
	'simulation'
]);

const COMPONENT_LABELS: Record<string, string> = {
	'section-header':       'Section Header',
	'hook-hero':            'Opening Hook',
	'explanation-block':    'Core Explanation',
	'prerequisite-strip':   'Prerequisites',
	'what-next-bridge':     'What Next',
	'interview-anchor':     'Explain Out Loud',
	'callout-block':        'Callout',
	'summary-block':        'Summary',
	'section-divider':      'Section Divider',
	'definition-card':      'Key Term Definition',
	'definition-family':    'Definition Family',
	'glossary-rail':        'Glossary Rail',
	'glossary-inline':      'Inline Glossary',
	'insight-strip':        'Insight Strip',
	'key-fact':             'Key Fact',
	'comparison-grid':      'Comparison Table',
	'worked-example-card':  'Worked Example',
	'process-steps':        'Process Steps',
	'practice-stack':       'Practice Problems',
	'student-textbox':      'Student Write-in',
	'short-answer':         'Short Answer',
	'fill-in-blank':        'Fill in the Blank',
	'pitfall-alert':        'Common Mistake Alert',
	'reflection-prompt':    'Reflection Prompt',
	'timeline-block':       'Timeline',
	'diagram-block':        'Diagram',
	'diagram-series':       'Diagram Series',
	'diagram-compare':      'Before / After Diagram',
	'simulation-block':     'Interactive Simulation',
};

export function roleLabel(role: SectionRole): string {
	return ROLE_LABELS[role] ?? role;
}

export function roleTone(role: SectionRole): 'intro' | 'explain' | 'practice' | 'summary' | 'neutral' {
	return ROLE_TONES[role] ?? 'neutral';
}

export function isHeavyComponent(componentId: string): boolean {
	return HEAVY_COMPONENTS.has(componentId);
}

export function componentLabel(
	componentId: string,
	contractComponents?: Array<{ id: string; teacher_label?: string }>
): string {
	if (contractComponents) {
		const match = contractComponents.find((c) => c.id === componentId);
		if (match?.teacher_label) return match.teacher_label;
	}
	return COMPONENT_LABELS[componentId] ?? componentId.replace(/-/g, ' ');
}

export function visualPolicyLabel(policy: VisualPolicy | null): string | null {
	if (!policy?.required) {
		return null;
	}

	if (policy.mode === 'svg') {
		return 'SVG diagram';
	}

	if (policy.mode === 'image') {
		return 'Image diagram';
	}

	return 'Visual required';
}

const VISUAL_INTENT_LABELS: Record<string, string> = {
	demonstrate_process: 'demonstrate process',
	compare_variants:    'compare variants',
	show_realism:        'show realism',
	explain_structure:   'explain structure',
};

export function visualPolicyDetail(
	policy: VisualPolicy | null
): { chip: string; goal: string | null } | null {
	if (!policy?.required) return null;
	const modeLabel = policy.mode === 'svg' ? 'SVG' : policy.mode === 'image' ? 'Image' : 'Visual';
	const intentLabel = policy.intent
		? (VISUAL_INTENT_LABELS[policy.intent] ?? policy.intent)
		: null;
	const chip = intentLabel ? `${modeLabel} · ${intentLabel}` : modeLabel;
	return { chip, goal: policy.goal ?? null };
}
