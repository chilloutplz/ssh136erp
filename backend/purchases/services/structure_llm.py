"""
OCR 텍스트(+블록) → 거래명세 구조화 JSON.

vendor / api_key / model 은 settings(STRUCTURE_LLM_*) 에서 읽는다.
  STRUCTURE_LLM_VENDOR = gemini | openrouter
  STRUCTURE_LLM_API_KEY
  STRUCTURE_LLM_MODEL
"""
from __future__ import annotations

import json
import re

import httpx
from django.conf import settings

from .vision_ocr import OCRResult


class StructureLLMError(Exception):
    pass


SYSTEM_PROMPT = """당신은 한국 식당의 거래명세서(세금계산서, 납품서 등) OCR 텍스트를 읽고 구조화된 JSON으로 변환하는 도우미입니다.

아래 OCR 텍스트(및 선택적 블록 목록)만 근거로 다음 JSON 스키마로만 응답하세요. 다른 설명 텍스트는 절대 포함하지 마세요.

{
  "supplier": {
    "name": "공급업체명 (문서에 있는 그대로, 예: (주)본네이처)",
    "business_number": "사업자등록번호 (예: 123-45-67890, 없으면 빈 문자열)",
    "representative": "대표자명 (없으면 빈 문자열)",
    "phone": "전화번호 (없으면 빈 문자열)",
    "fax": "팩스번호 (없으면 빈 문자열)",
    "email": "이메일 주소 (없으면 빈 문자열)",
    "address": "사업장 주소 (없으면 빈 문자열)"
  },
  "document_date": "YYYY-MM-DD 형식의 거래일자 (알 수 없으면 null)",
  "document_number": "전표번호/일련번호 (없으면 빈 문자열)",
  "items": [
    {
      "name": "품목명 전체 (예: 136참돔회(필렛) [일산])",
      "spec": "산지/규격 설명만 (예: 일산, 국산, 완도산). 수량·단위 아님",
      "unit": "수량 단위만 (예: kg, 마리, 박스). 없으면 빈 문자열",
      "quantity": 숫자 (소수 유지, 예: 0.782 를 0.78 로 줄이지 말 것). 단위 글자는 빼고 숫자만,
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
- OCR 오탈자가 있어도 문서에 보이는 내용을 최대한 그대로 살리세요

공급업체 정보 (supplier 블록):
- 명세서 상단/하단의 업체 정보를 읽어 채우세요. 사업자번호는 반드시 하이픈 포함 10자리 형식(XXX-XX-XXXXX)으로 적으세요.
- 명세서 어디에도 없는 항목은 빈 문자열로 두세요. 추측 금지.

한국 수산물/식자재 거래명세서 표 해석 (중요):
- 열 이름이 「품목명[규격]」이면 name 에 품목명+괄호+대괄호 산지까지 전부 넣고,
  spec 에는 [일산]·[국산] 같은 산지/규격만 넣으세요. name 을 "136" 처럼 앞부분만 자르지 마세요.
- 셀 값이 "0.782kg" 이면 quantity=0.782, unit="kg". "0.782kg" 전체를 spec 에 넣지 마세요.
- 단가·공급가액·금액 열을 unit_price / amount 에 각각 매핑하세요.
- 수량은 OCR에 보이는 숫자를 한 자리도 바꾸지 마세요.
"""


def _extract_json(text: str) -> dict:
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


def _build_user_payload(ocr: OCRResult) -> str:
    lines = ["다음 OCR 텍스트를 거래명세 JSON으로 변환하세요.", "", "[OCR full text]", ocr.full_text or "(비어 있음)"]
    if ocr.blocks:
        lines.append("")
        lines.append("[OCR blocks — reading order hint, y then x]")
        for i, b in enumerate(ocr.blocks[:200]):  # 토큰 폭주 방지
            pos = ""
            if b.y_min is not None:
                pos = f" y={b.y_min:.0f}"
                if b.x_min is not None:
                    pos += f" x={b.x_min:.0f}"
            lines.append(f"{i + 1}.{pos} {b.text}")
    return "\n".join(lines)


def _call_gemini(api_key: str, model: str, user_text: str) -> str:
    # API 키는 쿼리보다 헤더 권장 (특수문자·길이 이슈 방지)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=90)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise StructureLLMError(
            f"Gemini API 오류: {e.response.status_code} {e.response.text[:400]}"
        ) from e
    except httpx.HTTPError as e:
        raise StructureLLMError(f"Gemini 요청 실패: {e}") from e

    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError) as e:
        raise StructureLLMError(
            f"Gemini 응답 형식이 예상과 다릅니다: {json.dumps(data, ensure_ascii=False)[:400]}"
        ) from e


def _call_openrouter(api_key: str, model: str, user_text: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    try:
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": messages, "temperature": 0},
            timeout=90,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise StructureLLMError(
            f"OpenRouter API 오류: {e.response.status_code} {e.response.text[:400]}"
        ) from e
    except httpx.HTTPError as e:
        raise StructureLLMError(f"OpenRouter 요청 실패: {e}") from e

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise StructureLLMError(
            f"OpenRouter 응답 형식이 예상과 다릅니다: {json.dumps(data, ensure_ascii=False)[:400]}"
        ) from e


def structure_to_json(ocr: OCRResult) -> dict:
    """OCR 결과를 거래명세 JSON dict 로 변환. _raw_response / _model / _vendor 메타 포함."""
    vendor = (getattr(settings, "STRUCTURE_LLM_VENDOR", "") or "gemini").strip().lower()
    api_key = (getattr(settings, "STRUCTURE_LLM_API_KEY", "") or "").strip().strip('"').strip("'")
    model = (getattr(settings, "STRUCTURE_LLM_MODEL", "") or "").strip().strip('"').strip("'")

    # 하위 호환: STRUCTURE_* 비어 있으면 구 OPENROUTER_* 사용
    if not api_key and vendor == "openrouter":
        api_key = (getattr(settings, "OPENROUTER_API_KEY", "") or "").strip().strip('"').strip("'")
    if not model and vendor == "openrouter":
        model = (getattr(settings, "OPENROUTER_MODEL", "") or "").strip()

    if vendor == "gemini" and not model:
        model = "gemini-2.0-flash"
    if vendor == "openrouter" and not model:
        model = "google/gemma-3-27b-it:free"

    if not api_key:
        raise StructureLLMError(
            f"STRUCTURE_LLM_API_KEY 가 없습니다 (vendor={vendor})."
        )
    if not model:
        raise StructureLLMError("STRUCTURE_LLM_MODEL 이 없습니다.")

    if not (ocr.full_text or "").strip():
        raise StructureLLMError("OCR 텍스트가 비어 있어 구조화할 수 없습니다.")

    user_text = _build_user_payload(ocr)

    if vendor == "gemini":
        content = _call_gemini(api_key, model, user_text)
    elif vendor == "openrouter":
        content = _call_openrouter(api_key, model, user_text)
    else:
        raise StructureLLMError(
            f"지원하지 않는 STRUCTURE_LLM_VENDOR: {vendor} (gemini|openrouter)"
        )

    try:
        parsed = _extract_json(content)
    except (json.JSONDecodeError, ValueError) as e:
        raise StructureLLMError(
            f"구조화 응답을 JSON으로 파싱하지 못했습니다: {content[:400]}"
        ) from e

    parsed["_raw_response"] = content
    parsed["_model"] = model
    parsed["_vendor"] = vendor
    return parsed
