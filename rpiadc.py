import asyncio
from serial_asyncio import open_serial_connection
import json

async def adc(path='/dev/ttyACM0', **kwargs):
  reader, writer = await open_serial_connection(url=path, **kwargs)
  while True:
        line = await reader.readline()
        yield json.loads(line)

value = None

def start():
  async def x():
     async for v in adc():
      global value
#      print(v, value)
      value = v

  return asyncio.create_task(x(), name='rpiadc_x')
