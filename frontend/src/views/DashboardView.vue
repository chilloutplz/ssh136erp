<script setup>
import { computed, onMounted, ref, watch } from "vue";
import client from "../api/client";
import OrderDetailDrawer from "../components/OrderDetailDrawer.vue";
import { businessType, channelLabel } from "../utils/channel";

function toDateString(d) {
  return d.toLocaleDateString("sv-SE");
}

const todayString = toDateString(new Date());
const selectedDate = ref(todayString);

const today = ref(null);
const discount = ref({ discount_amount: 0, discount_order_count: 0 });
const channels = ref([]);
const orders = ref([]);
const loading = ref(true);
const error = ref("");
const selectedSaleId = ref(null);
const dateInput = ref(null);

const isToday = computed(() => selectedDate.value === todayString);
const todayDay = computed(() => new Date().getDate());

/** 내점/배달 — 실매출(actual_sale_amount) 기준 집계 */
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

const dateLabel = computed(() => {
  const date = new Date(`${selectedDate.value}T00:00:00`);

  // 두 자리 월/일
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  // 요일 (짧은 이름)
  const weekday = date.toLocaleDateString("ko-KR", { weekday: "short" });

  return `${date.getFullYear()}-${month}-${day} (${weekday})`;
});

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
    const [todayRes, channelRes, ordersRes, discountRes] = await Promise.all([
      client.get("/sales/summary/today/", { params: { date: selectedDate.value } }),
      client.get("/sales/summary/by-channel/", { params: { date: selectedDate.value } }),
      client.get("/sales/", {
        params: {
          business_date_from: selectedDate.value,
          business_date_to: selectedDate.value,
        },
      }),
      client.get("/sales/summary/discount/", { params: { date: selectedDate.value } }),
    ]);
    today.value = todayRes.data;
    channels.value = channelRes.data;
    orders.value = ordersRes.data;
    discount.value = discountRes.data;
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
        <h1>매출 현황</h1>
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

    <!-- 2x2 요약 카드 -->
    <section class="summary-grid">
      <div class="summary-card">
        <div class="order-row">
          <span class="card-label">주문</span>
          <span class="card-label">{{ today?.order_count ?? 0 }}건</span>
        </div>
        <span class="card-amount mono">{{ formatWon(today?.actual_sale_amount) }}</span>
      </div>
      <div class="summary-card">
        <div class="order-row">
          <span class="card-label">할인</span>
          <span class="card-label">{{ discount.discount_order_count }}건</span>
        </div>
        <span class="card-amount mono">{{ formatWon(discount.discount_amount) }}</span>
      </div>
      <div class="summary-card">
        <div class="order-row">
          <span class="card-label">내점</span>
          <span class="card-label">{{ dineIn.order_count }}건</span>
        </div>
        <span class="card-amount mono">{{ formatWon(dineIn.actual_sale_amount) }}</span>
      </div>
      <div class="summary-card">
        <div class="order-row">
          <span class="card-label">배달</span>
          <span class="card-label">{{ delivery.order_count }}건</span>
        </div>
        <span class="card-amount mono">{{ formatWon(delivery.actual_sale_amount) }}</span>
      </div>
    </section>

    <section class="channels">
      <p class="section-title">채널별</p>
      <ul v-if="channels.length" class="line-items">
        <li v-for="c in channels" :key="c.channel">
          <span class="name">{{ channelLabel(c.channel) }} · {{ c.order_count }}건</span>
          <span class="leader"></span>
          <span class="amt mono">{{
            formatWon(c.actual_sale_amount ?? c.net_sale_amount)
          }}</span>
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
.order-row {
  display: flex;
  justify-content: space-between; /* 양쪽 끝으로 배치 */
  align-items: center;            /* 세로 가운데 정렬 */
}

.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.topbar-right {
  display: flex;
  gap: 10px;
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

.ghost {
  background: none;
  border: 1px solid var(--rule);
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--ink-soft);
  border-radius: 6px;
}

.ghost:hover {
  border-color: var(--ink-soft);
}

.banner.error {
  background: var(--stamp-bg);
  color: var(--stamp);
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 16px;
  border-radius: 8px;
}

/* 2x2 요약 */
.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 24px;
}

.summary-card {
  background: #fff;
  border: 1px solid var(--rule);
  border-radius: 12px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.card-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}

.card-metric {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-soft);
}

.card-amount {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--ink);
  align-self: flex-end;
}

.section-title {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 12px;
}

.channels,
.orders {
  margin-bottom: 24px;
  background: #fff;
  border: 1px solid var(--rule);
  border-radius: 12px;
  padding: 18px 20px;
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
  padding: 8px 0;
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
}

@media (max-width: 480px) {
  .page {
    padding: 20px 14px 48px;
  }
  .card-amount {
    font-size: 18px;
  }
  .summary-grid {
    gap: 8px;
  }
  .summary-card {
    padding: 12px 14px;
  }
}
</style>
