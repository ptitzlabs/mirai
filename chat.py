import os
import re
import subprocess
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.document import Document
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML, ANSI
from prompt_toolkit.history import InMemoryHistory
import pprint

from rich.console import Console
from custommarkdown import CustomMarkdown, TomorrowNightTheme
from rich.syntax import Syntax, PygmentsSyntaxTheme
from rich.theme import Theme
from console import fg, bg, fx
from termcolor import colored
import shutil
import textwrap

from bot_engine import Bot

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from command_parser import CommandParser

bot = Bot()

def main():
  # Create custom key bindings
  kb = KeyBindings()
  history = InMemoryHistory()

  tomorrow_night_eighties_theme = {
      "text": "bold #cccccc",  # Default text color (s:foreground)
      "background_color": "#2d2d2d",  # Background color (s:background)
      "comment": "italic #999999",  # Comments color (s:comment)
      "red": "bold #f2777a",  # Red elements
      "orange": "bold #f99157",  # Orange elements
      "yellow": "bold #ffcc66",  # Yellow elements
      "green": "bold #99cc99",  # Green elements
      "aqua": "bold #009999",  # Aqua elements
      "blue": "bold #99cccc",  # Blue elements
      "purple": "bold #cc99cc",  # Purple elements
  }
  csl = Console(theme=Theme(tomorrow_night_eighties_theme), force_terminal=True)

  txt = ""
  curr_completion = -1
  def get_completions(txt):
    cmd = txt.split(' ')
    completions = []
    if len(cmd) > 1:
        if shutil.which(cmd[0]) is not None or cmd[0] == "cd":
            prefix = cmd[-1]
            if cmd[0] in ["cd", "ls"]:
                query = f"bash -ic 'compgen -d {prefix}'"
            else:
                query = f"bash -ic 'compgen -f {prefix}'"
            
            process = subprocess.Popen(query, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            # Split the output by new lines and strip the prefix
            raw_completions = stdout.decode().split('\n')
            # Use str.startswith to check if the item starts with the prefix and then strip it
            completions = [item[len(prefix):] if item.startswith(prefix) else item for item in raw_completions if item]

    return completions

  completions_orig = str("")
  @kb.add(Keys.Any)
  def _(event):
    nonlocal txt
    nonlocal curr_completion
    nonlocal completions_orig
    event.app.current_buffer.insert_text(event.data)
    txt = event.app.current_buffer.text
    curr_completion = -1
    completions_orig = txt

  @kb.add(Keys.Tab)
  def handle_tab(event):
    nonlocal curr_completion
    nonlocal completions_orig
    if curr_completion == -1:
      completions_orig = txt
    completions = get_completions(completions_orig)
    if len(completions) > 0:
      curr_completion = (curr_completion + 1) % len(completions)
      line = completions_orig + completions[curr_completion]
      event.app.current_buffer.set_document(Document(line))
    # pprint.pprint(get_completions(txt))
    # event.app.current_buffer.set_document(Document(f'complete {event.app.current_buffer.text}', 0))


  def change_instruction():
    pass

  def pass_instruction():
    pass
  

  def process_input(input):
    curr_completion = -1
    cmd = input.split(" ")
    res_txt = ""
    res_obj = {}
    # if cmd[0] == "switch":
    #   res = cmd_switch(input)
    if cmd[0] == "change_instruction":
      return {"source": "system", "input_preset": "submit_instruction " + bot.instructions}
    if cmd[0] == "submit_instruction":
      bot.set_instructions(" ".join(cmd[1:]))
      return {}
    if cmd[0] == "cd":
      os.chdir(cmd[1])
      return None
    if shutil.which(cmd[0]) is not None and cmd[0] != "write":
      if cmd[0] == "ls":
        cmd.append("--color=always")
      res_txt = subprocess.run(cmd, capture_output=True).stdout
      res_obj = {"source": "console", "format": "bash", "content": res_txt}

      if cmd[0] == "cat":
        res_txt = res_txt.decode('utf-8').strip()
        path = "# file: " + cmd[1] + "\n"
        res_obj = {"source": "console", "format": "code", "language": "python", "content": path+res_txt}
      return res_obj

    if res_txt == "":
      res_obj = {"source": "chat", "format": "markdown", "content": bot.exec_query(input)}
    return res_obj 


  def get_git_branch():
    try:
      output = subprocess.check_output(['git', 'branch', '--show-current'], stderr=subprocess.STDOUT).decode().strip()
      return f'\x1b[0m ({output})'
    except subprocess.CalledProcessError:
      return ""

  def get_ps():
      home = os.path.expanduser('~')  # Expands the '~' to the full home directory path
      cwd = os.getcwd()               # Gets the current working directory
      if cwd.startswith(home):
          # Replace the home directory path with '~'
          cwd = cwd.replace(home, '~', 1)
      robot = '\U0001F916'
      robot = '⚙ '
      icon = '👾 '
      # robot = '♣ '
      parts = [
         icon,
         '\x1b[95m{',
         f'\x1b[90m{cwd}',
         '\x1b[95m}',
         get_git_branch(),
         colored("$ ", 'cyan')]
      return ''.join(parts)
  last_output = ""
  def strip_ansi(text):
    """Remove ANSI escape sequences from a string."""
    ansi_escape = re.compile(r'''
        \x1b   # ESC
        \[     # [
        [0-?]* # 0 or more characters in the range 0 to ?
        [ -/]* # 0 or more characters in the range space to /
        [@-~]  # one character in the range @ to ~
    ''', re.VERBOSE)
    return ansi_escape.sub('', text)
  input_preset = ""
  while True:
    # print(get_ps(), end="")
    user_input = prompt(ANSI(get_ps()), default=input_preset, key_bindings=kb, history=history, enable_history_search=True)
    if user_input.lower() == "exit":
      break
    input_preset = ""
    res = process_input(user_input)
    if res is not None:
      if "source" in res:
        if res["source"] == "chat":
          print(fx.bold + fg.magenta +'🤖 Bot:' + fx.default)
      if "format" in res:
        if res["format"] == "markdown":
          csl.print(CustomMarkdown(res["content"], code_theme="tomorrownighteighties", inline_code_theme="tomorrownighteighties"))
        elif res["format"] == "bash":
          print(res["content"].decode('utf-8').strip())
        elif res["format"] == "code":
          csl.print(Syntax(res["content"], res["language"], theme=TomorrowNightTheme(), line_numbers=False))
        print('\n')
    
    if "input_preset" in res:
      input_preset = res["input_preset"]

if __name__ == '__main__':
  main()
