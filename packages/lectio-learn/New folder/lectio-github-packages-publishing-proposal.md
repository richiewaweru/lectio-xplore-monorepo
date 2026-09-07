# Lectio GitHub Packages Publishing Implementation Proposal

**Status**: Ready for Implementation  
**Target**: `richiewaweru/lectio` repository  
**Estimated Effort**: 2-3 hours  
**Dependencies**: GitHub repository access, existing TypeScript build pipeline

---

## Executive Summary

This proposal implements automated npm package publishing for Lectio via GitHub Packages, enabling the Textbook Generator and Lesson Builder to consume Lectio as a versioned npm dependency instead of relying on local file references or manual syncing.

**Key outcomes:**
- Automated publish on git tags via GitHub Actions
- Semantic versioning with contract stability guarantees
- Consumer setup for Generator frontend (Vercel) and Lesson Builder
- Rollback and version management procedures

**What this does NOT do:**
- Does not change Lectio's internal structure or component API
- Does not modify existing `export-contracts` script
- Does not create new TypeScript build tooling (uses existing `tsc`)
- Does not implement npm provenance or advanced security features (future enhancement)

---

## Pre-conditions Checklist

**Developer must verify these before starting:**

- [ ] Lectio repository exists at `richiewaweru/lectio`
- [ ] Repository has working TypeScript build (`npm run build` succeeds)
- [ ] `export-contracts` script exists and produces `contracts/` output
- [ ] Current build output directory is `dist/` (or confirm actual location)
- [ ] GitHub Actions is enabled on the repository
- [ ] You have admin access to the repository (needed for secrets/permissions)
- [ ] You have a GitHub Personal Access Token with `read:packages` scope (for testing consumer setup)

**Confirm current structure:**
```bash
# Expected in Lectio repo root:
# - package.json
# - tsconfig.json
# - src/ (source TypeScript files)
# - dist/ (compiled output, gitignored)
# - contracts/ (exported JSON schemas)
```

---

## Phase 1: Package Configuration

### Task 1.1: Update `package.json`

**Location**: `lectio/package.json`

**Action**: Add/modify the following fields (AI agent should merge with existing content):

```json
{
  "name": "@richiewaweru/lectio",
  "version": "0.1.0",
  "description": "Component library for pedagogically-structured lesson content",
  "author": "Richie Waweru",
  "license": "UNLICENSED",
  "private": false,
  
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    },
    "./contracts": "./contracts/types.json",
    "./components/*": "./dist/components/*.js"
  },
  
  "files": [
    "dist",
    "contracts",
    "README.md",
    "CHANGELOG.md"
  ],
  
  "publishConfig": {
    "registry": "https://npm.pkg.github.com",
    "access": "restricted"
  },
  
  "repository": {
    "type": "git",
    "url": "git+https://github.com/richiewaweru/lectio.git"
  },
  
  "scripts": {
    "build": "tsc",
    "export-contracts": "existing script here - DO NOT MODIFY",
    "prepublishOnly": "npm run build && npm run export-contracts",
    "version": "git add -A",
    "postversion": "git push && git push --tags"
  },
  
  "keywords": [
    "education",
    "edtech",
    "component-library",
    "lesson-content",
    "svelte"
  ]
}
```

**Important notes:**
- Set `version` to `0.1.0` as starting point (pre-1.0 signals contract instability)
- `private: false` is required for publishing
- `files` array controls what gets published (only dist + contracts)
- `prepublishOnly` ensures build happens before publish
- Preserve existing dependencies, devDependencies, and other scripts

---

### Task 1.2: Create `.npmrc`

**Location**: `lectio/.npmrc`

**Action**: Create new file

```
@richiewaweru:registry=https://npm.pkg.github.com
```

**Purpose**: Tells npm to publish `@richiewaweru` scoped packages to GitHub Packages

---

### Task 1.3: Update `.gitignore`

**Location**: `lectio/.gitignore`

**Action**: Ensure these entries exist (add if missing):

