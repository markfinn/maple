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
import fcntl
from control import Maple

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
          for queue, loop in self._watchers.items():
            loop.call_soon_threadsafe(asyncio.create_task, queue.put((evid, d)))

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
        new_loop.run_until_complete(webapp.app.run_task(host="0.0.0.0", port=8443, certfile='fullchain.pem', keyfile='privkey.pem', debug=False, use_reloader=False, shutdown_trigger=shutdown_event.wait))


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


  try:
    await maple.wait(Maple.SHUTDOWN)
  finally:
    if webloop:
      webloop.call_soon_threadsafe(webshut.set)


######################################################3
if __name__ == '__main__':
  lock_file_pointer = os.open(f"/tmp/instance_maple.lock", os.O_WRONLY|os.O_CREAT|os.O_TRUNC)
  try:
    fcntl.lockf(lock_file_pointer, fcntl.LOCK_EX | fcntl.LOCK_NB)
  except IOError:
    log.error('already running another copy')
    raise
  os.write(lock_file_pointer, str(os.getpid()).encode())
  os.fsync(lock_file_pointer)

  try:
    asyncio.run(main())
  finally:
    fcntl.lockf(lock_file_pointer, fcntl.LOCK_UN)
    os.close(lock_file_pointer)

