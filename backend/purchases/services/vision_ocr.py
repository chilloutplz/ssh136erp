"""
거래명세서(PDF/이미지) → Google Cloud Vision OCR.

인증 (둘 중 하나):
  - GOOGLE_VISION_CREDENTIALS_JSON : 서비스 계정 JSON 전체 문자열 (cloudtype)
  - GOOGLE_VISION_CREDENTIALS_FILE 또는 GOOGLE_APPLICATION_CREDENTIALS : JSON 파일 경로 (로컬)
"""
from __future__ import annotations

import io
import json
import os
import tempfile
from dataclasses import dataclass, field

import pymupdf as fitz
from django.conf import settings
from google.cloud import vision
from google.oauth2 import service_account


class VisionOCRError(Exception):
    pass


@dataclass
class OCRBlock:
    text: str
    # 정규화 좌표 0~1 (없으면 None). Vision bounding box 기준.
    y_min: float | None = None
    x_min: float | None = None


@dataclass
class OCRResult:
    full_text: str
    blocks: list[OCRBlock] = field(default_factory=list)


def _load_credentials():
    raw_json = (getattr(settings, "GOOGLE_VISION_CREDENTIALS_JSON", "") or "").strip()
    if raw_json:
        try:
            info = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise VisionOCRError(
                "GOOGLE_VISION_CREDENTIALS_JSON 이 올바른 JSON이 아닙니다."
            ) from e
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-vision"],
        )

    path = (
        (getattr(settings, "GOOGLE_VISION_CREDENTIALS_FILE", "") or "").strip()
        or (getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", "") or "").strip()
        or (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    )
    if path and os.path.isfile(path):
        return service_account.Credentials.from_service_account_file(
            path,
            scopes=["https://www.googleapis.com/auth/cloud-vision"],
        )

    raise VisionOCRError(
        "Vision 인증 정보가 없습니다. "
        "로컬: GOOGLE_VISION_CREDENTIALS_FILE=키.json 경로, "
        "cloudtype: GOOGLE_VISION_CREDENTIALS_JSON=키 전체 JSON"
    )


def _vision_client() -> vision.ImageAnnotatorClient:
    creds = _load_credentials()
    return vision.ImageAnnotatorClient(credentials=creds)


def _pdf_to_png_pages(file_bytes: bytes) -> list[bytes]:
    images: list[bytes] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            images.append(pix.tobytes("png"))
    finally:
        doc.close()
    return images


def _annotate_image(client: vision.ImageAnnotatorClient, image_bytes: bytes) -> OCRResult:
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise VisionOCRError(f"Vision API 오류: {response.error.message}")

    annotation = response.full_text_annotation
    if not annotation or not annotation.text:
        return OCRResult(full_text="", blocks=[])

    blocks: list[OCRBlock] = []
    for page in annotation.pages:
        for block in page.blocks:
            parts: list[str] = []
            y_vals: list[float] = []
            x_vals: list[float] = []
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    word_text = "".join(s.text for s in word.symbols)
                    parts.append(word_text)
                    if word.bounding_box and word.bounding_box.vertices:
                        ys = [v.y for v in word.bounding_box.vertices if v.y is not None]
                        xs = [v.x for v in word.bounding_box.vertices if v.x is not None]
                        if ys:
                            y_vals.extend(ys)
                        if xs:
                            x_vals.extend(xs)
            text = " ".join(parts).strip()
            if not text:
                continue
            # vertices 는 픽셀; 페이지 크기 대비 정규화는 생략하고 픽셀 최소값만 힌트로 전달
            blocks.append(
                OCRBlock(
                    text=text,
                    y_min=float(min(y_vals)) if y_vals else None,
                    x_min=float(min(x_vals)) if x_vals else None,
                )
            )

    # 읽기 순서 힌트: 위→아래, 같으면 왼쪽→오른쪽
    blocks.sort(key=lambda b: (b.y_min if b.y_min is not None else 0, b.x_min if b.x_min is not None else 0))
    return OCRResult(full_text=annotation.text.strip(), blocks=blocks)


def extract_text(file_bytes: bytes, content_type: str) -> OCRResult:
    """PDF/이미지 바이트에서 OCR 결과 반환. 여러 페이지면 텍스트를 이어 붙인다."""
    client = _vision_client()

    if content_type == "application/pdf" or (content_type and "pdf" in content_type.lower()):
        pages = _pdf_to_png_pages(file_bytes)
    else:
        pages = [file_bytes]

    if not pages:
        raise VisionOCRError("문서에서 페이지/이미지를 추출하지 못했습니다.")

    full_parts: list[str] = []
    all_blocks: list[OCRBlock] = []
    for i, page_bytes in enumerate(pages):
        result = _annotate_image(client, page_bytes)
        if result.full_text:
            if len(pages) > 1:
                full_parts.append(f"--- page {i + 1} ---\n{result.full_text}")
            else:
                full_parts.append(result.full_text)
        all_blocks.extend(result.blocks)

    return OCRResult(full_text="\n\n".join(full_parts).strip(), blocks=all_blocks)
