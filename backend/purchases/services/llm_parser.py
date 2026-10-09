"""
거래명세서(PDF/사진) 파싱 오케스트레이션.

1) Google Vision OCR (글자 + 블록 위치)
2) STRUCTURE_LLM_* 설정에 따른 구조화 (기본: Gemini)

views 는 기존처럼 parse_document() / LLMParseError 만 사용한다.
"""
from .structure_llm import StructureLLMError, structure_to_json
from .vision_ocr import VisionOCRError, extract_text


class LLMParseError(Exception):
    """업로드/재파싱 뷰에서 잡는 통합 파싱 오류."""

    pass


def parse_document(file_bytes: bytes, content_type: str) -> dict:
    """
    거래명세서 파일(PDF 또는 이미지)을 OCR + LLM 으로 파싱해 구조화된 dict 를 반환한다.
    반환값에는 "_raw_response"/"_model"/"_vendor" 키로 원본 응답도 함께 담는다.
    파싱 실패 시 LLMParseError 를 발생시킨다.
    """
    try:
        ocr = extract_text(file_bytes, content_type)
    except VisionOCRError as e:
        raise LLMParseError(str(e)) from e

    try:
        return structure_to_json(ocr)
    except StructureLLMError as e:
        raise LLMParseError(str(e)) from e
