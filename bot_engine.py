import os
import re
import repl
import threading
import pprint
import json
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

from command_parser import CommandParser

class Bot:
  def __init__(
      self,
      name = "default",
      llm_type = "mistral",
      model = "mistral-tiny",
      instructions = "You are a helpful assistant",
      context_window = 20
      ):
    
    # self.replacer = repl.SimpleReplacer()
    # pattern = r'db:(?P<db_name>\w+):(?P<collection_name>\w+):(?:(?P<field_name_1>\w+):(?P<field_value_1>\w+)|.*|(?P<field_name_n>\w+):(?P<field_value_n>\w+))+'                  
    # self.replacer.rule(pattern, self.db_replacer)
    self.command_parser = CommandParser()
    self.command_parser.add_callback("db_parse", self.db_parse)

    self.db_uri = f"mongodb+srv://{os.getenv('MONGODB_CREDENTIALS')}@cluster0.fm3gace.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    self.db = MongoClient(self.db_uri, server_api=ServerApi("1")).get_database("llm")
    bot = self.db.get_collection("bots").find_one({"name": name})
    if bot is None:
      bot = {
        "name": name,
        "llm_type": llm_type,
        "model": model,
        "instructions": instructions,
        "context_window": context_window
      }
      self.db.get_collection("bots").insert_one(bot)
      self.db.get_collection("sessions").insert_one({"name": name, "session_id": 0, "messages": []})
    
    self.name = bot["name"]
    self.llm_type = bot["llm_type"]
    if self.llm_type == "mistral":
      self.llm = MistralClient(api_key=os.environ.get('MISTRAL_API_KEY'))
    self.model = bot["model"]
    self.instructions = bot["instructions"]
    self.instructions_parsed = self.command_parser.replace_commands_with_results(self.instructions)
    self.context_window = bot["context_window"]
    self.session_id = 0
    self.context = []
    self.download_context()


  def download_context(self):
    session = self.db.get_collection("sessions").find_one({"name": self.name, "session_id": self.session_id})
    if session:
      self.context = []
      if self.llm_type == "mistral":
          for message in session["messages"]:
            self.context.append(ChatMessage(role=message["role"], content=message["content"]))
  
  def db_parse(self, args):
    db_name = args["db_name"] if "db_name" in args else "llm"
    collection_name = args["collection_name"] if "collection_name" in args else "bots"
    output_format = args["format"] if "format" in args else "json_string"
    match = args["match"] if "match" in args else {}
    db = MongoClient(self.db_uri, server_api=ServerApi("1")).get_database(db_name)
    collection = db.get_collection(collection_name)
    document = collection.find_one(match)
    if output_format == "json_string":
      return json.dumps(document, indent=2)


  
  def upload_context(self):
    messages = []
    for message in self.context:
      messages.append({"role": message.role, "content": message.content})
    
    db = MongoClient(self.db_uri, server_api=ServerApi("1")).get_database("llm")
    db.get_collection("sessions").update_one({"name": self.name, "session_id": self.session_id}, {"$set": {"messages": messages}})
  
  def exec_query(self, query):
    if self.llm_type == "mistral":
      self.context.append(ChatMessage(role="user", content=query))
      messages = [ChatMessage(role="system", content=self.instructions_parsed)] + self.context[-self.context_window:]
      response = self.llm.chat(model=self.model, messages=messages)
      self.context.append(response.choices[0].message)
      thread = threading.Thread(target=self.upload_context)
      thread.start()
      return response.choices[0].message.content
  
  def get_completions(self,query):
    pass

  def set_instructions(self, instructions):
    self.instructions = instructions
    self.instructions_parsed = self.command_parser.replace_commands_with_results(self.instructions)
    self.db.get_collection("bots").update_one({"name": self.name}, {"$set": {"instructions": instructions}})
