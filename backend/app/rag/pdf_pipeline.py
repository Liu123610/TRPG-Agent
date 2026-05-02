from __future__ import annotations

import pickle
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.settings import settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_NAME = "DnD_5E_新手套组_基础入门规则CN.pdf"
SOURCE_TAG = "DnD_5E_新手套组_基础入门规则CN"
DB_PATH = Path(settings.rag_db_dir)
if not DB_PATH.is_absolute():
    DB_PATH = BACKEND_DIR / DB_PATH
BM25_PATH = DB_PATH / "bm25_index.pkl"

IN_SCOPE_CATEGORIES = {"combat", "adventuring", "conditions"}

CHAPTER_CATEGORY = {
    "第2章 战斗": "combat",
    "第3章 冒险": "adventuring",
    "附录 状态": "conditions",
    "附录：状态": "conditions",
}

SECTION_SUB_CATEGORY = {
    "战斗流程": "combat_order",
    "移动与位置": "movement_position",
    "战斗动作": "action_in_combat",
    "发动攻击": "making_attack",
    "掩护": "cover",
    "伤害与治疗": "damage_healing",
    "旅行": "travel",
    "休息": "resting",
    "奖励": "rewards",
    "装备": "equipment",
    "目盲": "conditions_blinded",
    "魅惑": "conditions_charmed",
    "耳聋": "conditions_deafened",
    "恐慌": "conditions_frightened",
    "擒抱": "conditions_grappled",
    "失能": "conditions_incapacitated",
    "隐形": "conditions_invisible",
    "麻痹": "conditions_paralyzed",
    "石化": "conditions_petrified",
    "中毒": "conditions_poisoned",
    "倒地": "conditions_prone",
    "束缚": "conditions_restrained",
    "震慑": "conditions_stunned",
    "昏迷": "conditions_unconscious",
}

CONDITION_TITLES = {
    "目盲",
    "魅惑",
    "耳聋",
    "恐慌",
    "擒抱",
    "失能",
    "隐形",
    "麻痹",
    "石化",
    "中毒",
    "倒地",
    "束缚",
    "震慑",
    "昏迷",
}

TITLE_COLOR = 0x800000


@dataclass(slots=True)
class PdfLine:
    page_index: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    max_size: float
    color: int


@dataclass(slots=True)
class SectionAnchor:
    level: int
    title: str
    chapter: str
    category: str
    sub_category: str
    page_index: int
    y0: float
    x0: float = 0.0


