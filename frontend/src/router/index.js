import { createRouter, createWebHistory } from "vue-router";
import { authState } from "../stores/auth";
import LoginView from "../views/LoginView.vue";
import DashboardView from "../views/DashboardView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/login", name: "login", component: LoginView },
    {
      path: "/dashboard",
      name: "dashboard",
      component: DashboardView,
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !authState.isAuthenticated) {
    return { name: "login" };
  }
  if (to.name === "login" && authState.isAuthenticated) {
    return { name: "dashboard" };
  }
});

export default router;