```
# Build outputs
dist/
*.tsbuildinfo

# npm
node_modules/
*.log
npm-debug.log*

# Don't ignore contracts - these should be published
!contracts/
```

**Note**: Contracts directory should be version-controlled since it's part of the published package

---

### Task 1.4: Create `README.md` (if missing)

**Location**: `lectio/README.md`

**Action**: Create if not present (this gets published with the package)

```markdown
# Lectio

Component library for pedagogically-structured lesson content.

## Installation

```bash
npm install @richiewaweru/lectio
```

## Usage

```typescript
import { types } from '@richiewaweru/lectio/contracts';
import { SomeComponent } from '@richiewaweru/lectio';
```

## Contract Stability

This package follows semantic versioning with contract guarantees:

- **PATCH** (0.1.x): Bug fixes, no contract changes
- **MINOR** (0.x.0): New components/templates, backward-compatible contract additions
- **MAJOR** (x.0.0): Breaking contract changes (types.ts structure changes)

During `0.x` phase, minor versions may introduce larger changes. Lock to exact versions in production.

## Development

See main project documentation.
```

---

### Task 1.5: Create `CHANGELOG.md`

**Location**: `lectio/CHANGELOG.md`

**Action**: Create new file

```markdown
# Changelog

All notable changes to Lectio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-01-XX

### Added
- Initial package structure
- 23 components across 7 categories
- 12 named templates + open-canvas fallback
- Contract export system (types.json)
- Blue classroom preset

### Notes
- First published version to GitHub Packages
- Pre-1.0: contracts may change in minor versions
```

**Update instruction**: Developer should fill in actual release date when publishing

---

## Phase 2: GitHub Actions Publishing Workflow

### Task 2.1: Create Publish Workflow

**Location**: `lectio/.github/workflows/publish.yml`

**Action**: Create new file (create `.github/workflows/` directories if missing)

```yaml
name: Publish to GitHub Packages

on:
  push:
    tags:
      - 'v*.*.*'  # Trigger on semver tags like v0.1.0

jobs:
  publish:
    runs-on: ubuntu-latest
    
    permissions:
      contents: read
      packages: write
      
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://npm.pkg.github.com'
          scope: '@richiewaweru'
          
      - name: Install dependencies
        run: npm ci
        
      - name: Build package
        run: npm run build
        
      - name: Export contracts
        run: npm run export-contracts
        
      - name: Verify build outputs
        run: |
          test -d dist || (echo "dist/ not found" && exit 1)
          test -f dist/index.js || (echo "dist/index.js not found" && exit 1)
          test -f dist/index.d.ts || (echo "dist/index.d.ts not found" && exit 1)
          test -d contracts || (echo "contracts/ not found" && exit 1)
          echo "Build verification passed"
          
      - name: Publish to GitHub Packages
        run: npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Create GitHub Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref_name }}
          body: |
            Published version ${{ github.ref_name }} to GitHub Packages
            
            Install: `npm install @richiewaweru/lectio@${{ github.ref_name }}`
          draft: false
          prerelease: false
```

**Key features:**
- Triggers on any tag matching semver pattern (v0.1.0, v1.2.3)
- Runs verification before publish to catch build failures
- Automatically creates GitHub release for changelog tracking
- Uses built-in `GITHUB_TOKEN` (no manual secret setup needed)

---

### Task 2.2: Create Build Verification Workflow (Optional but Recommended)

**Location**: `lectio/.github/workflows/build-check.yml`

**Action**: Create new file

```yaml
name: Build Check

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install dependencies
        run: npm ci
        
      - name: Build package
        run: npm run build
        
      - name: Export contracts
        run: npm run export-contracts
        
      - name: Verify outputs
        run: |
          test -d dist || (echo "❌ dist/ not found" && exit 1)
          test -d contracts || (echo "❌ contracts/ not found" && exit 1)
          echo "✅ Build verification passed"
```

**Purpose**: Catches build failures before they reach the publish step

---

## Phase 3: Consumer Setup (Generator Frontend)

