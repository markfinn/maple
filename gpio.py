import gpiozero
import logging
import asyncio
import signal, os, sys


class Timer:
    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        self._callback()

    def cancel(self):
        self._task.cancel()

class AsyncDigitalInputDevice(gpiozero.DigitalInputDevice):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._awaiters = set()

  async def wait_for_active(self, timeout=None, *, inverse=False):
    #gpiozero is EDGE only, not level...  I want to detect either
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

      #gpiozero is EDGE only, not level...  I want to detect either
      #and since the edge event is threaded we have to test again after we install to avoid a race
      #note that active may get called twice, so we check done() on the future
      if self.value == int(not inverse):
        active()
      
    await asyncio.wait_for(f, timeout=timeout)

  def wait_for_inactive(self, timeout=None):
    return self.wait_for_active(inverse=True, timeout=timeout)

async def main():

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


  def handler(signum, frame):
    log.warn('Signal handler called with signal', signum)
    # Raises SystemExit(0):
    sys.exit(0)

  signal.signal(signal.SIGINT, handler)
  signal.signal(signal.SIGTERM, handler)



  try:
    log.info('Starting')

    airvac = gpiozero.DigitalOutputDevice(14, active_high=False)
    sapvac = gpiozero.DigitalOutputDevice(15, active_high=False)
    sapfloat = AsyncDigitalInputDevice(18, pull_up=True, active_state=None)
    romain = gpiozero.DigitalOutputDevice(23, active_high=False)
    rossr = gpiozero.PWMOutputDevice(24, active_high=True, frequency=.3)
    outvalve = gpiozero.DigitalOutputDevice(25, active_high=False)

    log.info('Setting Watchdog')
    watchdog=watchdogdev.watchdog('/dev/watchdog')
    watchdog.set_timeout(5)
    if watchdog.get_boot_status():
      log.error('Last boot was from Watchdog!!')

    romain.on()
    rossr.value=1
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


  except:
    log.exception('unhandled exception')
    raise

  finally:
    airvac.off()
    sapvac.off()
    romain.off()
    rossr.off()
    outvalve.off()
    watchdog.magic_close()


if __name__ == '__main__':


  asyncio.run(main())

