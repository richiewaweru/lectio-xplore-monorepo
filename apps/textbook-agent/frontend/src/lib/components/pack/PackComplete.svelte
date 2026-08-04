<script lang="ts">
	import type { PackStatusResponse } from '$lib/types/learning-pack';

	let {
		packStatus,
		onNewPack
	}: { packStatus: PackStatusResponse; onNewPack: () => void } = $props();
</script>

<section class="complete">
	<div>
		<p class="eyebrow">Pack {packStatus.status}</p>
		<h1>{packStatus.completed_count} resources ready</h1>
		<p>{packStatus.subject} · {packStatus.topic}</p>
	</div>

	<div class="grid">
		{#each packStatus.resources as resource}
			<article>
				<strong>{resource.label}</strong>
				<p>{resource.resource_type.replaceAll('_', ' ')} · {resource.status}</p>
				{#if resource.generation_id}
					<a href={`/studio/generations/${resource.generation_id}`}>Open</a>
				{/if}
			</article>
		{/each}
	</div>

	<button onclick={onNewPack}>Start new pack</button>
</section>

<style>
	.complete {
		display: grid;
		gap: 1rem;
	}

	.eyebrow,
	h1,
	p {
		margin: 0;
	}

	.eyebrow {
		font-size: 0.78rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.75rem;
	}

	article {
		display: grid;
		gap: 0.45rem;
		padding: 1rem;
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.68);
	}

	a {
		color: #24436a;
		font-weight: 700;
		text-decoration: none;
	}

	button {
		width: fit-content;
		border-radius: 999px;
		border: 1px solid rgba(36, 52, 63, 0.18);
		background: #24343f;
		color: #fff;
		padding: 0.5rem 0.85rem;
		cursor: pointer;
	}
</style>

