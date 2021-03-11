<template>
  <span>
  <button @click="click(0)" class="btn mx-1" :class="classOff">Off</button>
  <button @click="click(2)" class="btn mx-1" :class="classAuto">Auto</button>
  <button @click="click(1)" class="btn mx-1" :class="classOn">On</button>
  </span>
</template>

<script>
import { onMounted, ref } from 'vue'
import { postData } from "../util.js";

export default {
  name: "DigitalOutput",
  props: {
    which: String
  },
  computed: {
    classOn() {
      if (this.overridden == null)
        return 'btn-outline-secondary';
      if (this.overridden == 1)
        return 'btn-success';
      return 'btn-outline-success';
    },
    classAuto() {
      if (this.overridden == null)
        return 'btn-outline-secondary';
      if (this.overridden == 2) {
        if (this.natural == 0)
          return 'btn-danger';
        if (this.natural == 1)
          return 'btn-success';
      } else {
        if (this.natural == 0)
          return 'btn-outline-danger';
        if (this.natural == 1)
          return 'btn-outline-success';
      }
    },
    classOff() {
      if (this.overridden == null)
        return 'btn-outline-secondary';
      if (this.overridden == 0)
        return 'btn-danger';
      return 'btn-outline-danger';
    }
  },
  methods: {
    async click(mode) {
      const response = await postData(`https://maple.bluesparc.net:8443/api/outputs/${this.which}`, {value: mode});
      //console.log(response)
    }
  },
  setup(props) {
    const overridden = ref(null);
    const natural = ref(null);
    onMounted(async () => {
      var es = new EventSource(`https://maple.bluesparc.net:8443/api/outputs/${props.which}`);
      es.onmessage = (event) => {
        const data = JSON.parse(event.data)
        overridden.value = data['overmode'];
        natural.value = data['value'];
      }
    });
    return {
      overridden,
      natural
    }

  }
}
</script>



