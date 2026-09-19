<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { login } from "../stores/auth";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function handleSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await login(username.value, password.value);
    router.push({ name: "sales" });
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
      <p class="eyebrow">ssh136erp</p>
      <h1>매출 정산 화면</h1>
      <p class="sub">관리자 계정으로 로그인하세요</p>

      <hr class="hairline" />

      <label>
        <span>아이디</span>
        <input v-model="username" type="text" autocomplete="username" required />
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
}

.login-slip {
  width: 100%;
  max-width: 340px;
  background: #fff;
  border: 1px solid var(--rule);
  padding: 32px 28px;
  box-shadow: 0 1px 0 var(--rule-strong);
}

.eyebrow {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--muted);
}

h1 {
  margin: 6px 0 4px;
  font-size: 22px;
  font-weight: 600;
}

.sub {
  margin: 0 0 18px;
  color: var(--muted);
  font-size: 14px;
}

.hairline {
  margin: 0 0 20px;
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
  background: var(--paper);
  font-size: 14px;
  color: var(--ink);
}

input:focus {
  border-color: var(--ledger);
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
