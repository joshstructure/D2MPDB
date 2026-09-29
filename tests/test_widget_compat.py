import unittest
import ipywidgets as W
from pier_cap.widget_compat import Tab, Accordion


class ContainerCompatibilityTests(unittest.TestCase):
    def test_titles_and_selection_survive_child_changes(self):
        for cls in (Tab, Accordion):
            with self.subTest(container=cls.__name__):
                first, second = W.HTML('one'), W.HTML('two')
                container = cls(children=[first, second])
                try:
                    container.set_title(0, 'Inputs')
                    container.set_title(1, 'Plots')
                    self.assertEqual(list(container.get_state()['titles']), ['Inputs','Plots'])
                    container.selected_index = 1
                    self.assertEqual(container.selected_index, 1)
                    container.children = [first]
                    self.assertEqual(list(container.get_state()['titles']), ['Inputs'])
                    container.children = [first, second]
                    container.set_title(1, 'Results')
                    self.assertEqual(list(container.get_state()['titles']), ['Inputs','Results'])
                finally:
                    container.close(); first.close(); second.close()
