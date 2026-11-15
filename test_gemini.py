## Delete this file after testing Gemini API

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

#Dummy Function to test Gemini API
get_weather = types.FunctionDeclaration(
    name="get_weather",
    description="Get the current weather for a given location",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "location": types.Schema(
                type="STRING",
                description="The location to get the weather for"
            )
        },
        required=["location"]
    ),
)

tool = types.Tool(function_declarations=[get_weather])

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="What is the weather for New York?",
    config=types.GenerateContentConfig(tools=[tool])
)

part = response.candidates[0].content.parts[0]

if part.function_call:
    call = part.function_call
    print("Function call name:", call.name)
    print("Function call arguments:", call.args)
else:
    print("No function call found.")
    print(part.text)