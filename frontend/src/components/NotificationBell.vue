<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import client from "../api/client";

const open = ref(false);
const loading = ref(false);
const notes = ref([]);
const error = ref("");

const unreadCount = computed(
  () => notes.value.filter((n) => !n.is_read).length
);

async function loadNotes() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/sales/cancels/notes/", {
      params: { unread: 1 },
    });
    notes.value = Array.isArray(data) ? data : [];
  } catch (e) {
    error.value = "알림을 불러오지 못했습니다.";
    notes.value = [];
  } finally {
    loading.value = false;
  }
}

async function markRead(item) {
  if (!item?.id || item.is_read) return;
  try {
    await client.patch(`/sales/cancels/${item.id}/read/`);
    notes.value = notes.value.map((n) =>
      n.id === item.id ? { ...n, is_read: true } : n
    );
  } catch (e) {
    // 실패 시 목록은 유지
  }
}

async function markAllRead() {
  const unread = notes.value.filter((n) => !n.is_read);
  for (const item of unread) {
    await markRead(item);
  }
}

function toggle() {
  open.value = !open.value;
  if (open.value) loadNotes();
}

function close() {
  open.value = false;
}

function onDocClick(e) {
  const root = e.target?.closest?.(".notif-bell-root");
  if (!root) close();
}

function formatTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ko-KR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

onMounted(() => {
  loadNotes();
  document.addEventListener("click", onDocClick);
});

onUnmounted(() => {
  document.removeEventListener("click", onDocClick);
});

defineExpose({ loadNotes });
</script>

<template>
  <div class="notif-bell-root">
    <button
      class="bell-btn"
      type="button"
      :aria-expanded="open"
      aria-label="처리 알림"
      title="처리 알림"
      @click.stop="toggle"
    >
      <span class="bell-icon" aria-hidden="true">🔔</span>
      <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? "99+" : unreadCount }}</span>
    </button>

    <div v-if="open" class="dropdown" role="dialog" aria-label="알림 목록" @click.stop>
      <div class="dropdown-head">
        <strong>처리 알림</strong>
        <button
          v-if="unreadCount > 0"
          class="mark-all"
          type="button"
          @click="markAllRead"
        >
          모두 읽음
        </button>
      </div>

      <p v-if="loading" class="empty">불러오는 중...</p>
      <p v-else-if="error" class="empty error">{{ error }}</p>
      <p v-else-if="!notes.length" class="empty">새 알림 없음</p>
      <ul v-else class="list">
        <li
          v-for="n in notes"
          :key="n.id"
          class="item"
          :class="{ unread: !n.is_read }"
          @click="markRead(n)"
        >
          <p class="note">{{ n.process_note }}</p>
          <p class="meta">
            <span>{{ n.source }} · {{ n.channel_order_no || "-" }}</span>
            <span>{{ formatTime(n.cancelled_at || n.created_at) }}</span>
          </p>
          <p v-if="n.cancel_amount" class="amount">
            취소금액 {{ Number(n.cancel_amount).toLocaleString("ko-KR") }}원
          </p>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.notif-bell-root {
  position: relative;
  display: inline-flex;
}

.bell-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--rule, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.bell-btn:hover {
  background: var(--paper-dim, #f1f5f9);
}

.bell-icon {
  font-size: 16px;
  line-height: 1;
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 9px;
  background: #dc2626;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
}

.dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 90;
  width: min(92vw, 340px);
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--rule, #e2e8f0);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.14);
  color: var(--ink, #0f172a);
}

.dropdown-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--rule, #e2e8f0);
}

.dropdown-head strong {
  font-size: 14px;
}

.mark-all {
  border: 0;
  background: none;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.empty {
  margin: 0;
  padding: 20px 14px;
  font-size: 13px;
  color: var(--muted, #64748b);
  text-align: center;
}

.empty.error {
  color: #dc2626;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.item {
  padding: 12px 14px;
  border-bottom: 1px solid var(--paper-dim, #f1f5f9);
  cursor: pointer;
}

.item:last-child {
  border-bottom: 0;
}

.item:hover {
  background: var(--paper-dim, #f8fafc);
}

.item.unread {
  background: #eff6ff;
}

.note {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin: 0;
  font-size: 11px;
  color: var(--muted, #64748b);
}

.amount {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: #b91c1c;
}

/* 사이드바(다크) 안에서도 벨 버튼이 보이도록 */
.sidebar-variant .bell-btn {
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.08);
}

.sidebar-variant .bell-btn:hover {
  background: rgba(255, 255, 255, 0.16);
}
</style>
