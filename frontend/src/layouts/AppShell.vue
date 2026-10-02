<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import client from "../api/client";
import { authState, logout } from "../stores/auth";

const router = useRouter();
const route = useRoute();
const sidebarOpen = ref(false);

const navGroups = [
  {
    key: "sales",
    label: "매출",
    items: [
      { name: "sales-daily", label: "일일매출", path: "/sales" },
      { name: "sales-period", label: "기간매출", path: "/sales/period" },
    ],
  },
  {
    key: "purchases",
    label: "매입",
    items: [
      { name: "purchases", label: "자재매입", path: "/purchases" },
    ],
  },
];

/** 제품메뉴얼 (외부 링크) */
const manuals = ref([]);
const manualsLoading = ref(false);
const manualsError = ref("");
const showManualForm = ref(false);
const manualForm = ref({ product_name: "", manual_url: "" });
const manualSaving = ref(false);
const manualFormError = ref("");

async function loadManuals() {
  manualsLoading.value = true;
  manualsError.value = "";
  try {
    const { data } = await client.get("/product-manuals/");
    manuals.value = Array.isArray(data) ? data : [];
  } catch (e) {
    manualsError.value = "메뉴얼 목록을 불러오지 못했습니다.";
    manuals.value = [];
  } finally {
    manualsLoading.value = false;
  }
}

function openManual(m) {
  if (!m?.manual_url) return;
  window.open(m.manual_url, "_blank", "noopener,noreferrer");
  closeSidebar();
}

function openManualForm() {
  manualForm.value = { product_name: "", manual_url: "https://" };
  manualFormError.value = "";
  showManualForm.value = true;
}

function closeManualForm() {
  showManualForm.value = false;
  manualFormError.value = "";
}

async function saveManual() {
  manualFormError.value = "";
  const name = manualForm.value.product_name?.trim();
  const url = manualForm.value.manual_url?.trim();
  if (!name) {
    manualFormError.value = "제품 이름을 입력하세요.";
    return;
  }
  if (!url || !url.startsWith("https://")) {
    manualFormError.value = "링크는 https:// 로 시작해야 합니다.";
    return;
  }
  manualSaving.value = true;
  try {
    const { data } = await client.post("/product-manuals/", {
      product_name: name,
      manual_url: url,
      sort_order: (manuals.value.length + 1) * 10,
    });
    manuals.value = [...manuals.value, data].sort(
      (a, b) => (a.sort_order - b.sort_order) || (a.id - b.id)
    );
    closeManualForm();
  } catch (e) {
    const d = e?.response?.data;
    if (d?.product_name) manualFormError.value = [].concat(d.product_name).join(" ");
    else if (d?.manual_url) manualFormError.value = [].concat(d.manual_url).join(" ");
    else if (d?.detail) manualFormError.value = String(d.detail);
    else manualFormError.value = "저장에 실패했습니다.";
  } finally {
    manualSaving.value = false;
  }
}

async function deleteManual(m) {
  if (!m?.id) return;
  if (!window.confirm(`「${m.product_name}」 메뉴얼을 삭제할까요?`)) return;
  try {
    await client.delete(`/product-manuals/${m.id}/`);
    manuals.value = manuals.value.filter((x) => x.id !== m.id);
  } catch (e) {
    window.alert("삭제에 실패했습니다.");
  }
}

const activeNames = computed(() => {
  const n = route.name;
  if (n === "purchase-detail") return new Set(["purchases"]);
  return new Set([n]);
});

function isActive(name) {
  return activeNames.value.has(name);
}

function handleLogout() {
  logout();
  router.push({ name: "login" });
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value;
}

function closeSidebar() {
  sidebarOpen.value = false;
}

watch(() => route.fullPath, closeSidebar);
onMounted(loadManuals);
</script>

