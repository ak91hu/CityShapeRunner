# CI/CD and documentation delivery

The repository uses one GitHub Actions workflow, `.github/workflows/ci.yml`, for pull-request validation, branch validation, the production-container build, and GitHub Pages documentation publication.

## Trigger and concurrency

The workflow runs on every `push` and `pull_request`. Its concurrency key contains the workflow and Git ref, and `cancel-in-progress: true` ensures a newer commit supersedes an older run for the same branch or pull request.

The default workflow permission is read-only repository content. Only the documentation deployment job receives `pages: write` and `id-token: write`, following least privilege.

## Required jobs

| Job | Runtime | Commands and artifact | Timeout |
| --- | --- | --- | --- |
| `backend` | Python 3.14 | Editable `.[dev,all]` install, Ruff, mypy, pytest with offline geocoding | 15 min |
| `frontend` | Node 24 + Chromium | `npm ci`, Vite production build, Playwright functional suite | 15 min |
| `container` | Docker | Builds the exact multi-stage Northflank production image | 20 min |
| `docs` | Python 3.14 | Editable `.[docs]` install, `mkdocs build --strict`; uploads Pages artifact on `master` pushes | 10 min |
| `deploy-docs` | GitHub Pages | Deploys the uploaded static site to the protected `github-pages` environment | 10 min |

## Quality gate and deployment flow

```text
push / pull request
        |
        +--> backend --------+
        +--> frontend -------+--> deploy-docs (master push only) --> GitHub Pages
        +--> container ------+
        +--> docs build -----+
```

`deploy-docs` declares all four validation/build jobs in `needs`. It therefore cannot publish a commit unless backend checks, frontend checks, the production image build, and the strict documentation build all succeed.

Pull requests and non-`master` branches build the docs but never upload or deploy a Pages artifact. This keeps documentation regressions visible without creating preview releases or granting write permissions to untrusted workflow contexts.

## GitHub Pages configuration

One repository setting is required:

1. Open **Settings → Pages** in `ak91hu/CityShapeRunner`.
2. Under **Build and deployment**, select **GitHub Actions** as the source.
3. Keep the `github-pages` environment protection compatible with deployments from `master`.

The workflow then publishes `site/` to:

```text
https://ak91hu.github.io/CityShapeRunner/
```

The deployment job exposes the final address through `steps.deployment.outputs.page_url`, so it appears on the GitHub environment deployment record.

## Documentation build contract

The documentation toolchain is pinned in the `docs` optional dependency group in `pyproject.toml`. The build is reproducible with:

```powershell
python -m pip install -e ".[docs]"
python -m mkdocs build --strict
```

Source is read from `docs/`, configuration from `mkdocs.yml`, and output is written to `site/`. The output directory is ephemeral and ignored by Git. Edit Markdown, SVG, or CSS sources instead of generated HTML.

When adding a page:

1. create the Markdown file under `docs/`;
2. add it to the appropriate section in `mkdocs.yml`;
3. use source-relative links such as `[Configuration](configuration-reference.md)`;
4. run the strict local build;
5. inspect both light and dark themes at desktop and narrow widths with `mkdocs serve`.

## Application deployment versus documentation deployment

These are intentionally separate release paths:

| Release | Trigger/owner | Built output | Destination |
| --- | --- | --- | --- |
| Application | Northflank linked to `master` | Multi-stage Docker image containing FastAPI and compiled React SPA | Northflank service |
| Documentation | GitHub Actions after all CI jobs pass on `master` | Static MkDocs site | GitHub Pages |

The CI `container` job validates that the application image still builds, but Northflank performs the actual application deployment according to its linked-repository configuration. See [Production deployment](deployment.md) for service settings and rollout checks.

## Failure handling

| Failure | Effect | Investigation |
| --- | --- | --- |
| Ruff, mypy, pytest, build, or browser test fails | No docs deployment; Northflank behavior depends on its own build trigger | Open the failing job and reproduce its command locally |
| Strict MkDocs build fails | No Pages artifact and no deploy | Read the first warning/error; fix navigation, configuration, or Markdown link |
| Pages upload is skipped | Expected on PR/non-`master`; unexpected on `master` | Check event/ref condition and job logs |
| Pages deployment is rejected | Static artifact remains undeployed | Confirm Pages source, job permissions, and environment protection |
| New run cancels old run | Expected for the same ref | Inspect the newest commit's run |
| Northflank deploy fails while CI passed | Application remains on previous healthy revision | Inspect Northflank build/runtime logs and health check |

## Rollback

Documentation is immutable per workflow artifact and commit. Restore a previous version by reverting the documentation/configuration change on `master`; after the complete CI gate passes, the previous content is rebuilt and redeployed. Avoid manually uploading generated HTML because that bypasses review and reproducibility.

Application rollback remains a Northflank operation: select a previously healthy deployment or revert the responsible commit, then confirm `/health` and a real street-routed generation.

## Upstream implementation references

- [GitHub Pages: custom GitHub Actions workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub `upload-pages-artifact` action](https://github.com/actions/upload-pages-artifact)
- [GitHub `deploy-pages` action](https://github.com/actions/deploy-pages)
- [Material for MkDocs: creating a site](https://squidfunk.github.io/mkdocs-material/creating-your-site/)
- [Material for MkDocs: navigation setup](https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/)
