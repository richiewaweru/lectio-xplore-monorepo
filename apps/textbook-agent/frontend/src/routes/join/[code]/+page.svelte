<script lang="ts">
	import { page } from '$app/state';
	import JoinClass from '$lib/learn/student/JoinClass.svelte';
</script>

<JoinClass code={page.params.code ?? ''} />
