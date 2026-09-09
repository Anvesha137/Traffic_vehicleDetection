"""
Accuracy Comparison: AI Pipeline Output vs. Human Ground Truth
Compares outputs/Site_15_Full_Output.xlsx against Site 15 - Veerasandra_Main_Road.xlsx
"""
import openpyxl
import os
from datetime import time as dtime

WORKSPACE = r"C:\Users\Admin\Desktop\Traffic"
GROUND_TRUTH = os.path.join(WORKSPACE, "Site 15 - Veerasandra_Main_Road.xlsx")
AI_OUTPUT = os.path.join(WORKSPACE, "outputs", "Site_15_Full_Output.xlsx")

VEHICLE_COLS = [
    "Two Wheelers (WP)", "Two Wheelers (Taxi)", "Car/Jeep/Van",
    "Auto-3wh", "Bus-BMTC", "Bus-KSRTC", "Bus-Other", "Bus-Mini",
    "Goods/LCV", "Trucks", "Tractor", "Cycle", "PBS", "Others"
]

# Column offsets for each movement block (0-indexed from block start)
# Block starts: Block1=col2, Block2=col18, Block3=col34
BLOCK_STARTS = {
    "Arm A": {"A-A": 2, "A-B": 18, "A-C": 34},
    "Arm B": {"B-A": 2, "B-B": 18, "B-C": 34},
    "Arm C": {"C-A": 2, "C-B": 18, "C-C": 34},
}

# Video covers ~28 minutes starting at 08:01:33
# This means we have data for time buckets: 08:00 and 08:15 (partially)
# We compare only rows where the video has coverage
VIDEO_TIME_BUCKETS = ["08:00", "08:15"]


def read_counts(wb_path, sheet_names, block_starts, time_buckets):
    """Read vehicle counts from an Excel file."""
    wb = openpyxl.load_workbook(wb_path, data_only=True)
    data = {}

    for sheet_name in sheet_names:
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        data[sheet_name] = {}

        # Build row index: time_str -> row_number
        time_rows = {}
        for r in range(7, ws.max_row + 1):
            val = ws.cell(row=r, column=1).value
            if val is not None:
                if isinstance(val, dtime):
                    t_str = val.strftime("%H:%M")
                else:
                    t_str = str(val).strip()[:5]
                    if len(t_str.split(":")[0]) == 1:
                        t_str = "0" + t_str
                time_rows[t_str] = r

        blocks = block_starts.get(sheet_name, {})
        for mov_code, start_col in blocks.items():
            data[sheet_name][mov_code] = {}
            for t_bucket in time_buckets:
                row = time_rows.get(t_bucket)
                if row is None:
                    continue
                counts = []
                for offset in range(14):  # 14 vehicle columns
                    val = ws.cell(row=row, column=start_col + offset).value
                    counts.append(int(val) if val is not None else 0)
                data[sheet_name][mov_code][t_bucket] = counts

    return data


def compare_and_score(gt_data, ai_data):
    """Compare ground truth vs AI output, compute accuracy metrics."""
    results = []
    total_gt = 0
    total_ai = 0
    total_abs_error = 0
    total_cells = 0
    exact_matches = 0

    for sheet in gt_data:
        for mov in gt_data[sheet]:
            for t_bucket in gt_data[sheet][mov]:
                gt_row = gt_data[sheet].get(mov, {}).get(t_bucket, [0]*14)
                ai_row = ai_data.get(sheet, {}).get(mov, {}).get(t_bucket, [0]*14)

                for i in range(14):
                    gt_val = gt_row[i]
                    ai_val = ai_row[i] if i < len(ai_row) else 0
                    abs_err = abs(gt_val - ai_val)

                    total_gt += gt_val
                    total_ai += ai_val
                    total_abs_error += abs_err
                    total_cells += 1
                    if gt_val == ai_val:
                        exact_matches += 1

                    if gt_val > 0 or ai_val > 0:  # only report non-zero rows
                        results.append({
                            "sheet": sheet, "movement": mov, "time": t_bucket,
                            "category": VEHICLE_COLS[i],
                            "ground_truth": gt_val, "ai_output": ai_val,
                            "error": ai_val - gt_val, "abs_error": abs_err
                        })

    return results, total_gt, total_ai, total_abs_error, total_cells, exact_matches


