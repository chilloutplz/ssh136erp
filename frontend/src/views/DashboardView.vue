<script setup>
import { computed, onMounted, ref, watch } from "vue";
import client from "../api/client";
import OrderDetailDrawer from "../components/OrderDetailDrawer.vue";
import { businessType, channelLabel } from "../utils/channel";

function toDateString(d) {
  return d.toLocaleDateString("sv-SE"); // YYYY-MM-DD, 로컬 타임존 기준
}

const todayString = toDateString(new Date());
const selectedDate = ref(todayString);

const today = ref(null);
const channels = ref([]);
const orders = ref([]);
const loading = ref(true);
const error = ref("");
const selectedSaleId = ref(null);
const dateInput = ref(null);

const isToday = computed(() => selectedDate.value === todayString);
const todayDay = computed(() => new Date().getDate());
const businessChannels = computed(() => {
  const groups = new Map();
  for (const row of channels.value) {
    const type = businessType(row.channel);
    const current = groups.get(type) || {
      channel: type,
      sale_amount: 0,
      net_sale_amount: 0,
      order_count: 0,
    };
    current.sale_amount += Number(row.sale_amount || 0);
    current.net_sale_amount += Number(row.net_sale_amount || 0);
    current.order_count += Number(row.order_count || 0);
    groups.set(type, current);
  }
  return ["내점", "배달"].map((type) => groups.get(type) || {
    channel: type,
    sale_amount: 0,
    net_sale_amount: 0,
    order_count: 0,
  });
});

const dateLabel = computed(() =>
  new Date(`${selectedDate.value}T00:00:00`).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  })
);

function formatWon(n) {
  return `₩${Number(n || 0).toLocaleString("ko-KR")}`;
}

function statusTagClass(status) {
  if (status === "결제취소") return "tag stamp";
  if (status === "진행중") return "tag pending";
  return "tag ledger";
}

