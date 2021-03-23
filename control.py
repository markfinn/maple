import gpiozero
import logging
import asyncio
import signal, os, sys
import watchdogdev
import webapp
import threading
import contextlib
import collections
import time
import fcntl
import math
import sqlite3
import Adafruit_ADS1x15



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

  async def wait_for_active(self, timeout=None, *, inverse=False, loop=None):
    #gpiozero is EDGE only, not level...  I want to stop eaiting on either
    if self.value == (not inverse):
      return
    if loop is None:
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
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue(loop=loop)
    v = self.value
    await queue.put((2, v))
    async def loopfunc():
      while True:
        await self.wait_for_active(inverse=v, loop=loop)
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
    self._watchers = {}

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
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue(loop=loop)
    self._watchers[queue]=loop
    try:
      await queue.put((self._overmode, self._value))
      yield queue
    finally:
      del self._watchers[queue]

  def _notify(self):
    for queue, loop in list(self._watchers.items()):
      loop.call_soon_threadsafe(asyncio.create_task, queue.put((self._overmode, self._value)))

  def __str__(self):
    if self._overmode == 2:
      return '%s'%self._value
    else:
      return '%s <Overridden to %s>'%(self._value, self._overmode)



log = logging.getLogger('maple')


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



class onoffaverager():
  def __init__(self, *, state=False, initial=0, tc=300):
    self.val = initial
    self.tc=tc
    self.lastchange = time.time()
    self.state = state

  def setstate(self, state):
    if self.state == state:
      return
    now = time.time()
    dt = now-self.lastchange
    v= float(self.state)
    x = 1-math.exp(-dt/self.tc)
#    print(self.val, v, x, (v-self.val) * x)
    self.val += (v-self.val) * x
    self.lastchange=now
    self.state=state

  @property
  def avg(self):
    now = time.time()
    dt = now-self.lastchange
    v=1 if self.state else 0
    x = 1-math.exp(-dt/self.tc)
    return self.val + (v-self.val) * x
    

class Maple():
  def __init__(self):
    self._waiter = asyncio.Event()

    log.info('Setting Watchdog')
    watchdog = watchdogdev.watchdog('/dev/watchdog')
    watchdog.set_timeout(5)
    if watchdog.get_boot_status():
      log.error('Last boot was from Watchdog!!')  # not working?

    async def wd_alive():
      while True:
        watchdog.keep_alive()
        await asyncio.sleep(1)

    wd_task = asyncio.ensure_future(wd_alive())

    db = sqlite3.Connection('/home/mark/maple/db.sq3')
    db.execute('''
CREATE TABLE IF NOT EXISTS events (
    time REAL NOT NULL,
    type TEXT NOT NULL,
    state TEXT
);''')


#    def event(type, state, time=None):
#      if time is None:
#        time = timemod.time()
#      db.execute('insert into events (time, type, state) VALUES (?,?,?)', (time, type, state)


    self.syruprecerc = OverridableDigitalOutputDevice(7, active_high=False)
    self.outvalve = OverridableDigitalOutputDevice(25, active_high=False)
    self.sapvac = OverridableDigitalOutputDevice(15, active_high=False)
    self.romain = OverridableDigitalOutputDevice(23, active_high=False)
    self.rossr = OverridableDigitalOutputDevice(24, active_high=True, frequency=1, factory = gpiozero.PWMOutputDevice)
    self.airvac = OverridableDigitalOutputDevice(14, active_high=False)
    self.vacpump = OverridableDigitalOutputDevice(12, active_high=True)
    self.waterrecerc = OverridableDigitalOutputDevice(1, active_high=False)
    self.primepump = OverridableDigitalOutputDevice(20, active_high=False)


    self.sapfloathigh = AsyncDigitalInputDevice(8, pull_up=True, active_state=None)
    self.sapfloat = AsyncDigitalInputDevice(18, pull_up=True, active_state=None)
    self.recfloat = AsyncDigitalInputDevice(16, pull_up=True, active_state=None, invert=True)
    self.iicadc = Adafruit_ADS1x15.ADS1015()



    self.setpressure = 0


    def avgout(output):
      t1 = onoffaverager(state=output.value)
      t2 = onoffaverager(state=output.value if output.overmode == 2 else output.overmode)
      async def outtime_watch_task():
        async with output.watch() as q:
          while True:
            v = await q.get()
            t1.setstate(v[1])
            v = v[1] if v[0] == 2 else v[0]
            t2.setstate(v)
      task_t = watchedtask(outtime_watch_task())
      return t1,t2
      
    self.saptime1, self.saptime2 = avgout(self.sapvac)
    self.outtime1, self.outtime2 = avgout(self.outvalve)
    self.rotime1, self.rotime2 = avgout(self.rossr)



    async def task_pressure():
