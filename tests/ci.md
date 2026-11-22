# Run the project and publication checks

One workflow, `.github/workflows/design-publication.yml`, runs on every push to every branch. Its `AGENT_FRC_REF` line is the only plugin pin; check out the same plugin commit locally as `PLUGIN`.

| Job | What it runs |
| --- | --- |
| Paths and secrets | `node PLUGIN/scripts/branch-scan.mjs .` |
| Design publication | `node PLUGIN/scripts/design-publication.mjs check .`, which reruns the layout check of each in-progress or effective design from its committed inputs, then the registered checks in `tests/ci.json` |
| Site build | `node scripts/build-showcase.mjs BUILDER NEW_SITE_DIRECTORY` with the original showcase builder, the preliminary design releases copied under `preliminary-design/`, the role and support replays and the phone and desktop tower controls |

Run from the project checkout. Use a real ancestor of your candidate for `BASE`.

```sh
node PLUGIN/scripts/branch-scan.mjs .
node PLUGIN/scripts/design-publication.mjs check . --skip-rerun
node PLUGIN/scripts/design-publication.mjs check .
node PLUGIN/scripts/project-checks.mjs . changed BASE
node PLUGIN/scripts/project-checks.mjs . full
```

The site deploys from `main` after all three jobs pass. A failed check leaves the current site online.
