import { reactive } from "vue";
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const STORAGE_KEY = "ssh136erp.tokens";

export const authState = reactive({
  isAuthenticated: !!localStorage.getItem(STORAGE_KEY),
});

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
