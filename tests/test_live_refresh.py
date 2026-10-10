import unittest
from unittest.mock import patch
from pier_cap.live_refresh import LatestRefresh


class LatestRefreshTests(unittest.TestCase):
    def test_draw_precedes_checks_and_snapshot_is_isolated(self):
        events=[];source={'id':1}
        def draw(value):events.append(('draw',value));source['id']=99
        def calculate(case):events.append(('calculate',case['id']));return case['id'],
        driver=LatestRefresh(lambda c:c['id'],calculate,draw,
                             lambda n:events.append(('result',n)),self.fail)
        driver.submit(source)
        self.assertEqual(events,[('draw',1),('calculate',1),('result',1)])
        driver.close();driver.submit({'id':2})
        self.assertEqual(len(events),3)

    def test_errors_are_reported_and_next_refresh_recovers(self):
        for stage in ('geometry','draw','calculate','publish'):
            with self.subTest(stage=stage):
                errors=[];results=[]
                driver=LatestRefresh(lambda c:c,lambda c:(c,),lambda e:None,results.append,errors.append)
                original=getattr(driver,stage)
                def fail(*_):raise ValueError('test failure')
                setattr(driver,stage,fail);driver.submit(1)
                self.assertEqual(str(errors[0]),'test failure')
                self.assertFalse(results)
                setattr(driver,stage,original);driver.submit(2)
                self.assertEqual(results,[2]);driver.close()

    def test_reentrant_edit_cannot_publish_superseded_result(self):
        results=[]
        def calculate(case):
            if case==1:driver.submit(2)
            return case,
        driver=LatestRefresh(lambda c:c,calculate,lambda e:None,results.append,self.fail)
        driver.submit(1)
        self.assertEqual(results,[2]);driver.close()


class NotebookCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_running_loop_does_not_defer_refresh_until_callback_returns(self):
        # Colab may expose a running loop without advancing detached tasks once
        # a cell/widget callback ends. Verify completion BEFORE yielding to it.
        events=[]
        driver=LatestRefresh(lambda c:c,lambda c:(c,),
                             lambda c:events.append('draw'),lambda c:events.append('result'),self.fail)
        with patch('asyncio.get_running_loop',side_effect=AssertionError('must not schedule')):
            driver.submit({})
            self.assertEqual(events,['draw','result'])
        driver.close()

    async def test_notebook_initialization_edit_error_and_recovery_complete_inline(self):
        from pier_cap.widgets import CapNotebook
        from tests.test_end_grid import case
        with patch('IPython.display.display'):
            app=CapNotebook(case())
            try:
                self.assertFalse(app.calculating)
                self.assertTrue(app.cage.children)
                original=app.refresh_driver.calculate
                chart=app.cage_3d_widget
                def inspect_pending(c):
                    self.assertTrue(app.calculating)
                    self.assertIn('Calculating',app.register.value)
                    self.assertEqual(app.metrics.value,'')
                    self.assertTrue(app.case_report_button.disabled)
                    self.assertEqual(len([t for t in chart.data if (t.meta or {}).get('part')=='end_grid']),18)
                    return original(c)
                app.refresh_driver.calculate=inspect_pending
                app.end_grid.rows['horizontal']['count'].value=5
                self.assertFalse(app.calculating)
                self.assertIs(chart,app.cage_3d_widget)
                self.assertFalse(app.current.calculating)
                self.assertEqual(app.current.case['end_face_grid']['horizontal']['count'],5)
                self.assertFalse(app.case_report_button.disabled)
                self.assertIn('End-face',app.register.value)
                for index in range(7):
                    app.plot_tabs.selected_index=index
                    panel=app.plot_tabs.children[index]
                    if hasattr(panel,'children'):self.assertTrue(panel.children)
                    else:self.assertTrue(panel.value)
                def fail(_):raise ValueError('test calculation error')
                app.refresh_driver.calculate=fail;app.refresh()
                self.assertFalse(app.calculating)
                self.assertIn('test calculation error',app.banner.value)
                app.refresh_driver.calculate=original;app.refresh()
                self.assertFalse(app.calculating)
                self.assertIsNotNone(app.current)
                self.assertNotIn('Calculating',app.register.value)
            finally:app.close()
