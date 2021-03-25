import unittest
from unittest.mock import patch, MagicMock, Mock, AsyncMock

import asyncio

import gpiozero
import gpiozero.pins.mock

#import sqlite3
#import Adafruit_ADS1x15
#import watchdogdev


class TestMaple(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        #gets the actual module for gpio, but set to mock mode
        self.pin_factory = gpiozero.pins.mock.MockFactory(pin_class=gpiozero.pins.mock.MockPWMPin)
        gpiozero.Device.pin_factory = self.pin_factory
        self.mock_gpiozero = gpiozero

        self.mock_sqlite3 = MagicMock()

        self.mock_Adafruit_ADS1x15 = MagicMock()
        self.mock_Adafruit_ADS1x15.ADS1015().read_adc.return_value=5

        self.mock_watchdogdev = MagicMock()
        self.mock_watchdogdev.watchdog().get_boot_status.return_value=0

        self.patch1 = patch.dict('sys.modules', gpiozero=self.mock_gpiozero, sqlite3=self.mock_sqlite3, Adafruit_ADS1x15=self.mock_Adafruit_ADS1x15, watchdogdev=self.mock_watchdogdev)
        self.patch1.start()

        #get these imported AFTER we mock sys.modules
        global control
        import control
        global main
        import main
        global webapp
        import webapp
        global util
        import util

    async def asyncSetUp(self):
        # start up the maintask

        #use a mock to get access to the Maple() that main instantiates so we can analyze its pins
        original = main.Maple
        self.Maple = None
        with patch('main.Maple') as m:
            def side_effect(*a, **kw):
                self.Maple = original(*a, **kw)
                return self.Maple

            m.side_effect=side_effect
            self.maintask = asyncio.create_task(main.main(None))

            #wait for a Maple to be instantiated or a crash
            while not self.Maple and not self.maintask.done():
                await asyncio.sleep(.01)
            if self.maintask.done():
                await self.maintask
            m.assert_called_once()

        self.pin_sapfloathigh = self.pin_factory.pins[8]
        self.pin_sapfloat = self.pin_factory.pins[18]
        self.pin_rofloat = self.pin_factory.pins[16]

        self.pin_vacpump = self.pin_factory.pins[12]
        self.pin_airvac = self.pin_factory.pins[14]
        self.pin_sapvac = self.pin_factory.pins[15]
        self.pin_romain = self.pin_factory.pins[23]
        self.pin_rossr = self.pin_factory.pins[24]
        self.pin_outpump = self.pin_factory.pins[25]
        self.pin_waterin = self.pin_factory.pins[7]



    def tearDown(self):
        self.maintask.cancel()
        self.patch1.stop()

    async def test_sap_pulse(self):
        await asyncio.sleep(1)
        #check out gpiozero states_and_times, probably better than this

        #short pulse
        self.assertTrue(self.pin_sapvac.state)
        self.pin_sapfloat.drive_low()
        await asyncio.sleep(.25)
        self.assertFalse(self.pin_sapvac.state)
        self.pin_sapfloat.drive_high()
        await asyncio.sleep(.25)
        self.assertFalse(self.pin_sapvac.state)
        await asyncio.sleep(19.25)
        self.assertFalse(self.pin_sapvac.state)
        await asyncio.sleep(.5)
        self.assertTrue(self.pin_sapvac.state)

if __name__ == '__main__':
    unittest.main()
