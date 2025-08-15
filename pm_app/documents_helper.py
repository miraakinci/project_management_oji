import json
import ast
from django.conf import settings
from dotenv import load_dotenv
import os
from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError

load_dotenv() 

# 3. Get the API key from the environment
api_key = os.getenv("OPENAI_API_KEY") 
MODEL = "gpt-4o"
client = None

# 4. Check if the key exists and initialize the client
if api_key:
    client = OpenAI(api_key=api_key)
else:
    print("Warning: OPENAI_API_KEY not found in .env file.")


def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return s

def _coerce_obj(raw_text: str):
    txt = _strip_code_fences(raw_text)
    try:
        obj = json.loads(txt)
        if not isinstance(obj, dict): raise ValueError
        return obj
    except Exception:
        obj = ast.literal_eval(txt)
        if not isinstance(obj, dict): raise ValueError
        return obj

def chat_call(messages, temperature=0.3) -> str:
    if not client:
        raise RuntimeError("OpenAI client is not initialized. Check API Key.")
    try:
        resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=temperature)
        return resp.choices[0].message.content
    except (AuthenticationError, RateLimitError, APIConnectionError) as e:
        raise RuntimeError(f"OpenAI call failed: {e}") from e

def generate_comm_plan(desc: str) -> dict:
    system = f"""
    You are a senior project communications consultant.
    Create a Communication Plan JSON for the project described below.
    <desc>{desc}</desc>

    Return ONLY a JSON object with this exact structure:
    {{
     "Objective":"...",
     "Stakeholders":[
       {{"Name":"...","Role":"...","CommunicationMethod":"Status Email / Standup / SteerCo / Board Pack",
         "Frequency":"Weekly / Fortnightly / Monthly / Ad-hoc","Responsible":"...","Priority":"High/Medium/Low",
         "PreferredDeliveryMethod":"Email / MS Teams / Slack / Portal","CommunicationGoal":"..."}}
     ],
     "Channels":["Email","MS Teams","Standup","SteerCo"],
     "Notes":"Short notes if any"
    }}
    Rules: Generate 8–12 relevant stakeholder rows. Tailor Roles & Frequency to the project description in <desc>.
    """
    raw_response = chat_call([{"role": "system", "content": system}])
    return _coerce_obj(raw_response)

# --- Safety Net Functions ---

def _priority_norm(v: str) -> str:
    v = (v or "").strip().lower()
    if v.startswith("h"): return "High"
    if v.startswith("l"): return "Low"
    return "Medium"

def _comm_row_from_dict(d: dict) -> dict:
    return {
        "Name": d.get("Name") or d.get("Stakeholder") or "",
        "Role": d.get("Role") or "",
        "CommunicationMethod": d.get("CommunicationMethod") or "Status Email",
        "Frequency": d.get("Frequency") or "Weekly",
        "Responsible": d.get("Responsible") or "Project Manager",
        "Priority": _priority_norm(d.get("Priority")),
        "PreferredDeliveryMethod": d.get("PreferredDeliveryMethod") or "Email",
        "CommunicationGoal": d.get("CommunicationGoal") or d.get("Purpose") or "",
    }

def _default_comm_from_facts(project_name: str) -> dict:
    # A sensible default plan if the AI call fails
    return {
        "Objective": f"Keep stakeholders for the '{project_name}' project aligned on schedule, risks, and go-live readiness.",
        "Stakeholders": [
            {"Name": "Project Manager", "Role":"Delivery Lead", "CommunicationMethod":"Daily Standup", "Frequency":"Daily", "Responsible":"Self", "Priority":"High", "PreferredDeliveryMethod":"MS Teams", "CommunicationGoal":"Coordinate delivery & unblock issues"},
            {"Name": "Executive Sponsor", "Role":"Sponsor", "CommunicationMethod":"Steering Committee", "Frequency":"Fortnightly", "Responsible":"Project Manager", "Priority":"High", "PreferredDeliveryMethod":"Board Pack / Email", "CommunicationGoal":"Secure decisions, manage risks"},
            {"Name": "Product Team", "Role":"Product", "CommunicationMethod":"Backlog Review", "Frequency":"Weekly", "Responsible":"Product Manager", "Priority":"High", "PreferredDeliveryMethod":"Jira / Teams", "CommunicationGoal":"Align on scope and priorities"},
            {"Name": "Tech Lead", "Role":"Technology", "CommunicationMethod":"Tech Sync", "Frequency":"Weekly", "Responsible":"Tech Lead", "Priority":"Medium", "PreferredDeliveryMethod":"Teams", "CommunicationGoal":"Resolve architectural issues"},
        ],
        "Channels": ["Email", "MS Teams", "Standup", "Steering Committee"],
        "Notes": "This is a default plan. The AI-generated plan could not be created."
    }

