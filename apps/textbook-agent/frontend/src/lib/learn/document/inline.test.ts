import vectors from './inline-vectors.json'
import { describe, expect, it } from 'vitest'
import { parseInlineMarkup } from './inline'

describe('parseInlineMarkup', () => {
	for (const vector of vectors) {
		it(vector.name, () => {
			expect(parseInlineMarkup(vector.input)).toEqual(vector.expected)
		})
	}
})
