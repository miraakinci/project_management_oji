import json, re
import openai
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
client = openai.Client()
today = datetime.now().date()

def generate_flow_from_vision(vision_text, sample_project) -> dict:


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
        - "tasks": A list of strings or objects describing the specific actions required, the teams involved, and the duration of each task.
        """
    )


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



def create_tasks(deliverables, teams_data ):

    #print("Data from teams_data: ", teams_data)
    #print("type of teams_data: ", type(teams_data))
    

    prompt = f"""
    You are an expert project planner.
    Today's date is {today}.

    Here are some teams that can help with the project and their areas of expertise, you are not limited to these teams but they are a good starting point:
    {teams_data}

    Based on that context, create a detailed task list for each deliverable in this list: {deliverables}.

    Each task in your response must be a JSON object with the following keys:
    - "name": A descriptive name for the task.
    - "responsible_team": The name of the team from the provided list that is best suited to complete the task.
    - "duration": An integer representing the estimated duration in days (e.g., 5).
    - "start_date": The planned start date in "YYYY-MM-DD" format, starting from today or later.
    - "end_date": The calculated end date in "YYYY-MM-DD" format, based on the start_date and duration.

    Return ONLY a valid JSON object with a single key "tasks" that contains a list of these task objects. For example: {{"tasks": [...]}}
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a project management assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    print("Response from OpenAI: ", response.choices[0].message.content)
    return json.loads(response.choices[0].message.content)

    # tasks = json.loads(response.choices[0].message.content)

    # #compute end_date if missing 
    # for task in tasks:
    #     if not task.get('end_date'):
    #         duration_days = int(re.search(r'(\d+)', task['duration']).group(1))
    #         start_date = datetime.strptime(task['start_date'], '%Y-%m-%d')
    #         end_date = start_date + timedelta(days=duration_days)
    #         task['end_date'] = end_date.strftime('%Y-%m-%d')
    # return tasks
