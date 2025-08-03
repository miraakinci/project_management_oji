from .services import get_or_create_collection


#fetch relevant past projects from the vector database
def find_similar_projects(input_prompt):

    project_collection = get_or_create_collection("projects")

    "results is a disctionary with the following keys: 'ids', 'metadatas', 'documents', 'embeddings'"
    results = project_collection.query(
        query_texts=[input_prompt],
        n_results=1
    )

    return results.get('documents', [])

def find_similar_teams(input_prompt):

    org_collection = get_or_create_collection("organizational_teams")

    results = org_collection.query(
        query_texts=[input_prompt]
    )
    
    return results.get('documents', [[]])[0]


