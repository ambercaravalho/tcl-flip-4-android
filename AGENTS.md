# Agent operating rules

This repository researches full Android 14 bringup on the TCL Flip 4 5G
(T440W). Device writes are high risk; evidence and recoverability take priority
over completing a planned experiment.

## Required reading

Before proposing device actions, read:

1. `docs/README.md`
2. the latest relevant file in `docs/findings/`
3. the applicable page in `docs/reference/`
4. the applicable procedure in `docs/runbooks/`

Do not use a compatibility index as the canonical source.

## Session discipline

- Use one `docs/findings/YYYY-MM-DD-NN-slug.md` file per research/device
  session, based on `docs/findings/SESSION_TEMPLATE.md`.
- Record starting state before changing anything: mode, slot, fingerprints,
  exact flashed hashes, backup state, ADB/root state, and current symptom.
- Change one experimental variable at a time.
- Separate direct observation, inference, and unverified hypothesis.
- Record negative results and process mistakes; do not silently remove them.
- Completed findings are historical. Correct them with a dated addendum or a
  linked later session, not a rewrite that erases the original conclusion.
- End with exact device state, modified sectors/partitions, rollback path, and
  the smallest safe next step.

## Non-negotiable device gates

- Confirm the user's current device mode and outcome between risky or
  state-changing steps.
- Never infer root/debug state from image contents. After each boot verify
  `ro.debuggable`, `ro.force.debuggable`, `service.adb.root`, `adb shell id`,
  `adb root`, and the permissions needed by the planned diagnostic.
- EDL reads use `--skipresponse`; writes never do.
- Never trust EDL success text. Read back and compare every write before reboot.
- Use raw verified LBAs for both vbmeta partitions; name-based writes have
  falsely reported success.
- Confirm target slot, GPT geometry, source hashes, pre-write backups, and
  rollback commands before writing.
- Region A was overwritten during Lineage testing. Do not claim metadata-only
  stock rollback is sufficient.
- Stop and document contradictory evidence instead of forcing the next step.

## Repository hygiene

- Preserve unrelated working-tree changes and ignored/private artifacts.
- Keep durable facts in `docs/reference/`, procedures in `docs/runbooks/`, and
  outcomes in `docs/findings/`.
- Use paths under `artifacts/`, `evidence/`, and `tooling/`; do not recreate the
  former root-level directories.
- Check prior disproven assumptions before repeating a display experiment.
- Prepared SPI variants are controls, not confirmed fixes; satisfy the GSI
  trace gate before flashing them.
