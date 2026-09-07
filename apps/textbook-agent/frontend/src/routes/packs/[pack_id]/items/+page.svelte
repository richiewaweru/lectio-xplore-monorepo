<script lang="ts">
	import { page } from '$app/state';
	import ItemReview from '$lib/learn/authoring/builder/components/ItemReview.svelte';

	const packId = $derived(page.params.pack_id ?? '');
</script>

<ItemReview {packId} />
