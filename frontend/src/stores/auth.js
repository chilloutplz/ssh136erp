import { reactive } from "vue";
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const STORAGE_KEY = "ssh136erp.tokens";

export const authState = reactive({
  isAuthenticated: !!localStorage.getItem(STORAGE_KEY),
});

let refreshing = null;

export function getTokens() {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : {};
}

export function setTokens(tokens) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  authState.isAuthenticated = true;
}

export function clearTokens() {
  localStorage.removeItem(STORAGE_KEY);
  authState.isAuthenticated = false;
}

function isExpiredOrExpiring(token, marginSeconds = 30) {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return !payload.exp || payload.exp <= Math.floor(Date.now() / 1000) + marginSeconds;
  } catch {
    return true;
  }
}

export function accessTokenNeedsRefresh(token) {
  return isExpiredOrExpiring(token);
}

export async function refreshAccessToken() {
  const { refresh } = getTokens();
  if (!refresh) throw new Error("refresh token이 없습니다.");
  if (!refreshing) {
    refreshing = axios
      .post(`${API_BASE_URL}/auth/token/refresh/`, { refresh })
      .then(({ data }) => {
        setTokens({ access: data.access, refresh });
        return data.access;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export async function login(username, password) {
  const { data } = await axios.post(`${API_BASE_URL}/auth/token/`, {
    username,
    password,
  });
  setTokens({ access: data.access, refresh: data.refresh });
}

export function logout() {
  clearTokens();
}
