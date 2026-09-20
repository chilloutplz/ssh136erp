/** 채널 원본값(PLUGIN_BAEMIN 등) → 화면용 짧은 표시 */

const CHANNEL_MAP = {
  PLUGIN_BAEMIN: { label: "배민", icon: "🛵", className: "ch-baemin" },
  PLUGIN_COUPANGEATS: { label: "쿠팡", icon: "📦", className: "ch-coupang" },
  PLUGIN_YOGIYO: { label: "요기요", icon: "🍔", className: "ch-yogiyo" },
  PLUGIN_DDANGYO: { label: "땡겨요", icon: "🥡", className: "ch-etc" },
  TABLE_ORDER: { label: "테이블", icon: "🍽️", className: "ch-table" },
  POS: { label: "매장", icon: "🏪", className: "ch-pos" },
};

export function channelMeta(raw) {
  if (!raw) return { label: "미지정", icon: "•", className: "ch-etc" };
  if (CHANNEL_MAP[raw]) return CHANNEL_MAP[raw];
  if (String(raw).startsWith("PLUGIN_")) {
    const rest = String(raw).slice(7).replace(/EATS$/i, "");
    return { label: rest, icon: "🛵", className: "ch-etc" };
  }
  return { label: String(raw), icon: "•", className: "ch-etc" };
}

export function channelLabel(raw) {
  return channelMeta(raw).label;
}

export function businessType(raw) {
  const value = String(raw || "").toUpperCase();
  if (value === "POS" || value === "TABLE_ORDER") return "내점";
  if (value.startsWith("PLUGIN_")) return "배달";
  return "기타";
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
  // "배민_T2GD…_20260917" 형태면 가운데 토큰 우선
  if (s.includes("_")) {
    const segs = s.split("_").filter(Boolean);
    if (segs.length >= 2) {
      // 날짜(8자리 숫자) 제외한 가장 긴 세그먼트
      const candidates = segs.filter((x) => !/^\d{8}$/.test(x));
      const codeish = candidates.find((x) => /[A-Za-z0-9]{4,}/.test(x) && !/^(배민|쿠팡|요기요|배달)/.test(x));
      if (codeish) return codeish;
    }
  }
  return s;
}
