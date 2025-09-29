import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { Quasar, Notify, Loading, Dialog } from 'quasar'

// Import icon libraries
import '@quasar/extras/material-icons/material-icons.css'
import '@quasar/extras/fontawesome-v6/fontawesome-v6.css'

// Import Quasar css
import 'quasar/src/css/index.sass'

// Assumes your root component is App.vue
// and placed in same folder as main.js
import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)

// Install Pinia state management
app.use(createPinia())

// Install Vue Router
app.use(router)

// Install Quasar with plugins
app.use(Quasar, {
  plugins: {
    Notify,
    Loading,
    Dialog
  },
  config: {
    notify: {
      position: 'top-right',
      timeout: 5000,
      textColor: 'white',
      actions: [{ icon: 'close', color: 'white' }]
    },
    loading: {
      spinnerColor: 'primary',
      spinnerSize: 40,
      backgroundColor: 'rgba(255, 255, 255, 0.8)'
    }
  }
})

// Global error handler
app.config.errorHandler = (err: any, vm: any, info: string) => {
  console.error('Global error:', err, info)
  Notify.create({
    type: 'negative',
    message: '애플리케이션 오류가 발생했습니다.',
    caption: err.message || '알 수 없는 오류'
  })
}

app.mount('#app')