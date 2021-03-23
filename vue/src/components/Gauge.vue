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
        var v = data['value'];
      	if (Array.isArray(v)) {
      	  v = v.map(x => (typeof(x) == 'number') ? Math.round(x*100)/100 : x)
      	}
      	else if (typeof(v) == 'number') {
      	  v = Math.round(v*100)/100;
        }
		    value.value = v;
      }
    });
    return {
      value
    }

  }
}
</script>



