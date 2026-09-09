import gradio as gr

class PrettyGradioError(gr.Error):
    """gr.Error whose console traceback preserves real newlines.

    Why: gr.Error.__str__ returns repr(self.message), which escapes newlines
    when Python prints the uncaught-exception line — worker tracebacks become
    a single line of `\\n` literals in the server console.
    """
    def __str__(self):
        return str(self.message)
