import asyncio
import os
from quart import Quart, redirect, abort, make_response, request, json
from quart_cors import cors
import control
import time

app = Quart(__name__)
app = cors(app, allow_origin='http://maple.bluesparc.net:3000')#  '*' works too

import logging
logging.getLogger('quart.serving').setLevel('WARNING')



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
    async def send_events():
        async with app.config['logqueuer'].watch() as queue:
            while True:
                evid, data = await queue.get()
                if skipto is not None and evid <= skipto:
                  continue
                event = ServerSentEvent(data, id=evid)
                yield event.encode()

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response

@app.route("/api/inputs/<which>", methods=['GET', 'POST'], endpoint='inputs')
@app.route("/api/outputs/<which>", methods=['GET', 'POST'], endpoint='outputs')
async def outputs(which):
    try:
        o = getattr(app.config['maple'], which)
        if request.endpoint=='outputs':
          assert isinstance(o, control.OverridableDigitalOutputDevice)
        elif request.endpoint=='inputs':
          assert isinstance(o, control.AsyncDigitalInputDevice)
        else:
          assert 0, 'bad endpoint'
    except:
        abort(404)

    if request.method == 'POST':
        if request.is_json:
            val = await request.json
            val = val['value']
#        val = await request.get_data()
        o.overmode = val
        return {'overmode': o._overmode, 'value': o._value}

    async def send_events():
        async with o.watch() as queue:
            while True:
                data = await queue.get()
                event = ServerSentEvent(json.dumps({'overmode': data[0], 'value': data[1]}))
                yield event.encode()

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response

@app.route("/api/inputs", endpoint='inputsls')
@app.route("/api/outputs", endpoint='outputsls')
async def outputsls():
    response = {}
    for n in dir(app.config['maple']):
        o = getattr(app.config['maple'], n)
        if request.endpoint=='outputsls' and isinstance(o, control.OverridableDigitalOutputDevice):
            response[n] = str(o)
        elif request.endpoint=='inputsls' and isinstance(o, control.AsyncDigitalInputDevice):
            response[n] = str(o)

    return response

@app.route("/api/pressure")
async def pressure():
    async def send_events():
        async with app.config['maple'].pressure.watch() as queue:
            while True:
                data = await queue.get()
                event = ServerSentEvent(json.dumps({'value': data}))
                yield event.encode()

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response

@app.route("/api/ins")
async def tempins():
    async def send_events():
        #async with o.watch() as queue:
        while True:
                data = (app.config['maple'].sapfloat.value, app.config['maple'].sapfloathigh.value, app.config['maple'].rofloat.value)
                event = ServerSentEvent(json.dumps({'value': data}))
                yield event.encode()
                await asyncio.sleep(.3)

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response

@app.route("/api/saptimes")
async def saptimes():
    async def send_events():
        #async with o.watch() as queue:
        while True:
                data = (app.config['maple'].saptime1.avg, app.config['maple'].saptime2.avg)
                event = ServerSentEvent(json.dumps({'value': data}))
                yield event.encode()
                await asyncio.sleep(1)

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response

@app.route("/api/outtimes")
async def outtimes():
    async def send_events():
        #async with o.watch() as queue:
        while True:
                data = (app.config['maple'].outtime1.avg, app.config['maple'].outtime2.avg)
                event = ServerSentEvent(json.dumps({'value': data}))
                yield event.encode()
                await asyncio.sleep(1)

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response

@app.route("/api/rotimes")
async def rotimes():
    async def send_events():
        #async with o.watch() as queue:
        while True:
                data = (app.config['maple'].rotime1.avg, app.config['maple'].rotime2.avg)
                event = ServerSentEvent(json.dumps({'value': data}))
                yield event.encode()
                await asyncio.sleep(1)

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response

@app.route("/api/extratimes")
async def extratimes():
    async def send_events():
        # async with o.watch() as queue:
        while True:
            t1 = app.config['maple'].at_pressure_time
            if t1 is not None:
              t1 = time.time() - t1
            data = (t1, app.config['maple'].runningTimeWithFloatOff)
            event = ServerSentEvent(json.dumps({'value': data}))
            yield event.encode()
            await asyncio.sleep(1)

    response = await make_response(send_events(), ServerSentEvent.headers)
    response.timeout = None
    return response
