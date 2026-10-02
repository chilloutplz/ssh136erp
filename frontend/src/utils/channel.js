/**
 * 채널 표시/분류 유틸.
 *
 * 백엔드(mapper.py/matepos.py)가 이미 channel 값을 정규화된 한글명
 * ("배민", "쿠팡", "요기요", "땡겨요", "내점(POS)", "내점(테이블)")으로 저장한다.
 * 여기서는 그 값을 기준으로 분류/색상/약어를 판정한다.
 *
 * LEGACY_RAW_TO_NAME 은 혹시 정규화 전 원본 코드값(PLUGIN_BAEMIN 등)이
 * 섞여 들어오는 경우를 위한 안전망이다 — 정상 운영 중이라면 거의 안 쓰인다.
 */

const LEGACY_RAW_TO_NAME = {
  BAEMIN: "배민",
  CPEATS: "쿠팡",
  YOGIYO: "요기요",
  DKY: "땡겨요",
  POS: "내점(POS)",
  PLUGIN_BAEMIN: "배민",
  PLUGIN_COUPANGEATS: "쿠팡",
  PLUGIN_YOGIYO: "요기요",
  PLUGIN_DDANGYO: "땡겨요",
  PLUGIN_KARROT: "당근",
  PLUGIN_CARROT: "당근",
  TABLE_ORDER: "내점(테이블)",
};

const DELIVERY_NAMES = new Set(["배민", "쿠팡", "요기요", "땡겨요", "당근"]);

const SHORT_MAP = {
  배민: "배",
  쿠팡: "쿠",
  요기요: "요",
  땡겨요: "땡",
  당근: "당",
  내점: "내",
};

/** 원본값을 정규화된 표시명으로. 이미 정규화된 값이면 그대로 통과. */
function toDisplayName(raw) {
  if (!raw) return "";
  const s = String(raw);
  return LEGACY_RAW_TO_NAME[s] || s;
}

export function channelMeta(raw) {
  const name = toDisplayName(raw);
  if (!name) return { label: "미지정", icon: "•", className: "ch-etc" };
  if (name === "배민") return { label: name, icon: "🛵", className: "ch-baemin" };
  if (name === "쿠팡") return { label: name, icon: "📦", className: "ch-coupang" };
  if (name === "요기요") return { label: name, icon: "🍔", className: "ch-yogiyo" };
  if (name === "땡겨요") return { label: name, icon: "🥡", className: "ch-etc" };
  if (name === "당근") return { label: name, icon: "🥕", className: "ch-etc" };
  if (name.startsWith("내점")) return { label: name, icon: "🍽️", className: "ch-table" };
  return { label: name, icon: "•", className: "ch-etc" };
}

export function channelLabel(raw) {
  return channelMeta(raw).label;
}

/** 내점/배달 구분 — "내점(...)"으로 시작하면 내점, 배달앱 이름이면 배달 */
export function businessType(raw) {
  const name = toDisplayName(raw);
  if (name.startsWith("내점")) return "내점";
  if (DELIVERY_NAMES.has(name)) return "배달";
  return "기타";
}

/** 주문 목록용: 내점 계열은 "내점"으로 뭉치고, 그 외는 channelLabel 그대로 */
export function orderListChannelLabel(raw) {
  if (businessType(raw) === "내점") return "내점";
  return channelLabel(raw);
}

/** 주문 목록 좁은 칸용 한 글자 — 기본적으로 표시명 첫 글자 */
export function orderListChannelShort(raw) {
  const full = orderListChannelLabel(raw);
  if (SHORT_MAP[full]) return SHORT_MAP[full];
  return full ? full[0] : "·";
}

/**
 * orderNumber / channel_order_no 에서 플랫폼명 제거 후 코드만.
 * 예: "배달의민족 T2GD0000RMUV" → "T2GD0000RMUV"
 *     "쿠팡이츠 0TWLXU" → "0TWLXU"
 *     "001" → "001"
 */
export function orderCode(raw) {
  if (raw == null || raw === "") return "-";
  const s = String(raw).trim();
  const parts = s.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return parts[parts.length - 1];
  if (s.includes("_")) {
    const segs = s.split("_").filter(Boolean);
    if (segs.length >= 2) {
      const candidates = segs.filter((x) => !/^\d{8}$/.test(x));
      const codeish = candidates.find(
        (x) => /[A-Za-z0-9]{4,}/.test(x) && !/^(배민|쿠팡|요기요|배달)/.test(x)
      );
      if (codeish) return codeish;
    }
  }
  return s;
}

/**
 * 채널별 형광펜(배경) 클래스 — 브랜드 연상 파스텔.
 * CSS 클래스명(ch-hl-*)은 기존 그대로 유지, 매칭 기준만 정규화된 한글명으로 변경.
 */
export function channelHighlightClass(raw) {
  const name = toDisplayName(raw);
  if (name === "배민") return "ch-hl-baemin";
  if (name === "쿠팡") return "ch-hl-coupang";
  if (name === "요기요") return "ch-hl-yogiyo";
  if (name === "땡겨요") return "ch-hl-ddangyo";
  if (name === "당근") return "ch-hl-carrot";
  if (name === "내점(POS)") return "ch-hl-pos";
  if (name === "내점(테이블)") return "ch-hl-table";
  if (name.startsWith("내점")) return "ch-hl-pos";
  return "ch-hl-etc";
}
