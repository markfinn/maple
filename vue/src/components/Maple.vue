<template>
  <button @click="reload" class="btn btn-primary mx-1">reload app</button>
  <button @click="reboot" class="btn btn-primary mx-1">reboot</button>
  <button @click="poweroff" class="btn btn-primary mx-1">poweroff</button>
  <Outputs/>
  <Log/>
</template>

<script>
import Outputs from "./Outputs.vue";
import {postData} from "../util.js";
import Log from "./Log.vue";

export default {
  name: 'Maple',
  components: {Log, Outputs},
  methods: {
    reload() {
      location.reload(true)
    },
    async reboot() {
      const response = await postData('https://maple.bluesparc.net:8443/api/reboot');
      //console.log(response)
    },
    async poweroff() {
      const response = await postData('https://maple.bluesparc.net:8443/api/poweroff');
      //console.log(response)
    }
  }
}
</script>