#    self.setpressure = 0
      self.romain.on()
      self.primepump.on()
      avg=None
      t=0
      while True:

          v = self.iicadc.read_adc(0, gain=1)/500#4.096, but dont exceede 3.3 (+.3?)
          if avg is None:
            avg = v
          else:
            avg = avg*.75+.25*v
          now = time.time()
          if now-t>.2:
            t=now
            psi = max(0, ((avg*(47+10)/47)-.5)*200/4) + 6#10?!?!?
            #print(v, avg, psi)
            self.pressure = psi
            if psi > self.setpressure:
              self.rossr.off()
            else:
              self.rossr.on()
          await asyncio.sleep(.051)

    task_pressure_t = watchedtask(task_pressure())

    async def task_output():
      await self.recfloat.wait_for_inactive(120)
      while True:
        await self.recfloat.wait_for_active()
        self.outvalve.on()
        await self.recfloat.wait_for_inactive(360)
        self.outvalve.off()

    task_output_t = watchedtask(task_output())




    async def task_sap():
      if self.recfloat:
        log.info('repriming')
        self.setpressure = 125
        self.syruprecerc.on()
        await self.recfloat.wait_for_inactive(400)
        
      if self.sapfloat.value:
        log.info('draining')
        self.setpressure = 125
        self.sapvac.on()
        await self.sapfloat.wait_for_inactive(500)
      self.syruprecerc.on()
      log.info('drained')


      while True:
        log.info('Sap Pump off')
        self.sapvac.off()
        self.airvac.on()

        await self.sapfloat.wait_for_active()

        log.info('Sap Pump on')
        self.sapvac.on()

        try:
          await self.sapfloathigh.wait_for_active(5)
        except asyncio.TimeoutError:
          pass
        if not self.sapfloat.value:
          continue
        await asyncio.wait([
          asyncio.create_task(self.sapfloat.wait_for_inactive()),
          asyncio.create_task(self.sapfloathigh.wait_for_active())
        ], timeout=25, return_when=asyncio.FIRST_COMPLETED)
        if not self.sapfloat.value:
          continue
        self.airvac.off()
        await asyncio.sleep(5)
  
        await self.sapfloat.wait_for_inactive(120)

    task_sap_t = watchedtask(task_sap())

    async def task_vac():
      await self.sapfloat.wait_for_inactive(600)

      while True:
        self.vacpump.on()

        await self.sapfloathigh.wait_for_active()

        log.info('Vac Pump off')
        self.vacpump.off()
  
        await self.sapfloathigh.wait_for_inactive(600)

    task_vac_t = watchedtask(task_vac())

#   die_task_t = watchedtask(asyncio.sleep(3*3600))


    async def cleanup_task():
      log.info('Running')
      try:
        while 1:
          await asyncio.sleep(10)
      except SystemExit:
        log.info('SystemExit')
      except asyncio.CancelledError:
        log.info('SystemExit')
        raise
      except:
        log.exception('unhandled exception')
        # raise

      finally:
        self.airvac.off()
        self.airvac.overmode = 0
        self.vacpump.off()
        self.vacpump.overmode = 0
        self.sapvac.off()
        self.sapvac.overmode = 0
        self.romain.off()
        self.romain.overmode = 0
        self.rossr.off()
        self.rossr.overmode = 0
        self.syruprecerc.off()
        self.syruprecerc.overmode = 0
        self.outvalve.off()
        self.outvalve.overmode = 0
        self.waterrecerc.off()
        self.waterrecerc.overmode = 0
        self.primepump.off()
        self.primepump.overmode = 0

        watchdog.keep_alive()
        wd_task.cancel()
        watchdog.magic_close()
        log.info('Shutdown')
        self._waiter.set()


    cleanup_task_t = watchedtask(cleanup_task())

  @property
  def wait(self):
    return self._waiter.wait
    