**Context**: The Generator frontend (Vercel deployment) needs to consume Lectio as an npm package

### Task 3.1: Configure npm for GitHub Packages

**Location**: Generator frontend root (create if missing): `.npmrc`

**Action**: Create new file

```
@richiewaweru:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

**Important**: This uses environment variable interpolation - the token comes from environment, not hardcoded

---

### Task 3.2: Add Vercel Environment Variable

**Manual step** (developer must do this):

1. Go to Vercel project settings → Environment Variables
2. Add new variable:
   - **Name**: `GITHUB_TOKEN`
   - **Value**: Your GitHub Personal Access Token (create at https://github.com/settings/tokens)
     - Required scope: `read:packages`
   - **Environments**: Production, Preview, Development (check all)
3. Save

**For local development**, add to `.env.local` (gitignored):
```
GITHUB_TOKEN=ghp_yourpersonalaccesstoken
```

---

### Task 3.3: Install Lectio Dependency

**Location**: Generator frontend `package.json`

**Action**: Remove any local path references to Lectio, add as npm dependency:

```json
{
  "dependencies": {
    "@richiewaweru/lectio": "^0.1.0"
  }
}
```

**Then run**:
```bash
export GITHUB_TOKEN=your_token  # or use .env.local
npm install
```

---

### Task 3.4: Update Import Paths

**Locations**: All files in Generator frontend that import from Lectio

**Before** (if using local path):
```typescript
import { SectionContent } from '../../../lectio/src/types';
import { TemplateRenderer } from '../../../lectio/src/components';
```

**After**:
```typescript
import type { SectionContent } from '@richiewaweru/lectio/contracts';
import { TemplateRenderer } from '@richiewaweru/lectio';
```

**AI agent task**: Find and replace all Lectio imports to use npm package syntax

**Find pattern**: `from ['"].*lectio.*['"]`  
**Replace logic**: Determine if importing types (→ `/contracts`) or components (→ package root)

---

## Phase 4: Consumer Setup (Lesson Builder)

**Same steps as Phase 3**, applied to the Lesson Builder repository:

1. Create `.npmrc` with GitHub Packages config
2. Add `GITHUB_TOKEN` to local `.env` (Lesson Builder doesn't deploy yet, so no Vercel config)
3. Add `@richiewaweru/lectio` to `package.json` dependencies
4. Update all import paths from local references to npm package

---

## Phase 5: Publishing Workflow

### Developer Publishing Process

**When ready to publish a new version:**

1. **Make changes** to Lectio components/types
2. **Update CHANGELOG.md** with changes under `[Unreleased]`
3. **Decide version bump** based on changes:
   - Bug fix only → PATCH: `npm version patch` → 0.1.0 → 0.1.1
   - New component/template → MINOR: `npm version minor` → 0.1.0 → 0.2.0
   - Contract breaking change → MAJOR: `npm version major` → 0.1.0 → 1.0.0

4. **Run version command**:
   ```bash
   npm version patch  # or minor, major
   ```
   This will:
   - Update `package.json` version
   - Create a git commit "v0.1.1"
   - Create a git tag "v0.1.1"

5. **Move CHANGELOG.md** `[Unreleased]` section to new `[0.1.1]` section with date

6. **Push changes**:
   ```bash
   git push origin main
   git push origin v0.1.1  # Push the tag
   ```

7. **GitHub Actions automatically**:
   - Detects the tag push
   - Runs build + export-contracts
   - Publishes to GitHub Packages
   - Creates GitHub Release

8. **Verify publication**:
   - Check GitHub Actions tab for workflow success
   - Check Packages section in GitHub repo for new version
   - Check GitHub Releases for new release entry

---

### Alternative: Manual Local Publish

**If you need to publish without GitHub Actions:**

```bash
# 1. Login to GitHub Packages
npm login --registry=https://npm.pkg.github.com
# Username: your-github-username
# Password: your personal access token (with write:packages scope)
# Email: your-email

# 2. Build
npm run build
npm run export-contracts

# 3. Publish
npm publish
```

---

## Phase 6: Consuming New Versions

### Updating Consumers to New Lectio Versions

**In Generator Frontend or Lesson Builder:**

```bash
# Update to latest version
npm install @richiewaweru/lectio@latest

# Or update to specific version
npm install @richiewaweru/lectio@0.2.0

# Or use version range
npm install @richiewaweru/lectio@^0.2.0  # allows 0.2.x patches
```

**Recommended strategy during 0.x phase**:
- Development: Use `^0.x.0` (allows patches)
- Production: Lock to exact version `0.x.y` (prevents unexpected changes)

**Update package.json**:
```json
{
  "dependencies": {
    "@richiewaweru/lectio": "0.2.0"  // Exact version for stability
  }
}
```

---

## Verification Checklist

**After implementing all phases, verify:**

### Lectio Repository
- [ ] `package.json` has correct fields (name, version, publishConfig, files)
- [ ] `.npmrc` exists with GitHub Packages registry
- [ ] README.md and CHANGELOG.md exist
- [ ] GitHub Actions workflows created in `.github/workflows/`
- [ ] `npm run build` succeeds locally
- [ ] `npm run export-contracts` succeeds locally
- [ ] `dist/` and `contracts/` directories are populated after build

### First Publish Test
- [ ] Create test tag: `git tag v0.1.0 && git push origin v0.1.0`
- [ ] GitHub Actions workflow runs successfully
- [ ] Package appears in GitHub Packages (repo → Packages tab)
- [ ] GitHub Release created automatically

### Consumer (Generator Frontend)
- [ ] `.npmrc` created with GitHub Packages config
- [ ] `GITHUB_TOKEN` environment variable set in Vercel
- [ ] `@richiewaweru/lectio` added to package.json dependencies
- [ ] `npm install` succeeds (with GITHUB_TOKEN in environment)
- [ ] Import paths updated from local to npm package
- [ ] Application builds successfully
- [ ] Application runs successfully in development
- [ ] Vercel deployment succeeds

### Consumer (Lesson Builder)
- [ ] Same verification as Generator Frontend (minus Vercel)
- [ ] `GITHUB_TOKEN` in local `.env`
- [ ] Application builds and runs

---

## Rollback Procedures

### If a Published Version Has Critical Bugs

**Option 1: Deprecate version (recommended)**
```bash
npm deprecate @richiewaweru/lectio@0.2.0 "Critical bug, use 0.2.1"
```

**Option 2: Unpublish (only works within 72 hours)**
```bash
npm unpublish @richiewaweru/lectio@0.2.0
```

**Best practice**: Always publish a new patch version with the fix rather than unpublishing

### If Consumer Needs to Rollback

**In package.json**:
```json
{
  "dependencies": {
    "@richiewaweru/lectio": "0.1.9"  // Revert to last working version
  }
}
```

Then run `npm install`

---

## Common Issues and Solutions

### Issue: `npm install` fails with 401 Unauthorized

**Cause**: Missing or invalid GITHUB_TOKEN

**Solution**:
```bash
# Verify token is set
echo $GITHUB_TOKEN

# If missing, set it
export GITHUB_TOKEN=ghp_yourtoken

# Re-run install
npm install
```

**For Vercel**: Verify environment variable is set and deployment was triggered after adding it

---

### Issue: Package not found on npm install

**Cause**: Package hasn't been published yet or visibility issue

**Solution**:
1. Check GitHub Packages: `https://github.com/richiewaweru/lectio/packages`
2. Verify tag was pushed: `git tag -l`
3. Check GitHub Actions: Look for successful publish workflow
4. Verify package is not set to private in package.json

---

### Issue: Build fails during publish

**Cause**: TypeScript compilation errors or missing contracts export

**Solution**:
1. Run `npm run build` locally to see errors
2. Fix TypeScript errors
3. Ensure `export-contracts` script succeeds
4. Verify `dist/` and `contracts/` exist after build
5. Commit fixes and push new tag

---

### Issue: Import paths broken after switching to npm package

**Cause**: Incorrect import syntax for GitHub Packages

**Before (wrong)**:
```typescript
import { types } from '@richiewaweru/lectio/types';
```

**After (correct)**:
```typescript
import type { SectionContent } from '@richiewaweru/lectio/contracts';
```

**Solution**: Review all import statements and ensure they match the `exports` field in package.json

---

## Future Enhancements (Not in This Proposal)

These are explicitly **out of scope** for this initial implementation but noted for future consideration:

1. **npm Provenance** - Cryptographic proof of package origin (requires npm 9.5+)
2. **Automated Changelog Generation** - Generate from git commits
3. **Release Notes in Pull Requests** - GitHub bot integration
4. **Multiple Distribution Channels** - Publish to both GitHub Packages and npmjs.com
5. **Package Size Monitoring** - Track bundle size over versions
6. **Automated Contract Validation** - CI checks for breaking changes in types.ts
7. **Dependabot Integration** - Auto-update consumers when new Lectio versions publish

---

## Execution Order

**For AI coding agent:**

1. Execute Phase 1 tasks (1.1 through 1.5) - Package configuration
2. Execute Phase 2 tasks (2.1 and 2.2) - GitHub Actions setup
3. **STOP** - Developer must manually verify pre-conditions and test first publish
4. After first publish succeeds, execute Phase 3 - Generator frontend consumer setup
5. Execute Phase 4 - Lesson Builder consumer setup
6. **STOP** - Developer must verify both consumers can install and import Lectio

**Developer manual steps interspersed:**
- Before Phase 1: Verify pre-conditions checklist
- After Phase 2: Create and push first tag to test publish workflow
- After Phase 3: Set GITHUB_TOKEN in Vercel, test deployment
- After Phase 4: Test Lesson Builder can build and run

---

## Success Criteria

This implementation is considered successful when:

1. ✅ Developer can run `npm version patch` and push, triggering automatic publish
2. ✅ New Lectio versions appear in GitHub Packages within 2 minutes
3. ✅ Generator frontend can `npm install @richiewaweru/lectio@latest` and build
4. ✅ Lesson Builder can install and use Lectio as npm dependency
5. ✅ All imports work without modification after switching to npm package
6. ✅ Vercel deployment succeeds with Lectio as npm dependency
7. ✅ Local development works with `GITHUB_TOKEN` environment variable

---

## Appendix A: Version Numbering Conventions

**During 0.x phase (current):**
- `0.1.x` - Initial published versions, contracts stabilizing
- `0.2.x` - First round of real-world usage fixes
- `0.9.x` - Release candidate for 1.0

**Post-1.0:**
- `1.0.0` - First stable release, contract stability guaranteed
- `1.x.y` - Backward-compatible additions
- `2.0.0` - Breaking contract changes (rare, requires migration guide)

**Pre-release versions** (if needed):
- `0.2.0-beta.1` - Beta testing
- `0.2.0-rc.1` - Release candidate

---

## Appendix B: Package.json Export Map Explanation

The `exports` field controls how consumers import from your package:

```json
"exports": {
  ".": {
    "types": "./dist/index.d.ts",
    "default": "./dist/index.js"
  },
  "./contracts": "./contracts/types.json",
  "./components/*": "./dist/components/*.js"
}
```

**Usage examples:**
```typescript
// Main entry - gets index.js and index.d.ts
import { Something } from '@richiewaweru/lectio';

// Contracts - gets types.json
import contracts from '@richiewaweru/lectio/contracts';

// Specific component (if you support this pattern)
import { TemplateRenderer } from '@richiewaweru/lectio/components/TemplateRenderer';
```

**Note**: Adjust this based on your actual file structure after confirming with developer

---

## End of Proposal

**Next step**: Developer reviews this proposal, confirms pre-conditions, then hands to AI coding agent for execution with the instruction: "Implement Phases 1 and 2 from the Lectio GitHub Packages proposal"