function formatTime(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function shiftDate(days) {
  const d = new Date(`${selectedDate.value}T00:00:00`);
  d.setDate(d.getDate() + days);
  const next = toDateString(d);
  if (next > todayString) return;
  selectedDate.value = next;
}

function goToday() {
  selectedDate.value = todayString;
}

/** 모바일/데스크톱에서 달력 팝업 열기 */
function openDatePicker(e) {
  e?.preventDefault?.();
  const el = dateInput.value;
  if (!el) return;
  if (typeof el.showPicker === "function") {
    try {
      el.showPicker();
      return;
    } catch {
      // fallback below
    }
  }
  el.focus();
  el.click();
}

async function loadAll() {
  loading.value = true;
  error.value = "";
  try {
    const [todayRes, channelRes, ordersRes] = await Promise.all([
      client.get("/sales/summary/today/", { params: { date: selectedDate.value } }),
      client.get("/sales/summary/by-channel/", { params: { date: selectedDate.value } }),
      client.get("/sales/", {
        params: {
          business_date_from: selectedDate.value,
          business_date_to: selectedDate.value,
        },
      }),
    ]);
    today.value = todayRes.data;
    channels.value = channelRes.data;
    orders.value = ordersRes.data;
  } catch (e) {
    error.value = "데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.";
  } finally {
    loading.value = false;
  }
}

async function refreshDashboard() {
  loading.value = true;
  error.value = "";
  let syncError = "";
  try {
    await client.post("/integrations/tosspos/sync-pending/");
  } catch (e) {
    syncError = "진행 중 주문 동기화에 실패했습니다. 잠시 후 다시 시도해주세요.";
  }
  await loadAll();
  if (syncError) error.value = syncError;
}

watch(selectedDate, loadAll);
onMounted(loadAll);
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div>
        <h1>매출 정산</h1>
      </div>
      <div class="topbar-right">
        <button class="ghost" type="button" @click="refreshDashboard">새로고침</button>
      </div>
    </header>

    <div class="date-nav">
      <button class="ghost icon" type="button" @click="shiftDate(-1)" aria-label="전날">
        ◀
      </button>

      <button
        class="date-trigger"
        type="button"
        :aria-label="`날짜 선택: ${dateLabel}`"
        @click="openDatePicker"
      >
        <span class="date-label">{{ dateLabel }}</span>
        <input
          ref="dateInput"
          type="date"
          class="date-input-overlay"
          v-model="selectedDate"
          :max="todayString"
          tabindex="-1"
          @click.stop="openDatePicker"
        />
      </button>

      <button
        class="ghost icon"
        type="button"
        @click="shiftDate(1)"
        :disabled="isToday"
        aria-label="다음날"
      >
        ▶
      </button>

      <button
        v-if="!isToday"
        class="today-chip"
        type="button"
        :aria-label="`${todayDay}일(오늘)로`"
        @click="goToday"
      >
        {{ todayDay }}
      </button>
    </div>

    <div v-if="error" class="banner error">{{ error }}</div>

    <section class="totals-slip">
      <div class="totals-main">
        <span class="label">실매출</span>
        <span class="amount mono">{{ formatWon(today?.actual_sale_amount) }}</span>
      </div>
      <div class="totals-sub">
        <div>
          <span class="label">주문 건수</span>
          <span class="mono">{{ today?.order_count ?? 0 }}건</span>
        </div>
        <div>
          <span class="label">매출액</span>
          <span class="mono">{{ formatWon(today?.sale_amount) }}</span>
        </div>
      </div>
    </section>

    <section class="business-summary">
      <div v-for="group in businessChannels" :key="group.channel" class="business-card">
        <span class="business-label">{{ group.channel }}</span>
        <div class="business-metrics">
          <div>
            <span class="business-metric-label">주문 건수</span>
            <strong class="business-metric-value mono">{{ group.order_count }}건</strong>
          </div>
          <div>
            <span class="business-metric-label">매출액</span>
            <strong class="business-metric-value mono">{{ formatWon(group.sale_amount) }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="channels">
      <p class="section-title">채널별</p>
      <ul v-if="channels.length" class="line-items">
        <li v-for="c in channels" :key="c.channel">
          <span class="name">{{ channelLabel(c.channel) }} · {{ c.order_count }}건</span>
          <span class="leader"></span>
          <span class="amt mono">{{ formatWon(c.net_sale_amount) }}</span>
        </li>
      </ul>
      <p v-else class="empty">해당 날짜에 집계된 채널별 매출이 없습니다.</p>
    </section>

    <section class="orders">
      <p class="section-title">주문 목록 ({{ orders.length }}건)</p>

      <div v-if="loading" class="empty">불러오는 중...</div>
      <table v-else-if="orders.length" class="order-table">
        <thead>
          <tr>
            <th class="col-time">시간</th>
            <th>채널</th>
            <th>결제수단</th>
            <th>상태</th>
            <th class="right">실매출</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="o in orders"
            :key="o.id"
            @click="selectedSaleId = o.id"
          >
            <td class="mono col-time">{{ formatTime(o.sold_at) }}</td>
            <td>{{ channelLabel(o.channel) }}</td>
            <td>{{ o.payment_method || "-" }}</td>
            <td>
              <span :class="statusTagClass(o.payment_status)">
                {{ o.payment_status }}
              </span>
            </td>
            <td class="right mono">{{ formatWon(o.actual_sale_amount) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">해당 날짜에 들어온 주문이 없습니다.</p>
    </section>

    <OrderDetailDrawer
      :sale-id="selectedSaleId"
      @close="selectedSaleId = null"
    />
  </div>
</template>

<style scoped>
.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

h1 {
  margin: 4px 0 0;
  font-size: 24px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.date-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  min-width: 0;
}

.date-nav .icon {
  padding: 6px 10px;
  line-height: 1;
  flex-shrink: 0;
}

.date-nav .icon:disabled {
  opacity: 0.35;
  cursor: default;
}

.date-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-width: 0;
  flex: 1;
  min-height: 36px;
  padding: 6px 8px;
  margin: 0;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}

.date-label {
  font-size: 14px;
  color: var(--ink-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin: 0;
  pointer-events: none;
}

/* display:none 금지 — 달력 안 뜸. opacity 0도 일부 모바일에서 클릭 무시 */
.date-input-overlay {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  opacity: 0.01;
  border: 0;
  padding: 0;
  margin: 0;
  cursor: pointer;
  font-size: 16px;
}

.today-chip {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--ink-soft);
  cursor: pointer;
  line-height: 1;
}

.today-chip:hover {
  border-color: var(--ink-soft);
}

.ghost {
  background: none;
  border: 1px solid var(--rule);
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--ink-soft);
}

.ghost:hover {
  border-color: var(--ink-soft);
}

.banner.error {
  background: var(--stamp-bg);
  color: var(--stamp);
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 20px;
}

.totals-slip {
  background: #fff;
  border: 1px solid var(--rule);
  padding: 24px 28px;
  margin-bottom: 28px;
}

.totals-main {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px dashed var(--rule-strong);
}

.totals-main .label {
  font-size: 14px;
  color: var(--muted);
}

.totals-main .amount {
  font-size: 32px;
  font-weight: 600;
}

.totals-sub {
  display: flex;
  gap: 32px;
}

.totals-sub > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.totals-sub .label {
  font-size: 12px;
  color: var(--muted);
}

.totals-sub .mono {
  font-size: 15px;
}

.section-title {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 12px;
}

.channels {
  margin-bottom: 28px;
}

.line-items {
  list-style: none;
  margin: 0;
  padding: 0;
}

.line-items li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 7px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--paper-dim);
}

.line-items .name {
  white-space: nowrap;
  color: var(--ink-soft);
}

.line-items .leader {
  flex: 1;
  border-bottom: 1px dotted var(--rule-strong);
  transform: translateY(-3px);
}

.line-items .amt {
  white-space: nowrap;
}

.empty {
  color: var(--muted);
  font-size: 14px;
  padding: 16px 0;
}

.order-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.order-table th {
  text-align: left;
  font-weight: 500;
  color: var(--muted);
  font-size: 12px;
  padding: 8px 6px;
  border-bottom: 1px solid var(--rule);
}

.order-table td {
  padding: 10px 6px;
  border-bottom: 1px solid var(--paper-dim);
}

