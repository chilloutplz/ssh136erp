import { reactive } from "vue";
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const STORAGE_KEY = "ssh136erp.tokens";
const ACCOUNT_KEY = "ssh136erp.account";

export const authState = reactive({
  isAuthenticated: !!localStorage.getItem(STORAGE_KEY),
  username: localStorage.getItem(ACCOUNT_KEY) || "관리자",
});

let refreshing = null;

export function getTokens() {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : {};
}

export function setTokens(tokens) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  if (tokens.username) {
    localStorage.setItem(ACCOUNT_KEY, tokens.username);
    authState.username = tokens.username;
  }
  authState.isAuthenticated = true;
}

export function clearTokens() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(ACCOUNT_KEY);
  authState.isAuthenticated = false;
  authState.username = "관리자";
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
        setTokens({
          access: data.access,
          refresh,
          username: getTokens().username,
        });
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
  setTokens({ access: data.access, refresh: data.refresh, username });
}

export function logout() {
  clearTokens();
}
