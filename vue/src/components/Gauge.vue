<template>
  <span>
   {{ value }}
  </span>
</template>

<script>
import { onMounted, ref } from 'vue'

export default {
  name: "Gauge",
  props: {
    url: String
  },
  setup(props) {
    const value = ref(null);
    onMounted(async () => {
      var es = new EventSource(`${props.url}`);
      es.onmessage = (event) => {
        const data = JSON.parse(event.data)
        value.value = data['value'];
	if (Array.isArray(value.value) && value.value.length==2) {
		value.value = [Math.round(value.value[0]*100), Math.round(value.value[1]*100)];
	}
      }
    });
    return {
      value
    }

  }
}
</script>