.order-table tbody tr {
  cursor: pointer;
}

.order-table tbody tr:hover {
  background: var(--paper-dim);
}

.order-table th.right,
.order-table td.right {
  text-align: right;
}

.order-table .col-time {
  width: 52px;
  white-space: nowrap;
}

.tag {
  padding: 1px 8px;
  font-size: 12px;
  border-radius: 2px;
}

.tag.ledger {
  background: var(--ledger-bg);
  color: var(--ledger);
}

.tag.stamp {
  background: var(--stamp-bg);
  color: var(--stamp);
}

.tag.pending {
  background: var(--paper-dim);
  color: var(--muted);
  border: 1px dashed var(--rule-strong);
}

@media (max-width: 480px) {
  .date-label {
    font-size: 13px;
  }
  .today-chip {
    width: 30px;
    height: 30px;
  }
}
</style>


<style scoped>
.page { max-width: 1280px; padding: 32px 32px 64px; }
.topbar { align-items: center; margin-bottom: 20px; }
h1 { font-size: 28px; font-weight: 700; letter-spacing: -.03em; }
.topbar-right { gap: 10px; }
.ghost, .date-trigger, .today-chip {
  border: 1px solid var(--rule);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--ink-soft);
  box-shadow: 0 1px 2px rgba(15,23,42,.03);
}
.ghost { padding: 9px 14px; font-weight: 600; }
.ghost:hover, .today-chip:hover { border-color: #93c5fd; color: var(--ledger); background: #f8fbff; }
.date-nav { margin-bottom: 24px; }
.date-trigger { min-height: 40px; padding: 8px 12px; }
.banner.error { border: 1px solid #fecaca; border-radius: var(--radius-md); background: var(--stamp-bg); padding: 12px 14px; }
.totals-slip {
  border: 1px solid var(--rule);
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: var(--shadow-card);
  padding: 22px 24px;
  margin-bottom: 20px;
}
.totals-main { border-bottom: 0; padding: 0 0 20px; margin: 0 0 20px; }
.totals-main .label, .totals-sub .label { color: var(--muted); font-size: 12px; font-weight: 600; }
.totals-main .amount { color: var(--ink); font-size: 34px; font-weight: 750; letter-spacing: -.04em; }
.totals-sub { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.totals-sub > div { border: 1px solid var(--rule); border-radius: var(--radius-md); background: #f8fafc; padding: 14px; gap: 7px; }
.totals-sub .mono { color: var(--ink); font-size: 17px; font-weight: 700; }
.channels, .orders {
  border: 1px solid var(--rule);
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: var(--shadow-card);
  padding: 20px 22px;
  margin-bottom: 20px;
}
.section-title { color: var(--ink); font-size: 15px; font-weight: 700; margin-bottom: 16px; }
.line-items li { padding: 11px 0; border-bottom-color: var(--rule); }
.line-items .name { color: var(--ink-soft); }
.line-items .leader { border-bottom-color: #cbd5e1; }
.order-table { font-size: 14px; }
.order-table th { background: #f8fafc; color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .03em; text-transform: uppercase; padding: 12px 10px; border-bottom: 1px solid var(--rule); }
.order-table td { padding: 14px 10px; border-bottom: 1px solid #eef2f7; color: var(--ink-soft); }
.order-table tbody tr:hover { background: #f8fbff; }
.tag { border: 0; border-radius: 999px; padding: 4px 9px; font-size: 11px; font-weight: 700; }
.tag.ledger { background: var(--success-bg); color: var(--success); }
.tag.stamp { background: var(--stamp-bg); color: var(--stamp); }
.tag.pending { border: 0; background: var(--warning-bg); color: var(--warning); }
.empty { color: var(--muted); padding: 26px 0; }
@media (max-width: 720px) {
  .page { padding: 22px 16px 48px; }
  .topbar { align-items: flex-start; }
  h1 { font-size: 23px; }
  .totals-sub { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .totals-main .amount { font-size: 28px; }
  .channels, .orders, .totals-slip { padding: 16px; border-radius: var(--radius-md); }
  .order-table { min-width: 620px; }
  .orders { overflow-x: auto; }
}
</style>


<style scoped>
.business-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-bottom: 20px; }
.business-card { min-width: 0; padding: 18px 20px; border: 1px solid var(--rule); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-card); }
.business-card:nth-child(1) { border-top: 3px solid #2563eb; }
.business-card:nth-child(2) { border-top: 3px solid #f97316; }
.business-label { display: block; color: var(--muted); font-size: 13px; font-weight: 700; }
.business-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 16px; }
.business-metrics > div { min-width: 0; }
.business-metric-label { display: block; color: var(--muted); font-size: 11px; font-weight: 600; }
.business-metric-value { display: block; margin-top: 6px; color: var(--ink); font-size: 17px; font-weight: 750; letter-spacing: -.03em; white-space: nowrap; }
@media (max-width: 720px) {
  .business-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .business-card { padding: 15px 14px; }
  .business-metrics { grid-template-columns: 1fr; gap: 9px; }
  .business-metric-value { font-size: 16px; }
}
</style>
