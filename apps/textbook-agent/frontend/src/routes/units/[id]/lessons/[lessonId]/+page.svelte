<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	const unitId = page.params.id ?? '';
	const lessonId = page.params.lessonId ?? '';
	void goto(`/units/${encodeURIComponent(unitId)}/lessons/${encodeURIComponent(lessonId)}/plan`, {
		replaceState: true
	});
</script>

<p>Opening plan…</p>
