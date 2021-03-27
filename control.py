import sqlite3
import Adafruit_ADS1x15
import watchdogdev
from util import *

log = logging.getLogger('maple')

class Watchdog():
  def __init__(self):
    watchdog = watchdogdev.watchdog('/dev/watchdog')
    log.info('Setting Watchdog')
    watchdog.set_timeout(5)
    if watchdog.get_boot_status():
      log.error('Last boot was from Watchdog!!')  # not working?

    async def wd_alive():
      while True:
        watchdog.keep_alive()
        await asyncio.sleep(1)

    self.wd_task = asyncio.ensure_future(wd_alive())
    self.wd = watchdog

  def close(self):
    wd=self.wd
    if wd is None:
      return
    self.wd = None
    wd.keep_alive()
    self.wd_task.cancel()
    wd.magic_close()


class Maple():
  SHUTDOWN = 1
  RUN = 2
  def __init__(self):
    self._waiter = asyncio.Event()
    self.state = Maple.RUN

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


    watchdog = Watchdog()


    self.vacpump = OverridableDigitalOutputDevice(12, active_high=True)
    self.airvac = OverridableDigitalOutputDevice(14, active_high=False)
    self.sapvac = OverridableDigitalOutputDevice(15, active_high=True)

    self.outvalve = OverridableDigitalOutputDevice(13, 19, factory=HBValve)
    
    self.romain = OverridableDigitalOutputDevice(23, active_high=False)

    self.rossr = OverridableDigitalOutputDevice(24, active_high=True, frequency=1, factory = gpiozero.PWMOutputDevice)

    #self.outpump = OverridableDigitalOutputDevice(25, active_high=False)

    self.waterin = OverridableDigitalOutputDevice(7, active_high=False)

    #self.unused1 = OverridableDigitalOutputDevice(1, active_high=False)
    self.saprelease = OverridableDigitalOutputDevice(26, active_high=False)

    self.sapfloathigh = AsyncDigitalInputDevice(8, pull_up=True, active_state=None)
    self.sapfloat = AsyncDigitalInputDevice(18, pull_up=True, active_state=None)
    self.rofloat = AsyncDigitalInputDevice(16, pull_up=True, active_state=None, invert=True)
    self.iicadc = Adafruit_ADS1x15.ADS1015()

    self.setpressure = 140
    self.at_pressure_time = None
    self.runningTimeWithFloatOff = None

    self.saptime1, self.saptime2 = OnOffAverager.avgOfOutput(self.sapvac, tc=60)
    self.outtime1, self.outtime2 = OnOffAverager.avgOfOutput(self.outvalve, tc=60)
    self.rotime1, self.rotime2 = OnOffAverager.avgOfOutput(self.rossr)

    self.pressure = ADCPoll(self.iicadc, 0, tolerance=.1, samplePeriod=.05, tc=.2, scalefunc=lambda v: max(0, ((v / 500 * (47 + 10) / 47) - .5) * 200 / 4) + 6) #why the 6 offset?

    async def task_levelwatch():
      self.runningTimeWithFloatOff = None
      last = None
      while True:
        if self.rofloat.value:
          self.runningTimeWithFloatOff = 0
          last = None
        elif self.rossr.value:
          now = time.time()
          if last is not None:
            self.runningTimeWithFloatOff += now - last
          last = now
        else:
          last = None
        await asyncio.sleep(.09)

    task_levelwatch_t = watchedtask(task_levelwatch())


    async def task_ropump():
      #    self.setpressure = 0
      self.romain.on()
      while True:
        if self.pressure.value > self.setpressure:
          self.rossr.off()
          if self.at_pressure_time is None:
            self.at_pressure_time = time.time()
        else:
          if self.rofloat.value or self.runningTimeWithFloatOff is not None and self.runningTimeWithFloatOff < 15:
            self.rossr.on()
          else:
            self.rossr.off()
          if self.pressure.value < self.setpressure - 10:
            self.at_pressure_time = None

        await asyncio.sleep(.2)

    task_ropump_t = watchedtask(task_ropump())


    async def task_output():
      while True:
        self.outvalve.value = self.at_pressure_time is not None and time.time()-self.at_pressure_time > 30
        await asyncio.sleep(.2)

    task_output_t = watchedtask(task_output())


    async def task_sap():
      while True:
        log.info('Sap Pump off')
        self.sapvac.off()
        self.airvac.on()

        await self.sapfloat.wait_for_active()

        log.info('Sap Pump on')
        self.sapvac.on()
        self.airvac.off()
        self.saprelease.on()
        try:
          await self.sapfloathigh.wait_for_active(.9)
        except asyncio.TimeoutError:
          pass
        self.saprelease.off()
        self.airvac.on()

        try:
          await self.sapfloathigh.wait_for_active(2)
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

    async def task_wash():
      while True:
        self.waterin.off()

        await self.rofloat.wait_for_inactive()
        await self.sapfloat.wait_for_inactive()

        await asyncio.sleep(1)
        if self.sapfloat.value or self.rofloat.value or self.sapvac.value:
          continue

        self.waterin.on()

        try:
          await self.sapfloathigh.wait_for_active(2)
        except asyncio.TimeoutError:
          pass

    task_sap_t = watchedtask(task_sap())

    async def task_vac():
      await self.sapfloat.wait_for_inactive(600)

      while True:
        self.vacpump.on()

        await self.sapfloathigh.wait_for_active()

        log.info('Vac Pump off')
        self.vacpump.off()
  
        await self.sapfloathigh.wait_for_inactive(600)

    task_wash_t = watchedtask(task_wash())



    async def cleanup_task():
      log.info('Running')
      try:
        while 1:
          await asyncio.sleep(10)
      except SystemExit:
        log.info('SystemExit1')
      except asyncio.CancelledError:
        log.info('CancelledError2')
#        raise
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
        self.waterin.off()
        self.waterin.overmode = 0
        self.saprelease.off()
        self.saprelease.overmode = 0
        self.outvalve._dev.close() 
        watchdog.close()


        log.info('Shutdown')
        self.changestate(Maple.SHUTDOWN)

    cleanup_task_t = watchedtask(cleanup_task())


  def changestate(self, newstate):
    self.state = newstate
    self._waiter.set()
    self._waiter.clear()

  async def wait(self, state=None):
    if state is not None and self.state == state:
        return
    while 1:
      await self._waiter.wait()
      if state is None or self.state == state:
        return

