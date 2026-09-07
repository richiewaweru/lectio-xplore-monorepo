<script lang="ts">
	let { class: className = '' }: { class?: string } = $props();
</script>

<span class={className} aria-hidden="true" data-testid="icon"></span>
