import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

// 自绘 UI 组件库
import { installUI } from './components/ui'

// 全局样式
import './assets/styles/main.css'
import './assets/styles/theme.css'
import './assets/styles/scrollbar.css'
import './assets/styles/transitions.css'

const app = createApp(App)

// 状态管理
app.use(createPinia())

// 路由
app.use(router)

// 自绘 UI 组件库
installUI(app)

app.mount('#app')
