import type { LectioContentModule } from '$lib/lectio/core/types';
import { buildLegacyComponentRegistryFromModules } from './build-legacy-registry';

import { lectioModule as cm0 } from '../components/section-header/module';
import { lectioModule as cm1 } from '../components/hook-hero/module';
import { lectioModule as cm2 } from '../components/explanation-block/module';
import { lectioModule as cm3 } from '../components/prerequisite-strip/module';
import { lectioModule as cm4 } from '../components/what-next-bridge/module';
import { lectioModule as cm5 } from '../components/interview-anchor/module';
import { lectioModule as cm6 } from '../components/callout-block/module';
import { lectioModule as cm7 } from '../components/summary-block/module';
import { lectioModule as cm8 } from '../components/section-divider/module';
import { lectioModule as cm9 } from '../components/definition-card/module';
import { lectioModule as cm10 } from '../components/definition-family/module';
import { lectioModule as cm11 } from '../components/glossary-rail/module';
import { lectioModule as cm12 } from '../components/glossary-inline/module';
import { lectioModule as cm13 } from '../components/insight-strip/module';
import { lectioModule as cm14 } from '../components/key-fact/module';
import { lectioModule as cm15 } from '../components/comparison-grid/module';
import { lectioModule as cm16 } from '../components/worked-example-card/module';
import { lectioModule as cm17 } from '../components/process-steps/module';
import { lectioModule as cm18 } from '../components/practice-stack/module';
import { lectioModule as cm19 } from '../components/quiz-check/module';
import { lectioModule as cm20 } from '../components/reflection-prompt/module';
import { lectioModule as cm21 } from '../components/student-textbox/module';
import { lectioModule as cm22 } from '../components/short-answer/module';
import { lectioModule as cm23 } from '../components/fill-in-blank/module';
import { lectioModule as cm24 } from '../components/pitfall-alert/module';
import { lectioModule as cm25 } from '../components/diagram-block/module';
import { lectioModule as cm26 } from '../components/diagram-compare/module';
import { lectioModule as cm27 } from '../components/diagram-series/module';
import { lectioModule as cm28 } from '../components/video-embed/module';
import { lectioModule as cm29 } from '../components/image-block/module';
import { lectioModule as cm30 } from '../components/timeline-block/module';
import { lectioModule as cm31 } from '../components/simulation-block/module';
import { lectioModule as cm32 } from '../components/answer-key/module';

/** Ordered list mirrors legacy `registry.ts` insertion order for stable manifests/exports */
export const lectioContentModules = [
	cm0,
	cm1,
	cm2,
	cm3,
	cm4,
	cm5,
	cm6,
	cm7,
	cm8,
	cm9,
	cm10,
	cm11,
	cm12,
	cm13,
	cm14,
	cm15,
	cm16,
	cm17,
	cm18,
	cm19,
	cm20,
	cm21,
	cm22,
	cm23,
	cm24,
	cm25,
	cm26,
	cm27,
	cm28,
	cm29,
	cm30,
	cm31,
	cm32
] as const satisfies readonly LectioContentModule[];

/** Alias kept for the v3 proposal wording — these modules exclude Svelte */
export const lectioComponentModules = lectioContentModules;
export const lectioComponents = lectioContentModules;
export type LectioContentModuleList = typeof lectioContentModules;
export type LectioComponentModuleList = LectioContentModuleList;

/**
 * Legacy registry map keyed by PascalCase importer token (historical `src/lib/components/lectio/*.svelte` naming).
 * Built from Lectio modules; includes normalized generation hints.
 */
export const componentRegistry = buildLegacyComponentRegistryFromModules([...lectioContentModules]);