def main():
    print("=" * 80)
    print("ACCURACY REPORT: AI Pipeline vs Human Ground Truth")
    print("=" * 80)

    if not os.path.exists(AI_OUTPUT):
        print(f"ERROR: AI output not found at {AI_OUTPUT}")
        print("Run the pipeline first.")
        return

    sheets = ["Arm A", "Arm B", "Arm C"]

    gt_data = read_counts(GROUND_TRUTH, sheets, BLOCK_STARTS, VIDEO_TIME_BUCKETS)
    ai_data = read_counts(AI_OUTPUT, sheets, BLOCK_STARTS, VIDEO_TIME_BUCKETS)

    results, total_gt, total_ai, total_abs_err, total_cells, exact_matches = compare_and_score(gt_data, ai_data)

    # --- Per-cell detail (non-zero only) ---
    print(f"\n{'Sheet':<8} {'Move':<5} {'Time':<6} {'Category':<22} {'GT':>5} {'AI':>5} {'Err':>5}")
    print("-" * 70)
    for r in sorted(results, key=lambda x: (x['sheet'], x['movement'], x['time'], x['category'])):
        marker = " OK" if r['error'] == 0 else ""
        print(f"{r['sheet']:<8} {r['movement']:<5} {r['time']:<6} {r['category']:<22} {r['ground_truth']:>5} {r['ai_output']:>5} {r['error']:>+5}{marker}")

    # --- Per-sheet totals ---
    print("\n" + "=" * 60)
    print("PER-SHEET TOTAL VEHICLE COUNTS")
    print("=" * 60)
    for sheet in sheets:
        gt_sheet_total = 0
        ai_sheet_total = 0
        for mov in gt_data.get(sheet, {}):
            for tb in VIDEO_TIME_BUCKETS:
                gt_row = gt_data.get(sheet, {}).get(mov, {}).get(tb, [0]*14)
                ai_row = ai_data.get(sheet, {}).get(mov, {}).get(tb, [0]*14)
                gt_sheet_total += sum(gt_row)
                ai_sheet_total += sum(ai_row)
        pct_err = abs(gt_sheet_total - ai_sheet_total) / max(gt_sheet_total, 1) * 100
        print(f"  {sheet}: GT={gt_sheet_total:>5}   AI={ai_sheet_total:>5}   Abs Diff={abs(gt_sheet_total - ai_sheet_total):>5}   Error={pct_err:.1f}%")

    # --- Aggregate metrics ---
    print("\n" + "=" * 60)
    print("AGGREGATE ACCURACY METRICS")
    print("=" * 60)
    print(f"  Total Ground Truth vehicles:     {total_gt}")
    print(f"  Total AI-detected vehicles:      {total_ai}")
    print(f"  Total Absolute Cell Error:        {total_abs_err}")
    print(f"  Total Cells Compared:             {total_cells}")
    print(f"  Exact Cell Matches:               {exact_matches} / {total_cells} ({exact_matches/max(total_cells,1)*100:.1f}%)")

    mean_abs_err = total_abs_err / max(total_cells, 1)
    overall_pct_err = abs(total_gt - total_ai) / max(total_gt, 1) * 100
    print(f"  Mean Absolute Error per Cell:     {mean_abs_err:.2f}")
    print(f"  Overall Count Error (%):          {overall_pct_err:.1f}%")

    # Per-category accuracy
    print("\n" + "=" * 60)
    print("PER-CATEGORY ACCURACY")
    print("=" * 60)
    cat_gt = {}
    cat_ai = {}
    for r in results:
        cat = r['category']
        cat_gt[cat] = cat_gt.get(cat, 0) + r['ground_truth']
        cat_ai[cat] = cat_ai.get(cat, 0) + r['ai_output']

    print(f"  {'Category':<22} {'GT':>6} {'AI':>6} {'Diff':>6} {'Error%':>8}")
    print("  " + "-" * 52)
    for cat in VEHICLE_COLS:
        g = cat_gt.get(cat, 0)
        a = cat_ai.get(cat, 0)
        d = a - g
        pct = abs(d) / max(g, 1) * 100
        print(f"  {cat:<22} {g:>6} {a:>6} {d:>+6} {pct:>7.1f}%")


if __name__ == "__main__":
    main()
