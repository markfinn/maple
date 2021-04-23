<template>
  <button @click="reload" class="btn btn-primary mx-1">reload app</button>
  <button @click="reboot" class="btn btn-primary mx-1">reboot</button>
  <button @click="poweroff" class="btn btn-primary mx-1">poweroff</button>
  <hr>
  <a href="http://maple.bluesparc.net:3000/src/processFlow.html">Diagram</a><br>
  <a href="http://maple.bluesparc.net:3000/src/processFlowEditor.html">Editor</a><br>
  <Gauge :url="apiurl + '/pressure'"/><br>
  <Gauge :url="apiurl + '/saptimes'"/><br>
  <Gauge :url="apiurl + '/rotimes'"/><br>
  <Gauge :url="apiurl + '/outtimes'"/><br>
  <Gauge :url="apiurl + '/extratimes'"/><br>
  <Inputs :apiurl="apiurl" />
  <Outputs :apiurl="apiurl" />
  <Log :apiurl="apiurl" />
</template>

<script>
import Inputs from "./Inputs.vue";
import Outputs from "./Outputs.vue";
import Gauge from "./Gauge.vue";
import {postData} from "../util.js";
import Log from "./Log.vue";
import { useRoute, useRouter } from 'vue-router'
import { onMounted } from 'vue'

export default {
  name: 'Maple',
  components: {Log, Outputs, Inputs, Gauge},
  props: {
    apiurl: String
  },
  methods: {
    reload() {
      location.reload(true)
    },
    async reboot() {
      const response = await postData(this.apiurl + '/reboot');
      //console.log(response)
    },
    async poweroff() {
      const response = await postData(this.apiurl + '/poweroff');
      //console.log(response)
    }
  },
  setup(props) {
    onMounted(async () => {
      const route = useRoute();
      if ('startup' in route.query) {
        postData(props.apiurl + '/startup');
	//could remove the startup query param if we want it cleaner
        //const router = useRouter();
        //router.replace({path: route.path})
      }
    });
  }
}
</script>



