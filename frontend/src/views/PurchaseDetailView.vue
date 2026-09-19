<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import client from "../api/client";

const route = useRoute();
const router = useRouter();

const purchase = ref(null);
const items = ref([]);
const materials = ref([]);
const loading = ref(true);
const error = ref("");
const saving = ref(false);
const confirming = ref(false);
const saveMessage = ref("");

const newMaterialDrafts = ref({}); // { [rowIndex]: { open: bool, name: '', unit: '' } }

const isConfirmed = computed(() => purchase.value?.status === "CONFIRMED");
const isImageFile = computed(() => {
  const url = purchase.value?.file_url || "";
  return /\.(png|jpe?g|webp|gif)$/i.test(url);
});

function formatWon(n) {
  return `₩${Number(n || 0).toLocaleString("ko-KR")}`;
}

const totalAmount = computed(() =>
  items.value.reduce((sum, it) => sum + (Number(it.amount) || 0), 0)
);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [{ data: p }, { data: mats }] = await Promise.all([
      client.get(`/purchases/${route.params.id}/`),
      client.get("/purchases/materials/"),
    ]);
    purchase.value = p;
    items.value = p.items.map((it) => ({ ...it }));
    materials.value = mats;
  } catch (e) {
    error.value = "매입 전표를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

function addRow() {
  items.value.push({
    id: null, sequence: items.value.length, raw_name: "", spec: "",
    quantity: 1, unit_price: 0, amount: 0, material: null, material_name: "",
  });
}

function removeRow(idx) {
  items.value.splice(idx, 1);
}

function openNewMaterial(idx) {
  newMaterialDrafts.value[idx] = { open: true, name: items.value[idx].raw_name || "", unit: "" };
}

async function createMaterial(idx) {
  const draft = newMaterialDrafts.value[idx];
  if (!draft?.name?.trim()) return;
  const { data } = await client.post("/purchases/materials/", {
    name: draft.name.trim(),
    unit: draft.unit.trim(),
  });
  materials.value.push(data);
  items.value[idx].material = data.id;
  items.value[idx].material_name = data.name;
  newMaterialDrafts.value[idx].open = false;
}

async function save() {
  saving.value = true;
  saveMessage.value = "";
  error.value = "";
  try {
    const payload = {
      document_date: purchase.value.document_date || null,
      document_number: purchase.value.document_number,
      supplier_name_raw: purchase.value.supplier_name_raw,
      note: purchase.value.note,
      total_amount: totalAmount.value,
      items: items.value.map((it, idx) => ({
        sequence: idx,
        raw_name: it.raw_name,
        spec: it.spec,
        quantity: it.quantity,
        unit_price: it.unit_price,
        amount: it.amount,
        material: it.material || null,
      })),
    };
    const { data } = await client.patch(`/purchases/${route.params.id}/`, payload);
    purchase.value = data;
    items.value = data.items.map((it) => ({ ...it }));
    saveMessage.value = "저장했습니다.";
  } catch (e) {
    error.value = "저장에 실패했습니다.";
  } finally {
    saving.value = false;
  }
}

async function confirmPurchase() {
  await save();
  confirming.value = true;
  try {
    const { data } = await client.post(`/purchases/${route.params.id}/confirm/`);
    purchase.value = data;
    saveMessage.value = "확정되었습니다.";
  } catch (e) {
    error.value = "확정에 실패했습니다.";
  } finally {
    confirming.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div>
        <button class="ghost" type="button" @click="router.push({ name: 'purchases' })">← 목록으로</button>
        <h1>매입 전표 검토</h1>
      </div>
    </header>

    <div v-if="loading" class="empty">불러오는 중...</div>

    <template v-else-if="purchase">
      <div v-if="error" class="banner error">{{ error }}</div>
      <div v-if="saveMessage" class="banner ok">{{ saveMessage }}</div>
      <div v-if="purchase.status === 'FAILED'" class="banner error">
        AI 파싱에 실패했습니다: {{ purchase.parse_error }} — 아래 항목을 직접 입력해서 확정할 수 있습니다.
      </div>
      <div v-if="isConfirmed" class="banner ok">이미 확정된 전표입니다 (읽기 전용).</div>

      <div class="layout">
        <section class="preview">
          <p class="section-title">원본 문서</p>
          <img v-if="isImageFile" :src="purchase.file_url" class="preview-image" alt="거래명세서 원본" />
          <a v-else :href="purchase.file_url" target="_blank" rel="noopener" class="preview-link">
            원본 파일 열기 (PDF)
          </a>
        </section>

        <section class="form">
          <div class="field-row">
            <label>
              <span>공급업체</span>
              <input v-model="purchase.supplier_name_raw" type="text" :disabled="isConfirmed" />
            </label>
            <label>
              <span>거래일자</span>
              <input v-model="purchase.document_date" type="date" :disabled="isConfirmed" />
            </label>
            <label>
              <span>문서번호</span>
              <input v-model="purchase.document_number" type="text" :disabled="isConfirmed" />
            </label>
          </div>

          <p class="section-title">품목</p>
          <table class="item-table">
            <thead>
              <tr>
                <th>품목명</th>
                <th>규격</th>
                <th class="right">수량</th>
                <th class="right">단가</th>
                <th class="right">금액</th>
                <th>자재 매핑</th>
                <th v-if="!isConfirmed"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(it, idx) in items" :key="idx">
                <td><input v-model="it.raw_name" type="text" :disabled="isConfirmed" /></td>
                <td><input v-model="it.spec" type="text" class="narrow" :disabled="isConfirmed" /></td>
                <td><input v-model.number="it.quantity" type="number" class="num" :disabled="isConfirmed" /></td>
                <td><input v-model.number="it.unit_price" type="number" class="num" :disabled="isConfirmed" /></td>
                <td><input v-model.number="it.amount" type="number" class="num" :disabled="isConfirmed" /></td>
                <td>
                  <template v-if="!newMaterialDrafts[idx]?.open">
                    <select v-model="it.material" :disabled="isConfirmed">
                      <option :value="null">-- 미매핑 --</option>
                      <option v-for="m in materials" :key="m.id" :value="m.id">{{ m.name }}</option>
                    </select>
                    <button v-if="!isConfirmed" class="link" type="button" @click="openNewMaterial(idx)">
                      + 신규
                    </button>
                  </template>
                  <template v-else>
                    <input v-model="newMaterialDrafts[idx].name" type="text" placeholder="자재명" class="narrow" />
                    <input v-model="newMaterialDrafts[idx].unit" type="text" placeholder="단위" class="narrow" />
                    <button class="link" type="button" @click="createMaterial(idx)">등록</button>
                  </template>
                </td>
                <td v-if="!isConfirmed">
                  <button class="link danger" type="button" @click="removeRow(idx)">삭제</button>
                </td>
              </tr>
            </tbody>
          </table>
          <button v-if="!isConfirmed" class="ghost" type="button" @click="addRow">+ 품목 추가</button>

          <div class="totals">
            <span>합계</span>
            <span class="mono">{{ formatWon(totalAmount) }}</span>
          </div>

          <div v-if="!isConfirmed" class="actions">
            <button class="ghost" type="button" :disabled="saving" @click="save">
              {{ saving ? "저장 중..." : "임시 저장" }}
            </button>
            <button class="primary" type="button" :disabled="confirming" @click="confirmPurchase">
              {{ confirming ? "확정 중..." : "검토 완료 · 확정" }}
            </button>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page {
  max-width: 980px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.topbar {
  margin-bottom: 20px;
}

.topbar h1 {
  margin: 8px 0 0;
  font-size: 22px;
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

.primary {
  background: var(--ink);
  color: var(--paper);
  border: none;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.primary:disabled,
.ghost:disabled {
  opacity: 0.6;
  cursor: default;
}

.banner {
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 16px;
}

.banner.error {
  background: var(--stamp-bg);
  color: var(--stamp);
}

.banner.ok {
  background: var(--ledger-bg);
  color: var(--ledger);
}

.empty {
  color: var(--muted);
  font-size: 14px;
  padding: 24px 0;
}

.layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 28px;
}

@media (max-width: 800px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.section-title {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 10px;
}

.preview-image {
  width: 100%;
  border: 1px solid var(--rule);
}

.preview-link {
  display: inline-block;
  padding: 8px 12px;
  border: 1px solid var(--rule);
  color: var(--ink-soft);
  text-decoration: none;
  font-size: 13px;
}

.field-row {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.field-row label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
  flex: 1;
  min-width: 140px;
}

.field-row input {
  padding: 7px 9px;
  border: 1px solid var(--rule);
  background: #fff;
  font-size: 13px;
  color: var(--ink);
}

.item-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: #fff;
  margin-bottom: 10px;
}

.item-table th {
  text-align: left;
  font-weight: 500;
  color: var(--muted);
  font-size: 11px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--rule);
}

.item-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--paper-dim);
}

.item-table th.right {
  text-align: right;
}

.item-table input,
.item-table select {
  width: 100%;
  padding: 5px 6px;
  border: 1px solid var(--rule);
  font-size: 13px;
  background: #fff;
}

.item-table input.num {
  text-align: right;
  width: 90px;
}

.item-table input.narrow {
  width: 90px;
}

.link {
  background: none;
  border: none;
  color: var(--ledger);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
  white-space: nowrap;
}

.link.danger {
  color: var(--stamp);
}

.totals {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  font-size: 16px;
  font-weight: 600;
  padding: 14px 8px;
  border-top: 1px dashed var(--rule-strong);
  margin-bottom: 20px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
