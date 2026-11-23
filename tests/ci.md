# Run the project's checks

One workflow, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), runs on every push to every branch. It checks out this repository and nothing else, and every step runs a file of this repository. It needs Node, Python 3 and, for the last step, Chrome.

| Step | Command | Fails when |
| --- | --- | --- |
| Scan for personal paths and secrets | `node scripts/ci/scan.mjs .` | A tracked file holds a personal machine path or a credential |
| Check the published site | `node scripts/ci/site-check.mjs docs` | A design index and its folders disagree, a named file is missing or a relative link in a page leads nowhere |
| README still | `python scripts/cad-readmes.py .` | A README lacks the still block, its image, or the current design and status |
| Selected kickoff strategy | `node scripts/check-strategy.mjs` | The service clock, packing or frame numbers in `kickoff/` stop agreeing |
| Six-robot rehearsal evidence | `node scripts/check-match-series.mjs` | The recorded match series stops reconciling with the rules model |
| Pinned legacy sources | `python -m unittest discover -s tests` | A file listed in `PROVENANCE.json` changed |
| Entry page and field lab | `node scripts/check-site-pages.mjs SITE_URL CHROME` against `docs/` served over HTTP | The entry page, its links, the design pages or the field lab replay break at phone or desktop width |

Serve the site for the last step with `python -m http.server 8765 --bind 127.0.0.1 --directory docs` and pass `http://127.0.0.1:8765/` and the path of a Chrome or Chromium executable.

## The site

The published site is the `docs/` folder as committed. On `main`, after the checks pass, the workflow uploads `docs/` to GitHub Pages. Nothing is built. A failed check leaves the current site online.

- The field lab, alliance roles, depot lanes and match data pages are frozen: they were generated once and are now static files.
- `docs/index.html` is edited by hand. Change its status line and caption when the current design or its status changes.
- `docs/preliminary-design/` and `docs/detailed-design/` hold the design indexes and the page of each design.
- Views of earlier and withdrawn models are kept outside the site, in `cad/archived-views/`.

## Design checks

The layout check, staging and the publication check are run by the coding agent with its own design tool before a push; [AGENTS.md](../AGENTS.md) says which one for which change. This project runs none of them and holds no copy of or pin to that tool.
