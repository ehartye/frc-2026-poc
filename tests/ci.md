# Run the project and publication checks

One workflow, `.github/workflows/design-publication.yml`, runs on every push to every branch. Its `AGENT_FRC_REF` line is the only plugin pin; check out the same plugin commit locally as `PLUGIN`.

| Job | What it runs |
| --- | --- |
| Paths and secrets | `node PLUGIN/scripts/branch-scan.mjs .` |
| Design publication | `node PLUGIN/scripts/design-publication.mjs check .`, which reruns the layout check of each in-progress or effective design from its committed inputs, then the registered checks in `tests/ci.json` |
| Site build | `node scripts/build-showcase.mjs BUILDER NEW_SITE_DIRECTORY` with the season's original field builder: the field lab, alliance roles and depot lanes, the design status pages, the preliminary design releases and the entry page. Then the role and support replays and `scripts/check-site-pages.mjs`, which opens the entry page and the field lab on phone and desktop widths and follows every entry page link |

Run from the project checkout. Use a real ancestor of your candidate for `BASE`.

```sh
node PLUGIN/scripts/branch-scan.mjs .
node PLUGIN/scripts/design-publication.mjs check . --skip-rerun
node PLUGIN/scripts/design-publication.mjs check .
node PLUGIN/scripts/project-checks.mjs . changed BASE
node PLUGIN/scripts/project-checks.mjs . full
```

The site deploys from `main` after all three jobs pass. A failed check leaves the current site online.
