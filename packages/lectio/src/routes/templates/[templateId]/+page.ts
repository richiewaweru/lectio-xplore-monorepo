import { error } from '@sveltejs/kit';

import { getTemplateById } from '$lib/templates/registry';

export function load({ params }: { params: { templateId: string } }) {
	if (!getTemplateById(params.templateId)) {
		throw error(404, 'Template not found');
	}

	return {
		templateId: params.templateId
	};
}
