<script setup>
import { ref, watch } from "vue";
import client from "../api/client";

const props = defineProps({
  saleId: { type: [Number, String], default: null },
});
const emit = defineEmits(["close"]);

const sale = ref(null);
const loading = ref(false);
const error = ref("");

watch(
  () => props.saleId,
  async (id) => {
    if (!id) {
      sale.value = null;
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      const { data } = await client.get(`/sales/${id}/`);
      sale.value = data;
    } catch (e) {
      error.value = "상세 내역을 불러오지 못했습니다.";
    } finally {
      loading.value = false;
    }
  }
);

function formatWon(n) {
  return `₩${Number(n || 0).toLocaleString("ko-KR")}`;
}
</script>

<template>
  <div v-if="saleId" class="backdrop" @click.self="emit('close')">
    <aside class="drawer">
      <button class="close" @click="emit('close')" aria-label="닫기">닫기 ✕</button>

      <div v-if="loading" class="state">불러오는 중...</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="sale">
        <p class="eyebrow mono">{{ sale.source }} · {{ sale.order_seq }}</p>
        <h2>{{ sale.channel || "주문" }} 상세</h2>
        <p class="meta">
          {{ sale.business_date }} · {{ sale.order_type || "-" }} ·
          <span :class="sale.payment_status === '결제취소' ? 'tag stamp' : 'tag ledger'">
            {{ sale.payment_status }}
          </span>
        </p>

        <hr class="hairline" />

        <ul class="line-items">
          <li v-for="item in sale.items" :key="item.item_seq">
            <span class="name">{{ item.goods_nm }} × {{ item.sale_qty }}</span>
            <span class="leader"></span>
            <span class="amt mono">{{ formatWon(item.sale_amt) }}</span>
          </li>
        </ul>

        <hr class="hairline" />

        <div class="totals">
          <div class="row">
            <span>매출액</span>
            <span class="mono">{{ formatWon(sale.sale_amount) }}</span>
          </div>
          <div class="row" v-if="sale.discount_amount">
            <span>할인</span>
            <span class="mono">-{{ formatWon(sale.discount_amount) }}</span>
          </div>
          <div class="row total">
            <span>실매출</span>
            <span class="mono">{{ formatWon(sale.actual_sale_amount) }}</span>
          </div>
        </div>

        <hr class="hairline" />

        <p class="section-label">결제</p>
        <ul class="line-items">
          <li v-for="t in sale.tenders" :key="t.tender_seq">
            <span class="name">{{ t.tender_nm }}</span>
            <span class="leader"></span>
            <span class="amt mono">{{ formatWon(t.tender_amt) }}</span>
          </li>
        </ul>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(34, 37, 43, 0.25);
  display: flex;
  justify-content: flex-end;
  z-index: 20;
}

.drawer {
  width: 100%;
  max-width: 380px;
  height: 100%;
  background: #fff;
  border-left: 1px solid var(--rule);
  padding: 28px 26px;
  overflow-y: auto;
}

.close {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  margin-bottom: 20px;
}

.state {
  color: var(--muted);
  font-size: 14px;
}

.state.error {
  color: var(--stamp);
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

h2 {
  margin: 4px 0 8px;
  font-size: 19px;
}

.meta {
  margin: 0;
  font-size: 13px;
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

.hairline {
  margin: 18px 0;
}

.section-label {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--muted);
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
  padding: 6px 0;
  font-size: 14px;
}

.line-items .name {
  white-space: nowrap;
}

.line-items .leader {
  flex: 1;
  border-bottom: 1px dotted var(--rule-strong);
  transform: translateY(-3px);
}

.line-items .amt {
  white-space: nowrap;
}

.totals .row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  font-size: 14px;
  color: var(--ink-soft);
}

.totals .row.total {
  font-weight: 600;
  color: var(--ink);
  font-size: 16px;
  padding-top: 8px;
}
</style>
