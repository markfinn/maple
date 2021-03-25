<template>
  <img alt="Maple logo" src="./assets/large_maple-leaf.png" class="w-25 p-3 h-25" />
  <Maple apiurl="https://maple.bluesparc.net:8443/api" />
</template>

<script>
import Maple from './components/Maple.vue'

export default {
  name: 'App',
  components: {
    Maple
  }
}
</script>

