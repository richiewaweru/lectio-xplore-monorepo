<script lang="ts">
	import TemplateDetailView from '$lib/templates/TemplateDetailView.svelte';

	let { data }: { data: { templateId: string } } = $props();
</script>

<TemplateDetailView templateId={data.templateId} />
