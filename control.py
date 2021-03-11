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

######################################################3
class AsyncDigitalInputDevice(gpiozero.DigitalInputDevice):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._awaiters = set()

  def __str__(self):
      return '%s'%self.value

  async def wait_for_active(self, timeout=None, *, inverse=False):
    #gpiozero is EDGE only, not level...  I want to stop eaiting on either
    if self.value == int(not inverse):
      return
    loop = asyncio.get_event_loop()
    f = loop.create_future()
    install = not self._awaiters
    self._awaiters.add(f)
    if install:
      def active():
        awaiters = self._awaiters
        self._awaiters=set()
        if inverse:
          self.when_deactivated = None
        else:
          self.when_activated = None
        for f in awaiters:
          if not f.done():
            f.set_result(None)

      if inverse:
        self.when_deactivated = lambda: loop.call_soon_threadsafe(active)
      else:
        self.when_activated = active
        self.when_activated = lambda: loop.call_soon_threadsafe(active)

      #gpiozero is EDGE only, not level...  I want to stop waiting on either
      #and since the edge event is threaded we have to test again after we install to avoid a race
      #note that active may get called twice, so we check done() on the future
      if self.value == int(not inverse):
        active()
      
    await asyncio.wait_for(f, timeout=timeout)

  def wait_for_inactive(self, timeout=None):
    return self.wait_for_active(inverse=True, timeout=timeout)

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
    if self._overmode == 2 and ov != v:
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
    for queue, loop in self._watchers.items():
      loop.call_soon_threadsafe(asyncio.create_task, queue.put((self._overmode, self._value)))

  def __str__(self):
    if self._overmode == 2:
      return '%s'%self._value
    else:
      return '%s <Overridden to %s>'%(self._value, self._overmode)



log = logging.getLogger('maple')


class Maple():
  def __init__(self):
    self.syruprecerc = OverridableDigitalOutputDevice(7, active_high=False)
    self.waterrecerc = OverridableDigitalOutputDevice(25, active_high=False)
    self.sapvac = OverridableDigitalOutputDevice(15, active_high=False)
    self.romain = OverridableDigitalOutputDevice(23, active_high=False)
    self.rossr = OverridableDigitalOutputDevice(24, active_high=True, frequency=.3, factory = gpiozero.PWMOutputDevice)
    self.airvac = OverridableDigitalOutputDevice(14, active_high=False)


    self.sapfloathigh = AsyncDigitalInputDevice(8, pull_up=True, active_state=None)
    self.sapfloat = AsyncDigitalInputDevice(18, pull_up=True, active_state=None)

  async def run(self):
    try:
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

#      while 1:
#        await asyncio.sleep(5)
#      ASD

      self.romain.on()
      self.rossr.value = 1
 #     await asyncio.sleep(900)

 #     sdfg
      if self.sapfloat.value:
        log.info('draining')
        self.sapvac.on()
        await self.sapfloat.wait_for_inactive(120)
      self.sapvac.off()
      self.airvac.on()

      log.info('Running')
      while True:
        await self.sapfloat.wait_for_active()
        log.info('Sap Pump on')

        self.sapvac.on()
        while self.sapfloat.value:
          await self.sapfloat.wait_for_inactive(120)
          await asyncio.sleep(5)

        log.info('Sap Pump off')
        self.sapvac.off()


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
      self.airvac.overmode = 2
      self.sapvac.off()
      self.sapvac.overmode = 2
      self.romain.off()
      self.romain.overmode = 2
      self.rossr.off()
      self.rossr.overmode = 2
      self.syruprecerc.off()
      self.syruprecerc.overmode = 2
      self.waterrecerc.off()
      self.waterrecerc.overmode = 2

      watchdog.keep_alive()
      wd_task.cancel()
      watchdog.magic_close()
      log.info('Shutdown')

