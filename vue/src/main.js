import { createApp } from 'vue'
import { createRouter,createWebHistory } from 'vue-router'
import App from './App.vue'
import 'bootstrap/dist/css/bootstrap.css';
import './index.css'

import Maple from './components/Maple.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
  { path: '/', component: Maple, props: {apiurl: "https://maple.bluesparc.net:8443/api"} }
  ]
})


createApp(App).use(router).mount('#app')
