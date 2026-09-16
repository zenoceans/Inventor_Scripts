# Design: General Options popup (tab visibility)

**Date:** 2026-09-16
**Package:** `zabra_cadabra`
**Status:** Deferred — saved for later implementation, not scheduled yet.
**Source:** User request while scoping a KiCad-export feature (which ended up living in
`juicebox`'s `central_pcb` package instead, not here — see that repo's
`docs/superpowers/specs/` for the PCB production-package work). This popup is the one
piece of that conversation that's genuinely Zabra-Cadabra-shaped: it's about the GUI shell
itself, not about KiCad or PCB production.

## Problem

`tab_registry.TabSpec.prototype` only hides tabs gated behind `show_prototype_tabs`
(currently just "Vendor API"). There's no way to hide any *other* tab the user doesn't use
often — the shell has accreted enough tabs (Inventor Export, STEP Simplify, Drawing
Creation, Vendor API, BMU Commissioning, PDF Diff) that this is worth a general mechanism
rather than special-casing one more flag.

## Approach: generalize to a persisted hidden-tabs list, minimal dialog

1. **`zabra_cadabra/src/zabra_cadabra/shell_config.py`** (new, small) —
   `ShellConfig` dataclass: `hidden_tabs: list[str] = field(default_factory=list)` (tab
   *titles*). Loaded/saved the same `inventor_utils.config` way every other tool's config
   is (`load_dataclass_config`/`save_dataclass_config`), file
   `zabra_cadabra_shell_config.json`.

2. **`shell.py`**:
   - `ZabraApp.__init__` loads `ShellConfig` (or accepts it via the existing `configs`
     dict passed into `ZabraApp` — reuse that pattern, key `"shell"`).
   - `_build_notebook` filters: a tab is shown iff `not (spec.prototype and not
     show_prototypes)` **and** `spec.title not in hidden_tabs`. The existing `prototype`
     gate is unchanged — it's a *default*-hidden set; `hidden_tabs` is the *user*-hidden
     set layered on top of it.
   - Add an "Options" button in the header, left of "Guide" (same style/placement as the
     existing "Guide" and "Feedback" buttons — see `_build_header`).
   - `_on_options()` opens
     `OptionsDialog(self._root, all_titles=[t.title for t in TABS], hidden=self._shell_config.hidden_tabs, on_save=...)`.

3. **`zabra_cadabra/src/zabra_cadabra/options_dialog.py`** (new) — `OptionsDialog(tk.Toplevel)`,
   modeled directly on `usage_guide.py`'s `UsageGuideDialog` (same modal
   construction/centering/`Escape`-to-close pattern): one checkbox per tab title (checked =
   visible), OK writes the inverse-checked set back into `hidden_tabs`, saves config
   immediately, shows a one-line "Restart Zabra-Cadabra for tab changes to take effect"
   label — no live notebook rebuild. This is the simplest correct behavior, and every other
   config change in this app (e.g. picking a different default-folder mode in
   `inventor_export_tool`) already only takes effect on next action, so a restart-to-apply
   model for tab visibility is consistent with how the rest of the app already works.

## Testing

- `shell_config` round-trip (same pattern as every other tool's config test, e.g.
  `pdf_diff_tool/tests/test_config.py`).
- `_build_notebook`'s filter logic: extract it to a standalone function taking
  `(specs: list[TabSpec], hidden_tabs: list[str], show_prototypes: bool) -> list[TabSpec]`
  so it's unit-testable without a real Tk root.
- `OptionsDialog`: no test — matches the existing depth of coverage for `UsageGuideDialog`
  and `FeedbackDialog` (neither has a test today; this dialog is no more complex than
  either).

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run --package zabra-cadabra pytest
uv run zabra-cadabra   # manual: Options button opens the dialog, hides/shows tabs after restart
```

## Distribution

1. All tests / lint / type-check pass.
2. Rebuild the bundled exe: `cd zabra_cadabra && uv run python build.py`.

## Out of scope

- Live notebook rebuild on Options-dialog OK (restart is sufficient).
- Anything KiCad/PCB-related — see the `juicebox` repo's specs instead.
