<svelte:head>
	<title>Multi-section app example Ã¢â‚¬â€ Lectio docs</title>
</svelte:head>

<p class="eyebrow">Integration</p>
<h1>Multi-section documents (Textbook Agent pattern)</h1>
<p class="lead">
	The Textbook Agent SvelteKit app consumes Lectio as a library: it resolves the documentÃ¢â‚¬â„¢s template
	and preset, wraps the page in <code>LectioThemeSurface</code>, and renders each section with the
	registry layout component (<code>template.render</code>), including skeleton states while sections
	stream in.
</p>

<h2>Imports</h2>
<pre><code>{`import { LectioThemeSurface, basePresetMap, templateRegistryMap } from 'lectio';
import type { SectionContent } from 'lectio';`}</code></pre>

<h2>Resolve template and preset</h2>
<p>
	Your document model should carry stable string IDs that match the Lectio registries (for example
	<code>template_id</code> and <code>preset_id</code>).
</p>
<pre><code>{`const template = $derived(templateRegistryMap[document.template_id]);
const preset = $derived(basePresetMap[document.preset_id] ?? null);`}</code></pre>

<h2>Wrap the document</h2>
<p>
	<code>LectioThemeSurface</code> applies preset tokens to descendants. Your shell (titles, context,
	meta badges) stays outside or inside the surface as you prefer; the example below mirrors the
	production layout structure in simplified form.
</p>
<pre><code>{`{#if template}
  <LectioThemeSurface {preset}>
    <div class="page-frame rh-gap-section">
      <header class="lesson-shell rh-pad-shell">
        <!-- document title, context, template name -->
      </header>

      <div class="section-stack">
        {#each sections as slot (slot.section_id)}
          {#if slot.status === 'ready' && slot.section}
            {@const TemplateRender = template.render}
            <article>
              <TemplateRender section={slot.section} />
            </article>
          {:else}
            <article aria-busy="true">
              <!-- skeleton UI -->
            </article>
          {/if}
        {/each}
      </div>
    </div>
  </LectioThemeSurface>
{:else}
  <p>Unknown Lectio template</p>
{/if}`}</code></pre>

<h2>Why not TemplateRuntimeSurface here?</h2>
<p>
	<code>TemplateRuntimeSurface</code> is ideal for a <strong>single</strong> section in isolation.
	Multi-section apps usually need custom chrome, ordering, streaming, and per-slot loading UI. Calling
	<code>template.render</code> directly keeps one theme wrapper and full control of the stack.
</p>

<h2>Frontend checklist</h2>
<ul>
	<li>Import <code>lectio/theme.css</code> in the app stylesheet (Tailwind entry).</li>
	<li>Align <code>template_id</code> and <code>preset_id</code> with template contracts and <code>allowed_presets</code>.</li>
	<li>Type section payloads as <code>SectionContent</code> (or validate before render).</li>
</ul>

<div class="doc-callout">
	<p>
		This narrative matches the Textbook Agent component
		<code>LectioDocumentView.svelte</code> in the sibling project; adapt slot shapes and CSS classes
		to your own data layer.
	</p>
</div>
