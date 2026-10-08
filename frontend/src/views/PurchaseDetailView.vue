<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import client from "../api/client";

const route = useRoute();
const router = useRouter();

const purchase = ref(null);
const items = ref([]);
const materials = ref([]);
const suppliers = ref([]);
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
/** 거래처 신규 생성 드래프트 (human-in-the-loop: 사람이 명시적으로 생성 버튼을 눌러야 함).
 *  명세서 파싱값(supplier_draft)이 있으면 기본값으로 채워준다. */
const newSupplierDraft = ref({
  open: false,
  name: "",
  business_number: "",
  representative: "",
  phone: "",
  fax: "",
  email: "",
  address: "",
});

/** 명세서에서 파싱한 거래처 정보 (제안값 — 그대로 저장하지 않고 사람이 확인/수정 후 등록) */
const supplierDraft = computed(() => purchase.value?.supplier_draft || {});

const SUPPLIER_DRAFT_LABELS = {
  business_number: "사업자번호",
  representative: "대표자",
  phone: "전화",
  fax: "팩스",
  email: "이메일",
  address: "사업장 주소",
};

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

/** 아직 자재로 연결 안 된 품목 수 (검토 필요 알림용) */
const unresolvedItemCount = computed(
  () => items.value.filter((it) => !it.material).length
);

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
    const [{ data: p }, { data: mats }, { data: sups }] = await Promise.all([
      client.get(`/purchases/${route.params.id}/`),
      client.get("/purchases/materials/"),
      client.get("/purchases/suppliers/"),
    ]);
    purchase.value = p;
    items.value = (p.items || []).map((it) => ({ ...it }));
    materials.value = mats;
    suppliers.value = sups;
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
    material_candidates: [],
  });
}

function removeRow(idx) {
  items.value.splice(idx, 1);
}

// ---------------------------------------------------------------- 거래처

/** 거래처 선택 시 raw 이름도 같이 맞춤 (표시/정합성용) */
function onSupplierChange() {
  const id = purchase.value.supplier;
  const found = suppliers.value.find((s) => s.id === id);
  if (found) purchase.value.supplier_name_raw = found.name;
}

/** 새 거래처 폼 열기 — 파싱된 supplier_draft 값으로 미리 채움 (제안값) */
function openNewSupplier() {
  const d = supplierDraft.value;
  newSupplierDraft.value = {
    open: true,
    name: d.name || purchase.value?.supplier_name_raw || "",
    business_number: d.business_number || "",
    representative: d.representative || "",
    phone: d.phone || "",
    fax: d.fax || "",
    email: d.email || "",
    address: d.address || "",
  };
}

/** 사람이 확인/수정한 값으로만 거래처 생성 — 파싱값 자동 저장은 없음 */
async function createSupplier() {
  const d = newSupplierDraft.value;
  if (!d.name?.trim()) return;
  const payload = {};
  for (const k of ["name", "business_number", "representative", "phone", "fax", "email", "address"]) {
    if (d[k]?.trim()) payload[k] = d[k].trim();
  }
  const { data } = await client.post("/purchases/suppliers/", payload);
  suppliers.value.push(data);
  purchase.value.supplier = data.id;
  purchase.value.supplier_name_raw = data.name;
  newSupplierDraft.value.open = false;
}

// ---------------------------------------------------------------- 자재

function openNewMaterial(idx) {
  newMaterialDrafts.value[idx] = {
    open: true,
    name: items.value[idx].raw_name || "",
    unit: items.value[idx].unit || "",
  };
}

async function createMaterial(idx) {
  const draft = newMaterialDrafts.value[idx];
  if (!draft?.name?.trim()) {
    error.value = "자재명을 입력하세요.";
    return;
  }
  error.value = "";
  saveMessage.value = "";
  try {
    const { data } = await client.post("/purchases/materials/", {
      name: draft.name.trim(),
      unit: (draft.unit || "").trim(),
    });
    // 목록에 없을 때만 추가
    if (!materials.value.some((m) => m.id === data.id)) {
      materials.value.push(data);
    }
    // select v-model 과 타입 일치 (숫자)
    items.value[idx].material = Number(data.id);
    items.value[idx].material_name = data.name;
    newMaterialDrafts.value[idx].open = false;
    saveMessage.value = `자재 「${data.name}」을(를) 등록하고 이 품목에 연결했습니다. 전표 저장을 눌러 주세요.`;
  } catch (e) {
    const detail = e?.response?.data;
    let msg = "자재 등록에 실패했습니다.";
    if (detail) {
      if (typeof detail === "string") msg = detail;
      else if (detail.detail) msg = String(detail.detail);
      else if (detail.name) msg = `자재명: ${[].concat(detail.name).join(", ")}`;
      else msg = JSON.stringify(detail);
    }
    error.value = msg;
  }
}

// ---------------------------------------------------------------- 저장/확정

