<script lang="ts">
	import type { ParagraphNode } from '../types';

	interface Props {
		node: ParagraphNode;
	}

	let { node }: Props = $props();
</script>

<p class="learn-paragraph" data-testid="paragraph-node" data-node-id={node.id}>
	{node.text}
</p>

<style>
	.learn-paragraph {
		margin: 0;
		font-size: 15px;
		line-height: 1.65;
		color: var(--ink, #1a1a1a);
	}
</style>
