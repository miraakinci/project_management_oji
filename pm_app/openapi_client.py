import json, re
import openai
from dotenv import load_dotenv


def generate_flow_from_vision(vision_text, sample_project) -> dict:

    load_dotenv()

    prompt = (
        f"Here is a structured sample project that you can use as an example {sample_project}"
        f"Vision: {vision_text}\n\n"
    )

    system_prompt = (
        """
        You are a project management assistant.
        Your task is to generate a project flow based on the provided vision and a sample project that you can use as an example.
        Return ONLY a JSON object with the following five keys:
        - "title": A concise and descriptive name for the project based on the vision.
        - "outcomes": A list of strings describing the desired final results.
        - "benefits": A list of strings describing the value or advantages of the project.
        - "deliverables": A list of strings describing the tangible outputs of the project.
        - "tasks": A list of strings or objects describing the specific actions required.
        """
    )

    client = openai.Client()

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": system_prompt
            }
        ]
    )

    return json.loads(response.choices[0].message.content)