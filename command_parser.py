import re
import json

class CommandParser:
  def __init__(self):
    self.callbacks = {}
    pass

  def add_callback(self, command_name, callback):
    self.callbacks[command_name] = callback

  def parse_commands(self,text):
    """Parse text for embedded commands using double square brackets."""
    pattern = r"\[\[(\w+)\s+({.*?})\]\]"
    matches = re.finditer(pattern, text, re.DOTALL)
    commands = []
    for match in matches:
      command_name = match.group(1)
      args = json.loads(match.group(2))
      commands.append((command_name, args, match.span()))
    return commands

  def execute_command(self,command, args):
    """Execute a command based on the command name and arguments."""
    # Define command functions
    if command in self.callbacks:
      return self.callbacks[command](**args)
    return "Command not found"

  def replace_commands_with_results(self, text):
    """Replace commands in the original text with their execution results."""
    # Parse commands and replace from end to start to not mess up indices
    for command, args, span in reversed(self.parse_commands(text)):
      result = self.execute_command(command, args)
      text = text[:span[0]] + result + text[span[1]:]
    return text