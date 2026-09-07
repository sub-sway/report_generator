import json
import os
from pathlib import Path

import fitz
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
PDF_PATH = Path("documents/tunnel_safety_manual.pdf")
OUTPUT_DIR = Path("data")
CHUNKS_PATH = OUTPUT_DIR / "chunks.json"
EMBEDDINGS_PATH = OUTPUT_DIR / "embeddings.npy"

EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small",
)

client = OpenAI()


def extract_pdf_pages(pdf_path: Path) -> list[dict]:
    """PDF에서 페이지별 텍스트를 추출합니다."""
    document = fitz.open(pdf_path)
    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text", sort=True).strip()

        if text:
            pages.append({
                "page": page_number,
                "text": text,
            })

    document.close()
    return pages


def split_text(
    text: str,
    chunk_size: int = 900,
    overlap: int = 150,
) -> list[str]:
    """
    긴 페이지 텍스트를 일정 길이의 청크로 나눕니다.
    overlap은 조항이 청크 경계에서 끊기는 것을 줄여줍니다.
    """
    normalized = " ".join(text.split())

    if not normalized:
        return []

    chunks = []
    start = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end]

        # 가능하면 문장 또는 항목 끝에서 자릅니다.
        if end < len(normalized):
            candidates = [
                chunk.rfind("."),
                chunk.rfind("다."),
                chunk.rfind("\n"),
                chunk.rfind("○"),
            ]
            cut_position = max(candidates)

            if cut_position > chunk_size // 2:
                end = start + cut_position + 1
                chunk = normalized[start:end]

        chunks.append(chunk.strip())

        if end >= len(normalized):
            break

        start = max(end - overlap, start + 1)

    return chunks


def create_chunks(pages: list[dict]) -> list[dict]:
    chunks = []

    for page_data in pages:
        page_number = page_data["page"]
        page_chunks = split_text(page_data["text"])

        for chunk_number, text in enumerate(page_chunks):
            chunks.append({
                "id": f"page-{page_number}-chunk-{chunk_number}",
                "source": PDF_PATH.name,
                "page": page_number,
                "text": text,
            })

    return chunks


def create_embeddings(texts: list[str], batch_size: int = 100) -> np.ndarray:
    """여러 청크의 임베딩을 배치 단위로 생성합니다."""
    all_embeddings = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
        )

        batch_embeddings = [
            item.embedding
            for item in response.data
        ]

        all_embeddings.extend(batch_embeddings)

        print(
            f"임베딩 진행: "
            f"{min(start + batch_size, len(texts))}/{len(texts)}"
        )

    embeddings = np.asarray(all_embeddings, dtype=np.float32)

    # 코사인 유사도 계산을 위해 벡터를 정규화합니다.
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / np.clip(norms, 1e-12, None)

    return embeddings


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"PDF 파일을 찾을 수 없습니다: {PDF_PATH}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pages = extract_pdf_pages(PDF_PATH)

    if not pages:
        raise RuntimeError(
            "PDF에서 텍스트를 추출하지 못했습니다. "
            "스캔 PDF라면 OCR 처리가 필요합니다."
        )

    chunks = create_chunks(pages)

    if not chunks:
        raise RuntimeError("생성된 텍스트 청크가 없습니다.")

    embeddings = create_embeddings(
        [chunk["text"] for chunk in chunks]
    )

    with CHUNKS_PATH.open("w", encoding="utf-8") as file:
        json.dump(chunks, file, ensure_ascii=False, indent=2)

    np.save(EMBEDDINGS_PATH, embeddings)

    print(f"페이지 수: {len(pages)}")
    print(f"청크 수: {len(chunks)}")
    print(f"청크 저장: {CHUNKS_PATH}")
    print(f"벡터 저장: {EMBEDDINGS_PATH}")


if __name__ == "__main__":
    main()