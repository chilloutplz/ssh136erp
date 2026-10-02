<script setup>
import { computed, onMounted, ref, watch } from "vue";
import client from "../api/client";
import {
  businessType,
  channelLabel,
  channelHighlightClass,
} from "../utils/channel";

function toDateString(d) {
  return d.toLocaleDateString("sv-SE");
}

const todayString = toDateString(new Date());
const RANGE_STORAGE_KEY = "ssh136erp.sales.period.range";

function startOfWeek(d) {
  const x = new Date(d);
  const day = x.getDay();
  const diff = day === 0 ? 6 : day - 1;
  x.setDate(x.getDate() - diff);
  return x;
}

function startOfMonth(d) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function isValidDateStr(s) {
  return typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s);
}

function readStoredRange() {
  const fallback = {
    from: toDateString(startOfWeek(new Date())),
    to: todayString,
    mode: "week",
  };
  try {
    const raw = sessionStorage.getItem(RANGE_STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    let from = parsed?.from;
    let to = parsed?.to;
    const mode = ["7d", "week", "month", "custom"].includes(parsed?.mode)
      ? parsed.mode
      : "custom";
    if (!isValidDateStr(from) || !isValidDateStr(to)) return fallback;
    if (from > todayString) from = todayString;
    if (to > todayString) to = todayString;
    if (from > to) return fallback;
    return { from, to, mode };
  } catch {
    return fallback;
  }
}

const storedRange = readStoredRange();
const dateFrom = ref(storedRange.from);
const dateTo = ref(storedRange.to);
const storedMode = storedRange.mode;

const daily = ref([]);
const channels = ref([]);
const loading = ref(true);
const error = ref("");

const totals = computed(() => {
  let order_count = 0;
  let sale_amount = 0;
  let actual_sale_amount = 0;
  for (const row of daily.value) {
    order_count += Number(row.order_count || 0);
    sale_amount += Number(row.sale_amount || 0);
    actual_sale_amount += Number(row.actual_sale_amount || 0);
  }
  return { order_count, sale_amount, actual_sale_amount };
});

const businessChannels = computed(() => {
  const groups = new Map();
  for (const row of channels.value) {
    const type = businessType(row.channel);
    const current = groups.get(type) || {
      channel: type,
      order_count: 0,
      actual_sale_amount: 0,
    };
    current.order_count += Number(row.order_count || 0);
    current.actual_sale_amount += Number(
      row.actual_sale_amount ?? row.net_sale_amount ?? 0
    );
    groups.set(type, current);
  }
  return ["내점", "배달"].map(
    (type) =>
      groups.get(type) || {
        channel: type,
        order_count: 0,
        actual_sale_amount: 0,
      }
  );
});

const dineIn = computed(() => businessChannels.value[0]);
const delivery = computed(() => businessChannels.value[1]);

const rangeLabel = computed(() => {
  if (!dateFrom.value || !dateTo.value) return "";
  return `${dateFrom.value} ~ ${dateTo.value}`;
});

function formatWon(n) {
  return `₩${Number(n || 0).toLocaleString("ko-KR")}`;
}

function formatDay(iso) {
  if (!iso) return "-";
  const d = new Date(`${iso}T00:00:00`);
  const wd = d.toLocaleDateString("ko-KR", { weekday: "short" });
  return `${iso} (${wd})`;
}

const rangeMode = ref(storedMode);

function endOfWeek(d) {
  const start = startOfWeek(d);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return end;
}

function endOfMonth(d) {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function clampToToday(dateStr) {
  return dateStr > todayString ? todayString : dateStr;
}

function applyPreset(kind) {
  const now = new Date();
  rangeMode.value = kind;
  if (kind === "week") {
    dateFrom.value = toDateString(startOfWeek(now));
    dateTo.value = todayString;
  } else if (kind === "month") {
    dateFrom.value = toDateString(startOfMonth(now));
    dateTo.value = todayString;
  } else if (kind === "7d") {
    const from = new Date(now);
    from.setDate(from.getDate() - 6);
    dateFrom.value = toDateString(from);
    dateTo.value = todayString;
  }
}

function rangeDayCount() {
  const a = new Date(`${dateFrom.value}T00:00:00`);
  const b = new Date(`${dateTo.value}T00:00:00`);
  const ms = b.getTime() - a.getTime();
  return Math.max(1, Math.round(ms / 86400000) + 1);
}

const canShiftNext = computed(() => dateTo.value < todayString);

function shiftRange(direction) {
  const mode = rangeMode.value;
  let nextFrom;
  let nextTo;

  if (mode === "week") {
    const anchor = new Date(`${dateFrom.value}T00:00:00`);
    anchor.setDate(anchor.getDate() + direction * 7);
    const start = startOfWeek(anchor);
    const end = endOfWeek(anchor);
    nextFrom = toDateString(start);
    nextTo = clampToToday(toDateString(end));
  } else if (mode === "month") {
    const anchor = new Date(`${dateFrom.value}T00:00:00`);
    const shifted = new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
    nextFrom = toDateString(shifted);
    nextTo = clampToToday(toDateString(endOfMonth(shifted)));
  } else {
    const days = mode === "7d" ? 7 : rangeDayCount();
    const from = new Date(`${dateFrom.value}T00:00:00`);
    const to = new Date(`${dateTo.value}T00:00:00`);
    from.setDate(from.getDate() + direction * days);
    to.setDate(to.getDate() + direction * days);
    nextFrom = toDateString(from);
    nextTo = toDateString(to);
    if (nextTo > todayString) {
      const end = new Date(`${todayString}T00:00:00`);
      const start = new Date(end);
      start.setDate(start.getDate() - (days - 1));
      nextFrom = toDateString(start);
      nextTo = todayString;
    }
  }

  if (nextFrom > nextTo) nextFrom = nextTo;
  dateFrom.value = nextFrom;
  dateTo.value = nextTo;
}

function onManualDateChange() {
  rangeMode.value = "custom";
}

async function loadAll() {
  if (!dateFrom.value || !dateTo.value) return;
  if (dateFrom.value > dateTo.value) {
    error.value = "시작일이 종료일보다 늦을 수 없습니다.";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const params = {
      business_date_from: dateFrom.value,
      business_date_to: dateTo.value,
    };
    const [dailyRes, channelRes] = await Promise.all([
      client.get("/sales/summary/daily/", { params }),
      client.get("/sales/summary/by-channel/", { params }),
    ]);
    daily.value = dailyRes.data || [];
    channels.value = channelRes.data || [];
  } catch (e) {
    error.value = "데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.";
  } finally {
    loading.value = false;
  }
}

watch([dateFrom, dateTo, rangeMode], ([from, to, mode]) => {
  try {
    sessionStorage.setItem(
      RANGE_STORAGE_KEY,
      JSON.stringify({ from, to, mode })
    );
  } catch {
    /* ignore */
  }
  loadAll();
});

onMounted(async () => {
  try {
    await client.post("/integrations/tosspos/sync-pending/");
  } catch (e) {
    /* ignore */
  }
  await loadAll();
});
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div><h1>기간매출</h1></div>
      <div class="topbar-right">
        <button class="ghost" type="button" :disabled="loading" @click="loadAll">
          {{ loading ? "불러오는 중..." : "새로고침" }}
        </button>
      </div>
    </header>

    <div class="range-bar">
      <div class="range-nav">
        <button class="ghost icon" type="button" aria-label="이전 기간" @click="shiftRange(-1)">◀</button>
        <div class="range-inputs">
          <label class="range-field">
            <span class="range-caption">시작</span>
            <input type="date" v-model="dateFrom" :max="dateTo || todayString" @change="onManualDateChange" />
          </label>
          <span class="range-sep">~</span>
          <label class="range-field">
            <span class="range-caption">종료</span>
            <input type="date" v-model="dateTo" :max="todayString" :min="dateFrom" @change="onManualDateChange" />
          </label>
        </div>
        <button class="ghost icon" type="button" aria-label="다음 기간" :disabled="!canShiftNext" @click="shiftRange(1)">▶</button>
      </div>
      <div class="presets">
        <button class="chip" type="button" :class="{ on: rangeMode === '7d' }" @click="applyPreset('7d')">최근 7일</button>
        <button class="chip" type="button" :class="{ on: rangeMode === 'week' }" @click="applyPreset('week')">이번 주</button>
        <button class="chip" type="button" :class="{ on: rangeMode === 'month' }" @click="applyPreset('month')">이번 달</button>
      </div>
    </div>

    <div v-if="error" class="banner error">{{ error }}</div>

    <div v-if="loading" class="loading-panel" role="status" aria-live="polite">
      <div class="spinner" aria-hidden="true"></div>
      <p>기간 매출을 불러오는 중...</p>
    </div>

    <template v-else>
      <section class="totals-slip">
        <div class="totals-main">
          <span class="label">실매출 <span class="range-hint">{{ rangeLabel }}</span></span>
          <span class="amount mono">{{ formatWon(totals.actual_sale_amount) }}</span>
        </div>
        <div v-if="totals.order_count > 0" class="summary-grid">
          <div class="summary-card">
            <div class="order-row">
              <span class="card-label title-order">주문</span>
              <span class="card-label">{{ totals.order_count }}건</span>
            </div>
            <span class="card-amount mono">{{ formatWon(totals.sale_amount) }}</span>
          </div>
          <div class="summary-card">
            <div class="order-row">
              <span class="card-label title-dinein">내점</span>
              <span class="card-label">{{ dineIn.order_count }}건</span>
            </div>
            <span class="card-amount mono">{{ formatWon(dineIn.actual_sale_amount) }}</span>
          </div>
          <div class="summary-card">
            <div class="order-row">
              <span class="card-label title-delivery">배달</span>
              <span class="card-label">{{ delivery.order_count }}건</span>
            </div>
            <span class="card-amount mono">{{ formatWon(delivery.actual_sale_amount) }}</span>
          </div>
          <div class="summary-card">
            <div class="order-row">
              <span class="card-label">영업일</span>
              <span class="card-label">{{ daily.length }}일</span>
            </div>
            <span class="card-amount mono sub">일평균 {{ formatWon(totals.order_count ? Math.round(totals.actual_sale_amount / Math.max(daily.length, 1)) : 0) }}</span>
          </div>
        </div>
        <p v-else class="empty">해당 기간에 집계된 매출이 없습니다.</p>
      </section>

      <section class="totals-slip channels-slip">
        <div class="totals-main"><span class="label">채널별</span></div>
        <div v-if="channels.length" class="summary-grid">
          <div v-for="c in channels" :key="c.channel" class="summary-card">
            <div class="order-row">
              <span class="card-label channel-hl" :class="channelHighlightClass(c.channel)">{{ channelLabel(c.channel) }}</span>
              <span class="card-label">{{ c.order_count }}건</span>
            </div>
            <span class="card-amount mono">{{ formatWon(c.actual_sale_amount ?? c.net_sale_amount) }}</span>
          </div>
        </div>
        <p v-else class="empty">해당 기간에 집계된 채널별 매출이 없습니다.</p>
      </section>

      <section class="orders">
        <div class="totals-main">
          <span class="label">일별 매출</span>
          <span class="amount-sub mono">{{ daily.length }}일</span>
        </div>
        <table v-if="daily.length" class="order-table">
          <thead>
            <tr>
              <th>일자</th>
              <th class="right">건수</th>
              <th class="right">실매출</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in daily" :key="row.business_date">
              <td class="mono">{{ formatDay(row.business_date) }}</td>
              <td class="right mono">{{ row.order_count }}</td>
              <td class="right mono">{{ formatWon(row.actual_sale_amount) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">해당 기간에 일별 데이터가 없습니다.</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.order-row { display: flex; justify-content: space-between; align-items: center; }
.page { max-width: 760px; margin: 0 auto; padding: 32px 24px 64px; }
.topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
h1 { margin: 0; font-size: 24px; font-weight: 700; }
.topbar-right { display: flex; gap: 10px; }
.range-nav { display: flex; align-items: flex-end; gap: 8px; }
.range-nav .icon { flex-shrink: 0; padding: 6px 10px; line-height: 1; align-self: flex-end; }
.range-nav .icon:disabled { opacity: 0.35; cursor: default; }
.range-bar { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
.range-inputs { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.range-field { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 140px; }
.range-caption { font-size: 11px; color: var(--muted); font-weight: 600; }
.range-field input[type="date"] { min-height: 36px; padding: 6px 10px; border: 1px solid var(--rule); border-radius: 6px; font: inherit; background: #fff; }
.range-sep { color: var(--muted); margin-top: 16px; }
.presets { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--rule); background: #fff; border-radius: 999px; padding: 6px 12px; font-size: 12px; color: var(--ink-soft); cursor: pointer; }
.chip:hover { border-color: var(--ink-soft); }
.chip.on { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.ghost { background: none; border: 1px solid var(--rule); padding: 6px 12px; font-size: 13px; cursor: pointer; color: var(--ink-soft); border-radius: 6px; }
.ghost:hover { border-color: var(--ink-soft); }
.ghost:disabled { opacity: 0.55; cursor: default; }
.banner.error { background: var(--stamp-bg); color: var(--stamp); padding: 10px 14px; font-size: 13px; margin-bottom: 16px; border-radius: 8px; }
.totals-slip { background: #fff; border: 1px solid var(--rule); border-radius: 12px; padding: 20px 18px 16px; margin-bottom: 24px; }
.totals-main { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 14px; gap: 12px; flex-wrap: wrap; }
.totals-main .label { font-size: 14px; color: var(--muted); font-weight: 600; }
.range-hint { font-weight: 500; color: var(--ink-soft); font-size: 12px; margin-left: 6px; }
.totals-main .amount-sub { font-size: 15px; font-weight: 600; color: var(--ink-soft); }
.totals-main .amount { font-size: 32px; font-weight: 700; letter-spacing: -0.03em; color: var(--ink); }
.summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.summary-card { background: #f8fafc; border: 1px solid var(--rule); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.card-label { font-size: 12px; font-weight: 600; color: var(--muted); }
.card-amount { font-size: 18px; font-weight: 700; letter-spacing: -0.03em; color: var(--ink); align-self: flex-end; }
.card-amount.sub { font-size: 14px; }
.card-label.title-order, .card-label.title-dinein, .card-label.title-delivery { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 700; color: var(--ink-soft); }
.card-label.title-order { background: #dbeafe; }
.card-label.title-dinein { background: #d6ebff; }
.card-label.title-delivery { background: #d4f5f1; }
.card-label.channel-hl { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 700; color: var(--ink-soft); }
.ch-hl-baemin { background: #d4f5f1; }
.ch-hl-coupang { background: #e5d0bc; }
.ch-hl-yogiyo { background: #ffe0e6; }
.ch-hl-ddangyo { background: #ffe4d1; }
.ch-hl-carrot { background: #ffe8d6; }
.ch-hl-table, .ch-hl-pos { background: #d6ebff; }
.ch-hl-etc { background: #f0f0f0; }
.orders { margin-bottom: 24px; background: #fff; border: 1px solid var(--rule); border-radius: 12px; padding: 18px 20px; }
.empty { color: var(--muted); font-size: 14px; padding: 16px 0; }
.order-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.order-table th { text-align: left; font-weight: 500; color: var(--muted); font-size: 12px; padding: 8px 6px; border-bottom: 1px solid var(--rule); }
.order-table td { padding: 10px 6px; border-bottom: 1px solid var(--paper-dim); }
.order-table th.right, .order-table td.right { text-align: right; }
.loading-panel { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; min-height: 220px; margin: 12px 0 24px; padding: 32px 16px; border: 1px solid var(--rule); border-radius: 12px; background: #fff; color: var(--muted); font-size: 14px; }
.loading-panel p { margin: 0; }
.spinner { width: 28px; height: 28px; border: 3px solid #e2e8f0; border-top-color: #2563eb; border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 480px) {
  .page { padding: 20px 14px 48px; }
  .totals-main .amount { font-size: 26px; }
  .card-amount { font-size: 16px; }
}
</style>
