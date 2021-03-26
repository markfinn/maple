import unittest
from unittest.mock import patch, MagicMock, Mock, AsyncMock

import asyncio

import gpiozero
import gpiozero.pins.mock
import time
import math

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

        self.pressure = 100
        self.mock_Adafruit_ADS1x15.ADS1015().read_adc.side_effect=lambda ch, gain: ((self.pressure - 6)*4/200 +.5)*47/(47+10)*500

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
        #set web app to test mode
        webapp.app.testing = True
        self.web = webapp.app.test_client()

        # start up the maintask

        #use a mock to get access to the Maple() that main instantiates so we can analyze its pins
        original = main.Maple
        self.maple = None
        with patch('main.Maple') as m:
            def side_effect(*a, **kw):
                self.maple = original(*a, **kw)
                return self.maple

            m.side_effect=side_effect
            self.maintask = asyncio.create_task(main.main(8444))

            #wait for a Maple to be instantiated or a crash
            while not self.maple and not self.maintask.done():
                await asyncio.sleep(.01)
            if self.maintask.done():
                await self.maintask
            m.assert_called_once()

            await self.maple.wait(self.maple.RUNNING)

        # wait for the webserver thread to get its loop assigned
        for i in range(100):
            try:
                self.webloop = main.webloop
                self.webshut = main.webshut
                self.webthread = main.webthread
                self.mainshut = main.mainshut
                break
            except AttributeError:
                if i < 98:
                    await asyncio.sleep(.05)
                    continue
                raise

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


    async def asyncTearDown(self):
        self.mainshut.set()
        self.webloop.call_soon_threadsafe(self.webshut.set)
        await self.maintask
        self.webthread.join()

    def tearDown(self):
        self.patch1.stop()

    async def test_pressure_avg(self):
        self.assertEqual(self.maple.pressure.value, 100)
        self.pressure=200
        t = time.time()
        for i in range(10):
            await asyncio.sleep(.2)
            self.assertAlmostEqual(self.maple.pressure.value, 100 + 100 * (1-math.exp((t-time.time())/.2)), delta=1/(i+1))

        async with self.maple.pressure.watch() as q:
            v = await q.get()
            self.pressure = 100
            t = time.time()
            self.assertAlmostEqual(v, 200 - 100 * (1-math.exp((t-time.time())/.2)), delta=1/(i+1))
            self.assertAlmostEqual(self.maple.pressure.value, 200 - 100 * (1-math.exp((t-time.time())/.2)), delta=1/(i+1))


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


    async def test_web_start(self):
        response = await util.runinotherloop(self.web.get('/'), self.webloop)
        self.assertEqual(response.status_code, 302)
        response = await util.runinotherloop(self.web.get('/api/inputs'), self.webloop)
        self.assertEqual(response.status_code, 200)


    async def test_web_inputs(self):
        response = await util.runinotherloop(self.web.get('/api/inputs'), self.webloop)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({'rofloat': True, 'sapfloat': False, 'sapfloathigh': False}, await response.json)
        self.pin_sapfloat.drive_low()
        await asyncio.sleep(.25)
        response = await util.runinotherloop(self.web.get('/api/inputs'), self.webloop)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({'rofloat': True, 'sapfloat': True, 'sapfloathigh': False}, await response.json)
        self.pin_sapfloat.drive_high()
        await asyncio.sleep(.25)
        response = await util.runinotherloop(self.web.get('/api/inputs'), self.webloop)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({'rofloat': True, 'sapfloat': False, 'sapfloathigh': False}, await response.json)

if __name__ == '__main__':
    unittest.main()
