import aiosqlite
import time
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
  NOTRUN = 0
  STARTING = 1
  RUNNING = 2
  SHUTDOWN = 3
  def __init__(self):
    self._waiter = asyncio.Event()
    self.state = Maple.NOTRUN


  def eventdb(self, type, state, t=None):
    if t is None:
      t = time.time()
    asyncio.create_task(self.db.execute('insert into events (time, type, state) VALUES (?,?,?)', (time, type, state)))

  async def run(self, shutdown):

    self.changestate(Maple.STARTING)

    self.db = await aiosqlite.connect('/home/mark/maple/db.sq3')
    await self.db.execute('''
    CREATE TABLE IF NOT EXISTS events (
        time REAL NOT NULL,
        type TEXT NOT NULL,
        state TEXT
    );''')

    self.eventdb('prog', 'start')

    watchdog = Watchdog()

    self.vacpump = OverridableDigitalOutputDevice(12, active_high=True)
    self.airvac = OverridableDigitalOutputDevice(14, active_high=False)
    self.sapvac = OverridableDigitalOutputDevice(15, active_high=False)

    self.romain = OverridableDigitalOutputDevice(23, active_high=False)

    self.rossr = OverridableDigitalOutputDevice(24, active_high=True, frequency=1, factory = gpiozero.PWMOutputDevice)

    self.outpump = OverridableDigitalOutputDevice(25, active_high=False)

    self.waterin = OverridableDigitalOutputDevice(7, active_high=False)

    #self.unused1 = OverridableDigitalOutputDevice(1, active_high=False)
    #self.primepump = OverridableDigitalOutputDevice(20, active_high=False)


    self.sapfloathigh = AsyncDigitalInputDevice(8, pull_up=True, active_state=None)
    self.sapfloat = AsyncDigitalInputDevice(18, pull_up=True, active_state=None)
    self.rofloat = AsyncDigitalInputDevice(16, pull_up=True, active_state=None, invert=True)
    self.iicadc = Adafruit_ADS1x15.ADS1015()

    self.setpressure = 140
    self.at_pressure_time = None
    self.runningTimeWithFloatOff = None

    self.saptime1, self.saptime2 = OnOffAverager.avgOfOutput(self.sapvac)
    self.outtime1, self.outtime2 = OnOffAverager.avgOfOutput(self.outpump)
    self.rotime1, self.rotime2 = OnOffAverager.avgOfOutput(self.rossr)

    self.pressure = ADCPoll(self.iicadc, 0, tolerance=.1, samplePeriod=.05, tc=.2, scalefunc=lambda v: max(0, ((v / 500 * (47 + 10) / 47) - .5) * 200 / 4) + 6) #why the 6 offset?

    def xx(t, pressure, STATIC=[None]):
      if pressure >= 130 and STATIC[0] is None:
        STATIC[0] = t
      elif pressure < 130:
        STATIC[0] = None

      return 0 if STATIC[0] is None else t - STATIC[0]

    self.at_pressure_time2 = TimeWatchableExpression(xx, pressure=self.pressure)

    async def task_levelwatch(maple):
      maple.runningTimeWithFloatOff = None
      last = None
      while True:
        if maple.rofloat.value:
          maple.runningTimeWithFloatOff = 0
          last = None
        elif maple.rossr.value:
          now = time.time()
          if last is not None:
            maple.runningTimeWithFloatOff += now - last
          last = now
        else:
          last = None
        await asyncio.sleep(.09)

    task_levelwatch_t = watchedtask(task_levelwatch(self))


    async def task_ropump(maple):
      #    maple.setpressure = 0
      maple.romain.on()
      maple.rossr.off()
      while True:
        await maple.pressure.waittrue(lambda p: p > maple.setpressure)
        maple.rossr.off()
        if maple.at_pressure_time is None:
          maple.at_pressure_time = time.time()


        await maple.pressure.waittrue(lambda p: p < maple.setpressure-1)
        if maple.rofloat.value or maple.runningTimeWithFloatOff is not None and maple.runningTimeWithFloatOff < 15:
          maple.rossr.on()
        else:
          maple.rossr.off()
          await maple.rofloat.wait_for_active()

        if maple.pressure.value < maple.setpressure - 10:
          maple.at_pressure_time = None

    task_ropump_t = watchedtask(task_ropump(self))


    async def task_output(maple):
      while True:
        if maple.at_pressure_time is not None and time.time()-maple.at_pressure_time > 30:
          maple.outpump.on()
        else:
          maple.outpump.off()
        await asyncio.sleep(.2)

    task_output_t = watchedtask(task_output(self))


    async def task_sap(maple):
      while True:
        log.info('Sap Pump off')
        maple.sapvac.off()
        maple.airvac.on()

        await maple.sapfloat.wait_for_active()

        log.info('Sap Pump on')
        maple.sapvac.on()

        try:
          await maple.sapfloathigh.wait_for_active(20)
        except asyncio.TimeoutError:
          pass
        if not maple.sapfloat.value:
          continue
        await asyncio.wait([
          asyncio.create_task(maple.sapfloat.wait_for_inactive()),
          asyncio.create_task(maple.sapfloathigh.wait_for_active())
        ], timeout=25, return_when=asyncio.FIRST_COMPLETED)
        if not maple.sapfloat.value:
          continue
        maple.airvac.off()
        await asyncio.sleep(5)
  
        await maple.sapfloat.wait_for_inactive(120)

    task_sap_t = watchedtask(task_sap(self))

    async def task_vac(maple):
      await maple.sapfloat.wait_for_inactive(600)

      while True:
        maple.vacpump.on()

        await maple.sapfloathigh.wait_for_active()

        log.info('Vac Pump off')
        maple.vacpump.off()
  
        await maple.sapfloathigh.wait_for_inactive(600)

    task_vac_t = watchedtask(task_vac(self))

#   die_task_t = watchedtask(asyncio.sleep(3*3600))


    try:
      log.info('Running')
      self.changestate(Maple.RUNNING)
      self.eventdb('prog', 'run')
      await shutdown.wait()

    finally:
      self.eventdb('prog', 'stopping')
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
      self.outpump.off()
      self.outpump.overmode = 0

      watchdog.close()

      self.eventdb('prog', 'stopped')
      await self.db.close()

      log.info('Shutdown')
      self.changestate(Maple.SHUTDOWN)

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

