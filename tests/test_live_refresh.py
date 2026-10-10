import asyncio
import threading
import unittest
from unittest.mock import patch
from pier_cap.live_refresh import LatestRefresh


async def until(predicate,seconds=8):
    async with asyncio.timeout(seconds):
        while not predicate():await asyncio.sleep(.01)


class LatestRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_draw_precedes_checks_and_only_latest_running_result_publishes(self):
        events=[];started=threading.Event();release=threading.Event()
        def calculate(case):
            if case['id']==1:started.set();release.wait(5)
            return case['id'],
        driver=LatestRefresh(lambda c:c['id'],calculate,lambda n:events.append(('draw',n)),
                             lambda n:events.append(('result',n)),lambda exc:events.append(('error',str(exc))))
        try:
            driver.submit({'id':1});await until(started.is_set)
            self.assertEqual(events,[('draw',1)])
            driver.submit({'id':2});await until(lambda:('draw',2) in events)
            release.set();await driver.task
            self.assertEqual(events,[('draw',1),('draw',2),('result',2)])
        finally:release.set();driver.close()

    async def test_coalesces_edits_and_isolates_case_snapshot(self):
        results=[];draw=[];source={'id':1}
        driver=LatestRefresh(lambda c:c['id'],lambda c:(c['id'],),draw.append,results.append,lambda exc:None)
        try:
            driver.submit(source);source['id']=2;driver.submit(source);source['id']=99
            await driver.task
            self.assertEqual(draw,[2]);self.assertEqual(results,[2])
        finally:driver.close()

    async def test_error_is_explicit_and_close_discards_inflight_result(self):
        errors=[];results=[];started=threading.Event();release=threading.Event()
        def calculate(case):started.set();release.wait(5);return case,
        driver=LatestRefresh(lambda c:1/0,calculate,lambda e:None,results.append,errors.append)
        try:
            driver.submit({});await driver.task;self.assertIsInstance(errors[0],ZeroDivisionError)
            driver.geometry=lambda c:c;driver.submit({});await until(started.is_set)
            driver.close();release.set();await asyncio.sleep(.05)
            self.assertFalse(results)
        finally:release.set();driver.close()

    async def test_notebook_shows_new_grid_while_results_are_blank(self):
        from pier_cap.widgets import CapNotebook
        from tests.test_end_grid import case
        started=threading.Event();release=threading.Event()
        with patch('IPython.display.display'):
            app=CapNotebook(case())
            try:
                await app.refresh_driver.task
                original=app.refresh_driver.calculate
                def slow(c):started.set();release.wait(5);return original(c)
                app.refresh_driver.calculate=slow
                chart=app.cage_3d_widget
                app.end_grid.rows['horizontal']['count'].value=5
                self.assertTrue(app.calculating);self.assertIn('Calculating',app.register.value)
                self.assertEqual(app.metrics.value,'')
                await until(started.is_set)
                self.assertEqual(len([t for t in chart.data if (t.meta or {}).get('part')=='end_grid']),18)
                self.assertIs(chart,app.cage_3d_widget)
                self.assertTrue(app.case_report_button.disabled)
                release.set();await app.refresh_driver.task
                self.assertFalse(app.calculating);self.assertFalse(app.current.calculating)
                self.assertEqual(app.current.case['end_face_grid']['horizontal']['count'],5)
                self.assertFalse(app.case_report_button.disabled);self.assertIn('End-face',app.register.value)
            finally:release.set();app.close()
