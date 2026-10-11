"""Draw edits immediately; calculate the latest draft only on explicit request.

Both operations finish in their requesting callback. No detached tasks or
queued automatic calculations depend on Colab resuming background work.
"""
from copy import deepcopy


class LatestRefresh:
    def __init__(self,geometry,calculate,draw,publish,error):
        self.geometry=geometry;self.calculate=calculate;self.draw=draw
        self.publish=publish;self.error=error
        self.generation=0;self.closed=False;self.running=False;self.dirty=True
        self.pending=None

    def submit(self,case):
        if self.closed:return
        self.generation+=1;generation=self.generation
        self.dirty=True;self.pending=None
        snapshot=deepcopy(case)
        try:
            self.draw(self.geometry(snapshot))
            if not self.closed and generation==self.generation:self.pending=snapshot
        except Exception as exc:
            if not self.closed and generation==self.generation:self.error(exc)

    def recalculate(self):
        if self.closed or self.running or not self.dirty or self.pending is None:return
        generation=self.generation;snapshot=deepcopy(self.pending)
        self.running=True
        try:
            result=self.calculate(snapshot)
            if not self.closed and generation==self.generation:
                self.publish(*result)
                self.dirty=False
        except Exception as exc:
            if not self.closed and generation==self.generation:self.error(exc)
        finally:self.running=False

    def close(self):
        self.closed=True;self.generation+=1;self.pending=None
