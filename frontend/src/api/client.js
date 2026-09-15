import axios from "axios";
import { getTokens, setTokens, clearTokens } from "../stores/auth";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const client = axios.create({ baseURL: API_BASE_URL });

client.interceptors.request.use((config) => {
  const { access } = getTokens();
  if (access) {
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

let refreshing = null;

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const { refresh } = getTokens();

    if (error.response?.status === 401 && refresh && !original._retried) {
      original._retried = true;
      try {
        refreshing =
          refreshing ||
          axios.post(`${API_BASE_URL}/auth/token/refresh/`, { refresh });
        const { data } = await refreshing;
        refreshing = null;
        setTokens({ access: data.access, refresh });
        original.headers.Authorization = `Bearer ${data.access}`;
        return client(original);
      } catch (e) {
        refreshing = null;
        clearTokens();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default client;
