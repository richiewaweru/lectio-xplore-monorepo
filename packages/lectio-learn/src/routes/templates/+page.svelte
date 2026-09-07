<script lang="ts">
	import TemplatesGallery from '$lib/templates/TemplatesGallery.svelte';
	import { templateRegistry } from '$lib/templates/registry';
</script>

<div class="page-frame">
	<TemplatesGallery templates={templateRegistry.map((definition) => definition.contract)} />
</div>
