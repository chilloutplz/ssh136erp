import axios from "axios";
import {
  getTokens,
  clearTokens,
  accessTokenNeedsRefresh,
  refreshAccessToken,
} from "../stores/auth";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const client = axios.create({ baseURL: API_BASE_URL });

client.interceptors.request.use(async (config) => {
  let { access } = getTokens();
  if (accessTokenNeedsRefresh(access)) {
    try {
      access = await refreshAccessToken();
    } catch {
      clearTokens();
      window.location.href = "/login";
      return Promise.reject(new Error("로그인이 만료되었습니다."));
    }
  }
  if (access) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;

    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      try {
        const access = await refreshAccessToken();
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${access}`;
        return client(original);
      } catch (e) {
        clearTokens();
        window.location.href = "/login";
        return Promise.reject(e);
      }
    }
    return Promise.reject(error);
  }
);

export default client;
