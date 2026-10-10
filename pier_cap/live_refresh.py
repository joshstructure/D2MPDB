"""Complete each notebook refresh in the callback that requested it.

Colab does not reliably service detached asyncio tasks after a cell or widget
callback returns. Draw and then calculate inline so initialization and edits
cannot be left waiting for a task that the host never resumes. Widget updates
are still sent in drawing-before-results order.
"""
from copy import deepcopy


class LatestRefresh:
    def __init__(self,geometry,calculate,draw,publish,error):
        self.geometry=geometry;self.calculate=calculate;self.draw=draw
        self.publish=publish;self.error=error
        self.generation=0;self.closed=False

    def submit(self,case):
        if self.closed:return
        self.generation+=1;generation=self.generation
        snapshot=deepcopy(case)
        try:
            self.draw(self.geometry(snapshot))
            if self.closed or generation!=self.generation:return
            result=self.calculate(snapshot)
            if not self.closed and generation==self.generation:self.publish(*result)
        except Exception as exc:
            if not self.closed and generation==self.generation:self.error(exc)

    def close(self):
        self.closed=True;self.generation+=1
