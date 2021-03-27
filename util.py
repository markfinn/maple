import gpiozero
import asyncio
import sys
import contextlib
import time
import math
import logging

#not right to assum maple...
log = logging.getLogger('maple')


######################################################3
class AsyncDigitalInputDevice(gpiozero.DigitalInputDevice):
  def __init__(self, *args, **kwargs):
    self._invert = kwargs.pop('invert', False)
    super().__init__(*args, **kwargs)
    self._awaiters = set()

  def __str__(self):
      return '%s'%self.value

  @property
  def value(self):
    v = not super().value
    if not self._invert:
      v = not v
    return v

  async def wait_for_active(self, timeout=None, *, inverse=False):
    #gpiozero is EDGE only, not level...  I want to stop eaiting on either
    if self.value == (not inverse):
      return
    loop = asyncio.get_event_loop()
    f = loop.create_future()
    install = not self._awaiters
    self._awaiters.add(f)
    if install:
      def active():
        awaiters = self._awaiters
        self._awaiters=set()
        if inverse ^ self._invert:
          self.when_deactivated = None
        else:
          self.when_activated = None
        for f in awaiters:
          if not f.done():
            f.set_result(None)

      if inverse ^ self._invert:
        self.when_deactivated = lambda: loop.call_soon_threadsafe(active)
      else:
        self.when_activated = lambda: loop.call_soon_threadsafe(active)

      #gpiozero is EDGE only, not level...  I want to stop waiting on either
      #and since the edge event is threaded we have to test again after we install to avoid a race
      #note that active may get called twice, so we check done() on the future
      if self.value == (not inverse):
        active()
      
    await asyncio.wait_for(f, timeout=timeout)

  def wait_for_inactive(self, timeout=None):
    return self.wait_for_active(inverse=True, timeout=timeout)


  @contextlib.asynccontextmanager
  async def watch(self):
    queue = asyncio.Queue()
    v = self.value
    await queue.put((2, v))
    async def loopfunc():
      nonlocal v
      while True:
        await self.wait_for_active(inverse=v)
        v = not v
        await queue.put((2, v))
    try:
      task = asyncio.create_task(loopfunc())
      yield queue
    finally:
      task.cancel()



######################################################3
class OverridableDigitalOutputDevice():
  def __init__(self, *args, factory=gpiozero.DigitalOutputDevice, **kwargs):
    self._dev = factory(*args, **kwargs)
    self._overmode = 2#auto
    self._value = self._dev.value
    self._watchers = set()

  def on(self):
    self.value = 1

  def off(self):
    self.value = 0

  @property
  def value(self):
    return self._value
  @value.setter
  def value(self, v):
    ov = self._value
    self._value = v
    if ov != v:
      if self._overmode == 2:
        self._dev.value = v
      self._notify()

  @property
  def overmode(self):
    return self._overmode
  @overmode.setter
  def overmode(self, v):
    if v != self._overmode:
      self._overmode = v
      if self._overmode == 2:
        self._dev.value = self._value
      else:
        self._dev.value = self._overmode
      self._notify()


  @contextlib.asynccontextmanager
  async def watch(self):
    queue = asyncio.Queue()
    self._watchers.add(queue)
    try:
      await queue.put((self._overmode, self._value))
      yield queue
    finally:
      self._watchers.remove(queue)

  def _notify(self):
    for queue in list(self._watchers):
      asyncio.create_task(queue.put((self._overmode, self._value)))

  def __str__(self):
    if self._overmode == 2:
      return '%s'%self._value
    else:
      return '%s <Overridden to %s>'%(self._value, self._overmode)

class WatchableExpression():
  def __init__(self, exprfunc, tolerance=None, **kwargs):
    self.exprfunc = exprfunc
    self.kwargs = kwargs
    self._watchers = set()
    self.tolerance = tolerance

  @property
  def value(self):
    vals = {name: val.value for name, val in self.kwargs.items()}
    return self.exprfunc(**vals)

  @contextlib.asynccontextmanager
  async def watch(self):
    queue = asyncio.Queue()
    needinstall = not self._watchers
    vnow = self.value
    self._watchers.add(queue)
    if needinstall:
      async def wloop():
        nonlocal vnow
        async with contextlib.AsyncExitStack() as stack:
          queues = {await stack.enter_async_context(val.watch()): name for name, val in self.kwargs.items()}
          while True:
            await asyncio.wait([asyncio.create_task(q.get()) for q in queues], return_when=asyncio.FIRST_COMPLETED)
            v = self.value
            if v == vnow:
              continue
            if type(v) != type(vnow) or not self.tolerance or abs(vnow - v) > self.tolerance:
              vnow = v
              for queue in list(self._watchers):
                asyncio.create_task(queue.put(v))
      self.wloop_task = watchedtask(wloop())
      

    try:
      await queue.put(vnow)
      yield queue
    finally:
      self._watchers.remove(queue)
      if not self._watchers:
        self.wloop_task.cancel()
        del self.wloop_task


  async def waittrue(self):  # waits until true
    v = self.value
    if v:
      return v
    async with self.watch() as q:
      while True:
        await q.get()
        v = self.value
        if v:
          return v



