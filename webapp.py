import asyncio
import os
from quart import Quart, redirect, abort, make_response, request
from quart_cors import cors
import gpio

app = Quart(__name__)
app = cors(app, allow_origin='http://maple.bluesparc.net:3000')#  '*' works too


class ServerSentEvent:

    def __init__(
            self,
            data: str,
            *,
            event: str=None,
            id: int=None,
            retry: int=None,
    ) -> None:
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry

    def encode(self) -> bytes:
        message = f"data: {self.data}"
        if self.event is not None:
            message = f"{message}\nevent: {self.event}"
        if self.id is not None:
            message = f"{message}\nid: {self.id}"
        if self.retry is not None:
            message = f"{message}\nretry: {self.retry}"
        message = f"{message}\r\n\r\n"
        return message.encode('utf-8')

    headers = {
                'Content-Type'     : 'text/event-stream',
                'Cache-Control'    : 'no-cache',
                'Transfer-Encoding': 'chunked',
            }

@app.route("/")
async def index():
    return redirect("http://maple.bluesparc.net:3000", code=302)
 
@app.route("/api/reboot", methods=['POST'])
async def reboot():
    p = await asyncio.create_subprocess_shell("sudo reboot", shell=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await p.communicate()
    return stdout + stderr

@app.route("/api/poweroff", methods=['POST'])
async def poweroff():
    p = await asyncio.create_subprocess_shell("sudo poweroff", shell=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await p.communicate()
    return stdout + stderr

@app.route("/api/log")
async def log():
    skipto = request.headers.get("Last-Event-ID")
    async with app.config['logqueuer'].watch() as queue:
        async def send_events():
            while True:
                evid, data = await queue.get()
                if skipto is not None and evid <= skipto:
                  continue
                event = ServerSentEvent(data, id=evid)
                yield event.encode()

        response = await make_response(send_events(), ServerSentEvent.headers)
        response.timeout = None
        return response

@app.route("/api/outputs/<string:which>", methods=['GET', 'POST'])
async def outputs(which):
    try:
        o = getattr(app.config['maple'], which)
        assert isinstance(o, gpio.OverridableDigitalOutputDevice)
    except:
        abort(404)

    if request.method == 'POST':
#        if request.is_json
#            val = request.json['value']
        val = request.form['value']
        o.overmode = val
        return 'ok'

    with o.watch(asyncio.get_event_loop()) as queue:
        async def send_events():
            while True:
                data = await queue.get()
                event = ServerSentEvent(data)
                yield event.encode()

        response = await make_response(send_events(), ServerSentEvent.headers)
        response.timeout = None
        return response

@app.route("/api/outputs")
async def outputsls():
    response = {}
    for n in dir(app.config['maple']):
        o = getattr(app.config['maple'], n)
        if isinstance(o, gpio.OverridableDigitalOutputDevice):
            response[n] = str(o)

    return response

@app.route("/api/inputs")
async def inputsls():
    response = {}
    for n in dir(app.config['maple']):
        o = getattr(app.config['maple'], n)
        if isinstance(o, gpio.AsyncDigitalInputDevice):
            response[n] = str(o)

    return response

if __name__ == "__main__":
#    app.run(host="127.0.0.1", port=8080, debug=True)
    app.run(host="0.0.0.0", port=8080, debug=True)
    