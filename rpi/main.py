
#rshell -p /dev/ttyACM0 --buffer-size 512 cp main.py /pyboard



import utime, machine

tempadc = machine.ADC(4)
adc0 = machine.ADC(machine.Pin(26))
while True:
   temp = 27-(tempadc.read_u16() * 3.3 / 65535 - 0.706)/0.001721
   adc = adc0.read_u16() * 3.3 / 65535
   print('{"temp": %f, "adc0": %f}'%(temp, adc))
   utime.sleep(0.05)
