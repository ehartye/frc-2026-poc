# Legacy showcase withdrawal: handoff plan

Temporary handoff file. Delete it before opening the withdrawal PR: the project layout check rejects unknown root files.

## State (22 November 2026)

Two local commits on top of main `81dafcf`, both pushed, no PR open yet.

- `withdraw-legacy/policy` (`4f2cc1d`): the policy PR content. Three gated files only.
- `withdraw-legacy/content` (`93f4a63` plus this file): the withdrawal PR content, stacked on the policy commit.

Nothing is merged. No repository variable was changed.

## Decisions already made by the coordinator

- **Option B.** `docs` is a source public root here, so a committed `docs/detailed-design/archive/` fails the source audit (new geometry in a public root). Only `docs/detailed-design/index.html` and `designs.json` are committed. `scripts/build-showcase.mjs` still builds the 44 legacy files from the unchanged, gated sources with the pinned legacy builder (agent-frc `1751f86`) and moves them to `detailed-design/archive/draft-001/`. The builder pin must stay while the archive is published.
- Drop `assembly-view.js` from `primaryEntryPoints`; keep `index.html` and `assembly/assembly.png` (now the preliminary still).
- Add `README.draft-001.md` to `project-layout.json` `toolchainFiles` in the policy PR.
- No trusted-script constraint: `scripts/cad-readmes.py` and `tests/ci.json` run from the candidate and are not gated.

## PR order

1. **Policy PR** from `withdraw-legacy/policy`. Gated files: `.github/public-model-policy.json` (`detailedDesigns` twin freeing `scripts/build-showcase.mjs`, `preliminaryReadmeArchive` pins), `.github/staged-model-policy.json` (`detailedDesigns` with `draft-001` withdrawn and all 44 model files, `primaryEntryPoints` change), `project-layout.json`. Mechanical model eligibility fails by design. Coordinator admin-merges.
2. **Approval advance PR**: in `.github/workflows/robot-showcase.yml` set the approved checkout `ref:` and `approvedCommit` to the policy merge commit. `approvedSiteSha256` should stay `e5e7c3bc2082e87a91e651ccc310cb850bab136e4ac193f6ecdc619fa46d64d8` (no build input changes); confirm by rebuilding.
3. **Withdrawal PR** from `withdraw-legacy/content`, rebased onto main after step 2, with the policy commit dropped.

## Verified so far

Built as the workflow builds (builder `1751f86`, verifier `c69e23c`, portable layout), on Windows:

- Approved site from `9ce4168` reproduces digest `e5e7c3bc…`: 51 files = 44 staged model files + 3 field pages + 4 field data files.
- `detailed-design-release.mjs refresh` then `withdraw` on a copy of that build: the archive equals what the new build script writes (`diff -r` clean).
- Withdrawal commit `93f4a63` against policy commit `4f2cc1d` as approved: `local-showcase-release.mjs check` passes. `entryPointsFree: true`, `draft-001` withdrawn, 44 released, `scripts/build-showcase.mjs` the only freed source file, stage digest `4a61e730…`.
- `project-checks.mjs . full` passes all eight checks on `93f4a63`.
- Browser: front page renders; archived front page loads its model; preliminary review loads. Link crawl of 17 pages, 170 same-site links: the only 404s are archived pages' links to `field-lab.html`, `alliance-roles.html`, `depot-lanes/` and `match-series.json`, which the front page explains.
- Not yet verified: policy commit against today's approved commit (should fail on the policy file) and policy commit as both approved and candidate (should pass). Both were started and not read.

## Must change before the policy PR (pins freeze the content)

The policy PR pins `README.md`, the still and the archived README by hash. Finish these on the content branch first, then recompute the pins and amend the policy commit.

1. **Catalog (blocker).** `docs/detailed-design/index.html` is the old stock template, which shows "The design index could not be loaded" when no design is current. Replace it with `templates/detailed-design-index.html` from agent-frc `4ab39ad75c4efbd566f78bd7bd295c613b6aed33` (v0.111.1). The gate compares against the verifier's own template, so the coordinator must set `AGENT_FRC_PLUGIN_SHA` to that commit before the withdrawal PR's CI. First rerun the full project checks and all three gate states with that verifier and send the coordinator the proof.
2. Independent review findings still open (none are fixed yet):
   - `experiments/preliminary-design/review/README.md` line 9 says the still above is the published robot; now false.
   - `docs/showcase/front-page.html`: "The preliminary design above is in progress" is hard-coded; use `{{status}}`. "roller fixture" should match the archive's "Original mechanism fixture".
   - `scripts/build-showcase.mjs`: throw when the `<!-- archive-listing -->` marker is missing; clearer errors for a missing field file or a non-current release.
   - `scripts/preliminary-still.py`: check mode does not notice a renderer or backdrop change; caption counts are hand-written.
   - Retargeted study links should say the target is archived.
   - Add a front-page load and link check to CI (`scripts/check-tower-playback.mjs`).
   - `docs/workflow.md` line 3 calls the site root the "live field study".
