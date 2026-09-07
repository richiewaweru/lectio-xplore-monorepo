export type LectioFieldFormat =
	| 'plain_text'
	| 'plain_text_short'
	| 'plain_quote_text'
	| 'plain_phrase_list'
	| 'inline_markdown'
	| 'block_markdown'
	| 'latex_raw'
	| 'media_url'
	| 'accessibility_text'
	| 'positioned_callouts'
	| 'enum'
	| 'number'
	| 'number_of_print_lines'
	| 'boolean'
	| 'structured_object'
	| 'structured_array';

export interface LectioFieldContract {
	format: LectioFieldFormat;
	description: string;
	renderBehavior?: string;
	constraints?: string[];
}

export interface LectioContentContract {
	componentId: string;
	sectionField: string | null;
	fieldContracts: Record<string, LectioFieldContract>;
	componentConstraints?: string[];
}
