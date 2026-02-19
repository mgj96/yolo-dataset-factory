import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('../views/Home.vue'), meta: { title: '홈' } },
  { path: '/labeling', name: 'Labeling', component: () => import('../views/Labeling.vue'), meta: { title: '라벨링' } },
  { path: '/labeling/edit/:datasetId/:filename', name: 'LabelEdit', component: () => import('../views/LabelEdit.vue'), meta: { title: '라벨 편집' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · YOLO Dataset Factory` : 'YOLO Dataset Factory'
})

export default router
