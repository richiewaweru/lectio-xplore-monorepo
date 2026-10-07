<script lang="ts">
	import { onMount } from 'svelte';
	import { getQualityFlags, type QualityFlag } from '$lib/api/shared-documents';

	interface Props {
		editableLessonId?: string | null;
		generationId?: string | null;
	}

	let { editableLessonId = null, generationId = null }: Props = $props();

	let flags = $state<QualityFlag[]>([]);

	onMount(async () => {
		try {
			const target = editableLessonId
				? { editableLessonId }
				: generationId
					? { generationId }
					: null;
			if (!target) return;
			flags = (await getQualityFlags(target)).flags;
		} catch {
			// Quality notes are advisory: never block or break the editor.
			flags = [];
		}
	});
</script>

{#if flags.length > 0}
	<details class="quality-notes print:hidden" data-testid="quality-notes" open>
		<summary>Quality notes ({flags.length})</summary>
		<p class="hint">
			These are suggestions from automatic review. Nothing is blocked, so you can edit the lesson
			here and use it as it is.
		</p>
		<ul>
			{#each flags as flag, index (`${flag.code}-${flag.section_id}-${index}`)}
				<li>
					<div class="head">
						<strong>{flag.message}</strong>
					</div>
					<p class="meta">Section: {flag.next_section_title ?? flag.section_id}</p>
					<p class="suggestion">Suggestion: {flag.required_correction}</p>
				</li>
			{/each}
		</ul>
	</details>
{/if}

<style>
	.quality-notes {
		margin-bottom: 0.75rem;
		border: 1px solid #fcd34d;
		border-radius: 0.5rem;
		background: #fffbeb;
		padding: 0.625rem 0.875rem;
		font-size: 0.875rem;
		color: #78350f;
	}
	summary {
		cursor: pointer;
		font-weight: 600;
	}
	.hint,
	.meta,
	.suggestion {
		margin: 0.25rem 0 0;
	}
	.meta {
		font-size: 0.75rem;
		opacity: 0.8;
	}
	ul {
		margin: 0.5rem 0 0;
		padding-left: 1.1rem;
	}
	li + li {
		margin-top: 0.5rem;
	}
</style>
