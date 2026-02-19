<template>
  <div class="home">
    <h1>YOLO Dataset Factory</h1>
    <p>이미지 수집 → 자동 라벨링 → 수정/보완으로 YOLO 학습용 데이터셋을 만듭니다.</p>
    <p>
      <router-link to="/labeling" class="cta">라벨링 시작</router-link>
      (데이터셋 선택 · 자동 라벨 · 오픈소스 에디터로 수정)
    </p>
    <p class="muted">API: <code>{{ apiBase }}</code> · <a :href="apiDocs" target="_blank" rel="noopener">문서</a></p>
  </div>
</template>

<script setup>
const apiBase = import.meta.env.VITE_API_BASE ?? 'http://localhost:8081'
const apiDocs = `${apiBase}/docs`
</script>

<style scoped>
.home { text-align: center; padding: 2rem 0; }
.cta { display: inline-block; padding: 0.5rem 1rem; background: #1a1a2e; color: #fff; border-radius: 6px; text-decoration: none; }
.cta:hover { opacity: 0.9; }
.muted { color: #666; font-size: 0.9rem; }
code { background: #eee; padding: 0.2em 0.4em; border-radius: 4px; }
</style>
