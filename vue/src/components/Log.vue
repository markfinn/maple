<template>
  <p v-for="line in log">
    {{ line }}
  </p>
</template>

<script>
import {onMounted, ref} from 'vue'

export default {
  name: 'Log',
  props{
    apiurl: String
  }
  setup(props) {
    const log = ref([]);
    onMounted(async () => {
      var es = new EventSource(props.apiurl + '/log');
      es.onmessage = (event) => {
        log.value.unshift(event.data);
      }
    });
    return {
      log
    }
  }
}
</script>



