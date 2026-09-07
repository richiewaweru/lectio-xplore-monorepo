<svelte:head>
	<title>Installation — Lectio docs</title>
</svelte:head>

<p class="eyebrow">Installation</p>
<h1>Install and wire Lectio in your app</h1>
<p class="lead">
	Build the library from this repository, reference it from your SvelteKit project, add peer
	dependencies, and import the shared theme stylesheet so templates and components look correct.
</p>

<h2>1. Build the package</h2>
<pre><code>cd lectio
npm install
npm run package</code></pre>
<p>This compiles <code>src/lib/</code> into <code>dist/</code> with compiled Svelte and TypeScript declarations.</p>

<h2>2. Depend on the package</h2>
<p>In the consuming project <code>package.json</code>:</p>
<pre><code class="language-json">{`{
  "dependencies": {
    "lectio": "file:../lectio"
  }
}`}</code></pre>
<p>Then run <code>npm install</code> (adjust the path to match your folder layout).</p>

<h2>3. Install runtime dependencies</h2>
<p>Your app needs Lectio’s runtime stack alongside the package:</p>
<pre><code>npm install katex lucide-svelte bits-ui clsx tailwind-merge
npm install -D @tailwindcss/vite tailwindcss @types/katex</code></pre>

<h2>4. Import the theme once</h2>
<p>In your app stylesheet (Tailwind v4 entry):</p>
<pre><code>@import 'tailwindcss';
@import 'lectio/theme.css';</code></pre>
<p>
	This brings in design tokens, preset-scoped surfaces, KaTeX rules, and utilities that templates
	expect.
</p>

<h2>5. Use the public API</h2>
<p>Everything ships from a single entry:</p>
<pre><code>{`import {
  TemplateRuntimeSurface,
  TemplatePreviewSurface,
  validateSection,
  warnIfInvalid
} from 'lectio';
import type { SectionContent } from 'lectio';`}</code></pre>

<h2>After you change Lectio</h2>
<p>
	Run <code>npm run package</code> again in the Lectio repo so <code>dist/</code> updates; your
	consumer will pick up changes on the next install or link refresh.
</p>

<h2>Optional: contract export for pipelines</h2>
<p>
	If agents or a backend need structural metadata, run <code>npm run export-contracts</code> in
	Lectio and read JSON from the output directory (see
	<a href="/docs/contracts">Contracts and pipelines</a>).
</p>
