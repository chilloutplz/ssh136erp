/** 채널 원본값(PLUGIN_BAEMIN 등) → 화면용 짧은 표시 */

const CHANNEL_MAP = {
  PLUGIN_BAEMIN: { label: "배민", icon: "🛵", className: "ch-baemin" },
  PLUGIN_COUPANGEATS: { label: "쿠팡", icon: "📦", className: "ch-coupang" },
  PLUGIN_YOGIYO: { label: "요기요", icon: "🍔", className: "ch-yogiyo" },
  PLUGIN_DDANGYO: { label: "땡겨요", icon: "🥡", className: "ch-etc" },
  PLUGIN_KARROT: { label: "당근", icon: "🥕", className: "ch-etc" },
  PLUGIN_CARROT: { label: "당근", icon: "🥕", className: "ch-etc" },
  TABLE_ORDER: { label: "Table Order", icon: "🍽️", className: "ch-table" },
  POS: { label: "POS", icon: "🏪", className: "ch-pos" },
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

/** 내점/배달 구분 — TABLE_ORDER·POS 는 모두 내점 */
export function businessType(raw) {
  const value = String(raw || "").toUpperCase();
  if (value === "POS" || value === "TABLE_ORDER") return "내점";
  if (value.startsWith("PLUGIN_")) return "배달";
  return "기타";
}

/** 주문 목록용: POS·TABLE_ORDER → 내점, 그 외는 channelLabel */
export function orderListChannelLabel(raw) {
  if (businessType(raw) === "내점") return "내점";
  return channelLabel(raw);
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
 * 채널별 형광펜(배경) 클래스 — 브랜드 연상 파스텔
 * 배민 민트 / 쿠팡 블루 / 요기요 핑크 등
 */
export function channelHighlightClass(raw) {
  const v = String(raw || "").toUpperCase();
  if (v === "PLUGIN_BAEMIN") return "ch-hl-baemin";
  if (v === "PLUGIN_COUPANGEATS" || v.includes("COUPANG")) return "ch-hl-coupang";
  if (v === "PLUGIN_YOGIYO") return "ch-hl-yogiyo";
  if (v === "PLUGIN_DDANGYO") return "ch-hl-ddangyo";
  if (v.includes("KARROT") || v.includes("CARROT") || v.includes("당근")) return "ch-hl-carrot";
  if (v === "TABLE_ORDER") return "ch-hl-table";
  if (v === "POS") return "ch-hl-pos";
  if (v.startsWith("PLUGIN_")) return "ch-hl-etc";
  return "ch-hl-etc";
}
