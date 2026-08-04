<script lang="ts">
	import { objectRecords } from '$lib/catalogue/objects';
	import { intentRecords } from '$lib/catalogue/compatibility';
	import { PAGE_OBJECTS } from '$lib/contract';
	import BlockView from '$lib/render/BlockView.svelte';
	import type { DocumentBlock } from '$lib/contract/document';
	import '$lib/print/base-print.css';

	const samples: Record<string, DocumentBlock> = {
		heading: {
			id: 's-h',
			object: 'heading',
			intent: undefined,
			position: 0,
			content: { level: 2, text: 'Sample heading', number: '1' }
		},
		prose: {
			id: 's-p',
			object: 'prose',
			intent: 'explain',
			position: 0,
			content: { paragraphs: ['Prose carries the main argument without a box or label.'] }
		},
		list: {
			id: 's-l',
			object: 'list',
			intent: 'summarise',
			position: 0,
			content: {
				style: 'unordered',
				items: [{ text: 'First point' }, { text: 'Second point' }]
			}
		},
		table: {
			id: 's-t',
			object: 'table',
			intent: 'compare',
			position: 0,
			content: {
				columns: [
					{ id: 'a', label: 'A' },
					{ id: 'b', label: 'B' }
				],
				rows: [{ cells: { a: 'Left', b: 'Right' } }]
			}
		},
		figure: {
			id: 's-f',
			object: 'figure',
			intent: 'show-structure',
			position: 0,
			content: {
				alt_text: 'Placeholder figure',
				caption: 'A figure stays with its caption.',
				asset: {
					kind: 'svg',
					status: 'ready',
					svg: "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 80'><rect width='240' height='80' fill='#eee' stroke='#777'/></svg>"
				}
			}
		},
		aside: {
			id: 's-a',
			object: 'aside',
			intent: 'warn',
			position: 0,
			content: { label: 'Watch out', body: 'Aside is the only boxed object.' }
		},
		'worked-example': {
			id: 's-w',
			object: 'worked-example',
			intent: 'demonstrate',
			position: 0,
			content: {
				problem: 'Solve for x when 2x = 8.',
				steps: [{ text: 'Divide both sides by 2.' }],
				answer: 'x = 4'
			}
		},
		questions: {
			id: 's-q',
			object: 'questions',
			intent: 'practise-independent',
			position: 0,
			content: {
				items: [{ id: 'q1', prompt: 'Write a short answer.', answer_lines: 2, marks: 2 }]
			}
		},
		choices: {
			id: 's-c',
			object: 'choices',
			intent: 'check-understanding',
			position: 0,
			content: {
				stem: 'Pick the best option.',
				options: [
					{ letter: 'A', text: 'First' },
					{ letter: 'B', text: 'Second' }
				]
			}
		},
		'answer-key': {
			id: 's-ak',
			object: 'answer-key',
			intent: 'answer-key',
			position: 0,
			content: {
				groups: [{ entries: [{ question_id: 'q1', answer: 'Sample answer' }] }]
			}
		}
	};
</script>

<h1>Page objects</h1>
<p>Ten stable physical forms. Intents change meaning without changing layout grammar.</p>

<div class="lectio-document lectio-page-flow">
	{#each PAGE_OBJECTS as objectId}
		<section class="sample">
			<header class="sample-meta">
				<strong>{objectId}</strong>
				<span>{objectRecords[objectId]?.holds}</span>
			</header>
			<div class="lectio-main">
				<BlockView block={samples[objectId]} />
			</div>
		</section>
	{/each}
</div>

<details>
	<summary>Intent catalogue ({Object.keys(intentRecords).length})</summary>
	<ul>
		{#each Object.entries(intentRecords) as [id, intent]}
			<li>
				<code>{id}</code> — {intent.teacher_label}: {intent.valid_objects.join(', ')}
			</li>
		{/each}
	</ul>
</details>

<style>
	.sample {
		margin-bottom: 1.5rem;
		padding-bottom: 1rem;
		border-bottom: 1px solid #ddd;
	}
	.sample-meta {
		display: flex;
		gap: 0.75rem;
		align-items: baseline;
		margin-bottom: 0.5rem;
		font-family: system-ui, sans-serif;
		font-size: 0.85rem;
		color: #555;
	}
	.sample-meta strong {
		color: #111;
	}
</style>
