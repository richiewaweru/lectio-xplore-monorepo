<script lang="ts">
	let {
		isCorrect,
		showAnswers = true
	}: { isCorrect: boolean; showAnswers?: boolean } = $props();
</script>

{#if showAnswers && isCorrect}
	<span class="answer-marker" aria-label="Correct answer">✓</span>
{/if}

<style>
	.answer-marker {
		display: inline-block;
		margin-left: 0.5rem;
		font-weight: 700;
		color: #059669;
	}

	@media print {
		.answer-marker {
			color: #000;
		}
	}
</style>