<template>
  <div class="shell">
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="closeSidebar"></div>

    <aside class="sidebar" :class="{ open: sidebarOpen }" @click.stop>
      <div class="brand">
        <div class="brand-row">
          <img class="brand-logo" src="/icons/icon-96.png" width="40" height="40" alt="" />
          <div class="brand-text">
            <p class="eyebrow mono">ERP HOOK</p>
            <p class="brand-sub">숙성회136</p>
          </div>
        </div>
        <div class="account-box">
          <p class="account-label">로그인 계정</p>
          <p class="account-name" :title="authState.username">{{ authState.username }}</p>
          <button class="logout" type="button" @click="handleLogout">로그아웃</button>
        </div>
      </div>

      <nav class="nav">
        <div v-for="group in navGroups" :key="group.key" class="nav-group" :class="'g-' + group.key">
          <p class="nav-group-label">{{ group.label }}</p>
          <router-link
            v-for="item in group.items"
            :key="item.name"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item.name) }"
          >
            {{ item.label }}
          </router-link>
        </div>

        <div class="nav-group manuals-group">
          <div class="nav-group-head">
            <p class="nav-group-label manuals-label">제품메뉴얼</p>
            <button
              class="manual-add"
              type="button"
              title="메뉴얼 추가"
              aria-label="메뉴얼 추가"
              @click="openManualForm"
            >
              +
            </button>
          </div>

          <p v-if="manualsLoading" class="manual-empty">불러오는 중...</p>
          <p v-else-if="manualsError" class="manual-empty">{{ manualsError }}</p>
          <p v-else-if="!manuals.length" class="manual-empty">등록된 메뉴얼이 없습니다</p>
          <div v-else class="manual-list">
            <div v-for="m in manuals" :key="m.id" class="manual-row">
              <button
                class="nav-item manual-link"
                type="button"
                :title="m.manual_url"
                @click="openManual(m)"
              >
                {{ m.product_name }}
              </button>
              <button
                class="manual-del"
                type="button"
                title="삭제"
                aria-label="삭제"
                @click.stop="deleteManual(m)"
              >
                ×
              </button>
            </div>
          </div>
        </div>
      </nav>

      <!-- 메뉴얼 등록 팝업 -->
      <div
        v-if="showManualForm"
        class="manual-modal-overlay"
        @click.self="closeManualForm"
      >
        <div class="manual-modal" role="dialog" aria-label="메뉴얼 추가">
          <h3>메뉴얼 추가</h3>
          <label>
            <span>제품 이름</span>
            <input
              v-model="manualForm.product_name"
              type="text"
              placeholder="예: 전어 미나리 가이드"
              maxlength="100"
            />
          </label>
          <label>
            <span>링크 (https://)</span>
            <input
              v-model="manualForm.manual_url"
              type="url"
              placeholder="https://..."
            />
          </label>
          <p v-if="manualFormError" class="manual-form-error">{{ manualFormError }}</p>
          <div class="manual-modal-actions">
            <button class="ghost" type="button" @click="closeManualForm">취소</button>
            <button
              class="primary"
              type="button"
              :disabled="manualSaving"
              @click="saveManual"
            >
              {{ manualSaving ? "저장 중..." : "저장" }}
            </button>
          </div>
        </div>
      </div>
    </aside>

    <main class="content">
      <header class="mobile-header">
        <button
          class="menu-toggle"
          type="button"
          :aria-expanded="sidebarOpen"
          aria-label="메뉴 열기"
          @click="toggleSidebar"
        >
          <span></span><span></span><span></span>
        </button>
        <div class="mobile-brand">
          <img class="mobile-logo" src="/icons/icon-72.png" width="28" height="28" alt="" />
          <div>
            <strong>숙성회136</strong>
            <small>ERP HOOK</small>
          </div>
        </div>
      </header>
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  min-height: 100%;
}

.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  padding: 24px 0;
}

.brand {
  padding: 0 20px 20px;
  border-bottom: 1px solid var(--paper-dim);
  margin-bottom: 12px;
}

