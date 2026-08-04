<script lang="ts">
	import { fixtureIndex } from '$lib/fixtures';
	import { PAGE_OBJECTS, INTENT_IDS } from '$lib/contract';
</script>

<section class="hero">
	<p class="eyebrow">Page-object experiment</p>
	<h1>@lectio/page</h1>
	<p class="lede">
		Print-native document grammar: ten page objects and thirty-two pedagogical intents.
		The printed booklet is the product; the screen is a review surface.
	</p>
</section>

<section class="grid">
	<a class="card" href="/fixtures/photosynthesis-ref">
		<h2>Photosynthesis fixture</h2>
		<p>Three hand-authored pages using the full object vocabulary.</p>
	</a>
	<a class="card" href="/objects">
		<h2>Object gallery</h2>
		<p>{PAGE_OBJECTS.length} objects · {INTENT_IDS.length} intents</p>
	</a>
	<a class="card" href="/fixtures">
		<h2>All fixtures</h2>
		<p>{fixtureIndex.length} documents ready to inspect</p>
	</a>
</section>

<section>
	<h2>Hard rules in force</h2>
	<ul>
		<li>No print-media stripping — one rendering only</li>
		<li>Only <code>aside</code> may use a border</li>
		<li>No object or intent names printed on student pages</li>
		<li>Answer lines are real borders, not background images</li>
	</ul>
</section>

<style>
	.hero {
		max-width: 42rem;
		margin-bottom: 2rem;
	}
	.eyebrow {
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-size: 0.75rem;
		color: #666;
	}
	h1 {
		font-family: var(--font-serif);
		font-size: 2.6rem;
		margin: 0.2rem 0 0.6rem;
	}
	.lede {
		font-size: 1.1rem;
		line-height: 1.5;
		color: #333;
	}
	.grid {
		display: grid;
		gap: 1rem;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		margin-bottom: 2rem;
	}
	.card {
		display: block;
		padding: 1.1rem 1.2rem;
		background: #fff;
		border: 1px solid #ddd;
		text-decoration: none;
		color: inherit;
	}
	.card h2 {
		margin: 0 0 0.4rem;
		font-size: 1.1rem;
	}
	.card p {
		margin: 0;
		color: #555;
		font-size: 0.95rem;
	}
	ul {
		line-height: 1.7;
	}
	code {
		font-size: 0.9em;
	}
</style>