def _normalize_key(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[\s:：？?·.,，。()（）\-—]+", "", value)


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = title.replace("第1章", "第1章 ").replace("第2章", "第2章 ").replace("第3章", "第3章 ")
    title = title.replace("第4章", "第4章 ")
    return title


def _resolve_source_pdf() -> Path:
    if settings.rag_source_pdf_path:
        path = Path(settings.rag_source_pdf_path)
        if path.exists():
            return path

    search_root = Path.home() / "Downloads" / "DND_5E"
    if search_root.exists():
        for path in search_root.rglob("*.pdf"):
            if path.name == DEFAULT_SOURCE_NAME:
                return path

    fallback = Path(__file__).resolve().parent / "data" / DEFAULT_SOURCE_NAME
    if fallback.exists():
        return fallback

    raise FileNotFoundError(
        "未找到规则 PDF。请设置 TRPG_RAG_SOURCE_PDF_PATH 指向 DnD_5E_新手套组_基础入门规则CN.pdf。"
    )


def _line_text(line: dict) -> str:
    return "".join(span["text"] for span in line["spans"]).strip()


def _extract_page_lines(page: fitz.Page, page_index: int) -> list[PdfLine]:
    page_width = page.rect.width
    page_height = page.rect.height
    raw = page.get_text("dict")
    lines: list[PdfLine] = []

    for block in raw["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = _line_text(line)
            if not text:
                continue
            if text.isdigit():
                continue

            x0, y0, x1, y1 = line["bbox"]
            if y0 < 45 or y0 > page_height - 35:
                continue

            spans = line["spans"]
            max_size = max(span["size"] for span in spans)
            color = spans[0].get("color", 0)
            lines.append(PdfLine(page_index, x0, y0, x1, y1, text, max_size, color))

    # 中文双栏排版必须按栏排序，否则 PDF 文本流会串栏。
    mid_x = page_width / 2
    return sorted(lines, key=lambda item: (0 if item.x0 < mid_x else 1, item.y0, item.x0))


def _all_lines(doc: fitz.Document) -> list[PdfLine]:
    lines: list[PdfLine] = []
    for page_index in range(doc.page_count):
        lines.extend(_extract_page_lines(doc[page_index], page_index))
    return lines


def _chapter_for_toc(title: str, current_chapter: str) -> tuple[str, str]:
    if title.startswith("第2章"):
        return "第2章 战斗", "combat"
    if title.startswith("第3章"):
        return "第3章 冒险", "adventuring"
    if title.startswith("第4章"):
        return "", ""
    if title.startswith("附录"):
        return "附录：状态", "conditions"
    return current_chapter, CHAPTER_CATEGORY.get(current_chapter, "")


def _title_position(lines: list[PdfLine], title: str, page_index: int) -> tuple[float, float]:
    title_key = _normalize_key(title)
    title_head = _normalize_key(re.split(r"\s+", title)[0])
    candidates = [line for line in lines if line.page_index == page_index]
    for line in candidates:
        if not _is_title_line(line):
            continue
        line_key = _normalize_key(line.text)
        if title_key and title_key in line_key:
            return line.x0, line.y0
        if title_head and title_head in line_key and (line.color == TITLE_COLOR or line.max_size >= 9.5):
            return line.x0, line.y0
    return 0.0, 0.0


def _title_y(lines: list[PdfLine], title: str, page_index: int) -> float:
    return _title_position(lines, title, page_index)[1]


def _reading_key(page_index: int, x0: float, y0: float) -> tuple[int, int, float]:
    return page_index, 0 if x0 < 300 else 1, y0


def _condition_anchors(
    lines: list[PdfLine],
    chapter: str,
    category: str,
    start_page_index: int,
    start_y: float,
) -> list[SectionAnchor]:
    anchors: list[SectionAnchor] = []
    if category != "conditions":
        return anchors

    for line in lines:
        if line.page_index < start_page_index:
            continue
        if line.page_index == start_page_index and line.y0 <= start_y + 1 and line.x0 < 300:
            continue
        if line.color != TITLE_COLOR or line.max_size < 9.0:
            continue
        for title in CONDITION_TITLES:
            if _normalize_key(title) and _normalize_key(line.text).startswith(_normalize_key(title)):
                anchors.append(
                    SectionAnchor(
                        level=2,
                        title=title,
                        chapter=chapter,
                        category=category,
                        sub_category=SECTION_SUB_CATEGORY[title],
                        page_index=line.page_index,
                        y0=line.y0,
                        x0=line.x0,
                    )
                )
                break
    return anchors


def _toc_anchors(doc: fitz.Document, lines: list[PdfLine]) -> list[SectionAnchor]:
    anchors: list[SectionAnchor] = []
    current_chapter = ""
    current_category = ""
    condition_start_page_index: int | None = None
    condition_start_y = 0.0

    for level, raw_title, page_number, *_ in doc.get_toc(simple=False):
        title = _clean_title(raw_title)
        chapter, category = _chapter_for_toc(title, current_chapter)
        if level == 1:
            current_chapter = chapter
            current_category = category
            if category == "conditions":
                page_index = max(int(page_number) - 1, 0)
                y0 = _title_y(lines, chapter, page_index)
                if condition_start_page_index is None or page_index < condition_start_page_index:
                    condition_start_page_index = page_index
                    condition_start_y = y0
        if category not in IN_SCOPE_CATEGORIES and level != 1:
            continue

        page_index = max(int(page_number) - 1, 0)
        if level == 1:
            sub_category = "chapter"
            anchor_title = chapter
        else:
            sub_category = SECTION_SUB_CATEGORY.get(title, "unknown")
            anchor_title = title

        x0, y0 = _title_position(lines, anchor_title, page_index)
        anchors.append(
            SectionAnchor(
                level=level,
                title=anchor_title,
                chapter=chapter or current_chapter,
                category=category or current_category,
                sub_category=sub_category,
                page_index=page_index,
                y0=y0,
                x0=x0,
            )
        )

    anchors.extend(
        _condition_anchors(
            lines,
            "附录：状态",
            "conditions",
            condition_start_page_index or 0,
            condition_start_y,
        )
    )
    anchors.sort(key=lambda item: (*_reading_key(item.page_index, item.x0, item.y0), item.level))
    return anchors


def _line_in_span(line: PdfLine, start: SectionAnchor, end: SectionAnchor | None) -> bool:
    line_key = _reading_key(line.page_index, line.x0, line.y0)
    start_key = _reading_key(start.page_index, start.x0, start.y0)
    if line_key < start_key:
        return False
    if end and line_key >= _reading_key(end.page_index, end.x0, end.y0):
        return False
    return True


def _is_title_line(line: PdfLine) -> bool:
    return line.color == TITLE_COLOR or line.max_size >= 11.5


def _merge_text_lines(lines: Iterable[PdfLine]) -> str:
    paragraphs: list[str] = []
    current = ""
    previous: PdfLine | None = None

    for line in lines:
        text = line.text.strip()
        if not text:
            continue

        gap = line.y0 - previous.y1 if previous and previous.page_index == line.page_index else 99
        starts_new = (
            not current
            or text.startswith("•")
            or _is_title_line(line)
            or gap > 8
        )

        if starts_new:
            if current:
                paragraphs.append(current.strip())
            current = text
        else:
            joiner = " " if re.search(r"[A-Za-z0-9]$", current) and re.match(r"[A-Za-z0-9]", text) else ""
            current = f"{current}{joiner}{text}"

        previous = line

    if current:
        paragraphs.append(current.strip())

    text = "\n".join(paragraphs)
    text = re.sub(r"([，。；：！？、）])\n(?=[^\n•])", r"\1", text)
    return text.strip()


def _section_documents(doc: fitz.Document) -> list[Document]:
    lines = _all_lines(doc)
    anchors = _toc_anchors(doc, lines)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=360,
        chunk_overlap=40,
        separators=["\n\n", "\n", "。", "；", "，", ""],
    )
    documents: list[Document] = []

    for index, anchor in enumerate(anchors):
        if anchor.category not in IN_SCOPE_CATEGORIES or anchor.sub_category == "chapter":
            continue
        next_anchor = anchors[index + 1] if index + 1 < len(anchors) else None
        span_lines = [line for line in lines if _line_in_span(line, anchor, next_anchor)]
        content = _merge_text_lines(span_lines)
        # 状态规则经常只有一两条短句，不能按普通章节的长度阈值丢弃。
        min_content_length = 30 if anchor.category == "conditions" else 80
        if len(content) < min_content_length:
            continue

        page_end = span_lines[-1].page_index + 1 if span_lines else anchor.page_index + 1
        metadata = {
            "source": SOURCE_TAG,
            "source_file": DEFAULT_SOURCE_NAME,
            "page_start": anchor.page_index + 1,
            "page_end": page_end,
            "chapter": anchor.chapter,
            "section": anchor.title,
            "category": anchor.category,
            "sub_category": anchor.sub_category,
        }

        for chunk in splitter.split_text(content):
            chunk = chunk.strip()
            # 保留短状态条目，否则“目盲”“中毒”这类精准问答会失去证据。
            min_chunk_length = 30 if anchor.category == "conditions" else 80
            if len(chunk) >= min_chunk_length:
                documents.append(Document(page_content=chunk, metadata=dict(metadata)))

    return documents


def _reset_db_dir(path: Path) -> None:
    resolved = path.resolve()
    data_dir = (BACKEND_DIR / "data").resolve()
    if data_dir not in resolved.parents:
        raise ValueError(f"Refuse to reset RAG DB outside backend/data: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def main() -> None:
    pdf_path = _resolve_source_pdf()
    with fitz.open(pdf_path) as doc:
        documents = _section_documents(doc)

    print(f"PDF source: {pdf_path}")
    print(f"Total PDF chunks: {len(documents)}")
    if not documents:
        return

    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        check_embedding_ctx_length=False,
        chunk_size=10,
    )

    _reset_db_dir(DB_PATH)
    Chroma.from_documents(
        documents,
        embedding=embeddings,
        persist_directory=str(DB_PATH),
    )

    BM25_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_PATH, "wb") as file:
        pickle.dump(documents, file)

    print(f"ChromaDB persisted to {DB_PATH}")
    print(f"BM25 index persisted to {BM25_PATH}")


if __name__ == "__main__":
    main()
