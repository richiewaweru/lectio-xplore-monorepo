/**
 * Exact payload and response schemas per interaction kind.
 *
 * These are the schemas the writer view publishes and the runtime view
 * validates against. A generic `Record<string, unknown>` is not a payload
 * contract, so every kind gets a closed schema with required fields, id
 * uniqueness and finite-number constraints where they apply.
 */

import type { JsonSchema } from './types';

const OPTION_LIST: JsonSchema = {
	type: 'array',
	minItems: 2,
	uniqueItems: true,
	items: {
		type: 'object',
		additionalProperties: false,
		required: ['id', 'text'],
		properties: {
			id: { type: 'string', minLength: 1 },
			text: { type: 'string', minLength: 1 },
			explanation: { type: 'string' }
		}
	}
};

const PAIR_LIST: JsonSchema = {
	type: 'array',
	minItems: 1,
	items: {
		type: 'object',
		additionalProperties: false,
		required: ['left', 'right'],
		properties: {
			left: { type: 'string', minLength: 1 },
			right: { type: 'string', minLength: 1 }
		}
	}
};

export const CONFIG_SCHEMAS: Record<string, JsonSchema> = {
	choice: {
		$id: 'learn/choice/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['options', 'correct_option_id'],
		properties: {
			options: OPTION_LIST,
			correct_option_id: { type: 'string', minLength: 1 },
			presentation: { enum: ['text', 'image'] }
		}
	},
	'multi-select': {
		$id: 'learn/multi-select/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['options', 'correct_option_ids'],
		properties: {
			options: OPTION_LIST,
			correct_option_ids: {
				type: 'array',
				minItems: 1,
				uniqueItems: true,
				items: { type: 'string', minLength: 1 }
			}
		}
	},
	'fill-blank': {
		$id: 'learn/fill-blank/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['answers'],
		properties: {
			answers: {
				type: 'array',
				minItems: 1,
				items: {
					oneOf: [
						{ type: 'string', minLength: 1 },
						{
							type: 'array',
							minItems: 1,
							uniqueItems: true,
							items: { type: 'string', minLength: 1 }
						}
					]
				}
			},
			blank_ids: {
				type: 'array',
				minItems: 1,
				uniqueItems: true,
				items: { type: 'string', minLength: 1 }
			},
			case_sensitive: { type: 'boolean' }
		}
	},
	numeric: {
		$id: 'learn/numeric/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['value'],
		properties: {
			value: { type: 'number' },
			tolerance: { type: 'number', minimum: 0 },
			unit: { type: 'string', minLength: 1 }
		}
	},
	'short-response': {
		$id: 'learn/short-response/config.v1',
		type: 'object',
		required: ['evaluation'],
		oneOf: [
			{
				additionalProperties: false,
				required: ['evaluation', 'accepted_answers'],
				properties: {
					evaluation: { const: 'accepted-answers' },
					accepted_answers: {
						type: 'array',
						minItems: 1,
						uniqueItems: true,
						items: { type: 'string', minLength: 1 }
					},
					case_sensitive: { type: 'boolean' },
					max_words: { type: 'integer', minimum: 1 }
				}
			},
			{
				additionalProperties: false,
				required: ['evaluation'],
				properties: {
					evaluation: { const: 'teacher-review' },
					review_guidance: { type: 'string', minLength: 1 },
					max_words: { type: 'integer', minimum: 1 }
				}
			}
		]
	},
	'match-pairs': {
		$id: 'learn/match-pairs/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['pairs'],
		properties: { pairs: PAIR_LIST }
	},
	classify: {
		$id: 'learn/classify/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['pairs'],
		properties: {
			// `left` is the item, `right` is its single category. Single-category
			// membership is what the evaluator implements, so it is what the
			// schema declares.
			pairs: PAIR_LIST,
			categories: {
				type: 'array',
				minItems: 2,
				uniqueItems: true,
				items: {
					type: 'object',
					additionalProperties: false,
					required: ['id', 'label'],
					properties: {
						id: { type: 'string', minLength: 1 },
						label: { type: 'string', minLength: 1 }
					}
				}
			}
		}
	},
	sequence: {
		$id: 'learn/sequence/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['order'],
		properties: {
			order: {
				type: 'array',
				minItems: 2,
				uniqueItems: true,
				items: { type: 'string', minLength: 1 }
			},
			items: {
				type: 'array',
				minItems: 2,
				items: {
					type: 'object',
					additionalProperties: false,
					required: ['id', 'label'],
					properties: {
						id: { type: 'string', minLength: 1 },
						label: { type: 'string', minLength: 1 }
					}
				}
			}
		}
	},
	'image-hotspot': {
		$id: 'learn/image-hotspot/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['correct_option_id'],
		properties: {
			correct_option_id: { type: 'string', minLength: 1 },
			image: {
				type: 'object',
				additionalProperties: false,
				required: ['asset_id', 'alt'],
				properties: {
					asset_id: { type: 'string', minLength: 1 },
					alt: { type: 'string', minLength: 1 }
				}
			},
			regions: {
				type: 'array',
				minItems: 2,
				items: {
					type: 'object',
					additionalProperties: false,
					required: ['id', 'label', 'x', 'y'],
					properties: {
						id: { type: 'string', minLength: 1 },
						label: { type: 'string', minLength: 1 },
						// Percentages of the asset's intrinsic box, origin top-left.
						x: { type: 'number', minimum: 0, maximum: 100 },
						y: { type: 'number', minimum: 0, maximum: 100 }
					}
				}
			}
		}
	},
	'drag-label': {
		$id: 'learn/drag-label/config.v1',
		type: 'object',
		additionalProperties: false,
		required: ['pairs'],
		properties: {
			pairs: PAIR_LIST,
			image: {
				type: 'object',
				additionalProperties: false,
				required: ['asset_id', 'alt'],
				properties: {
					asset_id: { type: 'string', minLength: 1 },
					alt: { type: 'string', minLength: 1 }
				}
			}
		}
	}
};

