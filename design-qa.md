# VISA batch-entry design QA

- Source visual truth path: `tmp/visa-batch-audit/01-list-redesign.png` (existing SUNRISE page and design-system context)
- Implementation screenshot path: `tmp/visa-batch-audit/04-batch-final.png`
- Interaction evidence: `tmp/visa-batch-audit/03-batch-imported.png`
- Viewport: 1280 × 720 CSS px
- Source pixels: 2560 × 1440 at deviceScaleFactor 2
- Implementation pixels: 2560 × 1440 at deviceScaleFactor 2
- Density normalization: none required; both captures use the same viewport and density
- State: source is the VISA list; implementation is the batch-entry drawer opened from that list

## Full-view comparison evidence

The batch workspace continues the existing SUNRISE visual language: system typography, pale blue/pink surface treatment, border color, button hierarchy, radius, and low-elevation card shadows. The drawer intentionally changes the information structure from a record list to a task workspace, so exact region-to-region layout parity is not expected.

## Focused interaction evidence

`03-batch-imported.png` confirms that pasted spreadsheet rows appear in the left roster, the active applicant's mapped values appear in the detail form, completion indicators update, the selected guarantor remains visible, and the sticky save summary updates to the correct count. A separate crop was not needed because these details are legible in the viewport capture.

## Findings

- No actionable P0, P1, or P2 differences remain.
- Typography: system font, weights, hierarchy, wrapping, and tab labels match the existing application.
- Spacing and layout: shared settings, applicant roster, editor, and sticky action bar have a clear and consistent rhythm at 1280 px.
- Colors and tokens: existing `--sunrise-*` tokens and Element Plus states are reused consistently.
- Image and icon quality: no custom raster artwork is required; all controls use the project's existing Element Plus icon library.
- Copy and content: the new labels describe shared guarantor data, shared travel data, customer import, spreadsheet paste, and one-action save without changing the existing record terminology.

## Comparison history

1. Initial implementation (`02-batch-workspace.png`): P2 — five shared-trip fields were too dense at 1280 px, causing important placeholder text to truncate.
2. Fix: changed the shared-trip grid to three columns at standard desktop widths and retained five columns only from 1560 px upward.
3. Post-fix evidence (`04-batch-final.png`): field purposes are readable, the settings area remains compact, and no P0/P1/P2 issues remain.

## Primary interactions tested

- Opened the batch-entry workspace from the VISA list.
- Confirmed the saved guarantor template is selected and shown in the footer.
- Entered an applicant name and added another blank applicant.
- Pasted two TSV applicants with dates, gender, nationality, passport, and residence status.
- Confirmed applicant count, completion count, mapped values, and active-row switching.
- Checked browser console warnings and errors; none were present.

final result: passed