class ADCPoll(WatchableExpression):
  class InnerADC():#provides value and watch, although watch is degenerate and only meant to be used in ADCPoll
    def __init__(self, adc, channel, samplePeriod):
      self.t = None
      self.value = adc.read_adc(channel, gain=1), time.time()
      self._queue = asyncio.Queue()
      async def aw():
        while True:
          self.value = adc.read_adc(channel, gain=1), time.time()
          if self._queue.empty():
            await self._queue.put(None)
          await asyncio.sleep(samplePeriod)
      self.t = asyncio.create_task(aw())

    @contextlib.asynccontextmanager
    async def watch(self):
      try:
        yield self._queue
      finally:
        self.t.cancel()
        self.t = None

    def __del__(self):
      if self.t:
        self.t.cancel()

  def __init__(self, adc, channel, *, tolerance=None, samplePeriod=.1, tc=0, scalefunc=None):
    avg = None
    def valuefunc(valAndTime):
      nonlocal avg
      val, treading = valAndTime
      if tc:
        if avg is None:
          avg = val, treading
        else:
          dt = treading - avg[1]
          x = 1 - math.exp(-dt / tc)
          avg = avg[0] + (val - avg[0]) * x, treading
          val = avg[0]

      if scalefunc:
        val = scalefunc(val)

      return val

    self.innerADC = ADCPoll.InnerADC(adc, channel, samplePeriod)
    super().__init__(valuefunc, valAndTime=self.innerADC, tolerance=tolerance)

  def __del__(self):
    del self.innerADC



def watchedtask(aw, *, allowFinish=False):
  def test(f):
    if f.cancelled():
      return
    if f.exception() is not None or not allowFinish:
      log.error('Task died', exc_info=f.exception())
      sys.exit(1)
  t = asyncio.create_task(aw)
  t.add_done_callback(test)
  return t



class OnOffAverager():
  def __init__(self, *, state=False, initial=0, tc=300):
    self.val = initial
    self.tc=tc
    self.lastchange = time.time()
    self.startt = self.lastchange
    self.state = state

  def setstate(self, state):
    if self.state == state:
      return
    now = time.time()
    dt = now-self.lastchange
    v= float(self.state)
    tc = min(self.tc, time.time() - self.startt)
    x = 1-math.exp(-dt/tc)
#    print(self.val, v, x, (v-self.val) * x)
    self.val += (v-self.val) * x
    self.lastchange=now
    self.state=state

  @property
  def avg(self):
    now = time.time()
    dt = now-self.lastchange
    v=1 if self.state else 0
    tc = min(self.tc, time.time() - self.startt)
    x = 1-math.exp(-dt/tc)
    return self.val + (v-self.val) * x

  @classmethod
  def avgOfOutput(cls, output, **kwargs):
    t1 = cls(state=output.value, **kwargs)
    t2 = cls(state=output.value if output.overmode == 2 else output.overmode, **kwargs)

    async def outtime_watch_task():
      async with output.watch() as q:
        while True:
          v = await q.get()
          t1.setstate(v[1])
          v = v[1] if v[0] == 2 else v[0]
          t2.setstate(v)

    task_t = watchedtask(outtime_watch_task())
    return t1, t2

def runinotherloop(coro, loop):
  return asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, loop))


@contextlib.asynccontextmanager
async def awithinotherloop(coro, loop):
  x = await runinotherloop(coro.__aenter__(), loop)
  try:
    yield x
  except:
    if not await runinotherloop(coro.__aexit__(*sys.exc_info()), loop):
      raise
  else:
    await runinotherloop(coro.__aexit__(None, None, None), loop)

#fix the thread prob
# fix the "adc doesnt fire every sample, so averager wont update value issue
#MAKE INPUTS WORK ON WEB
#make onofavger watchable and use it
#make a time based watchable and use it
