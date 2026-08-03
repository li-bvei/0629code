from pathlib import Path
import json
import sys

import fitz


PRICES = [
    "391,400", "398,000", "566,100", "622,200",
    "483,600", "546,300", "807,000", "906,000",
    "984,500", "1,083,500", "1,136,300", "1,218,800",
]

PAGE_INDEX = 3
PAGE_WIDTH = 540.0
PAGE_HEIGHT = 780.0
PRICE_TOP = 44.111
PRICE_BOTTOM = 55.451
RMB_BOTTOM = 66.790
TABLE_LEFT = 231.330
CELL_WIDTH = 25.435
TABLE_RIGHT = 536.556


def centered_font_size(text: str, max_size: float = 5.05, padding: float = 1.15) -> float:
    available = CELL_WIDTH - 2 * padding
    size = max_size
    while fitz.get_text_length(text, fontname="helv", fontsize=size) > available:
        size -= 0.05
    return round(max(size, 3.8), 2)


def build(source_path: Path, output_path: Path, render_path: Path) -> dict:
    source = fitz.open(source_path)
    if len(source) <= PAGE_INDEX:
        raise ValueError("Source PDF does not contain page 4")
    source_rect = source[PAGE_INDEX].rect
    if abs(source_rect.width - PAGE_WIDTH) > 0.01 or abs(source_rect.height - PAGE_HEIGHT) > 0.01:
        raise ValueError(f"Unexpected page-4 size: {source_rect}")

    # Work in a one-page vector copy. Applying a true redaction removes the old
    # yen text from the content stream before the page fragments are composed.
    work = fitz.open()
    work.insert_pdf(source, from_page=PAGE_INDEX, to_page=PAGE_INDEX)
    work_page = work[0]
    work_page.add_redact_annot(
        fitz.Rect(TABLE_LEFT + 0.15, PRICE_TOP + 0.15, TABLE_RIGHT - 0.15, PRICE_BOTTOM - 0.15),
        fill=None,
    )
    work_page.add_redact_annot(
        fitz.Rect(2.0, PRICE_BOTTOM + 0.01, 537.05, RMB_BOTTOM - 0.01),
        fill=None,
    )
    work_page.apply_redactions(images=0, graphics=0, text=0)

    output = fitz.open()
    page = output.new_page(width=source_rect.width, height=source_rect.height)

    top_clip = fitz.Rect(0, 0, PAGE_WIDTH, PRICE_BOTTOM)
    page.show_pdf_page(top_clip, work, 0, clip=top_clip, keep_proportion=False)

    lower_clip = fitz.Rect(0, RMB_BOTTOM, PAGE_WIDTH, PAGE_HEIGHT)
    lower_target = fitz.Rect(0, PRICE_BOTTOM, PAGE_WIDTH, PAGE_HEIGHT - (RMB_BOTTOM - PRICE_BOTTOM))
    page.show_pdf_page(lower_target, work, 0, clip=lower_clip, keep_proportion=False)

    # Add the twelve replacement prices as independent, centered vector-text runs.
    placements = []
    for index, value in enumerate(PRICES):
        x0 = TABLE_LEFT + index * CELL_WIDTH
        x1 = TABLE_RIGHT if index == 11 else TABLE_LEFT + (index + 1) * CELL_WIDTH
        size = centered_font_size(value)
        width = fitz.get_text_length(value, fontname="helv", fontsize=size)
        x = x0 + ((x1 - x0) - width) / 2
        baseline = PRICE_TOP + ((PRICE_BOTTOM - PRICE_TOP) + size * 0.72) / 2
        page.insert_text((x, baseline), value, fontname="helv", fontsize=size, color=(0, 0, 0))
        placements.append({
            "value": value,
            "cell": [x0, PRICE_TOP, x1, PRICE_BOTTOM],
            "font_size": size,
            "text_width": width,
            "left_margin": x - x0,
            "right_margin": x1 - (x + width),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path, garbage=4, deflate=True, clean=True)
    output.close()
    work.close()
    source.close()

    check = fitz.open(output_path)
    check_page = check[0]
    extracted = check_page.get_text("text")
    rmb_terms = [
        "含税价格（人民币）", "9,570", "9,900", "18,305", "21,110", "14,180", "17,315",
        "30,350", "35,300", "39,225", "44,175", "46,815", "50,940",
    ]
    old_yen = [
        "191,400", "198,000", "366,100", "422,200", "283,600", "346,300",
        "607,000", "706,000", "784,500", "883,500", "936,300", "1,018,800",
    ]
    report = {
        "output": str(output_path),
        "pages": len(check),
        "page_size": [check_page.rect.width, check_page.rect.height],
        "rmb_absent": all(term not in extracted for term in rmb_terms),
        "old_yen_absent": all(term not in extracted for term in old_yen),
        "new_prices_present_once": {p: extracted.count(p) == 1 for p in PRICES},
        "yen_title_present": "含税价格（日元）" in extracted,
        "placements": placements,
        "all_margins_positive": all(x["left_margin"] > 1.0 and x["right_margin"] > 1.0 for x in placements),
    }
    matrix = fitz.Matrix(300 / 72, 300 / 72)
    pix = check_page.get_pixmap(matrix=matrix, alpha=False)
    render_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(render_path)
    report["render_pixels"] = [pix.width, pix.height]
    report["render_path"] = str(render_path)
    check.close()
    return report


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: modify_medcity_pdf.py SOURCE OUTPUT RENDER_PNG")
    result = build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
