
from typing import ClassVar, Dict, Iterable, List, Optional, Type, Union
from rich.console import Console, ConsoleOptions, JustifyMethod, RenderResult
from rich.markdown import CodeBlock, Markdown, MarkdownContext, Link, UnknownElement
from rich.style import Style, StyleStack
from rich.segment import Segment
from rich.syntax import Syntax, PygmentsSyntaxTheme

from tomorrownighteighties import TomorrownighteightiesStyle

class TomorrowNightTheme(PygmentsSyntaxTheme):
    def __init__(self):
        super().__init__(TomorrownighteightiesStyle)

class CustomCodeBlock(CodeBlock):
    def __init__(self, lexer_name: str, theme: str) -> None:
        self.lexer_name = lexer_name
        if theme == "tomorrownighteighties":
          self.theme = TomorrowNightTheme()
        else:
          self.theme = theme
    
class CustomMarkdownContext(MarkdownContext):
    def __init__(
        self,
        console: Console,
        options: ConsoleOptions,
        style: Style,
        inline_code_lexer: Optional[str] = None,
        inline_code_theme: str = "monokai",
    )-> None:
        super().__init__(console, options, style, inline_code_lexer, inline_code_theme)
        if inline_code_theme == "tomorrownighteighties":
          self._syntax = Syntax("", inline_code_lexer, theme=TomorrowNightTheme())
        else:
          self._syntax = Syntax("", inline_code_lexer, theme=inline_code_theme)

class CustomMarkdown(Markdown):
  def __init__(
      self,
      markup: str,
      code_theme: str = "monokai",
      justify: Optional[JustifyMethod] = None,
      style: Union[str, Style] = "none",
      hyperlinks: bool = True,
      inline_code_lexer: Optional[str] = None,
      inline_code_theme: Optional[str] = None,
  ) -> None:
      super().__init__(markup, code_theme, justify, style, hyperlinks, inline_code_lexer, inline_code_theme)
      self.elements["code_block"] = CustomCodeBlock
  def __rich_console__(
      self, console: Console, options: ConsoleOptions
  ) -> RenderResult:
      """Render markdown to the console."""
      style = console.get_style(self.style, default="none")
      options = options.update(height=None)
      context = CustomMarkdownContext(
          console,
          options,
          style,
          inline_code_lexer=self.inline_code_lexer,
          inline_code_theme=self.inline_code_theme,
      )
      tokens = self.parsed
      inline_style_tags = self.inlines
      new_line = False
      _new_line_segment = Segment.line()

      for token in self._flatten_tokens(tokens):
          node_type = token.type
          tag = token.tag

          entering = token.nesting == 1
          exiting = token.nesting == -1
          self_closing = token.nesting == 0

          if node_type == "text":
              context.on_text(token.content, node_type)
          elif node_type == "hardbreak":
              context.on_text("\n", node_type)
          elif node_type == "softbreak":
              context.on_text(" ", node_type)
          elif node_type == "link_open":
              href = str(token.attrs.get("href", ""))
              if self.hyperlinks:
                  link_style = console.get_style("markdown.link_url", default="none")
                  link_style += Style(link=href)
                  context.enter_style(link_style)
              else:
                  context.stack.push(Link.create(self, token))
          elif node_type == "link_close":
              if self.hyperlinks:
                  context.leave_style()
              else:
                  element = context.stack.pop()
                  assert isinstance(element, Link)
                  link_style = console.get_style("markdown.link", default="none")
                  context.enter_style(link_style)
                  context.on_text(element.text.plain, node_type)
                  context.leave_style()
                  context.on_text(" (", node_type)
                  link_url_style = console.get_style(
                      "markdown.link_url", default="none"
                  )
                  context.enter_style(link_url_style)
                  context.on_text(element.href, node_type)
                  context.leave_style()
                  context.on_text(")", node_type)
          elif (
              tag in inline_style_tags
              and node_type != "fence"
              and node_type != "code_block"
          ):
              if entering:
                  # If it's an opening inline token e.g. strong, em, etc.
                  # Then we move into a style context i.e. push to stack.
                  context.enter_style(f"markdown.{tag}")
              elif exiting:
                  # If it's a closing inline style, then we pop the style
                  # off of the stack, to move out of the context of it...
                  context.leave_style()
              else:
                  # If it's a self-closing inline style e.g. `code_inline`
                  context.enter_style(f"markdown.{tag}")
                  if token.content:
                      context.on_text(token.content, node_type)
                  context.leave_style()
          else:
              # Map the markdown tag -> MarkdownElement renderable
              element_class = self.elements.get(token.type) or UnknownElement
              if token.tag == "code":
                element_class = CustomCodeBlock
              element = element_class.create(self, token)

              if entering or self_closing:
                  context.stack.push(element)
                  element.on_enter(context)

              if exiting:  # CLOSING tag
                  element = context.stack.pop()

                  should_render = not context.stack or (
                      context.stack
                      and context.stack.top.on_child_close(context, element)
                  )

                  if should_render:
                      if new_line:
                          yield _new_line_segment

                      yield from console.render(element, context.options)
              elif self_closing:  # SELF-CLOSING tags (e.g. text, code, image)
                  context.stack.pop()
                  text = token.content
                  if text is not None:
                      element.on_text(context, text)

                  should_render = (
                      not context.stack
                      or context.stack
                      and context.stack.top.on_child_close(context, element)
                  )
                  if should_render:
                      if new_line:
                          yield _new_line_segment
                      yield from console.render(element, context.options)

              if exiting or self_closing:
                  element.on_leave(context)
                  new_line = element.new_line