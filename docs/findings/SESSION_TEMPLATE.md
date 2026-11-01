# YYYY-MM-DD NN: Session title

Status: in progress

## Objective

State one question this session is intended to answer.

## Starting state

- Device mode and active slot:
- Running OS, build fingerprint, SDK, and ABI:
- Exact images currently flashed:
- Backup/rollback state:
- ADB identity, root state, and required permissions:
- Known unresolved symptoms:

Do not copy a previous state without checking it.

## Artifacts

List source and output paths, SHA-256 hashes, build manifests, captures, and
relevant tool versions. Distinguish host artifacts from bytes read back from
the device.

## Actions and observations

Record actions in order. Change one experimental variable at a time. For each
action, record the command or procedure, expected result, actual result, and
read-back or runtime verification.

Label statements explicitly when useful:

- **Observation:** directly captured or seen.
- **Inference:** best explanation supported by observations.
- **Hypothesis:** unverified explanation or prediction.

## Conclusions

State only conclusions supported by this session. Link durable conclusions from
the appropriate file in `../reference/`.

## Disproven assumptions

Record failed hypotheses and negative results. A negative result is evidence,
not a reason to silently remove the attempted approach.

## Mistakes and process corrections

Record unsafe assumptions, missing validation, ambiguous commands, or process
failures. State the concrete guardrail that prevents recurrence.

## Ending state

- Device mode and active slot:
- Running OS/build:
- Partitions or sectors changed:
- Verified rollback path:
- ADB/root/trace access:
- Uncommitted host artifacts:

## Safe next step

Name the smallest evidence-gathering action that follows from the conclusions.
If a prerequisite is unverified, make verification the next step.

When the session is complete, change the status to `complete`. Do not rewrite a
completed finding to make a later theory appear correct; add a dated correction
or a new linked session.
