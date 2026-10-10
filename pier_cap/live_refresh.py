"""Draw first, calculate off the UI loop, and publish only the latest edit."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy


class LatestRefresh:
    def __init__(self,geometry,calculate,draw,publish,error):
        self.geometry=geometry;self.calculate=calculate;self.draw=draw
        self.publish=publish;self.error=error
        self.generation=0;self.task=None;self.executor=None;self.closed=False

    def submit(self,case):
        if self.closed:return
        self.generation+=1;generation=self.generation
        if self.task is not None:self.task.cancel()
        snapshot=deepcopy(case)
        try:loop=asyncio.get_running_loop()
        except RuntimeError:
            # Scripts/tests without a notebook event loop stay synchronous.
            try:
                self.draw(self.geometry(snapshot))
                self.publish(*self.calculate(snapshot))
            except Exception as exc:self.error(exc)
            return
        self.task=loop.create_task(self._run(snapshot,generation))

    async def _run(self,case,generation):
        try:
            # Coalesce a quick sequence of edits, including case restoration.
            await asyncio.sleep(.08)
            if self.closed or generation!=self.generation:return
            self.draw(self.geometry(case))
            # Yield so the browser can paint the new drawings and status.
            await asyncio.sleep(.01)
            if self.executor is None:
                self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='cap-checks')
            result=await asyncio.get_running_loop().run_in_executor(self.executor,self.calculate,case)
            if not self.closed and generation==self.generation:self.publish(*result)
        except asyncio.CancelledError:
            # A running worker owns only its snapshot, never widgets. Its result
            # is discarded; queued stale work is cancelled by the asyncio future.
            pass
        except Exception as exc:
            if not self.closed and generation==self.generation:self.error(exc)

    def close(self):
        self.closed=True;self.generation+=1
        if self.task is not None:self.task.cancel()
        if self.executor is not None:self.executor.shutdown(wait=False,cancel_futures=True)
