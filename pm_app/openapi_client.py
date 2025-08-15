import json, re
import openai
from dotenv import load_dotenv
from datetime import date
from .schemas import ProjectFlow
from pydantic import ValidationError

load_dotenv()
client = openai.Client()
today = date.today().isoformat()



def parse_llm_response(response):
    """A helper to safely extract and parse JSON from the LLM response."""
    try:
        content = response.choices[0].message.content
        clean_content = content.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_content)
    except (json.JSONDecodeError, IndexError, KeyError):
        print("Error: Failed to decode or parse JSON from LLM response.")
        return None


def generate_flow_from_vision(vision_text, sample_project, teams_data) -> dict:
    """
    Generates the initial project flow from a user's vision statement.
    """
    system_prompt = (
    """
    You are a project management assistant. Your task is to generate a project flow based on the provided vision.
    Return ONLY a single, valid JSON object with the following nested structure:
    - "title": A concise and descriptive name for the project.
    - "outcomes": An array of objects.
    - Each object in "outcomes" must have:
        - "description": A string describing the desired final result.
        - "benefits": An array of objects.
    - Each object in "benefits" must have:
        - "description": A string describing the value or advantage.
        - "deliverables": An array of objects.
    - Each object in "deliverables" must have:
        - "description": A string describing the tangible output.
        - "tasks": An array of objects.
    - Each object in "tasks" must have:
        - "name": A clear and concise name for the task.
        - "responsible_team": The most appropriate team to handle this task.
        - "duration": An estimated integer number of days required to complete the task.
    """
    )
    user_prompt = (
        f"Here is a structured sample project you can use as an example:{sample_project}\n\n"
        f"Here are some example teams and their expertise you can choose to use these where relevant but you are not limited to it: {teams_data}\n\n"
        f"Now, generate a new project flow (create at least 5 outcomes, each with its own benefits, deliverables, and tasks) for the following vision: '{vision_text}'"
    )

    #print("sample_project: ", sample_project)
    #print("teams_data: ", teams_data)   

    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )

    data_dict = parse_llm_response(response)
    if not data_dict:
        print("Error: Failed to parse LLM response.")
        return None
    # 2. Validate the data using your Pydantic model
    try:
        # This is the magic step. Pydantic checks everything.
        validated_flow = ProjectFlow.model_validate(data_dict)
        
        # 3. Convert the validated model back to a dictionary
        # The view can now use this clean, guaranteed-to-be-correct data.
        # `mode='json'` ensures dates are converted back to "YYYY-MM-DD" strings.
        return validated_flow.model_dump(mode='json')

    except ValidationError as e:
        # If the LLM returns bad data, this will catch it.
        print("--- Pydantic Validation Error ---")
        print("The LLM returned data that did not match the required format.")
        print(e)
        print("-------------------------------")
        return {} # Return an empty dict so the app doesn't crash

    #print("LLM response: ", parse_llm_response(response))
    return parse_llm_response(response)

def update_flow_with_llm(payload):
    """
    Takes the current project flow and the name of the field the user just edited,
    and returns a fully reconciled, logically consistent project flow.
    """
    edited_field = payload['edited_field']
    user_edit = payload['user_edit']
    current_values = payload['current_flow']
    similar_projects = payload.get('similar_projects', '[]')
    similar_teams = payload.get('similar_teams', '[]')

    #print(f"Updating flow with edited field: {edited_field}")
    #print(f"User edit: {user_edit}")
    #print(f"Current values: {current_values}")

    # --- ENHANCED PROMPT ---
    # This prompt is more explicit about making significant changes.
    system_prompt = (
        f"""
        You are an expert project management assistant. Your critical task is to update a project plan (Vision -> Outcomes -> Benefits -> Deliverables -> Tasks) to ensure it remains logically coherent after a user edits one part, here is the edited part ('{edited_field}').

        Follow these rules precisely:
        1.  **The user's edit is the primary source of truth.** The entire project plan must be re-aligned to this single change.
        2.  **Make radical changes if necessary.** If a low-level item (like a 'benefit') is edited to be more strategic, you MUST be prepared to completely change or replace higher-level items (like 'outcomes' or the project 'title'). Do not be conservative. The goal is logical consistency with the newest change.
        3.  **Maintain the hierarchy.** The final output must follow the strict logical flow: Vision -> Outcomes -> Benefits -> Deliverables -> Tasks.

        Return ONLY a single, valid JSON object with the following nested structure:
        - "title": A concise and descriptive name for the project.
        - "outcomes": An array of objects, each with a "description" and a "benefits" array.
        - "benefits": An array of objects, each with a "description" and a "deliverables" array.
        - "deliverables": An array of objects, each with a "description" and a "tasks" array.
        - "tasks": An array of objects, each with a "name", "responsible_team", and "duration".
        """
    )

    user_prompt = (
        f"Here is a structured sample project you can use as an example of format: {similar_projects}\n\n"
        f"The field the user just edited is: \"{user_edit}\"."
        f"Here is the entire project plan immediately after the user's edit: {current_values}\n\n"
        f"A user has just edited one part of a project plan, and your critical task is to update the rest of the plan to ensure it remains logically coherent. You can add new items, modify existing ones, or remove items as necessary to ensure the entire project plan is logically consistent and coherent.\n\n"
    )

    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    data_dict = parse_llm_response(response)
    if not data_dict:
        return {} 

    try:
        validated_flow = ProjectFlow.model_validate(data_dict)
        return validated_flow.model_dump(mode='json')
    except ValidationError as e:
        print(f"--- Pydantic Validation Error in update_flow_with_llm: {e} ---")
        return {}