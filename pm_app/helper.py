from .services import get_or_create_collection
import json
from .models import Project, Outcome, Benefit, Deliverable, Task
from .schemas import ProjectFlow
from pydantic import ValidationError


#fetch relevant past projects from the vector database
def find_similar_projects(input_prompt):

    project_collection = get_or_create_collection("projects")

    results = project_collection.query(
    query_texts=[input_prompt],
    n_results=1,
    include=["metadatas", "documents"]
)
    project_metadata = results['metadatas'][0][0]

    outcomes_json_string = project_metadata.get('outcomes_json', '[]')
    outcomes_data = json.loads(outcomes_json_string)

    final_result = {
        "id": results['ids'][0][0],
        "title": project_metadata.get('title'),
        "document": results['documents'][0][0],
        "outcomes": outcomes_data 
    }

    return final_result

def find_similar_teams(input_prompt):

    org_collection = get_or_create_collection("organizational_teams")

    results = org_collection.query(
        query_texts=[input_prompt]
    )
    
    return results.get('documents', [[]])[0]



def serialize_project_flow(project: Project) -> dict:
    """
    Serializes a Django Project object and its related nested objects
    (Outcomes, Benefits, Deliverables, Tasks) into a nested dictionary.
    
    This function is intended to be used to prepare a full project flow
    for an LLM call or for API responses.
    
    Args:
        project (Project): A Django Project model instance.

    Returns:
        dict: A nested dictionary representing the project's entire flow.
    """
    # Start with the top-level project details
    project_data = {
        'id': str(project.id),
        'title': project.name,
        'vision': project.vision,
        'outcomes': []
    }
    
    # Iterate through each outcome related to the project
    for outcome in project.outcomes.all():
        outcome_data = {
            'id': str(outcome.id),
            'description': outcome.description,
            'benefits': []
        }
        
        # Iterate through each benefit related to the outcome
        for benefit in outcome.benefits.all():
            benefit_data = {
                'id': str(benefit.id),
                'description': benefit.description,
                'deliverables': []
            }
            
            # Iterate through each deliverable related to the benefit
            for deliverable in benefit.deliverables.all():
                deliverable_data = {
                    'id': str(deliverable.id),
                    'description': deliverable.description,
                    'tasks': []
                }
                
                # Iterate through each task related to the deliverable
                for task in deliverable.tasks.all():
                    task_data = {
                        'id': str(task.id),
                        'name': task.name,
                        'responsible_team': task.responsible_team,
                        'duration': task.duration
                    }
                    deliverable_data['tasks'].append(task_data)
                
                benefit_data['deliverables'].append(deliverable_data)
            
            outcome_data['benefits'].append(benefit_data)
        
        project_data['outcomes'].append(outcome_data)
        
    return project_data


def validate_and_serialize_sample_project(project_data: dict) -> str:
    """
    Validates a project data dictionary against the ProjectFlow schema
    and returns a clean, indented JSON string for use in prompts.
    """
    # Return an empty JSON object if the fetched project data is missing
    if not project_data or 'title' not in project_data or 'outcomes' not in project_data:
        return "{}"

    # 1. Structure the data to perfectly match the ProjectFlow Pydantic model
    structured_for_validation = {
        "title": project_data.get("title"),
        "outcomes": project_data.get("outcomes", [])
    }

    try:
        # 2. Validate the structure using your Pydantic model
        validated_project = ProjectFlow.model_validate(structured_for_validation)
        
        # 3. Return a clean, indented JSON string.
        # This is the ideal format for an LLM prompt.
        return validated_project.model_dump_json(indent=2)

    except ValidationError as e:
        # This might happen if old data in your DB doesn't match the schema
        print(f"Warning: The sample project from the database failed validation. {e}")
        # Fallback to a simple JSON dump if validation fails
        return json.dumps(structured_for_validation, indent=2)