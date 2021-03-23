
#rshell -p /dev/ttyACM0 --buffer-size 512 cp main.py /pyboard
#rshell -p /dev/ttyACM0 --buffer-size 512 repl


from machine import Pin, PWM, ADC
from PID import PID
from rotary_irq_esp import RotaryIRQ
import time
from math import exp

r=RotaryIRQ(1,0,half_step=True)
#pidi = PID(16, 115, .5, setpoint=0, sample_time=0.1, output_limits=(-10, 10), proportional_on_measurement = False)
#pidp = PID(.39, .37, .1, setpoint=0, sample_time=0.1, output_limits=(-.2, .2), proportional_on_measurement = True)
pidv = PID(4.1, 70, .06, setpoint=0, sample_time=0.1, output_limits=(-10, 10), proportional_on_measurement = False)
pidp = PID(2, 0, .45, setpoint=0, sample_time=0.1, output_limits=(-2, 2), proportional_on_measurement = False)
adc=ADC(1)
p1=Pin(26, Pin.OUT)
p2=Pin(22, Pin.OUT)

p1.value(0)
p2.value(0)

while 1:
 pass

pwm1 = PWM(p1)
pwm1.freq(43000)
pwm2 = PWM(p2)
pwm2.freq(43000)


def setvoltage(v):
  pwm1.duty_u16(65535)
  pwm2.duty_u16(65535)
  if not v:
    return
  vp=v
  if v < 0:
    vp = -v
  vp = vp / 10 #10 volt rail
  vp = min(1, vp)
  vp = 65535-int(vp*65535)
  if v < 0:
    pwm2.duty_u16(vp)
  else:
    pwm1.duty_u16(vp)
  
setvoltage(0)


def getpos():
  return r.value()/1080

def getvel():
  p1 = getpos()
  time.sleep(.01)
  return (getpos()-p1)*100

zc=0
def readIraw():
  return (adc.read_u16()/65536*3.3*5.7/4.7-2.5)/1.9*5 - zc

zc2=0
for i in range(10):
  time.sleep(.03)
  zc2 += readIraw()
zc=zc2/10

class avgr():
  def __init__(self, tc, f):
    self.tc=tc
    self.f=f
    self.lastt = time.ticks_ms()
    self.lastv = f()
    
  def __call__(self):
    t = time.ticks_ms()
    v = self.f()
    dt = time.ticks_diff(t, self.lastt)
    self.lastt = t
    x = 1-exp(-dt/self.tc)
    self.lastv += (v-self.lastv) * x
    return self.lastv

readI = avgr(30, readIraw)


def autotune(swing=4, readf=readI, control=setvoltage, limit=.1, exf=None):
  v=swing
  tl=0
  llt=0
  while 1:
    sp = limit
    if v < 0:
      sp=-sp
    control(v, sp)
    peak = 0
    peakt = None
    lc=0
    while 1:
      if exf:
        exf(sp)
      lc+=1
      i=readf()  
      if v > 0 and i > peak or v < 0 and i < peak:
        peak = i
        peakt = time.ticks_ms()
      if v > 0 and i > limit or v < 0 and i < -limit:
        t = time.ticks_ms()
        dt = time.ticks_diff(t, tl)

        ku=v/peak
        tu=(dt+llt)/1000
        print('swap dt ', dt, 'peak/t ', peak, time.ticks_diff(peakt, tl), 'loopcount ', lc, 'ku', ku, 'tu ', tu)
        #https://en.wikipedia.org/wiki/Ziegler%E2%80%93Nichols_method
        print(.6*ku, 1.2*ku/tu, .075*ku*tu)
        v=-v
        tl=t
        llt=dt
        break


#pidi
#autotune(limit=.15)

#pidv
#autotune(swing=7, readf=getvel, control=lambda v, sp: setvoltage(v+sp*60/130*12), limit=1)

def s2():
  i=readI()
  vset = pidi(i)  
  setvoltage(vset)
#  print(i, vset)

def s1(v):
#  print(v)
  pidi.setpoint=v

#pidp on i
#autotune(swing=.2, readf=getpos, control=s1, limit=.3, exf=s2)


def s2(sp):
  i=getvel()
  vset = pidv(i) + sp*60/130*12
  setvoltage(vset)
  print(i, vset)

def s1(v, sp):
#  print(v)
  pidv.setpoint=v

#pidp on v
#autotune(swing=1, readf=getpos, control=s1, limit=.3, exf=s2)


while 1:
  print('homing')
  setvoltage(3)
  while readI() < .2:
    pass
  setvoltage(0)
  r.set(value=0)
  print('homing back')
  setvoltage(-6)

  t=time.ticks_ms()
  while getpos() > -1:
    if time.ticks_diff(time.ticks_ms(), t) > 2000:
      print('stuck. at back?')
      setvoltage(8)
      time.sleep(1)
      break
  else:
    break

print('asdf')      
setvoltage(0)
time.sleep(1)
print(getpos())

setvoltage(-3)
while readI() > -.2:
  pass
setvoltage(0)
time.sleep(1)
print(getpos())


while 1:
 pass




vset=0
oldr=getpos()
i=0
while 1:
  if time.time()%10>5:
    pidp.setpoint=1
  else:
    pidp.setpoint=0
  p = getpos()
  vel = (p-oldr)/.05*60
  oldr = p

  oo=vset
  velset = pidp(p)

  i=getvel()
  vset = pidv(i)
  print('pos % 1.2f voltset % 2.2f iread % 1.2f r % 4.1f vel % 3.1f, iset % 1.2f'%(p,vset,i, -100 if not i else oo/i, vel, velset))
#  vset+=vel/130*12
  setvoltage(vset)
  pidv.setpoint=velset
  time.sleep(.05)

