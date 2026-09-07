<svelte:head>
	<title>Reference — Lectio docs</title>
</svelte:head>

<p class="eyebrow">Reference</p>
<h1>Source material in the repository</h1>
<p class="lead">
	These Markdown files stay in the repo for editors and agents. The live site adds guided tutorials
	under <a href="/docs">/docs</a>; use both when onboarding.
</p>

<h2>Library guides</h2>
<ul>
	<li>
		<code>docs/reference/component-guide.md</code> — Public surface, showcase routes, contract export
		summary, fork checklist, SimulationBlock notes.
	</li>
	<li>
		<code>docs/reference/registry-field-map.md</code> — <code>sectionField</code>, field map
		derivation, pipeline JSON usage, extension workflow.
	</li>
</ul>

<h2>Component notes</h2>
<p>Shorter per-component reference (purpose, inputs, behaviours):</p>
<ul>
	<li><code>docs/components/comparison-grid.md</code></li>
	<li><code>docs/components/timeline-block.md</code></li>
</ul>

<h2>Root README</h2>
<p>
	<code>README.md</code> — Quick install, dependency list, full component table, template IDs,
	validation helpers, preset helpers, and export-contracts usage.
</p>

<h2>Showcase routes</h2>
<ul>
	<li><a href="/components">/components</a> — Component gallery with anchors per registry id.</li>
	<li><a href="/templates">/templates</a> — Template gallery and detail pages.</li>
</ul>

<h2>TypeScript sources of truth</h2>
<ul>
	<li><code>src/lib/schema/types.ts</code> — <code>SectionContent</code> and content interfaces.</li>
	<li><code>src/lib/schema/registry.ts</code> — Component metadata.</li>
	<li><code>src/lib/templates/registry.ts</code> — Template contracts and <code>render</code> components.</li>
	<li><code>src/lib/index.ts</code> — Public exports.</li>
</ul>

<h2>Project directory arrangement</h2>
<pre><code>src/lib/
├── index.ts              # Public exports (package entry)
├── schema/               # Core contracts, registry, validation
├── teacher/              # Lesson document + builder authoring helpers
├── templates/            # Template contracts, registry, runtime resolver
├── components/           # Lectio blocks and internal UI primitives
├── presets/              # Theme preset definitions
├── print/                # Print utility components
├── utils/                # Shared utilities (print context, markdown)
└── dev/                  # Internal sample content and fixtures
</code></pre>
