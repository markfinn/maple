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
    self._value = v
    if self._overmode == 2 and self._value != v:
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


  @contextlib.contextmanager
  def watch(self, loop=None):
    if loop is None:
      loop = asyncio.get_event_loop()
    queue = asyncio.Queue(loop=loop)
    self._watchers[queue]=loop
    try:
      loop.call_soon_threadsafe(queue.put, self._overmode, self._value)
      yield queue
    finally:
      del self._watchers[queue]

  def _notify(self):
    for loop, queue in self._watchers:
      loop.call_soon_threadsafe(queue.put, (self._overmode, self._value))

  def __str__(self):
    if self._overmode == 2:
      return '%s'%self._value
    else:
      return '%s <Overridden to %s>'%(self._value, self._overmode)



log = logging.getLogger('maple')
log.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
#ch = logging.FileHandler('/home/mark/maple.log')
if os.getenv("INVOCATION_ID"):
  #am under systemd for logging, journal has timestamp
  formatter = logging.Formatter('%(levelname)s - %(message)s')
else:
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
log.addHandler(ch)



class Maple():
  def __init__(self):
    self.airvac = OverridableDigitalOutputDevice(14, active_high=False)
    self.sapvac = OverridableDigitalOutputDevice(15, active_high=False)
    self.sapfloat = AsyncDigitalInputDevice(18, pull_up=True, active_state=None)
    self.romain = OverridableDigitalOutputDevice(23, active_high=False)
    self.rossr = OverridableDigitalOutputDevice(24, active_high=True, frequency=.3, factory = gpiozero.PWMOutputDevice)
    self.outvalve = OverridableDigitalOutputDevice(25, active_high=False)

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

      while 1:
        await asyncio.sleep(5)
      ASD

      romain.on()
      rossr.value = 1
      await asyncio.sleep(900)

      sdfg
      if sapfloat.value:
        log.info('draining')
        sapvac.on()
        await sapfloat.wait_for_inactive(120)
      sapvac.off()
      airvac.on()

      log.info('Running')
      while True:
        await sapfloat.wait_for_active()
        log.info('Sap Pump on')

        sapvac.on()
        while sapfloat.value:
          await sapfloat.wait_for_inactive(120)
          await asyncio.sleep(5)

        log.info('Sap Pump off')
        sapvac.off()


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
      self.sapvac.off()
      self.romain.off()
      self.rossr.off()
      self.outvalve.off()

      watchdog.keep_alive()
      wd_task.cancel()
      watchdog.magic_close()
      log.info('Shutdown')





#####
async def runinotherthread():
            await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(prepop(list(self.oldlines)), loop))


######################################################3
async def main():




  log.info('Starting')

  maple = Maple()

  webloop = None
  webshut = None
  try:
    def worker(mainloop):
      new_loop = asyncio.new_event_loop()
      asyncio.set_event_loop(new_loop)
      shutdown_event = asyncio.Event()
      nonlocal webloop
      webloop = new_loop
      nonlocal webshut
      webshut = shutdown_event

      # for sending to web
      class FakeStream():
        def __init__(self):
          self.oldlines = collections.deque(maxlen=10)
          self._watchers = {}
          self.linecount = 0
          self.idstart = str(time.time())+':'#so if we re-start, the lines dont srart at 0 and get lost
        def write(self, d):
          self.linecount += 1
          evid = self.idstart+str(self.linecount)
          self.oldlines.append((evid, d))
          for loop, queue in self._watchers:
            loop.call_soon_threadsafe(queue.put, (evid, d))

        @contextlib.asynccontextmanager
        async def watch(self):#can be called from wrong thread and loop
          loop = asyncio.get_event_loop()
          queue = asyncio.Queue()
          initialqueue = asyncio.Queue()
          todel = initialqueue
          self._watchers[initialqueue]=loop
          try:
            for line in list(self.oldlines):
              await queue.put(line)
            while not initialqueue.empty():
              line = await initialqueue.get()
              await queue.put(line)
            #tiny window here after while but before queue add where an event could get lost, but I don't care right now
            self._watchers[queue]=loop
            todel = queue
            del self._watchers[initialqueue]
            yield queue
          finally:
            del self._watchers[todel]

      logqueue = FakeStream()
      ch = logging.StreamHandler(stream=logqueue)
      formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
      ch.setFormatter(formatter)
      log.addHandler(ch)

      log.info('running web server')
      try:
        webapp.app.config['mainloop'] = mainloop
        webapp.app.config['maple'] = maple
        webapp.app.config['logqueuer'] = logqueue
        new_loop.run_until_complete(webapp.app.run_task(host="0.0.0.0", port=8443, certfile='fullchain.pem', keyfile='privkey.pem', debug=True, shutdown_trigger=shutdown_event.wait))
      finally:
        # being off in another therad is nice and all, but hypercorn sems to choke on asyncio.run() over here, and run until complete doesn't shut down in the end
        # steal the shutdown code from asyncio.run
        asyncio.runners._cancel_all_tasks(new_loop)
        new_loop.run_until_complete(new_loop.shutdown_asyncgens())
        new_loop.close()

    threading.Thread(target=worker, args=(asyncio.get_event_loop(),)).start()

  except:
    log.exception('failed to start web service')

  '''shutdown_event = asyncio.Event()

def _signal_handler(*_: Any) -> None:
        shutdown_event.set()

loop = asyncio.get_event_loop()
loop.add_signal_handler(signal.SIGTERM, _signal_handler)
loop.run_until_complete(
    serve(app, config, shutdown_trigger=shutdown_event.wait)
)

---or---

import asyncio
from signal import SIGINT, SIGTERM

async def main_coro():
    try:
        await awaitable()
    except asyncio.CancelledError:
        do_cleanup()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    main_task = asyncio.ensure_future(main_coro())
    for signal in [SIGINT, SIGTERM]:
        loop.add_signal_handler(signal, main_task.cancel)
    try:
        loop.run_until_complete(main_task)
    finally:
        loop.close()
'''

  def handler(signum, frame):
    log.warning('Signal handler called with signal %d', signum)
    if webloop:
      webloop.call_soon_threadsafe(webshut.set)
    # Raises SystemExit(0):
    sys.exit(0)

  signal.signal(signal.SIGINT, handler)
  signal.signal(signal.SIGTERM, handler)



  await maple.run()


######################################################3
if __name__ == '__main__':

  asyncio.run(main())

