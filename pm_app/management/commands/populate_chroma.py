import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from pm_app.services import get_or_create_collection

class Command(BaseCommand):
    help = 'Loads project and organizational data from JSON files into ChromaDB'

    def handle(self, *args, **kwargs):
        """
        Main handler that orchestrates the loading of all data sources.
        """
        self.stdout.write(self.style.SUCCESS("--- Starting ChromaDB Population ---"))
        
        self._load_projects()
        self.stdout.write("---") # Separator
        self._load_organizational_teams()

        self.stdout.write(self.style.SUCCESS("--- ChromaDB Population Complete ---"))

    def _load_projects(self):
        """
        Loads project data from projects_data.json into the 'projects' collection.
        """
        self.stdout.write("Processing projects...")
        
        # 1. Get the specific collection for projects
        project_collection = get_or_create_collection("projects")
        
        # 2. Check for the JSON file
        json_file_path = Path(settings.BASE_DIR) / 'pm_app' / 'projects_data.json'
        if not json_file_path.exists():
            self.stdout.write(self.style.ERROR(f"Project data file not found at: {json_file_path}"))
            return

        with open(json_file_path, 'r', encoding='utf-8') as f:
            projects = json.load(f)

        ids_to_add = []
        documents_to_add = []
        metadatas_to_add = []

        # 3. Process each project (your existing logic is preserved here)
        for project in projects:
            ids_to_add.append(project['id'])
            documents_to_add.append(project['document'])

            metadata = project['metadata']
            deliverables_string = ""
            if 'deliverables' in metadata and isinstance(metadata['deliverables'], list):
                for deliverable in metadata['deliverables']:
                    deliverables_string += f"Title: {deliverable.get('title', '')}\n"
                    for task in deliverable.get('tasks', []):
                        deliverables_string += f"- {task}\n"
                    deliverables_string += "\n"
            
            flat_metadata = {
                "title": metadata.get('title', ''),
                "benefits": metadata.get('benefits', ''),
                "deliverables": deliverables_string.strip()
            }
            metadatas_to_add.append(flat_metadata)

        if not ids_to_add:
            self.stdout.write(self.style.WARNING("No projects found to load."))
            return

        # 4. Use upsert() for idempotency
        project_collection.upsert(
            ids=ids_to_add,
            documents=documents_to_add,
            metadatas=metadatas_to_add
        )
        self.stdout.write(self.style.SUCCESS(f"Successfully loaded/updated {len(ids_to_add)} projects."))

    def _load_organizational_teams(self):
        """
        Loads team data from organizational_data.json into the 'organizational_teams' collection.
        """
        self.stdout.write("Processing organizational teams...")
        
        # 1. Get the specific collection for teams
        org_collection = get_or_create_collection("organizational_teams")

        # 2. Check for the JSON file
        json_file_path = Path(settings.BASE_DIR) / 'pm_app' / 'organizational_data.json'
        if not json_file_path.exists():
            self.stdout.write(self.style.ERROR(f"Organizational data file not found at: {json_file_path}"))
            return

        with open(json_file_path, 'r', encoding='utf-8') as f:
            teams = json.load(f)

        # 3. Process each team
        ids_to_add = [team['id'] for team in teams]
        documents_to_add = [team['document'] for team in teams]
        metadatas_to_add = [{"team_name": team['team_name']} for team in teams]

        if not ids_to_add:
            self.stdout.write(self.style.WARNING("No teams found to load."))
            return

        # 4. Use upsert() for idempotency
        org_collection.upsert(
            ids=ids_to_add,
            documents=documents_to_add,
            metadatas=metadatas_to_add
        )
        self.stdout.write(self.style.SUCCESS(f"Successfully loaded/updated {len(ids_to_add)} teams."))