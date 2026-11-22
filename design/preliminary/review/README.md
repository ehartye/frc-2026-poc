# R3-PD1 LAN review bundle

This folder holds only the review page for issue R3-PD1 (`package-motion.html`, about 31 MB, not committed). The page is self-contained: it loads no external scripts. Private CAD and supplier models are not in it.

## Build the page

From the project root, with the CAD Python environment selected:

```powershell
$env:PYTHON = '<cad python>'
node <agent-frc>/scripts/design.mjs preliminary-check . design/preliminary/layout.json --write-view --quiet > $null
```

The receipt records the page's SHA-256 (`view.sha256` in [receipt.json](../receipt.json)). A page earns credit only if its bytes match.

## Serve it on the LAN

```powershell
python -m http.server 8765 --bind <host LAN address> --directory design/preliminary/review
```

Open `http://<host LAN address>:8765/package-motion.html` on the host and then on a second device. Stop the server with Ctrl+C. The folder stays usable as a static bundle after the host shuts down.

## What to check

1. Reset the view, orbit a full revolution and underneath, pan, zoom, and toggle the labels.
2. Play `intake-deploy` through `park-lower` in order. Then scrub `launch-wrap` and the four flight arcs into the HUB cavity.
3. Select a component and read its purpose and rationale.
4. Open the mass and power ledgers.
5. Open the displaced-hood control (`package-displacement-control`). It shows a known failing case.

Expected scope: the represented package, cases and reserves. The issue's status is `reopen`; read why in [the study](../study.md).
