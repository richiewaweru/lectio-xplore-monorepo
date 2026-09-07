<script lang="ts">
	import { flushSyncQueue } from '$lib/builder/persistence/sync-queue';
	import { connectivityStore } from '$lib/builder/stores/connectivity.svelte';

	let prevOnline = $state<boolean | null>(null);

	$effect(() => {
		const now = connectivityStore.online;
		if (prevOnline === false && now === true) {
			void flushSyncQueue();
		}
		prevOnline = now;
	});
</script>
