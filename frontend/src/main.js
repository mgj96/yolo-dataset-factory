import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import '@annotorious/annotorious/annotorious.css'

createApp(App).use(router).mount('#app')
