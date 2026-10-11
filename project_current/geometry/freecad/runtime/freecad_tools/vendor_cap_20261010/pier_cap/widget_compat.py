"""Selection containers compatible with Colab's mixed widget protocol.

Colab's shipped controls manager reads ``titles`` even when the Python
runtime is ipywidgets 7, which sends ``_titles``. Keep both representations
in sync; ordinary ipywidgets 8 uses its native implementation unchanged.
"""
import ipywidgets as W
from traitlets import List, Unicode


class _LegacyTitles:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sync_titles()
        self.observe(self._children_titles_changed, names='children')

    def _sync_titles(self):
        self.titles = [self.get_title(i) or '' for i in range(len(self.children))]

    def _children_titles_changed(self, change):
        self._sync_titles()
        if self.selected_index is not None and self.selected_index >= len(self.children):
            self.selected_index = 0 if self.children else None

    def set_title(self, index, title):
        super().set_title(index, title)
        self._sync_titles()


if 'titles' in W.Tab.class_traits():
    Tab = W.Tab
    Accordion = W.Accordion
else:
    class Tab(_LegacyTitles, W.Tab):
        titles = List(Unicode()).tag(sync=True)

    class Accordion(_LegacyTitles, W.Accordion):
        titles = List(Unicode()).tag(sync=True)