.eyebrow {
  margin: 0;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.brand-sub {
  margin: 4px 0 0;
  font-size: 15px;
  font-weight: 600;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-logo {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  object-fit: cover;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.brand-text {
  min-width: 0;
}

.brand-text .brand-sub {
  margin: 2px 0 0;
}

.mobile-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.mobile-logo {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  object-fit: cover;
  flex-shrink: 0;
}


.nav {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.nav-group {
  margin-bottom: 12px;
}

.nav-group-label {
  margin: 0 0 4px;
  padding: 4px 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--muted);
  text-transform: none;
}

.nav-item {
  display: block;
  padding: 10px 20px 10px 28px;
  font-size: 14px;
  color: var(--ink-soft);
  text-decoration: none;
  border-left: 3px solid transparent;
}

.nav-item:hover {
  background: var(--paper-dim);
}

.nav-item.active {
  color: var(--ink);
  font-weight: 600;
  border-left-color: var(--ledger);
  background: var(--paper-dim);
}

.account-box {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--paper-dim);
}

.account-label {
  margin: 0 0 4px;
  color: var(--muted);
  font-size: 11px;
}

.account-name {
  margin: 0;
  overflow: hidden;
  color: var(--ink-soft);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout {
  width: 100%;
  margin: 10px 0 0;
  padding: 8px 0;
  background: none;
  border: 1px solid var(--rule);
  color: var(--muted);
  font-size: 13px;
  cursor: pointer;
}

.logout:hover {
  border-color: var(--ink-soft);
  color: var(--ink-soft);
}

.content {
  flex: 1;
  min-width: 0;
  overflow-x: auto;
}

.mobile-header {
  display: none;
}

@media (max-width: 640px) {
  .shell {
    display: block;
    min-height: 100vh;
  }

  .mobile-header {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 12px;
    height: 62px;
    padding: 0 16px;
    background: #fff;
    border-bottom: 1px solid var(--rule);
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  }

  .mobile-header strong {
    display: block;
    color: var(--ink);
    font-size: 15px;
  }

  .mobile-header small {
    display: block;
    margin-top: 2px;
    color: var(--muted);
    font-size: 10px;
    letter-spacing: 0.08em;
  }

  .menu-toggle {
    display: inline-flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
    width: 36px;
    height: 36px;
    padding: 8px;
    border: 1px solid var(--rule);
    border-radius: var(--radius-sm);
    background: #fff;
    cursor: pointer;
  }

  .menu-toggle span {
    display: block;
    width: 18px;
    height: 2px;
    border-radius: 2px;
    background: var(--ink-soft);
  }

  .sidebar-overlay {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: rgba(15, 23, 42, 0.48);
    backdrop-filter: blur(2px);
  }

  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 50;
    display: flex;
    width: min(82vw, 280px);
    height: 100vh;
    padding: 24px 14px 18px;
    transform: translateX(-105%);
    transition: transform 0.22s ease;
    box-shadow: 12px 0 30px rgba(15, 23, 42, 0.16);
    overflow-y: auto;
    flex-direction: column;
    align-items: stretch;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .brand {
    padding: 4px 12px 20px;
    margin-bottom: 20px;
    white-space: normal;
  }

  .nav {
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .nav-item {
    white-space: normal;
    padding: 10px 12px 10px 16px;
  }

  .nav-group-label {
    padding: 4px 12px;
  }

  .account-box {
    display: block;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .account-label {
    display: block;
  }

  .account-name {
    max-width: none;
  }

  .logout {
    width: 100%;
    margin-top: 10px;
  }

  .content {
    width: 100%;
    min-height: 100vh;
    overflow-x: hidden;
  }
}
</style>

<style scoped>
.shell {
  min-height: 100vh;
  background: var(--paper);
}
.sidebar {
  width: 248px;
  background: var(--sidebar);
  border-right: 0;
  padding: 24px 14px 18px;
  color: #fff;
}
.brand {
  padding: 4px 12px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 20px;
}
.eyebrow {
  color: #93c5fd;
  letter-spacing: 0.12em;
  font-weight: 700;
}
.brand-sub {
  color: #f8fafc;
  font-size: 17px;
}
.account-box {
  border-top-color: rgba(255, 255, 255, 0.08);
}
.account-label {
  color: var(--sidebar-muted);
}
.account-name {
  color: #e5e7eb;
}
.logout {
  border: 0;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.07);
  color: #cbd5e1;
  text-align: left;
  padding: 9px 11px;
}
.logout:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}
.nav {
  gap: 4px;
}
.nav-group-label {
  color: rgba(148, 163, 184, 0.95);
  padding: 6px 12px 4px;
}
.nav-item {
  border-left: 0;
  border-radius: var(--radius-sm);
  padding: 10px 12px 10px 16px;
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 500;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}
.nav-item.active {
  border-left: 0;
  color: #fff;
  background: #2563eb;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.22);
}
.content {
  background: var(--paper);
}
@media (max-width: 640px) {
  .sidebar {
    width: min(82vw, 280px);
    padding: 24px 14px 18px;
    background: var(--sidebar);
  }
  .brand {
    padding: 4px 12px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 20px;
  }
  .brand-sub {
    font-size: 17px;
  }
}

.nav-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-right: 8px;
}

/* 그룹 라벨 색 구분 */
.g-sales > .nav-group-label {
  color: #93c5fd;
}
.g-purchases > .nav-group-label {
  color: #6ee7b7;
}
.manuals-group > .nav-group-head .nav-group-label {
  color: #c4b5fd;
}

.manuals-label {
  margin: 0;
  flex: 1;
}

.manual-add {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}

.manual-add:hover {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}

.manual-empty {
  margin: 0;
  padding: 8px 16px 12px;
  font-size: 12px;
  color: rgba(148, 163, 184, 0.95);
  line-height: 1.4;
}

.manual-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.manual-row {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* 일일매출 nav-item 과 동일 톤 */
.manual-link.nav-item {
  flex: 1;
  min-width: 0;
  display: block;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  padding: 10px 12px 10px 16px;
  margin: 0;
  cursor: pointer;
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.35;
  color: #cbd5e1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  -webkit-appearance: none;
  appearance: none;
}

.manual-link.nav-item:hover {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}

.manual-del {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: rgba(148, 163, 184, 0.8);
  font-size: 16px;
  cursor: pointer;
  opacity: 0.6;
}

.manual-del:hover {
  opacity: 1;
  color: #fca5a5;
  background: rgba(255, 255, 255, 0.06);
}

.manual-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(15, 23, 42, 0.5);
}

.manual-modal {
  width: 100%;
  max-width: 360px;
  padding: 20px 18px;
  border-radius: 12px;
  background: #fff;
  color: var(--ink, #0f172a);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.2);
}

.manual-modal h3 {
  margin: 0 0 14px;
  font-size: 16px;
}

.manual-modal label {
  display: block;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--ink-soft, #334155);
}

.manual-modal label span {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
}

.manual-modal input {
  width: 100%;
  box-sizing: border-box;
  padding: 9px 10px;
  border: 1px solid var(--rule, #e2e8f0);
  border-radius: 8px;
  font: inherit;
  font-size: 14px;
}

.manual-form-error {
  margin: 0 0 10px;
  font-size: 13px;
  color: #dc2626;
}

.manual-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.manual-modal-actions .ghost {
  padding: 8px 12px;
  border: 1px solid var(--rule, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}

.manual-modal-actions .primary {
  padding: 8px 14px;
  border: 0;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.manual-modal-actions .primary:disabled {
  opacity: 0.6;
  cursor: default;
}

</style>
