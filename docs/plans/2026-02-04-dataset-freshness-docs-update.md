# Dataset Freshness Docs Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update design and TODO documentation to match the agreed dataset-level freshness rules (majority-minute, 30% threshold, 1-minute debounce, no trading calendar).

**Architecture:** Documentation-only change. No runtime behavior changes in this plan; it aligns the design and acceptance criteria with the agreed algorithm and configuration defaults.

**Tech Stack:** Markdown documentation in repository.

---

### Task 1: Update software design doc

**Files:**
- Modify: `requirements/SOFTWARE_DESIGN_CLOUDFLARE_TUNNEL.md`

**Step 1: Write the failing test (manual checklist)**

Checklist items that must be true:
- Freshness uses dataset-level aggregation, not per-file naming.
- Freshness computed by majority minute of file mtime across all CSVs.
- Update condition uses newer_ratio >= 0.30 against hub last_updated.
- Debounce is 60 seconds.
- Trading calendar is not required for freshness logic.

**Step 2: Run test to verify it fails**

Manual verify current doc still references 85% + trading calendar. Expected: FAIL.

**Step 3: Write minimal implementation (edit doc)**

Update sections: design principles, core concepts (data freshness), data flow, API notes, config examples, and remove trading-calendar dependency.

**Step 4: Run test to verify it passes**

Manual verify checklist items are reflected in doc. Expected: PASS.

**Step 5: Commit**

```bash
git add requirements/SOFTWARE_DESIGN_CLOUDFLARE_TUNNEL.md
git commit -m "docs: align freshness design with dataset-level rules"
```

### Task 2: Update TODO checklist doc

**Files:**
- Modify: `requirements/TODO.md`

**Step 1: Write the failing test (manual checklist)**

Checklist items that must be true:
- Phase 1.1 acceptance criteria use 30% threshold and 60s debounce.
- Criteria describe majority-minute mtime for dataset-level latest time.
- Remove calendar/period_offset dependency from acceptance criteria.
- Config examples align with new defaults.

**Step 2: Run test to verify it fails**

Manual verify current TODO still references 85% and period_offset.csv. Expected: FAIL.

**Step 3: Write minimal implementation (edit doc)**

Revise Phase 1.1 section and config snippets to reflect new rules.

**Step 4: Run test to verify it passes**

Manual verify checklist items are reflected in doc. Expected: PASS.

**Step 5: Commit**

```bash
git add requirements/TODO.md
git commit -m "docs: update TODO for new freshness thresholds"
```

---

## Notes
- No automated tests are required for documentation-only changes.
- Commit steps should be executed only if explicitly requested by the user.
