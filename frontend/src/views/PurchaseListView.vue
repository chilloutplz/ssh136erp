<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import client from "../api/client";

const router = useRouter();

const purchases = ref([]);
const loading = ref(true);
const error = ref("");
const uploading = ref(false);
const uploadError = ref("");
const fileInput = ref(null);

const STATUS_LABEL = {
  UPLOADED: "업로드중",
  PARSED: "검토대기",
  CONFIRMED: "확정",
  FAILED: "파싱실패",
};

function statusTagClass(status) {
  if (status === "CONFIRMED") return "tag ledger";
  if (status === "FAILED") return "tag stamp";
  return "tag pending";
}

function formatWon(n) {
  return `₩${Number(n || 0).toLocaleString("ko-KR")}`;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/purchases/");
    purchases.value = data;
  } catch (e) {
    error.value = "매입 목록을 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

function triggerUpload() {
  fileInput.value?.click();
}

async function handleFileChange(e) {
  const file = e.target.files?.[0];
  e.target.value = "";
  if (!file) return;

  uploading.value = true;
  uploadError.value = "";
  try {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await client.post("/purchases/upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    router.push({ name: "purchase-detail", params: { id: data.id } });
  } catch (e) {
    uploadError.value = "업로드/파싱에 실패했습니다. 잠시 후 다시 시도해주세요.";
  } finally {
    uploading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <header class="topbar">
      <h1>자재매입</h1>
      <div class="topbar-right">
        <input
          ref="fileInput"
          type="file"
          accept="application/pdf,image/*"
          class="hidden-input"
          @change="handleFileChange"
        />
        <button class="primary" type="button" :disabled="uploading" @click="triggerUpload">
          {{ uploading ? "업로드/파싱 중..." : "거래명세서 업로드" }}
        </button>
      </div>
    </header>

    <div v-if="uploadError" class="banner error">{{ uploadError }}</div>
    <div v-if="error" class="banner error">{{ error }}</div>

    <section class="list-section">
      <div v-if="loading" class="empty">불러오는 중...</div>
      <table v-else-if="purchases.length" class="purchase-table">
        <thead>
          <tr>
            <th>일자</th>
            <th>공급업체</th>
            <th>문서번호</th>
            <th>상태</th>
            <th class="right">합계금액</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in purchases"
            :key="p.id"
            @click="router.push({ name: 'purchase-detail', params: { id: p.id } })"
          >
            <td class="mono">{{ p.document_date || "-" }}</td>
            <td>{{ p.supplier_name || "-" }}</td>
            <td class="mono">{{ p.document_number || "-" }}</td>
            <td><span :class="statusTagClass(p.status)">{{ STATUS_LABEL[p.status] || p.status }}</span></td>
            <td class="right mono">{{ formatWon(p.total_amount) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">아직 등록된 매입 전표가 없습니다. 위 버튼으로 거래명세서를 업로드해보세요.</p>
    </section>
  </div>
</template>

<style scoped>
.page {
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

h1 {
  margin: 0;
  font-size: 24px;
}

.hidden-input {
  display: none;
}

.primary {
  background: var(--ink);
  color: var(--paper);
  border: none;
  padding: 9px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.primary:disabled {
  opacity: 0.6;
  cursor: default;
}

.primary:hover:not(:disabled) {
  background: var(--ink-soft);
}

.banner.error {
  background: var(--stamp-bg);
  color: var(--stamp);
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 20px;
}

.empty {
  color: var(--muted);
  font-size: 14px;
  padding: 24px 0;
}

.purchase-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  background: #fff;
}

.purchase-table th {
  text-align: left;
  font-weight: 500;
  color: var(--muted);
  font-size: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--rule);
}

.purchase-table td {
  padding: 10px;
  border-bottom: 1px solid var(--paper-dim);
}

.purchase-table tbody tr {
  cursor: pointer;
}

.purchase-table tbody tr:hover {
  background: var(--paper-dim);
}

.purchase-table th.right,
.purchase-table td.right {
  text-align: right;
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
</style>
