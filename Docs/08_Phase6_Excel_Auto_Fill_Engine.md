# Phase 6 — Excel Auto-Fill Engine

**Goal of this phase:** take the per-video results table from Phase 5 and write the
counts into a **copy** of the actual Excel template, into exactly the right cells,
without breaking any existing formatting, merged cells, or headers.

**Exit criteria:** running the writer on your sample video's results produces a filled
`.xlsx` file that, opened in Excel, looks indistinguishable in structure from a manually
filled one — just with numbers where zeros/blanks used to be.

Budget: **2–3 days.**

---

## 6.1 Why we don't just "create a new Excel file" — we edit a copy of the template

Your existing `.xlsx` files have specific formatting: merged header cells, fonts,
column widths, date formatting, sheet names. If we generate a brand-new spreadsheet from
scratch (e.g., with `pandas.to_excel`), we'd lose all of that and produce something that
looks different from what your enumerators/clients expect. Instead:

1. **Copy** the blank/target template file.
2. Open the copy with `openpyxl` (which preserves formatting when you don't touch it).
3. Only write values into the specific numeric cells — leave everything else alone.
4. Save as a new file (never overwrite the original template).

---

## 6.2 Build a "cell address finder" from the header structure

Rather than hardcoding cell addresses like `"AH7"` (fragile — breaks if a template
changes slightly), write a small function that finds the right cell by reading the
headers, using the same merged-cell inspection idea from Phase 1 Appendix A:

```python
import openpyxl
from datetime import datetime, time

def build_column_map(ws):
    """
    Scans row 5 (movement block markers, e.g. 'Time' 'Two Wheelers' etc.)
    and row 6 (sub-category markers where present) to build:
      { (movement_label, category_label): column_letter }
    movement_label is inferred from which block of columns we're in (by looking at
    row 4's 'DIRECTION: A-B' style headers).
    """
    # Read direction headers from row 4 to know which column range = which movement
    direction_ranges = []
    for cell in ws[4]:
        if cell.value and "DIRECTION" in str(cell.value):
            # e.g. "DIRECTION: A-B" -> "A-B"
            movement = str(cell.value).split(":")[-1].strip()
            direction_ranges.append((cell.column, movement))

    # Figure out where each direction block ends (next block's start, or last column)
    direction_ranges.sort()
    blocks = []
    for i, (col, movement) in enumerate(direction_ranges):
        end_col = direction_ranges[i+1][0] - 1 if i+1 < len(direction_ranges) else ws.max_column
        blocks.append((col, end_col, movement))

    # Within each block, map category header text (row 5, plus row 6 sub-header if present) to column
    column_map = {}
    for start_col, end_col, movement in blocks:
        for col in range(start_col, end_col + 1):
            main_header = ws.cell(row=5, column=col).value
            sub_header = ws.cell(row=6, column=col).value
            if not main_header:
                continue
            label = f"{main_header} {sub_header}".strip() if sub_header else str(main_header).strip()
            column_map[(movement, label)] = openpyxl.utils.get_column_letter(col)

    return column_map
```

Run this once on a template and print `column_map` — sanity check it against the
`EXCEL_TO_DETECTOR` mapping table from Phase 5 §5.4 (the labels should match, or you'll
need to align the exact text strings — Excel headers are sometimes slightly inconsistent,
e.g. "Autorickshaw - 3wh" vs "Autorickshaw-3wh" — copy-paste the exact text from the real
file rather than retyping it).

---

## 6.3 Build a "row finder" for the time buckets

```python
def build_row_map(ws, time_column="A"):
    row_map = {}
    for row_idx in range(7, ws.max_row + 1):
        cell_value = ws[f"{time_column}{row_idx}"].value
        if isinstance(cell_value, time):
            row_map[cell_value.strftime("%H:%M")] = row_idx
    return row_map
```

---

## 6.4 The actual writer

```python
import shutil
import pandas as pd

def fill_excel(template_path, output_path, results_csv_path, sheet_name):
    shutil.copy(template_path, output_path)   # never touch the original
    wb = openpyxl.load_workbook(output_path)
    ws = wb[sheet_name]

    column_map = build_column_map(ws)
    row_map = build_row_map(ws)

    results = pd.read_csv(results_csv_path)
    # Aggregate: how many vehicles of each (movement, excel_column_label, bucket_time)
    counts = (
        results
        .assign(excel_column=lambda df: df["vehicle_class"].map(DETECTOR_TO_EXCEL_COLUMN))
        .groupby(["movement", "excel_column", "bucket_time"])
        .size()
        .reset_index(name="count")
    )

    unmatched = []
    for _, r in counts.iterrows():
        key = (r["movement"], r["excel_column"])
        if key not in column_map:
            unmatched.append(r.to_dict())
            continue
        if r["bucket_time"] not in row_map:
            unmatched.append(r.to_dict())
            continue

        col_letter = column_map[key]
        row_idx = row_map[r["bucket_time"]]
        cell = ws[f"{col_letter}{row_idx}"]
        # ADD to existing value rather than overwrite, in case the writer runs
        # multiple times for multiple video segments covering the same sheet
        existing = cell.value if isinstance(cell.value, (int, float)) else 0
        cell.value = existing + int(r["count"])

    wb.save(output_path)

    if unmatched:
        print(f"WARNING: {len(unmatched)} result rows could not be matched to a cell. "
              f"Review these — likely a header text mismatch or missing time bucket:")
        for u in unmatched:
            print(" ", u)

    return output_path
```

**Why "add to existing value" instead of overwrite:** because (per Phase 1's findings)
one Excel sheet's full time range is likely filled from **multiple video segment files**
(e.g. six 28-minute clips covering 8:00–11:00). You'll run this writer once per video
segment, always targeting the same output file, and counts should accumulate correctly
rather than each run wiping out the previous segment's results.

---

## 6.5 Always print/log the "unmatched" warnings — never silently drop data

The `unmatched` list in the code above is critical: if your Phase 5 output produces a
`bucket_time` or `excel_column` label that doesn't exactly match what's in the real
template (e.g., a typo, or a class mapped to a column label that doesn't exist in this
particular site's template), you want to **know immediately**, not discover it as a
silently-empty cell days later. Treat any non-empty `unmatched` list as a build failure
to investigate before trusting the output.

---

## 6.6 Deliverables checklist for Phase 6

- [ ] `build_column_map` and `build_row_map` tested against both your sample templates
      (`Site_15_...xlsx` and `Data_Entry_Temp.xlsx`) — confirm they correctly find every
      column/row without hardcoding cell letters
- [ ] Writer produces a filled copy that opens cleanly in Excel with formatting intact
- [ ] Writer accumulates correctly across multiple video-segment runs targeting the same
      sheet
- [ ] Any unmatched/unmapped result triggers a visible warning, not a silent drop

---

Next: open `09_Phase7_Validation_and_QA.md`.
