"""
파싱된 raw 문자열(거래처명/품목명)과 기존 마스터(Supplier/Material) 간
유사도 기반 후보 생성.

중요: 이 모듈은 어떤 것도 '자동 결정'하지 않는다.
후보 목록만 만들어 검토 화면에 제시하고, 연결/신규 생성 여부는
반드시 사람이 결정한다 (human-in-the-loop).
"""
from difflib import SequenceMatcher
import re

# 유사도 후보로 올릴 최저 점수. 이 미만은 noise 다.
SCORE_THRESHOLD = 0.45
DEFAULT_LIMIT = 5


# ---------------------------------------------------------------- 이름 정규화

_COMPANY_PREFIX = re.compile(r"^(주식회사|유한책임회사|유한회사|㈜|（주）|\(주\)|\(유\)|（유）)")


def normalize_text(s: str) -> str:
    """비교용 문자열 정규화. 원본은 절대 바꾸지 않는다."""
    if not s:
        return ""
    s = str(s).strip()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)  # 띄어쓰기/줄바꿈 무시
    return s.lower()


def normalize_supplier_name(name: str) -> str:
    """거래처명 정규화: 법인 접두어를 떼고 비교해 '(주)본네이처' = '본네이처' 가 되게 한다."""
    s = normalize_text(name)
    prev = None
    while prev != s:  # '(주)(주)x' 같은 중복도 처리
        prev = s
        s = _COMPANY_PREFIX.sub("", s)
    return s


def normalize_bizno(bizno: str) -> str:
    """사업자등록번호 정규화: 숫자 10자리만 남긴다. '123-45-67890' -> '1234567890'"""
    if not bizno:
        return ""
    digits = re.sub(r"\D", "", str(bizno))
    return digits if len(digits) == 10 else ""


def material_base_name(raw_name: str) -> str:
    """
    품목명에서 산지/규격 괄호를 제외한 순수 품목명을 뽑는다.
    '136참돔회(필렛) [일산]' -> '136참돔회'
    괄호 안이 규격이 아니라 일부인 경우(예: '참돔회(필렛)')를 대비해
    원문과 베이스명 둘 다로 유사도를 본다.
    """
    s = str(raw_name or "").strip()
    s = re.sub(r"\[[^\]]*\]", "", s).strip()   # [일산] 제거
    prev = None
    while prev != s:  # 끝쪽 (필렛)/(특) 을 연속 제거. 공백 때문에 strip 을 반복한다
        prev = s
        s = re.sub(r"\([^)]*\)\s*$", "", s).strip()
    return s or str(raw_name or "").strip()


# ---------------------------------------------------------------- 유사도

def _score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _best_score(raw_variants: list[str], target_variants: list[str]) -> float:
    """양쪽 변형 조합 중 최고 유사도."""
    return max((_score(rv, tv) for rv in raw_variants for tv in target_variants), default=0.0)


# ---------------------------------------------------------------- 거래처

def supplier_exact_match(raw_name: str, raw_bizno: str, suppliers, aliases):
    """
    파싱값에 대해 '안전한 자동 연결'이 가능한 Supplier 가 있으면 반환한다.
    유사도 추측은 하지 않으며, 아래 3가지 중 하나만 해당될 때만 연결한다.

    1. SupplierAlias — 사람이 과거에 연결한 표기명 (최우선)
    2. 사업자번호 정확 일치 — 가장 강한 신호
    3. 거래처명 정규화 후 완전 일치

    해당 없으면 None → 화면에서 후보 목록으로 제시한다.
    """
    raw_norm = normalize_supplier_name(raw_name)
    raw_biz = normalize_bizno(raw_bizno)

    # 1) 사람이 과거에 연결한 별칭
    for alias in aliases or []:
        if normalize_supplier_name(alias.raw_name) == raw_norm:
            return alias.supplier

    # 2) 사업자번호 정확 일치
    if raw_biz:
        for s in suppliers or []:
            if normalize_bizno(getattr(s, "business_number", "")) == raw_biz:
                return s

    # 3) 이름 정규화 완전 일치
    if raw_norm:
        for s in suppliers or []:
            if normalize_supplier_name(s.name) == raw_norm:
                return s
    return None


def supplier_candidates(raw_name: str, suppliers, raw_bizno: str = "", aliases=None,
                        limit: int = DEFAULT_LIMIT) -> list[dict]:
    """
    파싱된 거래처명과 유사한 기존 Supplier 후보 목록.
    사업자번호가 일치하면 score 1.0 / matched_by='bizno' 로 최우선 제시한다.
    반환: [{"id", "name", "business_number", "score", "matched_by"}, ...] 점수 내림차순.
    """
    raw_norm = normalize_supplier_name(raw_name)
    raw_biz = normalize_bizno(raw_bizno)
    if not raw_norm and not raw_biz:
        return []

    out = []
    seen = set()

    # 1) 별칭 매칭 — 사람이 과거에 결정한 연결을 최우선으로 제시
    if aliases is not None and raw_norm:
        for alias in aliases:
            if normalize_supplier_name(alias.raw_name) == raw_norm and alias.supplier_id not in seen:
                out.append({"id": alias.supplier_id, "name": alias.supplier.name,
                            "business_number": alias.supplier.business_number,
                            "score": 1.0, "matched_by": "alias"})
                seen.add(alias.supplier_id)

    # 2) 사업자번호 일치
    if raw_biz:
        for s in suppliers:
            if s.id in seen:
                continue
            if normalize_bizno(getattr(s, "business_number", "")) == raw_biz:
                out.append({"id": s.id, "name": s.name,
                            "business_number": getattr(s, "business_number", ""),
                            "score": 1.0, "matched_by": "bizno"})
                seen.add(s.id)

    # 3) 이름 유사도
    for s in suppliers:
        if s.id in seen:
            continue
        sc = _score(raw_norm, normalize_supplier_name(s.name))
        if sc >= SCORE_THRESHOLD:
            out.append({"id": s.id, "name": s.name,
                        "business_number": getattr(s, "business_number", ""),
                        "score": round(sc, 3), "matched_by": "similarity"})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


# ---------------------------------------------------------------- 자재

def material_candidates(raw_name: str, materials, aliases=None, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """
    파싱된 품목명에 대한 자재 후보.

    1순위: MaterialAlias 정확/정규화 일치 (score 1.0, "이전에 사람이 연결해준 것")
    2순위: Material.name 유사도 상위 N개
    """
    raw_norm = normalize_text(raw_name)
    base_norm = normalize_text(material_base_name(raw_name))
    raw_variants = [v for v in {raw_norm, base_norm} if v]

    out = []
    seen = set()

    # 1) 별칭 매칭 — 사람이 과거에 결정한 연결을 최우선으로 제시
    if aliases is not None and raw_norm:
        for alias in aliases:
            if normalize_text(alias.raw_name) in raw_variants and alias.material_id not in seen:
                out.append({"id": alias.material_id, "name": alias.material.name,
                            "unit": alias.material.unit, "score": 1.0,
                            "matched_by": "alias"})
                seen.add(alias.material_id)

    # 2) 이름 유사도
    for m in materials:
        if m.id in seen:
            continue
        sc = _best_score(raw_variants, [normalize_text(m.name)])
        if sc >= SCORE_THRESHOLD:
            out.append({"id": m.id, "name": m.name, "unit": m.unit,
                        "score": round(sc, 3), "matched_by": "similarity"})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]
