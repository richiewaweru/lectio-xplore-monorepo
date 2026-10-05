/**
 * Total parser for the learner-facing inline markup language.
 *
 * It returns an AST rather than HTML. Consumers must escape text when
 * rendering it, which keeps literal unmatched markers and HTML safe.
 */

export type InlineKind = 'text' | 'strong' | 'emphasis' | 'subscript' | 'superscript'

export type InlineNode =
	| { type: 'text'; value: string }
	| { type: Exclude<InlineKind, 'text'>; children: InlineNode[] }

function append(nodes: InlineNode[], node: InlineNode): void {
	if (node.type === 'text' && node.value.length === 0) return
	const previous = nodes.at(-1)
	if (previous?.type === 'text' && node.type === 'text') {
		previous.value += node.value
	} else {
		nodes.push(node)
	}
}

function parseSegment(value: string, allowEmphasis: boolean, allowSubSup: boolean): InlineNode[] {
	const nodes: InlineNode[] = []
	let textStart = 0
	let index = 0

	const flush = (until: number): void => {
		if (until > textStart) append(nodes, { type: 'text', value: value.slice(textStart, until) })
	}

	while (index < value.length) {
		let marker: string | undefined
		let kind: Exclude<InlineKind, 'text'> | undefined
		let nested = false
		if (value.startsWith('**', index)) {
			marker = '**'
			kind = 'strong'
			nested = true
		} else if (allowEmphasis && value[index] === '*') {
			marker = '*'
			kind = 'emphasis'
		} else if (allowSubSup && (value[index] === '~' || value[index] === '^')) {
			marker = value[index]
			kind = marker === '~' ? 'subscript' : 'superscript'
		}

		if (!marker || !kind) {
			index += 1
			continue
		}

		const close = value.indexOf(marker, index + marker.length)
		if (close < 0) {
			index += marker.length
			continue
		}

		flush(index)
		const body = value.slice(index + marker.length, close)
		const children: InlineNode[] = nested
			? parseSegment(body, false, true)
			: body
				? [{ type: 'text', value: body }]
				: []
		append(nodes, { type: kind, children })
		index = close + marker.length
		textStart = index
	}

	flush(value.length)
	return nodes
}

export function parseInlineMarkup(value: string): InlineNode[] {
	return parseSegment(value, true, true)
}
