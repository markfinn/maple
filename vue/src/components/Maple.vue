<template>
  <button @click="reload" class="btn btn-primary mx-1">reload app</button>
  <button @click="reboot" class="btn btn-primary mx-1">reboot</button>
  <button @click="poweroff" class="btn btn-primary mx-1">poweroff</button>
  <hr>
  <a href="http://maple.bluesparc.net:3000/src/processFlow.html">Diagram</a><br>
  <a href="http://maple.bluesparc.net:3000/src/processFlowEditor.html">Editor</a><br>
  <Gauge url="https://maple.bluesparc.net:8443/api/pressure"/><br>
  <Gauge url="https://maple.bluesparc.net:8443/api/saptimes"/><br>
  <Gauge url="https://maple.bluesparc.net:8443/api/rotimes"/><br>
  <Gauge url="https://maple.bluesparc.net:8443/api/outtimes"/><br>
  <Gauge url="https://maple.bluesparc.net:8443/api/extratimes"/><br>
  <Inputs/>
  <Outputs/>
  <Log/>
</template>

<script>
import Inputs from "./Inputs.vue";
import Outputs from "./Outputs.vue";
import Gauge from "./Gauge.vue";
import {postData} from "../util.js";
import Log from "./Log.vue";

export default {
  name: 'Maple',
  components: {Log, Outputs, Inputs, Gauge},
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



