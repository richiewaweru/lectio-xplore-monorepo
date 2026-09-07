# Lectio GitHub Packages Publishing - Handoff

## What Has Been Completed 

The initial setup for publishing Lectio automatically via GitHub Packages is now fully deployed. 

We successfully completed **Phase 1** and **Phase 2** of the implementation proposal:
1. **Configured `package.json`**:
   - Set the package name to your scope: `@richiewaweru/lectio`
   - Added specific export mappings for `./print`, `./contracts`, and `./components/*`.
   - Pre-configured `npm run package` prior to deployment.
2. **Added GitHub Workflows**:
   - `build-check.yml`: Automatically tests pull requests/pushes against compilation errors.
   - `publish.yml`: Automatically builds, exports contracts, signs, and deploys any `v*.*.*` tags to the GitHub Packages registry. 
3. **Repository Configuration**:
   - Integrated a `.npmrc` file directly tying npm back to the `pkg.github.com` registry.
   - Updated `.gitignore` dynamically to safely permit `contracts/` uploads.
   - Bootstrapped `CHANGELOG.md` starting at **0.1.0**.
   - Added user package installation guidance in the main `README.md`.

*Note: As discussed, the code has already been pushed to `master` and the `v0.1.0` tag was cut, triggering the first real package deployment to GitHub.*

---

## Action Items For You (Phases 3 & 4)

Since your Lecturer Component Library is restricted to your private domain, any project (like Vercel websites and Lesson Builder applications) attempting to download it will need authentication. 

You must execute the remaining configuration on those independent applications:

### 1. Generate Your GitHub Secret
- Navigate to your [GitHub Personal Access Tokens page (Classic)](https://github.com/settings/tokens).
- Choose **Generate new token (classic)**.
- Select the `read:packages` permission.
- Copy this token exactly once (GitHub won't show it again).

### 2. Configure Vercel (Generator Frontend)
- Go to the Vercel Dashboard for your Generator project.
- Click **Settings** > **Environment Variables**.
- Create `GITHUB_TOKEN` and paste your new token as the value. Check the boxes to apply it to Production, Preview, and Development.

### 3. Configure Local Workspaces (Lesson Builder / Generator)
In the root folders of these applications on your computer:
- Make sure they contain a `.npmrc` matching the one we just placed in Lectio:
  ```ini
  @richiewaweru:registry=https://npm.pkg.github.com
  //npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
  ```
- Make sure your local PowerShell environment actually has the token mapped before installing:
  ```powershell
  $env:GITHUB_TOKEN="ghp_your_new_token_here"
  npm install @richiewaweru/lectio@latest
  ```

### Future Publishing
When you want to cut a new release in the future, simply:
1. Make your code updates.
2. Add an entry to `CHANGELOG.md`.
3. Commit everything as normal.
4. Run `npm version patch` (or minor/major) 
5. Run `git push --follow-tags` to send everything online, which will automatically trigger the GitHub workflow to securely deploy the new version!
