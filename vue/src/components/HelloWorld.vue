<template>
  <h1>{{ msg }}</h1>
  <button @click="count++" class="btn btn-primary">count is: {{ count }}</button>
  <p>Edit <code>components/HelloWorld.vue</code> to test hot module replacement.</p>
  <p>{{ log }}</p>
</template>

<script>
import { onMounted, ref } from 'vue'

export default {
  name: 'HelloWorld',
  props: {
    msg: String
  },
  setup() {
const log = ref(null);
/*async function fetchData() {
      const r = await fetch('http://maple.lan:8080/api/log');
      log.value=await r.text()
    }
*/
 onMounted(async () => {
//      await fetchData();

var es = new EventSource('https://maple.bluesparc.net:8443/api/log');
es.onmessage = (event) => {
    log.value+=event.data;
}
    });
    return {
      count: 0,
      log
    }

}
}
</script>



