# Run the project and showcase checks

Set `AGENT_FRC_PLUGIN_SHA` to the reviewed release commit in GitHub and check out the same plugin commit locally. The single Robot showcase workflow calls Verify project evidence for pull requests and main. A manual run checks the full project, builds the showcase and checks its eligibility. Only a push to main deploys.

Run from the project checkout. Use a local path to the reviewed plugin for `PLUGIN` and a real ancestor of your candidate for `BASE`.

```sh
node PLUGIN/scripts/project-checks.mjs . changed BASE
node PLUGIN/scripts/project-checks.mjs . full
```

The seven registered checks cover the actual project tests and published evidence. The CI build separately exercises the role and support replays and the phone and desktop tower controls.

## Check the exact release

Build into an empty destination using the original pinned presentation builder. Reproduce the approved edition from the frozen project commit and independently generate the field pages as shown in the workflow. Keep the reference build, external reviewer public key and trusted configuration outside both your candidate checkout and final site. The role-page build is sensitive to its working directory. Preserve the project and output layout used in the workflow.

```sh
node PLUGIN/scripts/local-showcase-release.mjs check TRUSTED_CONFIG . FINAL_SITE
```

The workflow supplies this same command with the digest of the 51-file baseline, the two policies in the approved commit, the independently rebuilt field and the project paths to the two optional signed release packets. New model assets require a matching source and staged issue. For an ordinary signed teaching model, the following test runs the production gate against an isolated temporary repository and a copy of the final site. Both packets must describe the same engineering study.

```sh
node tests/signed-showcase.mjs PLUGIN SOURCE_ROOT SOURCE_PACKET STAGED_ROOT STAGED_PACKET REVIEWER_PUBLIC_KEY
```
