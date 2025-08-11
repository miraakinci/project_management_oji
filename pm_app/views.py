from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from .models import Project, Outcome, Benefit, Deliverable, Task
import json
from .forms import InputForm
from django.http import JsonResponse
from .openapi_client import generate_flow_from_vision, update_flow_with_llm
from .helper import find_similar_projects, find_similar_teams, serialize_project_flow, validate_and_serialize_sample_project
from datetime import date
import traceback


def index(request):
    """
    Handles the initial prompt submission page.
    """
    if request.method == 'POST':
        form = InputForm(request.POST)
        if form.is_valid():
            prompt = form.cleaned_data['prompt']

            #Create new project with the vision from the prompt
            project = Project.objects.create(name='initial project', vision=prompt)
            

            #find relevant past projects and organizational team/data
            similar_projects = find_similar_projects(prompt)
            teams_data = find_similar_teams(project.vision)

            # Validate and serialize the sample project into a clean JSON string
            sample_project_json = validate_and_serialize_sample_project(similar_projects)


            #generate the initial project flow
            project_flow_data = generate_flow_from_vision(prompt, sample_project_json, teams_data)

            #Update the project with the name from the flow data
            project_title = project_flow_data.get('title', 'Untitled Project')
            project.name = project_title
            project.save()

            # 3. Create related objects in the database
            for outcome_data in project_flow_data.get('outcomes', []):
                outcome = Outcome.objects.create(
                    projectID=project,
                    description=outcome_data.get('description')
                )
                #Create related benefits to each outcome 
                for benefit_data in outcome_data.get('benefits', []):
                    benefit = Benefit.objects.create(
                        outcomeID=outcome,
                        description=benefit_data.get('description')
                    )
                    #Create related deliverables to each benefit
                    for deliverable_data in benefit_data.get('deliverables', []):
                        deliverable = Deliverable.objects.create(
                            benefitID=benefit,
                            description=deliverable_data.get('description')
                        )
                        #Create related tasks to each deliverable
                        for task_data in deliverable_data.get('tasks', []):
                            start_date = task_data.get('start_date')
                            end_date = task_data.get('end_date')

                            Task.objects.create(
                                deliverableID=deliverable,
                                name=task_data.get('name'),
                                responsible_team=task_data.get('responsible_team', 'Unassigned'),
                                duration=task_data.get('duration', '1 day'),
                                start_date=date.fromisoformat(start_date) if start_date else None,
                                end_date=date.fromisoformat(end_date) if end_date else None
                            )
            # Redirect to the editable project flow page
            return redirect('project_flow', project_id=project.id)
        else:
            return render(request, 'pm_app/index.html', {'form': form, 'error': 'Invalid form submission'})
            
    return render(request, 'pm_app/index.html')

def get_project_flow(request, project_id):
    """
    Handles the page where the user can see and edit the project flow.
    """
    project = get_object_or_404(Project, id=project_id)
    outcomes = project.outcomes.all()
    benefits = Benefit.objects.filter(outcomeID__projectID=project)
    deliverables = Deliverable.objects.filter(benefitID__outcomeID__projectID=project)
    tasks = Task.objects.filter(deliverableID__benefitID__outcomeID__projectID=project) 

    return render(request, "pm_app/project_flow.html", {
        "project": project,
        "outcomes": outcomes,
        "benefits": benefits,
        "deliverables": deliverables,
        "tasks": tasks, 
    })



def update_flow_ajax(request, project_id):
    """
    Handles AJAX requests for project flow updates. It retrieves the entire current
    project flow from the database, combines it with the user's edit, and sends
    the full context to an LLM to generate the complete, updated flow.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            project = get_object_or_404(Project.objects.prefetch_related(
                'outcomes__benefits__deliverables__tasks'
            ), id=project_id)
            
            with transaction.atomic():
                edited_field = data.get('edited_field')
                payload = data.get('payload')
                
                if not edited_field or not payload:
                    return JsonResponse({'status': 'error', 'message': 'Missing edited_field or payload.'}, status=400)


                # First, update the specific item in the database so the change is reflected.
                if edited_field == 'vision':
                    project.vision = payload.get('vision')
                    
                elif edited_field == 'outcomes':
                    item = get_object_or_404(Outcome, id=payload.get('id'))
                    item.description = payload.get('description')
                    item.save()
                elif edited_field == 'benefits':
                    item = get_object_or_404(Benefit, id=payload.get('id'))
                    item.description = payload.get('description')
                    item.save()
                elif edited_field == 'deliverables':
                    item = get_object_or_404(Deliverable, id=payload.get('id'))
                    item.description = payload.get('description')
                    item.save()
                
                project.save() # Save any changes to the project model itself (like vision)

                # Now, serialize the fully updated project to send to the LLM
                current_project_flow = serialize_project_flow(project)
                
                similar_projects = find_similar_projects(project.vision)
                similar_teams = find_similar_teams(project.vision)

                llm_payload = {
                    'edited_field': edited_field,
                    'user_edit': payload,
                    'current_flow': current_project_flow,
                    'similar_projects': similar_projects,
                    'similar_teams': similar_teams,
                }
                
                # Call the LLM to get the complete, re-aligned project flow
                updated_flow_data = update_flow_with_llm(llm_payload)
                
                if not updated_flow_data:
                    return JsonResponse({'status': 'error', 'message': 'LLM failed to return valid data.'}, status=500)

                # Clear old data and repopulate with the new, LLM-generated data
                project.outcomes.all().delete()
                project.name = updated_flow_data.get('title', project.name)
                # The vision is already up-to-date, but we save it again with the title
                project.save()

                for outcome_data in updated_flow_data.get('outcomes', []):
                    outcome = Outcome.objects.create(
                        projectID=project, description=outcome_data.get('description'))
                    for benefit_data in outcome_data.get('benefits', []):
                        benefit = Benefit.objects.create(
                            outcomeID=outcome, description=benefit_data.get('description'))
                        for deliverable_data in benefit_data.get('deliverables', []):
                            deliverable = Deliverable.objects.create(
                                benefitID=benefit, description=deliverable_data.get('description'))
                            for task_data in deliverable_data.get('tasks', []):
                                Task.objects.create(
                                    deliverableID=deliverable, name=task_data.get('name'),
                                    responsible_team=task_data.get('responsible_team'),
                                    duration=task_data.get('duration'))
                
                return JsonResponse({'status': 'success', 'message': 'Project flow updated successfully.'})

        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

def gantt_chart(request, project_id):
    """
    This view might now be deprecated or repurposed, as the main page is project_flow.
    """
    project = get_object_or_404(Project, id=project_id)
    # ... rest of your gantt chart logic
    return render(request, 'pm_app/gantt_chart.html', {'project': project})