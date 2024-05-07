from filecmp import cmp
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
from mistralai.models.chat_completion import ChatMessage
import requests
import html2text
from bs4 import BeautifulSoup
from readability import Document as ReadDoc

from bot_engine import Bot

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from command_parser import CommandParser


bot = Bot()

def html_to_markdown(html):
    # Use Beautiful Soup to parse the HTML content
    # soup = BeautifulSoup(html, 'html.parser')
    readability_document = ReadDoc(html,positive_keywords=["section"])
    
    # Initialize html2text converter
    converter = html2text.HTML2Text()
    converter.ignore_links = False  # Set to True if you want to ignore converting links
    converter.ignore_images = True  # Set to False if you want to include images in Markdown
    converter.ignore_emphasis = False
    converter.body_width = 0  # Set to 0 to prevent wrapping of lines

    # Convert the HTML to Markdown
    markdown = converter.handle(readability_document.summary())
    return markdown

def web_to_markdown(url):
    # Get the HTML content of the URL
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3094.110 Safari/56.0.3"
    response = requests.get(url, headers={'User-Agent': user_agent})
    html = response.text
    return html_to_markdown(html)

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

  def strip_ansi(text):
    tmp = ""
    if type(text) == bytes:
      tmp = text.decode('utf-8')
    else:
      tmp = text
    """Remove ANSI escape sequences from a string."""
    ansi_escape = re.compile(r'''
        \x1b   # ESC
        \[     # [
        [0-?]* # 0 or more characters in the range 0 to ?
        [ -/]* # 0 or more characters in the range space to /
        [@-~]  # one character in the range @ to ~
    ''', re.VERBOSE)
    tmp = ansi_escape.sub('', tmp)
    ansi_escape = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', tmp)

  txt = ""
  curr_completion = -1
  def get_completions(txt):
    cmd = txt.split(' ')
    completions = []
    raw_completions = []
    prefix = cmd[-1]
    if len(cmd) == 1:
      if len(cmd[0]) > 0 and cmd[0][0] != "$":
        query = f"bash -ic 'compgen -c {cmd[0]}'"
        process = subprocess.Popen(query, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        raw_completions = stdout.decode().split('\n')
        raw_completions = [strip_ansi(item) for item in raw_completions if len(item) > 0]
    if len(cmd) > 1:
      if shutil.which(cmd[0]) is not None or cmd[0] == "cd":
        prefix = cmd[-1]
        if cmd[0] in ["cd", "ls"]:
            query = f"bash -ic 'compgen -d {prefix}'"
        else:
            query = f"bash -ic 'compgen -f {prefix}'"
        
        process = subprocess.Popen(query, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        raw_completions = stdout.decode().split('\n')
        raw_completions = [strip_ansi(item) for item in raw_completions if len(item) > 0]
        if len(prefix) == 0 or prefix[0] != ".":
            raw_completions = [item for item in raw_completions if item[0] != "."]
    raw_completions.sort()
    completions = [item[len(prefix):] if item.startswith(prefix) else item for item in raw_completions if item]

    return completions

  completions_orig = str("")
  @kb.add(Keys.Any)
  def _(event):
    nonlocal txt
    nonlocal curr_completion
    nonlocal completions_orig
    # if event.key != Keys.Tab:
    if re.match(r'^[\x20-\x7E]+$', event.data):
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
    # pprint.pprint(completions)
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
  

  last_output = ""
  def process_input(input):
    nonlocal last_output
    curr_completion = -1
    cmd = input.split(" ")
    res_txt = ""
    res_obj = {}
    # if cmd[0] == "switch":
    #   res = cmd_switch(input)
    if cmd[0] == "$context":
      messages = [ChatMessage(role="system", content=bot.instructions_parsed)] + bot.context[-bot.context_window:]
      colors = {"user": fg.yellow, "assistant": fg.magenta, "system": fg.cyan}
      messages_str = ""
      for message in messages:
        messages_str += fx.bold + colors[message.role] + message.role + ": " + fx.default + message.content + "\n"
      messages_str = messages_str.encode("utf-8")
      return {"content": messages_str, "format": "bash"}
    if cmd[0] == "$change_instruction":
      return {"source": "system", "input_preset": "submit_instruction " + bot.instructions}
    if cmd[0] == "$append":
      input = input[len("$append"):] + "\n" + last_output
    if cmd[0] == "$submit_instruction":
      bot.set_instructions(" ".join(cmd[1:]))
      return {}
    if cmd[0] == "$fetch":
      md = web_to_markdown(cmd[1])
      print(md)
      input = "I'm going to ask you some questions about this article:\n" + md 
    if cmd[0] == "$summarize":
      input = "Summarize this article:\n" + web_to_markdown(cmd[1])
    for i in range(len(cmd)):
      if len(cmd[i]) > 0:
        if cmd[i][0] == "~":
          cmd[i] = re.sub(r'^~', os.path.expanduser('~'), cmd[i])
    if cmd[0] == "cd":
      os.chdir(cmd[1])
      return None
    if shutil.which(cmd[0]) is not None and cmd[0] != "write":
      if cmd[0] in ["ls", "cat"]:
        if cmd[0] == "ls":
          cmd.append("--color=always")
        res_txt = subprocess.run(cmd, capture_output=True).stdout
        res_obj = {"source": "console", "format": "bash", "content": res_txt}

        if cmd[0] == "cat":
          res_txt = res_txt.decode('utf-8').strip()
          path = "# file: " + cmd[1] + "\n"
          res_obj = {"source": "console", "format": "code", "language": "python", "content": path+res_txt}
        return res_obj
      else:
        process = subprocess.Popen(cmd, stdout=None, stderr=None)
        process.wait()
        res_txt = str(process.returncode)

    if res_txt == "" and len(cmd) > 1:
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
          print(fx.bold + fg.magenta +'🤖 AI:' + fx.default)
      if "format" in res:
        if res["format"] == "markdown":
          csl.print(CustomMarkdown(res["content"], code_theme="tomorrownighteighties", inline_code_theme="tomorrownighteighties"))
        elif res["format"] == "bash":
          print(res["content"].decode('utf-8').strip())
        elif res["format"] == "code":
          csl.print(Syntax(res["content"], res["language"], theme=TomorrowNightTheme(), line_numbers=False))
        
        last_output = strip_ansi(res["content"])
      
    
      if "input_preset" in res:
        input_preset = res["input_preset"]

if __name__ == '__main__':
  main()
