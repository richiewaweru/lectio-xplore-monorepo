import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const contractsDir = join(root, 'contracts');
const outDir = join(root, 'contracts');

const files = [
	'lectio-document-v2.schema.json',
	'object-catalogue.v1.json',
	'intent-catalogue.v1.json',
	'base-print.css'
] as const;

mkdirSync(outDir, { recursive: true });

const entries = files.map((name) => {
	const path = join(contractsDir, name);
	const bytes = readFileSync(path);
	return {
		path: name,
		sha256: createHash('sha256').update(bytes).digest('hex'),
		bytes: bytes.byteLength
	};
});

const manifest = {
	manifest_version: '1.0.0',
	package: '@lectio/page',
	contract_version: '1.0.0',
	generated_at: new Date().toISOString(),
	files: entries
};

writeFileSync(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');

// Keep architecture pack contracts in sync with FIX 1 schema
copyFileSync(
	join(contractsDir, 'lectio-document-v2.schema.json'),
	join(root, 'docs/architecture/page-objects/contracts/lectio-document-v2.schema.json')
);

console.log('Exported contracts + manifest.json');
for (const entry of entries) {
	console.log(`  ${entry.path}  ${entry.sha256.slice(0, 12)}…  ${entry.bytes}b`);
}
