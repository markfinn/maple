import gpiozero
from time import sleep
import logging

log = logging.getLogger('maple')
log.setLevel(logging.DEBUG)
#ch = logging.StreamHandler()
ch = logging.FileHandler('maple.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
log.addHandler(ch)



try:

 airvac = gpiozero.DigitalOutputDevice(14, active_high=False)
 sapvac = gpiozero.DigitalOutputDevice(15, active_high=False)
 sapfloat = gpiozero.DigitalInputDevice(18, pull_up=True, active_state=None)


 log.info('Starting')
 if sapfloat.value: 
   log.info('draining')
   sapvac.on()
   sapfloat.wait_for_inactive(10)
 sapvac.off()
 airvac.on()

 log.info('Running')
 while True:
  sapfloat.wait_for_active()
  log.info('Sap Pump on')

  sapvac.on()
  sleep(20)
  sapfloat.wait_for_inactive(120)
  log.info('Sap Pump off')
  sapvac.off()


except:
 log.exception('unhandled exception')
 raise
 