<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { login } from "../stores/auth";

const router = useRouter();
const username = ref("");
const password = ref("");
const usernameInput = ref(null);
const error = ref("");
const loading = ref(false);

onMounted(() => {
  usernameInput.value?.focus();
});

async function handleSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await login(username.value, password.value);
    router.push({ name: "sales-daily" });
  } catch (e) {
    error.value = "아이디 또는 비밀번호가 올바르지 않습니다.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <form class="login-slip" @submit.prevent="handleSubmit">
      <div class="logo-wrap">
        <img
          class="logo"
          src="/icons/icon-192.png"
          width="72"
          height="72"
          alt="ERP HOOK"
        />
      </div>
      <h1 class="brand-title">ERP HOOK</h1>

      <hr class="hairline" />

      <label>
        <span>아이디</span>
        <input
          ref="usernameInput"
          v-model="username"
          type="text"
          autocomplete="username"
          required
        />
      </label>
      <label>
        <span>비밀번호</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit" :disabled="loading">
        {{ loading ? "확인 중..." : "로그인" }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(ellipse at top, rgba(37, 99, 235, 0.08), transparent 55%),
    var(--paper, #f8fafc);
}

.login-slip {
  width: 100%;
  max-width: 340px;
  background: #fff;
  border: 1px solid var(--rule);
  border-radius: 16px;
  padding: 32px 28px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.logo-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 14px;
}

.logo {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  object-fit: cover;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
}

.brand-title {
  margin: 0 0 18px;
  text-align: center;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ink);
}

.hairline {
  margin: 0 0 20px;
  border: 0;
  border-top: 1px solid var(--rule);
}

label {
  display: block;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--ink-soft);
}

label span {
  display: block;
  margin-bottom: 6px;
}

input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--paper);
  font-size: 14px;
  color: var(--ink);
  box-sizing: border-box;
}

input:focus {
  border-color: var(--ledger);
  outline: none;
}

.error {
  color: var(--stamp);
  font-size: 13px;
  margin: -4px 0 16px;
}

button {
  width: 100%;
  padding: 11px 0;
  background: var(--ink);
  color: var(--paper);
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.02em;
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}

button:hover:not(:disabled) {
  background: var(--ink-soft);
}
</style>
