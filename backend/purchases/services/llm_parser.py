"""
거래명세서(PDF/사진) → LLM(OpenRouter vision 모델) 구조화 파싱.

모델은 .env 의 OPENROUTER_MODEL 로 교체 가능하게 설계했다.
공급업체마다 표 양식이 제각각이라, OCR+텍스트LLM 2단계보다 이미지를 직접 보고
표 구조를 판단하는 vision 모델 쪽이 더 안정적이라고 판단해 이 방식을 택했다.
"""
import base64
import io
import json
import re

import pymupdf as fitz  # PyMuPDF (신규 패키지명)
import httpx
from django.conf import settings
from PIL import Image

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MAX_IMAGE_DIM = 2000  # 너무 큰 이미지는 리사이즈 (토큰/비용/속도 절약)

SYSTEM_PROMPT = """당신은 한국 식당의 거래명세서(세금계산서, 납품서 등)를 읽고 구조화된 JSON으로 변환하는 도우미입니다.

이미지에 있는 표를 보고 다음 JSON 스키마로만 응답하세요. 다른 설명 텍스트는 절대 포함하지 마세요.

{
  "supplier_name": "공급업체명 (문서에 있는 그대로, 예: (주)본네이처)",
  "document_date": "YYYY-MM-DD 형식의 거래일자 (알 수 없으면 null)",
  "document_number": "전표번호/일련번호 (없으면 빈 문자열)",
  "items": [
    {
      "name": "품목명 전체 (예: 136참돔회(필렛) [일산])",
      "spec": "산지/규격 설명만 (예: 일산, 국산, 완도산). 수량·단위 아님",
      "unit": "수량 단위만 (예: kg, 마리, 박스). 없으면 빈 문자열",
      "quantity": 숫자 (소수 유지, 예: 0.782 를 0.78 로 줄이지 말 것). 단위 글자는 빼고 숫자만",
      "unit_price": 숫자,
      "amount": 숫자 (공급가액/금액 열의 값)
    }
  ],
  "supply_amount": 공급가액 합계 숫자 (없으면 0),
  "tax_amount": 부가세 합계 숫자 (없으면 0),
  "total_amount": 합계금액 숫자 (없으면 items의 amount 합)
}

규칙:
- 숫자는 콤마/원화기호 없이 순수 숫자로만 (예: 69969, "69,969원" 아님)
- 표에 없는 값은 추측하지 말고 0 또는 빈 문자열/null로 두세요
- 여러 페이지/여러 표가 있으면 모든 품목을 items 배열 하나에 합치세요

한국 수산물/식자재 거래명세서 표 해석 (중요):
- 열 이름이 「품목명[규격]」이면 name 에 품목명+괄호+대괄호 산지까지 전부 넣고,
  spec 에는 [일산]·[국산] 같은 산지/규격만 넣으세요. name 을 "136" 처럼 앞부분만 자르지 마세요.
- 열 이름이 「수량(단위포함)」이고 셀 값이 "0.782kg" 이면 quantity=0.782 이고,
  "0.782kg" 전체를 spec 에 넣지 마세요. (spec 은 규격/산지용)
- 단가·공급가액·금액 열을 unit_price / amount 에 각각 매핑하세요.
- 예:
  원문 행: 136참돔회(필렛) [일산] | 0.782kg | 69,969 | 54,716
  → {"name":"136참돔회(필렛) [일산]","spec":"일산","unit":"kg","quantity":0.782,"unit_price":69969,"amount":54716}
- "0.782kg" 는 quantity=0.782, unit="kg" 로 분리. 소수 자릿수를 임의로 줄이지 마세요.

- 수량은 이미지에 보이는 숫자를 한 자리도 바꾸지 마세요. 0.782 를 0.78 이나 0.780 으로 만들지 마세요.
- 수량×단가≈금액 검증만 하고, 수량 자체를 반올림하지 마세요.
"""


class LLMParseError(Exception):
    pass


def _pdf_to_images(file_bytes: bytes) -> list[bytes]:
    """PDF 각 페이지를 PNG 이미지 바이트로 변환."""
    images = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            images.append(pix.tobytes("png"))
    finally:
        doc.close()
    return images


def _resize_if_needed(image_bytes: bytes) -> tuple[bytes, str]:
    """너무 큰 이미지는 리사이즈. 반환값: (이미지 바이트, mime 타입)"""
    img = Image.open(io.BytesIO(image_bytes))
    if max(img.size) <= MAX_IMAGE_DIM:
        return image_bytes, "image/png"
    img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue(), "image/jpeg"


def _to_data_url(image_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_json(text: str) -> dict:
    """LLM 응답에서 JSON 부분만 추출 (```json 코드펜스로 감싸는 경우 대비)."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            text = text[brace_start : brace_end + 1]
    return json.loads(text)


def parse_document(file_bytes: bytes, content_type: str) -> dict:
    """
    거래명세서 파일(PDF 또는 이미지)을 LLM 으로 파싱해 구조화된 dict 를 반환한다.
    반환값에는 "_raw_response"/"_model" 키로 원본 응답도 함께 담아 감사 목적으로 보관한다.
    파싱 실패 시 LLMParseError 를 발생시킨다.
    """
    if not settings.OPENROUTER_API_KEY:
        raise LLMParseError("OPENROUTER_API_KEY 가 설정되어 있지 않습니다.")

    model = (settings.OPENROUTER_MODEL or "").strip()
    if not model:
        raise LLMParseError(
            "OPENROUTER_MODEL 이 비어 있습니다. .env 에 vision 모델 id 를 설정하세요."
        )

    if content_type == "application/pdf" or (
        content_type and "pdf" in content_type.lower()
    ):
        page_images = _pdf_to_images(file_bytes)
    else:
        page_images = [file_bytes]

    if not page_images:
        raise LLMParseError("문서에서 페이지/이미지를 추출하지 못했습니다.")

    image_contents = []
    for img_bytes in page_images:
        resized, mime = _resize_if_needed(img_bytes)
        image_contents.append(
            {"type": "image_url", "image_url": {"url": _to_data_url(resized, mime)}}
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "이 거래명세서를 읽고 JSON으로 변환해주세요."},
                *image_contents,
            ],
        },
    ]

    try:
        resp = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0,
            },
            timeout=90,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise LLMParseError(
            f"OpenRouter API 오류: {e.response.status_code} {e.response.text[:300]}"
        ) from e
    except httpx.HTTPError as e:
        raise LLMParseError(f"OpenRouter 요청 실패: {e}") from e

    body = resp.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMParseError(
            f"OpenRouter 응답 형식이 예상과 다릅니다: {json.dumps(body, ensure_ascii=False)[:300]}"
        ) from e

    try:
        parsed = _extract_json(content)
    except (json.JSONDecodeError, ValueError) as e:
        raise LLMParseError(f"LLM 응답을 JSON으로 파싱하지 못했습니다: {content[:300]}") from e

    parsed["_raw_response"] = content
    parsed["_model"] = model
    return parsed
