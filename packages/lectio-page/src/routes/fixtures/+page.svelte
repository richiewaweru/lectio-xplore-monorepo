<script lang="ts">
	import { fixtureIndex } from '$lib/fixtures';
</script>

<h1>Fixtures</h1>
<p>Hand-authored LectioDocument v2 samples for visual and contract checks.</p>

<ul class="list">
	{#each fixtureIndex as fixture}
		<li>
			<a href={`/fixtures/${fixture.id}`}>
				<strong>{fixture.title}</strong>
				<span>{fixture.description}</span>
			</a>
		</li>
	{/each}
</ul>

<style>
	.list {
		list-style: none;
		padding: 0;
		max-width: 40rem;
	}
	.list a {
		display: grid;
		gap: 0.25rem;
		padding: 0.9rem 0;
		border-bottom: 1px solid #ddd;
		text-decoration: none;
		color: inherit;
	}
	.list span {
		color: #555;
		font-size: 0.95rem;
	}
</style>
