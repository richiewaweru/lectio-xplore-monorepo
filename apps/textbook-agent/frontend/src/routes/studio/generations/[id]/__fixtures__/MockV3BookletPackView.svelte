<script lang="ts">
	export let pack: { sections: unknown[] };
	export let status: string;
</script>

<div data-testid="v3-pack-view">
	<span>{status}</span>
	<span>{pack.sections.length}</span>
</div>
