from pathlib import Path
import hashlib
import json
import sys

import fitz


REPLACEMENTS = [
    ("¥308,000", "¥508,000"),
    ("¥440,000", "¥640,000"),
    ("¥693,000", "¥893,000"),
    ("¥693,000", "¥893,000"),
    ("¥517,000", "¥717,000"),
    ("¥550,000", "¥750,000"),
    ("¥1,210,000", "¥1,410,000"),
    ("¥1,408,000", "¥1,608,000"),
]

OPTION_LEFT = 771.946
OPTION_RIGHT = 822.687
TABLE_TOP = 54.0
TABLE_BOTTOM = 939.39


def price_spans(page):
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                x0, y0, x1, y1 = span["bbox"]
                if (
                    span["font"] == "YuGothic-Bold"
                    and 365 < x0 < 770
                    and 98 < y0 < 105
                ):
                    spans.append(span)
    spans.sort(key=lambda s: s["bbox"][0])
    return spans


def untouched_span_signature(page, is_source):
    result = []
    old_price_boxes = []
    if is_source:
        old_price_boxes = [fitz.Rect(s["bbox"]) for s in price_spans(page)]
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                rect = fitz.Rect(span["bbox"])
                in_deleted_column = rect.x0 >= OPTION_LEFT and rect.y0 < TABLE_BOTTOM
                is_old_price = any(rect.intersects(box) for box in old_price_boxes)
                is_new_price = (
                    not is_source
                    and span["font"] == "YuGothic-Bold"
                    and 365 < rect.x0 < 770
                    and 98 < rect.y0 < 105
                )
                if in_deleted_column or is_old_price or is_new_price:
                    continue
                result.append((
                    span["text"], span["font"], round(span["size"], 3), span["color"],
                    tuple(round(v, 2) for v in span["bbox"]),
                ))
    return result


def build(source_path: Path, output_path: Path, render_path: Path, top_render_path: Path):
    source = fitz.open(source_path)
    if len(source) != 1:
        raise ValueError(f"Expected one source page, found {len(source)}")
    source_page = source[0]
    spans = price_spans(source_page)
    if len(spans) != 8:
        raise ValueError(f"Expected 8 package-price spans, found {len(spans)}")
    old_values = [s["text"] for s in spans]
    if old_values != [x[0] for x in REPLACEMENTS]:
        raise ValueError(f"Unexpected source prices: {old_values}")

    output = fitz.open()
    output.insert_pdf(source)
    page = output[0]

    # Remove each old package price from the content stream without touching
    # its gray cell background or borders.
    for span in spans:
        rect = fitz.Rect(span["bbox"])
        page.add_redact_annot(rect + (-0.2, -0.2, 0.2, 0.2), fill=None)

    # Remove all text and self-contained graphics in the optional-price column.
    # The white fill clears row backgrounds that span multiple columns; because
    # text and contained graphics are truly redacted, this is not concealment.
    page.add_redact_annot(
        fitz.Rect(OPTION_LEFT, TABLE_TOP, OPTION_RIGHT + 0.2, TABLE_BOTTOM),
        fill=(1, 1, 1),
    )
    page.apply_redactions(images=0, graphics=2, text=0)

    # Reuse the exact embedded Yu Gothic Bold font from the source PDF.
    font_xref = next(f[0] for f in source_page.get_fonts(full=True) if "YuGothic-Bold" in f[3])
    font_buffer = source.extract_font(font_xref)[3]
    font = fitz.Font(fontbuffer=font_buffer)
    writer = fitz.TextWriter(page.rect)
    placements = []
    for span, (_, new_value) in zip(spans, REPLACEMENTS):
        origin = fitz.Point(span["origin"])
        size = span["size"]
        writer.append(origin, new_value, font=font, fontsize=size)
        placements.append({
            "old": span["text"],
            "new": new_value,
            "origin": [origin.x, origin.y],
            "font_size": size,
            "rendered_width": font.text_length(new_value, size),
        })
    writer.write_text(page, color=(0, 0, 0), overlay=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path, garbage=4, deflate=True, clean=True)
    output.close()

    check = fitz.open(output_path)
    check_page = check[0]
    text = check_page.get_text("text")
    new_values = [x[1] for x in REPLACEMENTS]
    option_texts = [
        "可选项价格", "（含税）", "¥4,125", "¥1,375", "¥2,750", "¥110,000",
        "¥165,000", "¥192,500", "¥13,750", "¥41,250", "¥22,000", "¥16,500",
        "¥68,750", "¥206,250", "¥137,500", "¥55,000", "¥53,625", "¥27,500",
    ]
    # Some option prices also occur in the unchanged legend/notes or package
    # area. Coordinate-level checks are therefore authoritative for the column.
    remaining_column_spans = []
    for block in check_page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                r = fitz.Rect(span["bbox"])
                if r.x0 >= OPTION_LEFT and r.y0 < TABLE_BOTTOM:
                    remaining_column_spans.append((span["text"], tuple(span["bbox"])))

    matrix = fitz.Matrix(300 / 72, 300 / 72)
    pix = check_page.get_pixmap(matrix=matrix, alpha=False)
    render_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(render_path)
    top_pix = check_page.get_pixmap(
        matrix=fitz.Matrix(400 / 72, 400 / 72),
        clip=fitz.Rect(340, 45, 835, 125),
        alpha=False,
    )
    top_pix.save(top_render_path)

    report = {
        "output": str(output_path),
        "pages": len(check),
        "page_size": [check_page.rect.width, check_page.rect.height],
        "new_prices_exact_once": {v: text.count(v) == new_values.count(v) for v in set(new_values)},
        "old_unique_prices_absent": all(v not in text for v in ["¥308,000", "¥440,000", "¥517,000", "¥550,000", "¥1,210,000", "¥1,408,000"]),
        "deleted_column_spans": remaining_column_spans,
        "deleted_column_title_absent": "可选项价格" not in text,
        "all_option_prices_absent": all(value not in text for value in option_texts[2:]),
        "untouched_spans_identical": untouched_span_signature(source_page, True) == untouched_span_signature(check_page, False),
        "placements": placements,
        "render_pixels": [pix.width, pix.height],
        "render_path": str(render_path),
        "top_render_path": str(top_render_path),
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }
    check.close()
    source.close()
    return report


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("Usage: modify_timc_pdf.py SOURCE OUTPUT PAGE_PNG TOP_PNG")
    print(json.dumps(build(*(Path(x) for x in sys.argv[1:])), ensure_ascii=False, indent=2))
