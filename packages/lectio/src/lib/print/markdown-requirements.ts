export type PrintMarkdownRequirement = {
	field: string;
	renderer: 'renderBlockMarkdown' | 'renderInlineMarkdown';
};

export const PRINT_MARKDOWN_REQUIREMENTS: Record<string, PrintMarkdownRequirement[]> = {
	'src/lib/print/ExpandedSteps.svelte': [
		{ field: 'step.content', renderer: 'renderBlockMarkdown' },
		{ field: 'step.note', renderer: 'renderInlineMarkdown' }
	]
};
