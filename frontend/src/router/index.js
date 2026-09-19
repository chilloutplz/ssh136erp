import { createRouter, createWebHistory } from "vue-router";
import { authState } from "../stores/auth";
import LoginView from "../views/LoginView.vue";
import DashboardView from "../views/DashboardView.vue";
import PurchaseListView from "../views/PurchaseListView.vue";
import PurchaseDetailView from "../views/PurchaseDetailView.vue";
import AppShell from "../layouts/AppShell.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    {
      path: "/",
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/sales" },
        { path: "sales", name: "sales", component: DashboardView },
        { path: "purchases", name: "purchases", component: PurchaseListView },
        { path: "purchases/:id", name: "purchase-detail", component: PurchaseDetailView },
      ],
    },
  ],
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !authState.isAuthenticated) {
    return { name: "login" };
  }
  if (to.name === "login" && authState.isAuthenticated) {
    return { name: "sales" };
  }
});

export default router;
