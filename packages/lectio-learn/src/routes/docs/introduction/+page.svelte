<svelte:head>
	<title>Introduction — Lectio docs</title>
</svelte:head>

<p class="eyebrow">Introduction</p>
<h1>What is Lectio?</h1>
<p class="lead">
	Lectio is an educational component library for <strong class="text-foreground">Svelte 5</strong> and
	<strong class="text-foreground">SvelteKit</strong>. It turns typed lesson data into coherent
	instructional UI: hooks, explanations, definitions, practice, comparisons, diagrams, timelines,
	and more — each component encodes a <em>teaching move</em>, not a generic widget.
</p>

<h2>What you build with it</h2>
<ul>
	<li>
		<strong>Single sections</strong> — Render one <code>SectionContent</code> object with a chosen
		template surface, or compose individual lectio components when you control layout yourself.
	</li>
	<li>
		<strong>Multi-section documents</strong> — Wrap many sections in a shared theme (preset) and loop
		registry template layouts, the pattern used by the Textbook Agent frontend.
	</li>
	<li>
		<strong>Pipeline-aware generation</strong> — Export JSON contracts so agents and backends can
		learn required fields, capacities, and allowed presets without importing TypeScript from this
		repo.
	</li>
</ul>

<h2>How this site is organized</h2>
<ul>
	<li>
		<a href="/components">Components</a> — Interactive gallery of all stable lectio components with
		sample content.
	</li>
	<li>
		<a href="/templates">Templates</a> — Thirteen registry-backed lesson templates with previews and
		per-template detail pages.
	</li>
	<li>
		<a href="/docs">Documentation</a> (this section) — Installation, concepts, rendering patterns,
		contracts, and integration examples.
	</li>
</ul>

<div class="doc-callout">
	<p>
		Lectio is distributed as an npm-style package built with <code>@sveltejs/package</code>. Consumers
		import from <code>lectio</code> and pull in <code>lectio/theme.css</code> once for tokens,
		presets, KaTeX styling, and shared utilities.
	</p>
</div>