def normalize_comm_obj(comm_obj, project_name: str) -> dict:
    try:
        if not isinstance(comm_obj, dict):
            return _default_comm_from_facts(project_name)

        stakeholders_list = []
        raw_stakeholders = comm_obj.get("Stakeholders")
        if isinstance(raw_stakeholders, list) and raw_stakeholders:
            for item in raw_stakeholders:
                if isinstance(item, dict):
                    stakeholders_list.append(_comm_row_from_dict(item))

        if not stakeholders_list:
            return _default_comm_from_facts(project_name)

        return {
            "Objective": (comm_obj.get("Objective") or "").strip() or f"Communicate status, risks and decisions for {project_name}.",
            "Stakeholders": stakeholders_list,
            "Channels": comm_obj.get("Channels") or ["Email", "MS Teams", "Standup"],
            "Notes": comm_obj.get("Notes") or "",
        }
    except Exception:
        return _default_comm_from_facts(project_name)



#Financial Plan Generation

def generate_financial_plan(desc: str) -> dict:
    """
    Generates a financial plan with a data structure that perfectly matches the target screenshot.
    """
    # FINAL PROMPT VERSION
    system = f"""
    You are a senior financial planner following the PRINCE2 methodology.
    Based on the project description below, create a detailed Financial Plan JSON.
    <desc>{desc}</desc>

    Generate a JSON object with the exact keys: "summary", "stages", "expenses", "cashflow", "tolerance", and "governance".

    Follow these detailed instructions for each key:
    1.  **summary**: Write a 2-3 sentence overview of the project's financial objectives. This should be a single string of text.
    2.  **stages**: Create a list of 4-6 project stages. For each stage, provide a "name", "duration", and estimated "cost".
    3.  **expenses**: Create a list of 5-7 key expense items. For each item, provide a "category" and a "cost". This structure should be a list of dictionaries, like the 'stages' section.
        - Example: `{{ "category": "Staff Training", "cost": "£10000" }}`
    4.  **cashflow**: Create a dictionary of key financial metrics: "initial_investment", "monthly_outflow", "expected_return_on_investment_roi", and "break_even_point".
    5.  **tolerance**: Create a dictionary defining deviation limits for "time_tolerance", "cost_tolerance", and "quality_tolerance".
    6.  **governance**: Write a 2-3 sentence paragraph describing the project's financial governance, including review frequency and change control. This should be a single string of text, NOT a dictionary.

    Use the currency "£". Return ONLY the JSON object.
    """
    raw_response = chat_call([{"role":"system", "content":system}], 0.3)
    return _coerce_obj(raw_response)
def _rows_from_any(data):
    """Normalize various JSON shapes to a list of lists for a table."""
    if data is None or data == "":
        return None

    # Handle stringified JSON
    if isinstance(data, str):
        txt = _strip_code_fences(data)
        try: data = json.loads(txt)
        except Exception:
            try: data = ast.literal_eval(txt)
            except Exception: return [["Text"], [txt]]

    # Handle a list of dictionaries (most common case)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        headers = list(data[0].keys())
        rows = [headers]
        for item in data:
            rows.append([item.get(h, "") for h in headers])
        return rows
    
    # Handle a list of lists
    if isinstance(data, list) and data and isinstance(data[0], list):
        return data

    # Handle a simple dictionary of key-value pairs
    if isinstance(data, dict):
        return [["Field", "Value"]] + [[k, v] for k, v in data.items()]
        
    return None

