import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from pdf_report import create_combined_report
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

CHUNKS_PATH = Path("data/chunks.json")
EMBEDDINGS_PATH = Path("data/embeddings.npy")

EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small",
)

LLM_MODEL = os.getenv(
    "OPENAI_LLM_MODEL",
    "gpt-5.6-terra",
)

client = OpenAI()


def load_index() -> tuple[list[dict], np.ndarray]:
    if not CHUNKS_PATH.exists() or not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(
            "검색 인덱스가 없습니다. 먼저 build_index.py를 실행하세요."
        )

    with CHUNKS_PATH.open("r", encoding="utf-8") as file:
        chunks = json.load(file)

    embeddings = np.load(EMBEDDINGS_PATH)

    if len(chunks) != len(embeddings):
        raise RuntimeError(
            "청크 개수와 임베딩 개수가 일치하지 않습니다."
        )

    return chunks, embeddings


def make_search_query(defect: dict[str, Any]) -> str:
    """
    단순 JSON 문자열보다 시설물, 손상 종류, 치수와
    판단 목적을 명확히 넣어 검색 정확도를 높입니다.
    """
    return (
        f"시설물 종류: {defect.get('facility', '')}\n"
        f"점검 부재: {defect.get('component', '')}\n"
        f"손상 종류: {defect.get('defect', '')}\n"
        f"균열 길이: {defect.get('length_mm', '')} mm\n"
        f"최대 균열폭: {defect.get('max_width_mm', '')} mm\n"
        "이 손상의 평가 기준, 균열폭 기준, 상태등급, "
        "보수 필요 여부, 추적관찰 주기 및 조치 방법"
    )


def embed_query(query: str) -> np.ndarray:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )

    vector = np.asarray(
        response.data[0].embedding,
        dtype=np.float32,
    )

    norm = np.linalg.norm(vector)

    if norm == 0:
        raise RuntimeError("검색 질의 임베딩의 크기가 0입니다.")

    return vector / norm


def retrieve(
    defect: dict[str, Any],
    chunks: list[dict],
    embeddings: np.ndarray,
    top_k: int = 5,
) -> list[dict]:
    query = make_search_query(defect)
    query_vector = embed_query(query)

    scores = embeddings @ query_vector

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []

    for index in top_indices:
        chunk = chunks[int(index)].copy()
        chunk["similarity"] = round(float(scores[index]), 4)
        results.append(chunk)

    return results


def build_context(search_results: list[dict]) -> str:
    sections = []

    for index, result in enumerate(search_results, start=1):
        sections.append(
            f"[근거 {index}]\n"
            f"문서: {result['source']}\n"
            f"페이지: {result['page']}\n"
            f"검색 유사도: {result['similarity']}\n"
            f"내용:\n{result['text']}"
        )

    return "\n\n".join(sections)


def generate_inspection_result(
    defect: dict[str, Any],
    search_results: list[dict],
) -> dict[str, Any]:
    context = build_context(search_results)

    prompt = f"""
당신은 터널 시설물 안전점검 보고서 작성 보조 시스템입니다.

다음 점검 데이터와 검색된 안전점검 기준만 사용하여 결과를 작성하세요.

[중요 원칙]
1. 검색된 근거에 없는 기준값이나 등급을 임의로 만들지 마세요.
2. 근거가 부족하면 반드시 "판단 보류" 또는 "추가 확인 필요"라고 작성하세요.
3. 균열 검출 신뢰도는 AI 모델의 검출 신뢰도이며, 구조 안전도를 의미하지 않습니다.
4. 최종 판정은 자격을 갖춘 점검자가 검토해야 합니다.
5. 반드시 유효한 JSON만 출력하세요.
6. 근거 페이지 번호를 sources에 기록하세요.

[점검 데이터]
{json.dumps(defect, ensure_ascii=False, indent=2)}

[검색된 점검 기준]
{context}

다음 형식으로 출력하세요.

{{
  "inspection_summary": "점검결과 요약",
  "defect_assessment": "손상 정도에 대한 판단",
  "recommended_action": "권장 조치사항",
  "urgency": "즉시조치 | 단기조치 | 추적관찰 | 판단보류",
  "additional_inspection": [
    "추가로 확인할 항목"
  ],
  "sources": [
    {{
      "document": "문서명",
      "page": 1,
      "reason": "해당 근거를 사용한 이유"
    }}
  ],
  "review_required": true
}}
"""

    response = client.responses.create(
        model=LLM_MODEL,
        input=prompt,
    )

    raw_output = response.output_text.strip()

    # 모델이 코드 블록을 붙인 경우를 대비합니다.
    if raw_output.startswith("```"):
        raw_output = raw_output.removeprefix("```json")
        raw_output = raw_output.removeprefix("```")
        raw_output = raw_output.removesuffix("```")
        raw_output = raw_output.strip()

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"LLM 출력이 올바른 JSON이 아닙니다.\n\n{raw_output}"
        ) from error

def main() -> None:
    with Path("defect.json").open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        defects = json.load(file)

    # 단일 결함 객체도 배열로 변환
    if isinstance(defects, dict):
        defects = [defects]

    if not isinstance(defects, list):
        raise ValueError(
            "defect.json은 객체 또는 객체 배열이어야 합니다."
        )

    chunks, embeddings = load_index()

    all_results = []

    for index, defect in enumerate(defects, start=1):
        print(
            f"\n=== 결함 {index}/{len(defects)} 처리 시작 ==="
        )

        search_results = retrieve(
            defect=defect,
            chunks=chunks,
            embeddings=embeddings,
            top_k=5,
        )

        print("검색된 기준:")

        for search_result in search_results:
            print(
                f"- 페이지 {search_result['page']}, "
                f"유사도 {search_result['similarity']}"
            )

        output = generate_inspection_result(
            defect=defect,
            search_results=search_results,
        )

        print("\n점검 결과:")
        print(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
            )
        )

        all_results.append({
            "defect_id": index,
            "defect_data": defect,
            "inspection_result": output,
            "retrieved_sources": search_results,
        })

    pdf_output_path = Path(
        "inspection_combined_report.pdf"
    )

    create_combined_report(
        report_items=all_results,
        output_path=pdf_output_path,
    )

    print(
        f"종합 PDF 저장 완료: "
        f"{pdf_output_path.resolve()}"
    )


if __name__ == "__main__":
    main()