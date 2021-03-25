<template>
  <div>
    <ul class="list-group">
      <li v-for="item in items" class="list-group-item">
        {{ item }}
        <DigitalInput :which="item" :apiurl="apiurl" />
      </li>
    </ul>
  </div>
</template>

<script>
import DigitalInput from "./DigitalInput.vue";
import {onMounted, ref} from "vue";

export default {
  name: "Inputs",
  components: {DigitalInput},
  props: {
    apiurl: String
  },
  setup(props) {
    const items = ref([]);
    onMounted(() => {
      async function getinputs() {
        let next = 5000;
        try {
          const response = await fetch(props.apiurl + '/inputs');
          const inputs = await response.json();
          items.value = Object.keys(inputs);
        } catch (e) {
          next = 1000;
        }
        setTimeout(getinputs, next);
      }

      setTimeout(getinputs, 0);
    });
    return {
      items
    }

  }

}
</script>

<style scoped>

</style>