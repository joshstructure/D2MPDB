# Create a BPAD task order

Use this prompt with a specific objective:

> Create a task order for **[objective]** using the current D2MPDB journal.
> **[Plan only / Plan and execute]**. Identify the native modules and resources
> that may change, their upstream dependencies, downstream effects, prerequisites,
> output interfaces and checks. Keep the work within the requested objective.

Read AGENTS.md and workflow/README.md. Inspect the current journal with the helper;
do not choose a source by modification date or parenthetical filename numbering.

1. Identify the exact journal hash, the affected native report/spreadsheet names,
   current shared-input owners and existing output references. Inspect actual
   formulas, named containers, live links, source documents and engineering
   assumptions. Explain any uncertainty in the proposed dependencies.
2. Write `tasks/<ID>/plan.md` with: objective; exclusions; read dependencies;
   permitted component keys; assumptions and conventions; source documents;
   output contract (meaning, units, signs, reference point, factoring and case);
   downstream calculations and external analyses; prerequisite task IDs; structural,
   numerical, native appearance and engineering acceptance criteria; stop conditions.
   A plan-only request stops here. Do not register or execute it yet.
3. When execution is authorized, create a registered task with `prepare`. The
   command creates the task folder or retains its existing plan.md. Pick an unused
   ID. Do not overwrite an existing task. Its `order.json` is the enforceable JSON contract; `plan.md`
   supplies engineering detail. The registry freezes the scope and fingerprints.
4. Use the conservative dependency fallback unless a reviewed declaration is
   already present. To narrow it, review all upstream modules recursively and
   record `reads`, `complete: true`, `reviewed_by`, and a substantive `rationale`
   under the exact component key in `workflow/dependencies.json` BEFORE preparing
   tasks. Account for assumptions and source files in the matching registers.
   Updating these declarations invalidates existing prepared tasks by design.
5. Work only in `tasks/<ID>/working.bpad` or its assigned component fragments.
   Do not replace math with Python results, copy shared numbers as new inputs,
   or copy engineering assumptions from a layout exemplar. Use native formatting
   patterns from standards/BPAD_Ref_V5.txt. Register added resources/modules as a
   separate planned topology change; the pilot rejects their silent insertion.
6. Complete `submission.json` with actual outputs, checks, review items and
   external-analysis impacts. Run `check`; use `assemble` for a fresh candidate.
   Report changed components, identified dependencies and remaining review gates.

Large objectives may need several linked task orders. Separate task folders permit
parallel work. Coordinate in this chat unless the user asks for new chats or agents.
Use managed worktrees when requested or when code/tool changes need isolation;
native journal tasks already receive their own full working journal and resources.

Never report native Blockpad recalculation or engineering approval unless actually
performed. A working build may contain stale display caches and inherited errors.
