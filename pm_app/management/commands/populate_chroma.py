import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from pm_app.services import get_or_create_collection

class Command(BaseCommand):
    help = 'Loads project data from a JSON file into ChromaDB'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("--- Starting ChromaDB Population ---"))
        project_collection = get_or_create_collection()

        json_file_path = Path(settings.BASE_DIR) / 'pm_app' / 'projects_data.json'
        if not json_file_path.exists():
            self.stdout.write(self.style.ERROR(f"Data file not found at: {json_file_path}"))
            return

        with open(json_file_path, 'r', encoding='utf-8') as f:
            projects = json.load(f)

        ids_to_add = []
        documents_to_add = []
        metadatas_to_add = []

        for project in projects:
            # Add the simple fields
            ids_to_add.append(project['id'])
            documents_to_add.append(project['document'])

            # Process the metadata to flatten the deliverables list
            metadata = project['metadata']
            
            # Convert the list of deliverable objects into a single formatted string
            deliverables_string = ""
            if 'deliverables' in metadata and isinstance(metadata['deliverables'], list):
                for deliverable in metadata['deliverables']:
                    deliverables_string += f"Title: {deliverable.get('title', '')}\n"
                    tasks = deliverable.get('tasks', [])
                    for task in tasks:
                        deliverables_string += f"- {task}\n"
                    deliverables_string += "\n" # Add a newline for spacing
            
            # Create a new, flat metadata object
            flat_metadata = {
                "title": metadata.get('title', ''),
                "benefits": metadata.get('benefits', ''),
                "deliverables": deliverables_string.strip() # Use the flattened string
            }
            metadatas_to_add.append(flat_metadata)
        # ---------------------------------------------

        self.stdout.write(f"Found {len(ids_to_add)} projects to load.")
        project_collection.add(
            ids=ids_to_add,
            documents=documents_to_add,
            metadatas=metadatas_to_add
        )
        self.stdout.write(self.style.SUCCESS(f"--- Successfully loaded {len(projects)} projects into ChromaDB ---"))