export const RESPONSE_SCHEMAS: Record<string, JsonSchema> = {
	choice: {
		$id: 'learn/choice/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['selected_option_id'],
		properties: { selected_option_id: { type: 'string', minLength: 1 } }
	},
	'multi-select': {
		$id: 'learn/multi-select/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['selected_option_ids'],
		properties: {
			selected_option_ids: {
				type: 'array',
				uniqueItems: true,
				items: { type: 'string', minLength: 1 }
			}
		}
	},
	'fill-blank': {
		$id: 'learn/fill-blank/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['blanks'],
		properties: { blanks: { type: 'array', minItems: 1, items: { type: 'string' } } }
	},
	numeric: {
		$id: 'learn/numeric/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['value'],
		properties: { value: { type: 'number' } }
	},
	'short-response': {
		$id: 'learn/short-response/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['text'],
		properties: { text: { type: 'string', minLength: 1 } }
	},
	'match-pairs': {
		$id: 'learn/match-pairs/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['matches'],
		properties: { matches: PAIR_LIST }
	},
	classify: {
		$id: 'learn/classify/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['matches'],
		properties: { matches: PAIR_LIST }
	},
	sequence: {
		$id: 'learn/sequence/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['order'],
		properties: {
			order: { type: 'array', minItems: 2, uniqueItems: true, items: { type: 'string' } }
		}
	},
	'image-hotspot': {
		$id: 'learn/image-hotspot/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['selected_option_id'],
		properties: { selected_option_id: { type: 'string', minLength: 1 } }
	},
	'drag-label': {
		$id: 'learn/drag-label/response.v1',
		type: 'object',
		additionalProperties: false,
		required: ['matches'],
		properties: { matches: PAIR_LIST }
	}
};
