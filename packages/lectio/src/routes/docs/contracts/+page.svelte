<svelte:head>
	<title>Contracts and pipelines - Lectio docs</title>
</svelte:head>

<p class="eyebrow">Contracts and pipelines</p>
<h1>JSON exports for agents and backends</h1>
<p class="lead">
	External pipelines (Python services, LLM agents, validators) should read exported artifacts from this
	repository - not import TypeScript from <code>src/</code>. The export script keeps a single
	consumer-facing contract in sync with component-owned sources.
</p>

<h2>Run the exporter</h2>
<pre><code>npm run export-contracts
npm run export-contracts -- --out /path/to/output
LECTIO_CONTRACTS_DIR=/path/to/output npm run export-contracts</code></pre>

<h2>Artifacts</h2>
<table>
	<thead>
		<tr>
			<th>File</th>
			<th>Contents</th>
		</tr>
	</thead>
	<tbody>
		<tr>
			<td><code>section-content-schema.json</code></td>
			<td>Canonical JSON schema for <code>SectionContent</code></td>
		</tr>
		<tr>
			<td><code>lectio-content-contract.json</code></td>
			<td>Unified content contract: template constraints, planner index, component cards, field contracts, examples, print behavior, and excluded component policy</td>
		</tr>
		<tr>
			<td><code>generated/python/section_content.py</code></td>
			<td>Official Pydantic v2 adapter generated from the SectionContent schema</td>
		</tr>
	</tbody>
</table>

<h2>Migration note</h2>
<p>
	Older fragmented exports were removed in favor of <code>lectio-content-contract.json</code>.
	Consumers should migrate any reads of <code>component-registry.json</code>,
	<code>component-field-map.json</code>, <code>manifest.json</code>, and per-template JSON files
	to the unified contract.
</p>

<h2>When to re-run</h2>
<p>
	Whenever templates, components, or presets change, run <code>npm run package</code> for consumers and
	<code>npm run export-contracts</code> for pipeline snapshots before you publish or deploy generators.
</p>

<div class="doc-callout">
	<p>
		Authoritative deep dive (repo file): <code>docs/reference/registry-field-map.md</code> - same
		architecture as summarized here, with sample JSON and file pointers.
	</p>
</div>