3. Coordinator's option B conditions, not done yet: a committed check that the built archive equals the approved build byte for byte; a sentence on the front page archive section and in the PR that the archive is rebuilt from locked sources with builder `1751f86`; a friction note to `plugin-backlog` (doc says commit the tree; broad `publicRoots` cannot).
4. After any README or still change: `python scripts/cad-readmes.py . --template scripts/cad-orbit.html --update`, recompute `preliminaryReadmeArchive.readmeSha256` and `imageSha256`, rerun without `--update`.

## Exact next step

Copy the fixed catalog template (item 1), fix the review findings, add the archive equality check, re-pin, rerun the three gate states and the project checks on verifier `4ab39ad`, get a second independent review, then open the policy PR.

## What the coordinator must do

- Set `AGENT_FRC_PLUGIN_SHA` to `4ab39ad75c4efbd566f78bd7bd295c613b6aed33` once the checks are shown to pass on it.
- Admin-merge the policy PR after reading the whole diff.
- Keep `r3-complete` from making another release current before the withdrawal merges: the README pin names `layout-001` and its status.

## Other notes

- The plugin's stable preliminary viewer says "The current detailed design is on the main robot page", which is no longer true. Report to `plugin-backlog`.
- The date "22 November 2026" is static text in `docs/showcase/front-page.html` (not pinned). The README carries no date.

## Superseded: the withdrawal will be redone under the simplified gate

The coordinator has stopped the three-PR plan above. The gate is being simplified: no approval baseline, no whole-site freeze, no page, README or catalog pins and no signature. A withdrawal becomes a status change in the design index plus removing the files, in one ordinary PR. Git history is the archive. Wait for the plugin's migration guide before redoing this. The two branches stay as reference only.

### What carries over from `withdraw-legacy/content`

- **Still renderer.** `scripts/preliminary-still.py` with its record `docs/robot/preliminary-layout-001.json` and image `docs/robot/preliminary-layout-001.png`. It renders from `docs/preliminary-design/releases/ID/review-scene.json.gz` at case `park-lower`, with the field fixtures and the three FUEL hidden. `--update` needs OCP and VTK; verify mode needs only the standard library. Keep the `.gitattributes` line that marks the PNG binary, the `tests/ci.json` check and the allowlist entry in `scripts/check_public_content.py`.
- **README content.** The new `README.md` body and the preliminary mode in `scripts/cad-readmes.py` (`preliminary_feature`, `siteUrl` in `cad-showcase.json`), with `tests/test_cad_readme_modes.py`. The mode switch currently reads the policy pins and `docs/detailed-design/designs.json`; rewrite that part for the new index. `README.draft-001.md` and the `project-layout.json` exception are only needed if a copy of the old README is still wanted.
- **Front page.** `docs/showcase/front-page.html` is self-contained (inline CSS, no script) and is filled by the tail of `scripts/build-showcase.mjs`. Drop the archive table, the "links inside archived pages" notice and the archive links if no on-site archive is kept. Keep the status line, the still and caption, the "No detailed design is current" section and the field-page cards.
- **The 44 legacy files.** The list is `detailedDesigns.withdrawn[0].files` in `.github/staged-model-policy.json` on `withdraw-legacy/policy`. It equals the staged `modelFiles` list on main. The built site at `9ce4168` is exactly those 44 plus `alliance-roles.html`, `depot-lanes/index.html`, `field-lab.html`, `match-profile.json`, `match-series.json`, `match-summary.json` and `depot-lanes/results.json`. The field pages are self-contained and need none of the 44. The last commit where the files are built is main `81dafcf`.
- **Document links.** Seven documents had links to withdrawn pages retargeted to archive addresses (`cad/assembly-release/engineering.md`, `cad/own-zone-upper/design.md`, `docs/workflow.md`, four `experiments/*/study.md` files). Without an on-site archive these need a different target or wording.
- **Workflow.** The build job's Python step that injects the "Preliminary design (work in progress)" link must go once the front page links the review itself. `scripts/check-tower-playback.mjs` opens `#model` and `robot/tower.html`; those pages will not exist, so cut those parts and keep the field-lab part.

### Review findings worth keeping

- `experiments/preliminary-design/review/README.md` line 9 says the still above is the published robot. False once the still is the preliminary design.
- Use `{{status}}` in the front page's "The preliminary design above is in progress" sentence.
- Throw in the build script when a template marker is missing, when a field file is missing, and when the current release is not in progress or effective.
- `scripts/preliminary-still.py` verify mode does not notice a renderer or backdrop change. Caption counts are hand-written and not compared with `shownBodies` and `hiddenBodies`.
- Add a front-page load and link check to CI.
- `docs/workflow.md` line 3 calls the site root the "live field study".
- "Work in progress" wording survives in issued files outside this change: `docs/preliminary-design/releases/layout-001/field/r3-field-trials.html`, `cad/preliminary-design/stage.py`, `experiments/preliminary-design/review/package-motion.html`. The plugin's stable preliminary viewer also says "The current detailed design is on the main robot page".

### No longer needed

Both policy edits, the approval advance, the `detailedDesigns` twin, `scripts/withdrawn/draft-001/`, the committed catalog page, the archive equality check and the `AGENT_FRC_PLUGIN_SHA` move to `4ab39ad` for the catalog.
