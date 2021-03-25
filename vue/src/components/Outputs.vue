<template>
  <div>
    <ul class="list-group">
      <li v-for="item in items" class="list-group-item">
        {{ item }}
        <DigitalOutput :which="item" :apiurl="apiurl" />
      </li>
    </ul>
  </div>
</template>

<script>
import DigitalOutput from "./DigitalOutput.vue";
import {onMounted, ref} from "vue";

export default {
  name: "Outputs",
  components: {DigitalOutput},
  props: {
    apiurl: String
  },
  setup(props) {
    const items = ref([]);
    onMounted(() => {
      async function getoutputs() {
        let next = 5000;
        try {
          const response = await fetch(props.apiurl + '/outputs');
          const outputs = await response.json();
          items.value = Object.keys(outputs);
        } catch (e) {
          next = 1000;
        }
        setTimeout(getoutputs, next);
      }

      setTimeout(getoutputs, 0);
    });
    return {
      items
    }

  }

}
</script>

<style scoped>

</style>