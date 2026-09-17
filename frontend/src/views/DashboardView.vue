<script setup>
import { computed, onMounted, ref, watch } from "vue";
import client from "../api/client";
import { logout } from "../stores/auth";
import { useRouter } from "vue-router";
import OrderDetailDrawer from "../components/OrderDetailDrawer.vue";
import { channelMeta, orderCode } from "../utils/channel";

const router = useRouter();

function toDateString(d) {
  return d.toLocaleDateString("sv-SE");
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

const paidCount = computed(
  () => orders.value.filter((o) => o.payment_status === "결제완료").length
);
const cancelledCount = computed(
  () => orders.value.filter((o) => o.payment_status === "결제취소").length
);
const pendingCount = computed(
  () => orders.value.filter((o) => o.payment_status === "진행중").length
);

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

function openDatePicker(e) {
  e?.preventDefault?.();
  const el = dateInput.value;
  if (!el) return;
  if (typeof el.showPicker === "function") {
    try {
      el.showPicker();
      return;
    } catch {
      /* fallback */
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

function handleLogout() {
  logout();
  router.push({ name: "login" });
}

watch(selectedDate, loadAll);
onMounted(loadAll);
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div>
        <p class="eyebrow mono">ssh136erp</p>
        <h1>매출 정산</h1>
      </div>
      <div class="topbar-right">
        <button class="ghost" type="button" @click="loadAll">새로고침</button>
        <button class="ghost" type="button" @click="handleLogout">로그아웃</button>
      </div>
    </header>

    <div class="date-nav">
      <button class="ghost icon" type="button" @click="shiftDate(-1)" aria-label="전날">◀</button>

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
        <div>
          <span class="label">순매출</span>
          <span class="mono">{{ formatWon(today?.net_sale_amount) }}</span>
        </div>
      </div>
    </section>

    <section class="channels">
      <p class="section-title">채널별</p>
      <ul v-if="channels.length" class="line-items">
        <li v-for="c in channels" :key="c.channel">
          <span class="name channel-line">
            <span class="ch-badge" :class="channelMeta(c.channel).className">
              <span class="ch-icon">{{ channelMeta(c.channel).icon }}</span>
              <span class="ch-text">{{ channelMeta(c.channel).label }}</span>
            </span>
            <span class="ch-count">{{ c.order_count }}건</span>
          </span>
          <span class="leader"></span>
          <span class="amt mono">{{ formatWon(c.net_sale_amount) }}</span>
        </li>
      </ul>
      <p v-else class="empty">해당 날짜에 집계된 채널별 매출이 없습니다.</p>
    </section>

    <section class="orders">
      <p class="section-title">
        주문 목록
        <span class="count-parts">
          <span v-if="paidCount">결제완료 {{ paidCount }}</span>
          <span v-if="cancelledCount">취소 {{ cancelledCount }}</span>
          <span v-if="pendingCount">진행중 {{ pendingCount }}</span>
          <span v-if="!orders.length">0건</span>
        </span>
      </p>

      <div v-if="loading" class="empty">불러오는 중...</div>
      <table v-else-if="orders.length" class="order-table">
        <thead>
          <tr>
            <th class="col-time">시간</th>
            <th class="col-ch">채널</th>
            <th class="col-type">유형</th>
            <th class="col-code">주문번호</th>
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
            <td class="col-ch">
              <span class="ch-badge" :class="channelMeta(o.channel).className" :title="o.channel">
                <span class="ch-icon">{{ channelMeta(o.channel).icon }}</span>
                <span class="ch-text">{{ channelMeta(o.channel).label }}</span>
              </span>
            </td>
            <td class="col-type">{{ o.order_type || "-" }}</td>
            <td class="mono col-code">{{ orderCode(o.channel_order_no) }}</td>
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
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}

.count-parts {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
}

.count-parts span::after {
  content: "";
}

.count-parts span:not(:last-child)::after {
  content: "·";
  margin-left: 8px;
  color: var(--rule-strong);
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

.channel-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ch-count {
  font-size: 13px;
  color: var(--muted);
}

.line-items .leader {
  flex: 1;
  border-bottom: 1px dotted var(--rule-strong);
  transform: translateY(-3px);
}

.line-items .amt {
  white-space: nowrap;
}

/* 채널 뱃지 */
.ch-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 6px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.3;
  white-space: nowrap;
  max-width: 100%;
}

.ch-icon {
  font-size: 13px;
  line-height: 1;
}

.ch-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.ch-baemin {
  background: #e8f9f8;
  color: #0d7370;
}

.ch-coupang {
  background: #fff0e8;
  color: #c44a12;
}

.ch-yogiyo {
  background: #fdecef;
  color: #c2185b;
}

.ch-table {
  background: #eef2ff;
  color: #3f51b5;
}

.ch-pos {
  background: #f3f4f6;
  color: #374151;
}

.ch-etc {
  background: var(--paper-dim);
  color: var(--ink-soft);
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
  vertical-align: middle;
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

.order-table .col-ch {
  width: 1%;
  white-space: nowrap;
}

.order-table .col-type {
  width: 1%;
  white-space: nowrap;
  font-size: 13px;
  color: var(--ink-soft);
}

.order-table .col-code {
  width: 1%;
  white-space: nowrap;
  font-size: 12px;
  color: var(--muted);
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
  .ch-text {
    /* 모바일 테이블: 아이콘만 보이게 하려면 주석 해제
    display: none;
    */
  }
}
</style>
