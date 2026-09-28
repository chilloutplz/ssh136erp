<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
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
        <div v-for="group in navGroups" :key="group.key" class="nav-group">
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
      </nav>
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
</style>
