import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus, { ElConfigProvider } from 'element-plus'
import ja from 'element-plus/es/locale/lang/ja'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp({
  render: () => h(ElConfigProvider, { locale: ja }, () => h(App)),
})

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: ja })

app.mount('#app')
