<svelte:head>
	<title>Best practices — Lectio docs</title>
</svelte:head>

<p class="eyebrow">Best practices</p>
<h1>Teaching moves, validation, and polish</h1>
<p class="lead">
	Lectio components are named for what they do in a lesson, not for generic UI roles. Lean on registry
	metadata and validation to keep generated content honest and teachable.
</p>

<h2>Design for the learner arc</h2>
<ul>
	<li>
		<strong>Match template intent</strong> — Pick a template whose contract fits the instructional
		flow (compare/contrast vs lab vs formal track). Components listed in <code>always_present</code>
		are there for a reason.
	</li>
	<li>
		<strong>Respect capacities</strong> — Registry entries document min/max items, hint limits, and
		behaviour modes. Exceeding them triggers validation warnings and can clutter the UI.
	</li>
	<li>
		<strong>Use the right cognitive job</strong> — When browsing <a href="/components">components</a>,
		read the cognitive job and group; it encodes how the piece should feel in context.
	</li>
</ul>

<h2>Validate early</h2>
<p>
	During integration, call <code>warnIfInvalid(section)</code> in development builds or log
	<code>validateSection(section)</code> server-side when ingesting generated JSON. Fix upstream
	generation when warnings appear instead of silencing them.
</p>

<h2>Math and media</h2>
<p>
	KaTeX is bundled for math strings in content. Keep expressions within supported LaTeX subsets your
	pipeline can guarantee. For <code>SimulationBlock</code>, prefer structured fields; when using
	<code>html_content</code>, treat it as trusted or sanitized in your app policy.
</p>

<h2>Accessibility and motion</h2>
<p>
	Prefer semantic structure from templates over ad-hoc div stacks. Respect reduced-motion preferences
	already handled in shared styles; avoid adding disruptive animation outside the design system.
</p>

<h2>Keep contracts fresh</h2>
<p>
	If you fork or extend Lectio, run <code>npm run export-contracts</code> after registry or template
	changes so external agents never train against stale JSON.
</p>
