/**
 * Compile-time contract checks for discriminated DocumentBlock.
 * Run via `pnpm check` / tsc — these are type-level assertions.
 */
import type {
	DocumentBlock,
	HeadingBlock,
	ProseBlock,
	QuestionsBlock,
	AnswerKeyBlock
} from './document';

type Assert<T extends true> = T;
type Extends<A, B> = A extends B ? true : false;

type _headingHasNoIntent = Assert<
	Extends<HeadingBlock['intent'], undefined>
>;
type _proseHasIntent = Assert<Extends<ProseBlock['intent'], string>>;
type _questionsContent = Assert<
	Extends<QuestionsBlock['content'], { items: unknown[] }>
>;
type _answerKeyIntent = Assert<
	Extends<AnswerKeyBlock['intent'], 'answer-key'>
>;

declare const block: DocumentBlock;
if (block.object === 'prose') {
	const _paragraphs: unknown = block.content.paragraphs;
	void _paragraphs;
}
if (block.object === 'heading') {
	const _text: string = block.content.text;
	void _text;
}

export {};
