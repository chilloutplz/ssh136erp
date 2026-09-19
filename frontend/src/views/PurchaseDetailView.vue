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
const deleting = ref(false);
const reparsing = ref(false);
const saveMessage = ref("");
/** 확정 전표를 다시 고칠 때 true */
const editMode = ref(false);
const previewOpen = ref(false);
const previewImages = ref([]);
const previewLoading = ref(false);
const previewError = ref("");

const newMaterialDrafts = ref({});

const isConfirmed = computed(() => purchase.value?.status === "CONFIRMED");
/** 실제 입력 잠금: 확정이면서 수정모드가 아닐 때만 */
const isLocked = computed(() => isConfirmed.value && !editMode.value);
const canDelete = computed(
  () =>
    purchase.value &&
    (purchase.value.status !== "CONFIRMED" || editMode.value)
);
const canReparse = computed(
  () =>
    purchase.value &&
    purchase.value.status !== "CONFIRMED" &&
    purchase.value.file_url
);
const isImageFile = computed(() => {
  const url = purchase.value?.file_url || "";
  return /\.(png|jpe?g|webp|gif)$/i.test(url);
});

function formatWon(n) {
  return `₩${Number(n || 0).toLocaleString("ko-KR")}`;
}

function formatNumber(n) {
  if (n === null || n === undefined || n === "") return "";
  const num = Number(n);
  if (Number.isNaN(num)) return String(n);
  return num.toLocaleString("ko-KR");
}

function formatQty(n) {
  if (n === null || n === undefined || n === "") return "";
  const s = String(n);
  if (!s.includes(".")) return s;
  return s.replace(/(\.\d*?[1-9])0+$/, "$1").replace(/\.0+$/, "") || s;
}

function parseNumberInput(raw) {
  if (raw === null || raw === undefined || raw === "") return 0;
  const cleaned = String(raw).replace(/,/g, "").trim();
  const num = Number(cleaned);
  return Number.isNaN(num) ? 0 : num;
}

const totalAmount = computed(() =>
  items.value.reduce((sum, it) => sum + (Number(it.amount) || 0), 0)
);

async function load() {
  loading.value = true;
  error.value = "";
  editMode.value = false;
  previewOpen.value = false;
  previewImages.value = [];
  previewError.value = "";
  try {
    const [{ data: p }, { data: mats }] = await Promise.all([
      client.get(`/purchases/${route.params.id}/`),
      client.get("/purchases/materials/"),
    ]);
    purchase.value = p;
    items.value = (p.items || []).map((it) => ({ ...it }));
    materials.value = mats;
  } catch (e) {
    error.value = "매입 전표를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

function enterEditMode() {
  editMode.value = true;
  saveMessage.value = "수정 모드입니다. 저장하면 확정 상태는 유지됩니다.";
}

function cancelEditMode() {
  editMode.value = false;
  load();
}

function addRow() {
  items.value.push({
    id: null,
    sequence: items.value.length,
    raw_name: "",
    spec: "",
    unit: "",
    quantity: 1,
    unit_price: 0,
    amount: 0,
    material: null,
    material_name: "",
  });
}

function removeRow(idx) {
  items.value.splice(idx, 1);
}

function openNewMaterial(idx) {
  newMaterialDrafts.value[idx] = {
    open: true,
    name: items.value[idx].raw_name || "",
    unit: "",
  };
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
        unit: it.unit || "",
        quantity: it.quantity,
        unit_price: it.unit_price,
        amount: it.amount,
        material: it.material || null,
      })),
    };
    const { data } = await client.patch(`/purchases/${route.params.id}/`, payload);
    purchase.value = data;
    items.value = (data.items || []).map((it) => ({ ...it }));
    editMode.value = false;
    saveMessage.value = isConfirmed.value
      ? "수정 내용을 저장했습니다. (확정 유지)"
      : "저장했습니다.";
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
    editMode.value = false;
    saveMessage.value = "확정되었습니다.";
  } catch (e) {
    error.value = "확정에 실패했습니다.";
  } finally {
    confirming.value = false;
  }
}

