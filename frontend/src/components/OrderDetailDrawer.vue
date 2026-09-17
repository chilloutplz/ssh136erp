<script setup>
import { ref, watch } from "vue";
import client from "../api/client";
import { channelMeta, orderCode } from "../utils/channel";

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

function optionLabel(opt) {
  if (opt == null) return "";
  if (typeof opt === "string") return opt;
  return (
    opt.title ||
    opt.name ||
    opt.label ||
    opt.optionName ||
    opt.optionChoice?.title ||
    opt.optionChoice?.name ||
    opt.item?.title ||
    ""
  );
}

function optionPrice(opt) {
  if (opt == null || typeof opt !== "object") return 0;
  const raw =
    opt.price ??
    opt.priceValue ??
    opt.amount ??
    opt.itemPrice?.priceValue ??
    0;
  return Number(raw) || 0;
}

function statusTagClass(status) {
  if (status === "결제취소") return "tag stamp";
  if (status === "진행중") return "tag pending";
  return "tag ledger";
}
</script>

<template>
  <div v-if="saleId" class="backdrop" @click.self="emit('close')">
    <aside class="drawer">
      <button class="close" @click="emit('close')" aria-label="닫기">닫기 ✕</button>

      <div v-if="loading" class="state">불러오는 중...</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="sale">
        <p class="eyebrow mono">
          {{ sale.source }}
          <template v-if="orderCode(sale.channel_order_no) !== '-'">
            · {{ orderCode(sale.channel_order_no) }}
          </template>
        </p>
        <h2 class="title-row">
          <span class="ch-badge" :class="channelMeta(sale.channel).className">
            <span class="ch-icon">{{ channelMeta(sale.channel).icon }}</span>
            <span class="ch-text">{{ channelMeta(sale.channel).label }}</span>
          </span>
          <span class="title-suffix">상세</span>
        </h2>
        <p class="meta">
          {{ sale.business_date }} · {{ sale.order_type || "-" }} ·
          <span :class="statusTagClass(sale.payment_status)">
            {{ sale.payment_status }}
          </span>
        </p>

        <hr class="hairline" />

        <ul class="line-items">
          <li v-for="(item, idx) in sale.items" :key="item.item_seq ?? idx">
            <div class="item-block">
              <div class="item-row">
                <span class="name">{{ item.goods_nm }} × {{ item.sale_qty }}</span>
                <span class="leader"></span>
                <span class="amt mono">{{ formatWon(item.sale_amt) }}</span>
              </div>
              <ul
                v-if="item.item_opt_details?.length"
                class="options"
              >
                <li v-for="(opt, oi) in item.item_opt_details" :key="oi">
                  <span class="opt-name">+ {{ optionLabel(opt) }}</span>
                  <span
                    v-if="optionPrice(opt)"
                    class="opt-amt mono"
                  >{{ formatWon(optionPrice(opt)) }}</span>
                </li>
              </ul>
            </div>
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
        <ul class="line-items tenders">
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

.title-row {
  margin: 4px 0 8px;
  font-size: 19px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-suffix {
  font-weight: 600;
}

.meta {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}

.ch-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 6px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
}

.ch-icon {
  font-size: 14px;
  line-height: 1;
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
  display: block;
  padding: 8px 0;
  font-size: 14px;
}

.line-items.tenders li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 0;
}

.line-items.tenders .name {
  white-space: nowrap;
}

.line-items.tenders .leader {
  flex: 1;
  border-bottom: 1px dotted var(--rule-strong);
  transform: translateY(-3px);
}

.line-items.tenders .amt {
  white-space: nowrap;
}

.item-block {
  flex: 1;
  min-width: 0;
}

.item-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.item-row .name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-row .leader {
  flex: 1;
  border-bottom: 1px dotted var(--rule-strong);
  transform: translateY(-3px);
}

.item-row .amt {
  white-space: nowrap;
}

.options {
  list-style: none;
  margin: 4px 0 0;
  padding: 0 0 0 8px;
}

.options li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 0;
  font-size: 12px;
  color: var(--muted);
  border-bottom: none;
}

.opt-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.opt-amt {
  flex-shrink: 0;
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
