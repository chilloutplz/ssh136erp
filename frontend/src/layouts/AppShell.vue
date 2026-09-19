<script setup>
import { useRouter } from "vue-router";
import { authState, logout } from "../stores/auth";

const router = useRouter();

const navItems = [
  { name: "sales", label: "매출 정산", path: "/sales" },
  { name: "purchases", label: "자재매입", path: "/purchases" },
];

function handleLogout() {
  logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <p class="eyebrow mono">ssh136erp</p>
        <p class="brand-sub">숙성회136</p>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.name"
          :to="item.path"
          class="nav-item"
          active-class="active"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="account-box">
        <p class="account-label">로그인 계정</p>
        <p class="account-name" :title="authState.username">{{ authState.username }}</p>
        <button class="logout" type="button" @click="handleLogout">로그아웃</button>
      </div>
    </aside>

    <main class="content">
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

.nav {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.nav-item {
  padding: 12px 20px;
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
  margin: 12px 20px 0;
  padding-top: 14px;
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

@media (max-width: 640px) {
  .shell {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    flex-direction: row;
    align-items: center;
    padding: 12px 16px;
    gap: 16px;
    overflow-x: auto;
  }

  .brand {
    padding: 0;
    border-bottom: none;
    margin-bottom: 0;
    white-space: nowrap;
  }

  .nav {
    flex-direction: row;
    flex: none;
  }

  .nav-item {
    border-left: none;
    border-bottom: 3px solid transparent;
    white-space: nowrap;
    padding: 8px 12px;
  }

  .nav-item.active {
    border-left-color: transparent;
    border-bottom-color: var(--ledger);
  }

  .account-box {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 0 auto;
    padding: 0;
    border-top: none;
  }

  .account-label {
    display: none;
  }

  .account-name {
    max-width: 120px;
  }

  .logout {
    width: auto;
    margin: 0;
    white-space: nowrap;
  }
}
</style>
