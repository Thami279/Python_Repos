# Skill: workflow-invocation

## Purpose

This skill is the invocation layer that bridges a task request to the governance
architecture. It does not replace the governance skills (uncertainty, deployment,
escalation, provenance). It activates them in a defined sequence and supplies the
fill-in templates and decision gates that those skills assume you already have.

Load this skill first for any implementation task.

---

## Step 1 — Fill the Obligation Contract

Before touching code, complete this template in your working context.

```
OBLIGATION CONTRACT
───────────────────
Task:          <one sentence, subject-verb-object>
Success state: <observable, testable condition that proves the task is done>
Scope limit:   <what this task explicitly does NOT include>
Caller:        <who or what initiated this task>
Deadline:      <hard deadline, or "none">
Reversibility: <can this be undone after completion? yes / partial / no>
```

Rules:
- "Success state" must be falsifiable. "Works correctly" is not a success state.
  "All existing tests pass and the new endpoint returns 200 for valid input" is.
- "Scope limit" must name at least one thing. Leaving it blank is a red flag that
  scope has not been examined.
- Do not proceed to Step 2 until this contract is complete.

---

## Step 2 — Record Uncertainty State

Complete this template. This is the input to the uncertainty governance skill.

```
UNCERTAINTY STATE
─────────────────
Known knowns:    <what you understand and have verified>
Known unknowns:  <what you know you do not know — list at least one>
Unknown unknowns flag: <yes = you suspect hidden dependencies / no = low-complexity task>
Confidence tier: <HIGH = well-understood path | MED = some ambiguity | LOW = exploratory>
```

Rules:
- If confidence tier is LOW, escalation governance must be consulted before proceeding.
- If unknown unknowns flag is "yes", add a spike step before implementation: a
  contained probe to surface hidden dependencies before committing to a plan.
- An empty "known unknowns" field at MED or LOW confidence is a contract violation.

---

## Step 3 — Plan Falsification (mandatory gate)

State the plan in one paragraph, then answer this question explicitly:

> **What evidence, if found during execution, would prove this plan wrong?**

Write at least two falsifiers. Examples:
- "If the database schema differs from the migration file, the insert logic is wrong."
- "If the third-party API rate-limits on burst, the retry strategy is insufficient."

This step is not a formality. If you cannot name two falsifiers, the plan is not
specific enough to execute. Return to Step 1.

Do not begin implementation until falsifiers are written.

---

## Step 4 — Deployment State Check

Load the deployment governance skill. Record:

```
DEPLOYMENT STATE
────────────────
Environment:     <local | staging | production | unknown>
State owner:     <who controls deployment decisions for this environment>
Blast radius:    <number of users / systems affected if this change fails>
Rollback path:   <how to undo — command, PR revert, feature flag, or "none">
Deploy gate:     <what approval or check is required before this reaches production>
```

If rollback path is "none" and environment is staging or production, stop and
escalate before proceeding. This is a hard stop, not a recommendation.

---

## Step 5 — Execute and Observe

Implement the task. At each decision point during execution, check the falsifiers
from Step 3. If a falsifier is triggered:

1. Stop implementation.
2. Record what was found.
3. Return to Step 1 with updated information.

Do not paper over a triggered falsifier by adjusting the implementation to hide it.
A triggered falsifier means the plan was wrong, not the evidence.

---

## Step 6 — Failure Classification Gate

If execution produces an error, a test failure, or an unexpected result, classify
it before any remediation. Use this table:

| Class | Definition | Required response |
|-------|------------|-------------------|
| **A — Contract violation** | The task as defined cannot be completed as written | Halt, return to Step 1, renegotiate contract |
| **B — Plan error** | The approach was wrong but the task is achievable | Return to Step 3, new plan with new falsifiers |
| **C — Implementation defect** | The approach is correct, execution had a bug | Fix and re-run; do not change plan or contract |
| **D — Environmental fault** | External system, dependency, or environment failed | Escalate per escalation governance skill |
| **E — Unknown** | Cannot classify yet | Spike to classify; do not guess |

Rules:
- You must assign a class before writing a fix.
- Class E is not a fallback for "hard." It means the failure type is genuinely
  unknown and a probe is needed. If you can reason about likely cause, classify it.
- Treating a Class A as Class C (fixing code instead of renegotiating contract)
  is the most common governance failure. Check this explicitly.

---

## Step 7 — Provenance Record

Before closing the task, complete the provenance record. This is the input to the
provenance governance skill.

```
PROVENANCE RECORD
─────────────────
Task ref:          <obligation contract task field, verbatim>
Outcome:           <COMPLETE | PARTIAL | BLOCKED | ESCALATED>
Falsifiers hit:    <list any falsifiers from Step 3 that were triggered, or "none">
Failures seen:     <list failure classes encountered, or "none">
Scope drift:       <did the task grow beyond the Step 1 scope limit? yes / no — if yes, describe>
Open obligations:  <anything that was deferred and needs follow-up>
```

A PARTIAL or BLOCKED outcome requires an open obligation entry. An ESCALATED
outcome requires the escalation governance skill to be loaded and its record
completed before this record is filed.

---

## Skill dependencies

This skill calls the following governance skills explicitly. Load them at the
steps indicated:

- **uncertainty** — loaded at Step 2 for tier assessment
- **deployment** — loaded at Step 4 for state verification
- **escalation** — loaded when Step 4 hard stop is hit, or Step 6 Class D
- **provenance** — loaded at Step 7 for record completion

These skills must exist in `mnt/skills/user/` alongside this one. If any are
missing, note the gap in the provenance record and proceed with the in-line
templates above as a fallback.

---

## Quick reference: step sequence

```
1. Obligation Contract    → defines what done looks like
2. Uncertainty State      → flags what you do not know
3. Plan Falsification     → names what would prove the plan wrong  ← mandatory gate
4. Deployment State       → checks blast radius and rollback path
5. Execute and Observe    → implements; stops on triggered falsifiers
6. Failure Classification → classifies before any remediation      ← mandatory gate
7. Provenance Record      → closes the task with evidence
```