async function save() {
  saving.value = true;
  saveMessage.value = "";
  error.value = "";
  try {
    const payload = {
      document_date: purchase.value.document_date || null,
      document_number: purchase.value.document_number,
      supplier: purchase.value.supplier || null,
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
        material: it.material != null && it.material !== "" ? Number(it.material) : null,
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
    saveMessage.value = "확정되었습니다. 같은 거래처·품목명은 다음부터 자동으로 연결됩니다.";
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
      <div v-if="reparsing" class="loading-overlay">
        <div class="loading-box">
          <div class="spinner"></div>
          <p>AI가 명세서를 다시 분석하고 있습니다.<br />잠시만 기다려주세요...</p>
        </div>
      </div>
      <div v-if="reparsing" class="loading-overlay">
        <div class="loading-box">
          <div class="spinner"></div>
          <p>AI가 명세서를 다시 분석하고 있습니다.<br />잠시만 기다려주세요...</p>
        </div>
      </div>
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
      <!-- 등록 미해소 안내 -->
      <div
        v-if="unresolvedItemCount > 0 || (!purchase.supplier && purchase.supplier_name_raw)"
        class="banner warn"
      >
        <template v-if="!purchase.supplier && purchase.supplier_name_raw">
          거래처가 아직 등록되지 않았습니다 —
          아래 공급업체에서 기존 거래처를 고르거나 「새 거래처 등록(수정 가능)」으로 등록하세요.
        </template>
        <template v-if="unresolvedItemCount > 0">
          자재가 연결되지 않은 품목이 {{ unresolvedItemCount }}건 있습니다 —
          확정하면 같은 품목명은 다음부터 자동으로 연결됩니다.
        </template>
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
        <!-- 명세서에서 파싱한 거래처 정보 (제안값) -->
        <div v-if="!purchase.supplier && Object.keys(supplierDraft).some((k) => supplierDraft[k])" class="draft-panel">
          <p class="section-title">명세서 표기 정보 (AI 제안 — 등록 전 확인)</p>
          <dl class="draft-list">
            <div v-for="(label, key) in SUPPLIER_DRAFT_LABELS" :key="key" v-show="supplierDraft[key]">
              <dt>{{ label }}</dt>
              <dd>{{ supplierDraft[key] }}</dd>
            </div>
          </dl>
          <button v-if="!isLocked" class="ghost small" type="button" @click="openNewSupplier">
            새 거래처 등록(수정 가능)
          </button>
        </div>

        <div class="field-row">
          <label>
            <span>공급업체</span>
            <template v-if="!newSupplierDraft.open">
              <div class="map-controls">
                <select
                  v-model="purchase.supplier"
                  :disabled="isLocked"
                  @change="onSupplierChange"
                >
                  <option :value="null">— 미지정 —</option>
                  <optgroup
                    v-if="purchase.supplier_candidates?.length"
                    label="추천 거래처"
                  >
                    <option
                      v-for="c in purchase.supplier_candidates"
                      :key="c.id"
                      :value="c.id"
                    >
                      {{ c.name
                      }}{{ c.matched_by === "bizno"
                        ? " (사업자번호 일치)"
                        : c.matched_by === "alias"
                          ? " (이전 연결)"
                          : ` (${Math.round(c.score * 100)}%)` }}
                      {{ c.business_number ? `[${c.business_number}]` : "" }}
                    </option>
                  </optgroup>
                  <optgroup label="전체 거래처">
                    <option v-for="s in suppliers" :key="s.id" :value="s.id">
                      {{ s.name }}{{ s.business_number ? ` [${s.business_number}]` : "" }}
                    </option>
                  </optgroup>
                </select>
              </div>
            </template>
            <template v-else>
              <!-- 새 거래처 등록 폼: 파싱값이 채워져 있고, 사람이 확인/수정 후 등록 -->
              <div class="supplier-create">
                <div class="map-controls">
                  <input v-model="newSupplierDraft.name" type="text" placeholder="거래처명 *" />
                  <input v-model="newSupplierDraft.business_number" type="text" placeholder="사업자번호" />
                  <input v-model="newSupplierDraft.representative" type="text" placeholder="대표자" />
                </div>
                <div class="map-controls">
                  <input v-model="newSupplierDraft.phone" type="text" placeholder="전화번호" />
                  <input v-model="newSupplierDraft.fax" type="text" placeholder="팩스" />
                  <input v-model="newSupplierDraft.email" type="text" placeholder="이메일" />
                </div>
                <div class="map-controls">
                  <input v-model="newSupplierDraft.address" type="text" placeholder="사업장 주소" />
                  <button class="link" type="button" @click="createSupplier">등록</button>
                  <button class="link danger" type="button" @click="newSupplierDraft.open = false">취소</button>
                </div>
              </div>
            </template>
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
              <span class="head-tags">
                <span v-if="!it.material" class="tag-unmapped">자재 미연결</span>
                <button
                  v-if="!isLocked"
                  class="link danger"
                  type="button"
                  @click="removeRow(idx)"
                >
                  삭제
                </button>
              </span>
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
                      <optgroup
                        v-if="it.material_candidates?.length"
                        label="추천 자재"
                      >
                        <option
                          v-for="c in it.material_candidates"
                          :key="c.id"
                          :value="c.id"
                        >
                          {{ c.name
                          }}{{ c.matched_by === "alias"
                            ? " (이전 연결)"
                            : ` (${Math.round(c.score * 100)}%)` }}
                        </option>
                      </optgroup>
                      <optgroup label="전체 자재">
                        <option v-for="m in materials" :key="m.id" :value="m.id">
                          {{ m.name }}
                        </option>
                      </optgroup>
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
                      placeholder="자재명 *"
                    />
                    <input
                      v-model="newMaterialDrafts[idx].unit"
                      type="text"
                      placeholder="단위"
                      class="unit-input"
                    />
                    <button class="link" type="button" @click="createMaterial(idx)">등록</button>
                    <button
                      class="link"
                      type="button"
                      @click="newMaterialDrafts[idx].open = false"
                    >
                      취소
                    </button>
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

.banner.warn {
  background: var(--warning-bg);
  color: var(--warning);
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

.head-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag-unmapped {
  font-size: 11px;
  font-weight: 700;
  color: var(--warning);
  background: var(--warning-bg);
  border-radius: 999px;
  padding: 2px 8px;
}

.hint {
  font-size: 11px;
  color: var(--muted);
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

.map-controls .unit-input {
  flex: 0 0 56px;
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


<style scoped>
.page { max-width: 1280px; padding: 32px 32px 64px; }
.topbar { margin-bottom: 22px; }
h1 { font-size: 28px; font-weight: 700; letter-spacing: -.03em; }
.ghost, .preview-open { border-radius: var(--radius-sm); border-color: var(--rule); background: #fff; color: var(--ink-soft); }
.ghost:hover { border-color: #93c5fd; color: var(--ledger); background: #f8fbff; }
.danger-btn { color: var(--stamp); }
.banner { border-radius: var(--radius-md); padding: 12px 14px; }
.banner.error { border: 1px solid #fecaca; background: var(--stamp-bg); color: var(--stamp); }
.banner.ok { border: 1px solid #bbf7d0; background: var(--success-bg); color: var(--success); }
.banner.warn { border: 1px solid #fde68a; background: var(--warning-bg); color: var(--warning); }
.preview-block, .form, .preview-body, .item-card {
  border: 1px solid var(--rule);
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: var(--shadow-card);
}
.preview-block, .form { padding: 22px; margin-bottom: 20px; }
.preview-head { padding-bottom: 14px; border-bottom: 1px solid var(--rule); }
.section-title { color: var(--ink); font-size: 15px; font-weight: 700; }
.preview-body { box-shadow: none; border-radius: var(--radius-md); background: #f8fafc; padding: 14px; }
.field-row, .row { gap: 16px; }
label span { color: var(--muted); font-size: 12px; font-weight: 600; }
input, select, textarea { border: 1px solid var(--rule); border-radius: var(--radius-sm); background: #fff; color: var(--ink); padding: 10px 11px; }
input:focus, select:focus, textarea:focus { border-color: #60a5fa; box-shadow: 0 0 0 3px rgba(96,165,250,.14); outline: none; }
input:disabled, select:disabled { background: #f8fafc; color: var(--muted); }
.item-card { box-shadow: none; border-radius: var(--radius-md); padding: 16px; }
.item-card + .item-card { margin-top: 12px; }
.item-card-head { color: var(--muted); }
.item-idx { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 999px; background: var(--ledger-bg); color: var(--ledger); font-size: 12px; font-weight: 700; }
.tag-unmapped { background: var(--warning-bg); color: var(--warning); }
.link { color: var(--ledger); }
.link.danger { color: var(--stamp); }
@media (max-width: 720px) {
  .page { padding: 22px 16px 48px; }
  .topbar { align-items: flex-start; gap: 12px; }
  h1 { font-size: 23px; }
  .preview-block, .form { padding: 16px; border-radius: var(--radius-md); }
  .field-row, .row { gap: 10px; }
}
</style>


<style scoped>
/* 명세서 표기 정보 패널 + 거래처 생성 폼 */
.draft-panel {
  border: 1px dashed var(--rule-strong);
  border-radius: var(--radius-md);
  background: #fffbeb;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.draft-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 24px;
  margin: 0 0 10px;
}
.draft-list div {
  display: flex;
  gap: 8px;
  font-size: 12px;
}
.draft-list dt {
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
}
.draft-list dd {
  margin: 0;
  color: var(--ink);
}
.supplier-create {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-box {
  background: #fff;
  padding: 32px;
  border-radius: var(--radius-lg);
  text-align: center;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.loading-box .spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f1f5f9;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

.loading-box p {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--ink);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
