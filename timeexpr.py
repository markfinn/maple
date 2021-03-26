import util
import time
import asyncio
import contextlib
import math

class TimeWatchableExpression(util.WatchableExpression):
    class TIME():
        def __init__(self):
            self.maxtimewait = .1

        @contextlib.asynccontextmanager
        async def watch(self):
            queue = asyncio.Queue()
            try:
                async def f():
                    while 1:
                        await queue.put(None)
                        await asyncio.sleep(self.maxtimewait)
                t = asyncio.create_task(f())
                yield queue
            finally:
                t.cancel()

        @property
        def value(self):
            return time.time()

    def __init__(self, exprfunc, **kwargs):
        t = TimeWatchableExpression.TIME()
        super().__init__(exprfunc, t=t, **kwargs)

class AveragedWatchableExpression(TimeWatchableExpression):
  def __init__(self, exprfunc, tc, *, valAndTime, **kwargs):
    avg = None

    def update(old, new, dt):
      x = 1 - math.exp(-dt / tc)
      return old + (new - old) * x

    def valuefunc(valAndTime, t):
      val, treading = valAndTime
      nonlocal avg
      if tc:
        if avg is None:
          avg = val, treading
        else:
          dt = treading - avg[1]
          avg = update(avg[0], val, dt), treading

        dt = t - avg[1]
        if dt:
          val = update(avg[0], val, dt)

      if exprfunc:
        val = exprfunc(val)
      return val

    # tolerance has to be None so that we dont miss the time of the similar samples.
    super().__init__(valuefunc, valAndTime=valAndTime, tolerance=None, **kwargs)


class ADCPoll(util.WatchableExpression):
  class InnerADC():#provides value and watch, although watch is degenerate and only meant to be used in ADCPoll
    def __init__(self, adc, channel, samplePeriod, tolerance=None):
      self.t = None
      self.value = adc.read_adc(channel, gain=1), time.time()
      self._queue = asyncio.Queue()
      async def aw():
        while True:
          self.value = adc.read_adc(channel, gain=1), time.time()
          if self._queue.empty():
            await self._queue.put(None)
          await asyncio.sleep(samplePeriod)
      self.t = asyncio.create_task(aw())

    @contextlib.asynccontextmanager
    async def watch(self):
      try:
        yield self._queue
      finally:
        self.t.cancel()
        self.t = None

    def __del__(self):
      if self.t:
        self.t.cancel()

  def __init__(self, adc, channel, *, samplePeriod=.1, tc=0, scalefunc=None, tolerance=None):
    self.innerADC = None
    def valuefunc(val):
      if scalefunc:
        val = scalefunc(val)
      return val


    self.innerADC = ADCPoll.InnerADC(adc, channel, samplePeriod)

    if tc:
      # if tc is nonzero use an averager and wrap it so we can still have a tolerance
      e = AveragedWatchableExpression(None, valAndTime=self.innerADC, tc=tc, dontclosewatched=True)
      super().__init__(valuefunc, val=e, tolerance=tolerance)
    else:
      #otherwise we just are the expression directly
      super().__init__(valuefunc, valAndTime=self.innerADC, tc=tc, dontclosewatched=True)

  def __del__(self):
    if self.innerADC and self.innerADC.t:
      self.innerADC.t.cancel()