async function deletePurchase() {
  if (!canDelete.value) return;
  const ok = window.confirm(
    isConfirmed.value
      ? "확정된 전표입니다. 정말 삭제할까요?\n원본 파일(PDF/이미지)도 함께 삭제됩니다."
      : "이 매입 전표를 삭제할까요?\n원본 파일(PDF/이미지)도 함께 삭제됩니다."
  );
  if (!ok) return;

  deleting.value = true;
  error.value = "";
  try {
    await client.delete(`/purchases/${route.params.id}/`);
    router.push({ name: "purchases" });
  } catch (e) {
    const msg =
      e?.response?.data?.detail ||
      "삭제에 실패했습니다. (확정 전표는 삭제할 수 없습니다)";
    error.value = typeof msg === "string" ? msg : "삭제에 실패했습니다.";
  } finally {
    deleting.value = false;
  }
}

async function reparsePurchase() {
  if (!canReparse.value) return;
  const ok = window.confirm(
    "원본 파일로 AI 파싱을 다시 실행할까요?\n현재 수정한 품목 내용은 덮어씌워집니다."
  );
  if (!ok) return;

  reparsing.value = true;
  error.value = "";
  saveMessage.value = "";
  try {
    const { data } = await client.post(`/purchases/${route.params.id}/reparse/`);
    purchase.value = data;
    items.value = (data.items || []).map((it) => ({ ...it }));
    if (data.status === "FAILED") {
      error.value = `다시 파싱 실패: ${data.parse_error || ""}`;
    } else {
      saveMessage.value = "다시 파싱했습니다. 수량·품목을 원본과 비교해 확인하세요.";
    }
  } catch (e) {
    const msg = e?.response?.data?.detail || "다시 파싱에 실패했습니다.";
    error.value = typeof msg === "string" ? msg : "다시 파싱에 실패했습니다.";
  } finally {
    reparsing.value = false;
  }
}


