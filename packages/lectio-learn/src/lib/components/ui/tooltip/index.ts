import type { Component } from 'svelte';
import { Tooltip as TooltipPrimitive } from 'bits-ui';

type PrimitiveComponent = Component<any>;

const Root = TooltipPrimitive.Root as PrimitiveComponent;
const Trigger = TooltipPrimitive.Trigger as PrimitiveComponent;
const Content = TooltipPrimitive.Content as PrimitiveComponent;
const Provider = TooltipPrimitive.Provider as PrimitiveComponent;

export {
	Root,
	Root as Tooltip,
	Trigger,
	Trigger as TooltipTrigger,
	Content,
	Content as TooltipContent,
	Provider,
	Provider as TooltipProvider,
};
