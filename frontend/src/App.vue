<template>
  <div class="app">
    <header class="header">
      <router-link to="/" class="logo">YOLO Dataset Factory</router-link>
      <nav>
        <router-link to="/">홈</router-link>
        <router-link to="/labeling">라벨링</router-link>
        <a :href="apiDocs" target="_blank" rel="noopener">API Docs</a>
      </nav>
    </header>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
const apiBase = import.meta.env.VITE_API_BASE ?? (typeof location !== 'undefined' ? `${location.origin.replace(/:\d+$/, ':8081')}` : 'http://localhost:8081')
const apiDocs = `${apiBase}/docs`
</script>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; }
.app { min-height: 100vh; display: flex; flex-direction: column; }
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
  background: #1a1a2e;
  color: #eee;
}
.header a { color: #eee; text-decoration: none; }
.header a:hover { text-decoration: underline; }
.header .logo { font-weight: 700; }
.header nav { display: flex; gap: 1.25rem; }
.main { flex: 1; padding: 1.5rem; max-width: 960px; margin: 0 auto; width: 100%; }
</style>
