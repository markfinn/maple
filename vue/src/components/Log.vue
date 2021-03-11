<template>
  <p v-for="line in log">
    {{ line }}
  </p>
</template>

<script>
import {onMounted, ref} from 'vue'

export default {
  name: 'Log',
  setup() {
    const log = ref([]);
    onMounted(async () => {
      var es = new EventSource('https://maple.bluesparc.net:8443/api/log');
      es.onmessage = (event) => {
        log.value.push(event.data);
      }
    });
    return {
      log
    }
  }
}
</script>