async function togglePreview() {
  if (previewOpen.value) {
    previewOpen.value = false;
    return;
  }
  previewLoading.value = true;
  previewError.value = "";
  try {
    const { data } = await client.get(`/purchases/${route.params.id}/preview/`);
    previewImages.value = data.images || [];
    if (!previewImages.value.length) {
      previewError.value = "미리보기 이미지가 없습니다.";
    }
    previewOpen.value = true;
  } catch (e) {
    previewError.value =
      e?.response?.data?.detail || "미리보기를 불러오지 못했습니다.";
    previewOpen.value = true;
  } finally {
    previewLoading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div>
        <button class="ghost" type="button" @click="router.push({ name: 'purchases' })">
          ← 목록으로
        </button>
        <h1>매입 전표 검토</h1>
      </div>
      <div class="topbar-actions">
        <button
          v-if="isConfirmed && !editMode"
          class="ghost"
          type="button"
          @click="enterEditMode"
        >
          수정
        </button>
        <button
          v-if="isConfirmed && editMode"
          class="ghost"
          type="button"
          :disabled="saving"
          @click="cancelEditMode"
        >
          수정 취소
        </button>
        <button
          v-if="canReparse"
          class="ghost"
          type="button"
          :disabled="reparsing || deleting"
          @click="reparsePurchase"
        >
          {{ reparsing ? "파싱 중..." : "다시 파싱" }}
        </button>
        <button
          v-if="canDelete"
          class="ghost danger-btn"
          type="button"
          :disabled="deleting || reparsing"
          @click="deletePurchase"
        >
          {{ deleting ? "삭제 중..." : "전표 삭제" }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="empty">불러오는 중...</div>

    <template v-else-if="purchase">
      <div v-if="error" class="banner error">{{ error }}</div>
      <div v-if="saveMessage" class="banner ok">{{ saveMessage }}</div>
      <div v-if="purchase.status === 'FAILED'" class="banner error">
        AI 파싱에 실패했습니다: {{ purchase.parse_error }} — 직접 수정하거나 「다시 파싱」을 눌러 보세요.
      </div>
      <div v-if="isConfirmed && !editMode" class="banner ok">
        확정된 전표입니다 (읽기 전용). 내용을 바꾸려면 「수정」을 누르세요.
      </div>
      <div v-if="isConfirmed && editMode" class="banner ok">
        수정 모드 — 저장 시 확정 상태는 유지됩니다.
      </div>

      <!-- 세로 배치: 원본 문서 → 공급업체/품목 (공간 절약) -->
      <section class="preview-block">
        <div class="preview-head">
          <p class="section-title">원본 문서</p>
          <div class="preview-head-actions">
            <button
              v-if="purchase.file_url"
              class="ghost small"
              type="button"
              :disabled="previewLoading"
              @click="togglePreview"
            >
              {{
                previewLoading
                  ? "불러오는 중..."
                  : previewOpen
                    ? "원본 닫기"
                    : "원본 보기"
              }}
            </button>
            <a
              v-if="purchase.file_url"
              :href="purchase.file_url"
              target="_blank"
              rel="noopener"
              class="preview-open"
            >
              PDF 새 창
            </a>
          </div>
        </div>

        <div v-if="previewOpen" class="preview-body">
          <p v-if="previewError" class="preview-empty">{{ previewError }}</p>
          <img
            v-for="(src, i) in previewImages"
            :key="i"
            :src="src"
            class="preview-image"
            :alt="`거래명세서 ${i + 1}페이지`"
          />
        </div>
      </section>

      <section class="form">
        <div class="field-row">
          <label>
            <span>공급업체</span>
            <input v-model="purchase.supplier_name_raw" type="text" :disabled="isLocked" />
          </label>
          <label class="narrow">
            <span>거래일자</span>
            <input v-model="purchase.document_date" type="date" :disabled="isLocked" />
          </label>
          <label class="narrow">
            <span>문서번호</span>
            <input v-model="purchase.document_number" type="text" :disabled="isLocked" />
          </label>
        </div>

        <p class="section-title">품목</p>
        <div class="item-list">
          <article v-for="(it, idx) in items" :key="idx" class="item-card">
            <div class="item-card-head">
              <span class="item-idx">{{ idx + 1 }}</span>
              <button
                v-if="!isLocked"
                class="link danger"
                type="button"
                @click="removeRow(idx)"
              >
                삭제
              </button>
            </div>

            <div class="row row-main">
              <label class="grow">
                <span>품목명</span>
                <input v-model="it.raw_name" type="text" :disabled="isLocked" />
              </label>
              <label class="spec">
                <span>규격·산지</span>
                <input v-model="it.spec" type="text" :disabled="isLocked" />
              </label>
              <label class="map">
                <span>자재 매핑</span>
                <template v-if="!newMaterialDrafts[idx]?.open">
                  <div class="map-controls">
                    <select v-model="it.material" :disabled="isLocked">
                      <option :value="null">— 미매핑 —</option>
                      <option v-for="m in materials" :key="m.id" :value="m.id">
                        {{ m.name }}
                      </option>
                    </select>
                    <button
                      v-if="!isLocked"
                      class="link"
                      type="button"
                      @click="openNewMaterial(idx)"
                    >
                      +
                    </button>
                  </div>
                </template>
                <template v-else>
                  <div class="map-controls">
                    <input
                      v-model="newMaterialDrafts[idx].name"
                      type="text"
                      placeholder="자재명"
                    />
                    <button class="link" type="button" @click="createMaterial(idx)">OK</button>
                  </div>
                </template>
              </label>
            </div>

            <div class="row row-nums">
              <label>
                <span>수량</span>
                <input
                  :value="formatQty(it.quantity)"
                  type="text"
                  inputmode="decimal"
                  class="num"
                  :disabled="isLocked"
                  @change="it.quantity = parseNumberInput($event.target.value)"
                />
              </label>
              <label class="unit">
                <span>단위</span>
                <input v-model="it.unit" type="text" :disabled="isLocked" />
              </label>
              <label>
                <span>단가</span>
                <input
                  :value="formatNumber(it.unit_price)"
                  type="text"
                  inputmode="numeric"
                  class="num"
                  :disabled="isLocked"
                  @change="it.unit_price = parseNumberInput($event.target.value)"
                />
              </label>
              <label>
                <span>금액</span>
                <input
                  :value="formatNumber(it.amount)"
                  type="text"
                  inputmode="numeric"
                  class="num"
                  :disabled="isLocked"
                  @change="it.amount = parseNumberInput($event.target.value)"
                />
              </label>
            </div>
          </article>
        </div>

        <button v-if="!isLocked" class="ghost" type="button" @click="addRow">
          + 품목 추가
        </button>

        <div class="totals">
          <span>합계</span>
          <span class="mono">{{ formatWon(totalAmount) }}</span>
        </div>

        <div v-if="!isLocked" class="actions">
          <button
            v-if="!isConfirmed"
            class="ghost"
            type="button"
            :disabled="reparsing || deleting"
            @click="reparsePurchase"
          >
            {{ reparsing ? "파싱 중..." : "다시 파싱" }}
          </button>
          <button
            v-if="canDelete"
            class="ghost danger-btn"
            type="button"
            :disabled="deleting || reparsing"
            @click="deletePurchase"
          >
            {{ deleting ? "삭제 중..." : "전표 삭제" }}
          </button>
          <button
            class="ghost"
            type="button"
            :disabled="saving || deleting || reparsing"
            @click="save"
          >
            {{ saving ? "저장 중..." : isConfirmed ? "수정 저장" : "임시 저장" }}
          </button>
          <button
            v-if="!isConfirmed"
            class="primary"
            type="button"
            :disabled="confirming || deleting || reparsing"
            @click="confirmPurchase"
          >
            {{ confirming ? "확정 중..." : "검토 완료 · 확정" }}
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 16px 48px;
}

.topbar {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.topbar h1 {
  margin: 6px 0 0;
  font-size: 20px;
}

.topbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
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

.ghost.danger-btn {
  color: var(--stamp);
  border-color: var(--stamp);
}

.primary {
  background: var(--ink);
  color: var(--paper);
  border: none;
  padding: 8px 14px;
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
  margin-bottom: 12px;
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

.section-title {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 8px;
}

.preview-block {
  margin-bottom: 16px;
}

.preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.preview-head .section-title {
  margin: 0;
}

.preview-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ghost.small {
  padding: 4px 10px;
  font-size: 12px;
}

.preview-open {
  font-size: 12px;
  color: var(--ink-soft);
  text-decoration: none;
  white-space: nowrap;
}

.preview-open:hover {
  text-decoration: underline;
}

.preview-body {
  border: 1px solid var(--rule);
  background: #fff;
  min-height: 280px;
  max-height: 480px;
  overflow: auto;
}

.preview-image {
  width: 100%;
  display: block;
}

.preview-pdf {
  width: 100%;
  height: 420px;
  display: block;
}

.preview-empty {
  margin: 0;
  padding: 16px;
  font-size: 13px;
  color: var(--muted);
}

.field-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.field-row label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: var(--muted);
  flex: 1;
  min-width: 120px;
}

.field-row label.narrow {
  flex: 0 0 140px;
}

.field-row input,
.item-card input,
.item-card select {
  padding: 6px 8px;
  border: 1px solid var(--rule);
  background: #fff;
  font-size: 13px;
  color: var(--ink);
  font-family: inherit;
  width: 100%;
  box-sizing: border-box;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}

.item-card {
  background: #fff;
  border: 1px solid var(--rule);
  padding: 10px 12px;
}

.item-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.item-idx {
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
}

.item-card label {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
  color: var(--muted);
}

.row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: flex-end;
}

.row-main {
  margin-bottom: 8px;
}

.row-main .grow {
  flex: 1 1 160px;
  min-width: 120px;
}

.row-main .spec {
  flex: 1 1 140px;
  min-width: 110px;
}

.row-main .map {
  flex: 0 1 120px;
  min-width: 100px;
}

.row-nums label {
  flex: 1 1 72px;
  min-width: 64px;
}

.row-nums .unit {
  flex: 0 1 56px;
  min-width: 48px;
}

.row-nums input.num {
  text-align: right;
}

.map-controls {
  display: flex;
  gap: 4px;
  align-items: center;
}

.map-controls select,
.map-controls input {
  flex: 1;
  min-width: 0;
}

.link {
  background: none;
  border: none;
  color: var(--ledger);
  font-size: 13px;
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
  font-size: 15px;
  font-weight: 600;
  padding: 12px 4px;
  border-top: 1px dashed var(--rule-strong);
  margin: 12px 0 16px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
