"""An output-local, zero-row floating calculation control."""
import ipywidgets as W


STYLE = '''<style>
.cap-recalc-viewport { position: relative; overscroll-behavior: contain; }
.cap-recalc-dock {
  position: sticky; top: 10px; z-index: 100;
  height: 0 !important; min-height: 0 !important; flex: 0 0 0 !important;
  overflow: visible !important; pointer-events: none;
  display: flex; justify-content: flex-end;
}
.cap-recalc-button {
  pointer-events: auto; margin: 0 14px 0 0 !important;
  border-radius: 20px !important; font-weight: 600;
  box-shadow: 0 2px 8px #0003; opacity: 1 !important;
}
.cap-recalc-button:disabled { cursor: default; }
.cap-recalc-button:focus-visible { outline: 3px solid #244b83; outline-offset: 2px; }
</style>'''


class RecalcControl:
    def __init__(self, callback):
        self.button=W.Button(layout=W.Layout(width='158px',height='36px',flex='0 0 auto'))
        self.button.add_class('cap-recalc-button')
        self.button.on_click(callback)
        self.dock=W.Box([self.button],layout=W.Layout(width='100%',overflow='visible'))
        self.dock.add_class('cap-recalc-dock')
        self.style=W.HTML(STYLE,layout=W.Layout(display='none'))
        self.set_state('dirty')

    def set_state(self,state):
        self.state=state
        label,color,icon,disabled,tip={
            'dirty':('Recalc','danger','refresh',False,'Inputs changed. Update cap checks for the current layout.'),
            'running':('Calculating…','warning','hourglass-half',True,'Calculating the current layout. Additional runs are not queued.'),
            'done':('Calc done','success','check',True,'Results match the current inputs. This does not mean every design check passes.'),
            'error':('Retry calc','danger','exclamation-triangle',False,'Calculation failed. Review the message below, then retry.'),
            'invalid':('Check inputs','danger','exclamation-triangle',True,'Correct the input error below before calculating.'),
        }[state]
        self.button.description=label;self.button.button_style=color
        self.button.icon=icon;self.button.disabled=disabled;self.button.tooltip=tip

    def wrap(self,children):
        body=W.VBox(children,layout=W.Layout(width='100%',min_width='0',flex='0 0 auto'))
        # Colab sizes its output iframe to this content. A vh limit would feed
        # back into that height and progressively shrink the scroll viewport.
        root=W.VBox([self.style,self.dock,body],layout=W.Layout(
            width='100%',min_width='0',max_height='850px',overflow='auto'))
        root.add_class('cap-recalc-viewport')
        return root

    def close(self):
        for widget in (self.button,self.dock,self.style):widget.close()
