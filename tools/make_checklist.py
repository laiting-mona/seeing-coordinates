"""Build the source-verification checklist for every status=review relation.

Last edited: 2026-10-29 — markdown written with LF on every OS (data_io.write_text_lf).
2026-10-28: 關係 column split into separate 來源 / 目標 columns; decision
dropdown column derived from HEADERS. 2026-10-27: functions + main(); loaders from data_io;
entity names follow data_io.display_label; openpyxl styling isolated in one function.

Outputs (both under docs/):
  原典查核清單.md    version-controlled table
  原典查核清單.xlsx  editable: 頁碼 column + 決定 dropdown (approved / rejected / 重構)
Usage (from the project root): python tools/make_checklist.py
"""
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent   # tools/ → project root
sys.path.insert(0, str(ROOT))
import data_io  # noqa: E402

OUTPUT_MD = ROOT / "docs/原典查核清單.md"
OUTPUT_XLSX = ROOT / "docs/原典查核清單.xlsx"
HEADERS = ["#", "來源", "目標", "類型", "主張", "建議查核原典", "頁碼(待補)", "決定", "備註"]
COLUMN_WIDTHS = [5, 24, 24, 8, 46, 34, 14, 14, 40]
DECISION_OPTIONS = '"approved,rejected,重構"'
DECISION_COLUMN = chr(65 + HEADERS.index("決定"))   # Excel column letter of the dropdown

# Suggested direction when source_ref has no bibliographic entry.
SOURCE_OVERRIDE = {
    "interpretation": "蕭爾《The Nature of Photographs》與相關評論(需指定具體文本)",
    "asx": "American Suburb X 評論平台(需找到具體文章)",
    "cphmag": "Conscientious 等評論平台(需找到具體文章)",
}
# Findings already recorded for specific pending relations.
NOTES = {
    ("sherman", "pictures_1977", "belongs_to"): "查證發現:1977 Pictures 展原始五人不含雪曼(1979 才被加入);已另記為圖景世代成員",
    ("sontag", "weston", "discusses"): "查證發現:桑塔格《論攝影》具名清單中未見威斯頓,建議 reject 或待原文確認",
}
KIND_SHORT = {"influence": "影響", "critique": "批判", "extend": "延伸", "belongs_to": "屬於", "contrast": "對照",
              "discusses": "討論", "translate": "譯本", "study": "研究", "review": "評論", "interpret": "詮釋", "exhibit": "展覽"}


def pending_relations(root: Path = ROOT) -> list[dict]:
    """status=review relations, grouped by target then source so one book is checked at once."""
    pending = [r for r in data_io.load_relation_dicts(root) if r["status"] == "review"]
    return sorted(pending, key=lambda r: (r["target_id"], r["source_id"]))


def suggested_source(relation: dict, sources: dict[str, dict]) -> str:
    """Which primary text to open for this relation."""
    ref = relation.get("source_ref", "")
    if ref in SOURCE_OVERRIDE:
        return SOURCE_OVERRIDE[ref]
    if ref in sources:
        title, author = sources[ref]["name_zh"], sources[ref].get("author", "")
        return f"{title}（{author}）" if author else title
    return "(需自行指定原典)"


def checklist_rows(pending: list[dict], label: dict[str, str], sources: dict[str, dict]) -> list[list]:
    """One table row per pending relation (page and decision columns left blank)."""
    rows = []
    for index, r in enumerate(pending, 1):
        source_name = label.get(r["source_id"], r["source_id"])
        target_name = label.get(r["target_id"], r["target_id"])
        note = NOTES.get((r["source_id"], r["target_id"], r["kind"]), "")
        rows.append([index, source_name, target_name, KIND_SHORT.get(r["kind"], r["kind"]), r["claim"],
                     suggested_source(r, sources), "", "", note])
    return rows


def write_markdown(rows: list[list], path: Path = OUTPUT_MD) -> None:
    lines = ["# 原典查核清單（觀看的座標）", "",
             f"待查證關係共 **{len(rows)}** 條。建議回對應原典補上頁碼級出處後,把『決定』填為 approved / rejected / 重構;",
             "確認後,把對應關係在 `data/raw_relations.jsonl` 的 `status` 改為 approved / rejected,並於 evidence 補上頁碼與來源,再執行 `python graph_build.py` 重建圖。", "",
             "| " + " | ".join(HEADERS) + " |", "|" + "---|" * len(HEADERS)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    data_io.write_text_lf(path, "\n".join(lines) + "\n")


def write_excel(rows: list[list], path: Path = OUTPUT_XLSX) -> None:
    """Styled sheet: dark header, wrapped cells, frozen header, decision dropdown."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "原典查核清單"
    header_fill, header_font = PatternFill("solid", fgColor="1E2329"), Font(bold=True, color="FFFFFF", size=11)
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    sheet.append(HEADERS)
    for column, width in enumerate(COLUMN_WIDTHS, 1):
        sheet.column_dimensions[chr(64 + column)].width = width
        cell = sheet.cell(row=1, column=column)
        cell.fill, cell.font, cell.border = header_fill, header_font, border
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        sheet.append(row)
    for row_cells in sheet.iter_rows(min_row=2, max_row=len(rows) + 1):
        for cell in row_cells:
            cell.alignment, cell.border = Alignment(wrap_text=True, vertical="top"), border
    dropdown = DataValidation(type="list", formula1=DECISION_OPTIONS, allow_blank=True)
    sheet.add_data_validation(dropdown)
    dropdown.add(f"{DECISION_COLUMN}2:{DECISION_COLUMN}{len(rows) + 1}")
    sheet.freeze_panes = "A2"
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def main() -> None:
    label = {row["id"]: data_io.display_label(row) for row in data_io.load_entity_rows(ROOT)}
    sources = {row["id"]: row for row in data_io.load_source_rows(ROOT)}
    rows = checklist_rows(pending_relations(ROOT), label, sources)
    write_markdown(rows)
    write_excel(rows)
    print(f"產出:{OUTPUT_MD.name}（{len(rows)} 條）、{OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
