from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Project, Outcome, Benefit, Deliverable, Task
import json
from .forms import InputForm
from django.http import JsonResponse
from .openapi_client import generate_flow_from_vision, create_tasks
from .helper import find_similar_projects, find_similar_teams
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
            #find relevant past projects and organizational team/data
            similar_projects = find_similar_projects(prompt)
            #LLM call
            send_sim_project = json.dumps(similar_projects)

            project_flow_data = generate_flow_from_vision(prompt, send_sim_project)

            project_title = project_flow_data.get('title', 'Untitled Project')

            project = Project.objects.create(name=project_title, vision=prompt)

            # 3. Create related objects in the database
            for item in project_flow_data.get('outcomes', []):
                Outcome.objects.create(project=project, description=item)
            
            for item in project_flow_data.get('benefits', []):
                Benefit.objects.create(project=project, description=item)
            
            for deliverable_desc in project_flow_data.get('deliverables', []):
                Deliverable.objects.create(project=project, description=deliverable_desc)

            # Redirect to the editable project flow page
            return redirect('project_flow', project_id=project.id)
        else:
            return render(request, 'pm_app/index.html', {'form': form, 'error': 'Invalid form submission'})
            
    return render(request, 'pm_app/index.html')


def project_flow(request, project_id):
    """
    Handles the page where the user can see and edit the project flow.
    """
    project = get_object_or_404(Project, id=project_id)
    return render(request, 'pm_app/project_flow.html', {'project': project})




@require_POST
def generate_tasks_ajax(request, project_id):
    """
    Handles the AJAX request to regenerate the project plan and tasks based on edited flow.
    """
    try:
        project = get_object_or_404(Project, id=project_id)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body'}, status=400)

        # 1. Update vision if provided
        vision = data.get('vision')
        if vision is not None:
            project.vision = vision
            project.save()

        # 2. Clear previous related objects
        Outcome.objects.filter(project=project).delete()
        Benefit.objects.filter(project=project).delete()
        Deliverable.objects.filter(project=project).delete()
        Task.objects.filter(deliverable__project=project).delete()

        # 3. Re-create outcomes and benefits
        for desc in data.get('outcomes', []):
            Outcome.objects.create(project=project, description=desc)
        for desc in data.get('benefits', []):
            Benefit.objects.create(project=project, description=desc)

        # 4. Re-create deliverables
        new_deliverables = []
        for desc in data.get('deliverables', []):
            d = Deliverable.objects.create(project=project, description=desc)
            new_deliverables.append(d)
        if not new_deliverables:
            return JsonResponse({'status': 'error', 'message': 'No deliverables provided'}, status=400)

        # 5. Derive team suggestions
        teams_data = find_similar_teams(project.vision)
        sende_teams_data = json.dumps(teams_data)

        # 6. Generate tasks
        delli = data.get('deliverables', [])
        print("Deliverables from data: ", delli)
        print("type of deliverables: ", type(delli))
        
        raw_tasks = create_tasks(data.get('deliverables', []), teams_data)
        print("Raw tasks from create_tasks: ", raw_tasks)

        tasks_for_response = []
        for task in raw_tasks.get("tasks"):
            sd = task.get("start_date") 
            ed = task.get("end_date")
            start = date.fromisoformat(sd) if sd else None
            end = date.fromisoformat(ed) if ed else None
            task_obj = Task.objects.create(
                name=task.get('name', 'Unnamed Task'),
                responsible_team=task.get('responsible_team', 'Unassigned'),
                duration=task.get('duration', '1 day'),
                start_date=start,
                end_date=end    
            )
            tasks_for_response.append({
                'name': task_obj.name,
                'assigned_to': task_obj.responsible_team,
                'duration': task_obj.duration,
            })
        print("Tasks for response: ", tasks_for_response)
        return JsonResponse({'status': 'success', 'tasks': tasks_for_response})
 
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



def gantt_chart(request, project_id):
    """
    This view might now be deprecated or repurposed, as the main page is project_flow.
    """
    project = get_object_or_404(Project, id=project_id)
    # ... rest of your gantt chart logic
    return render(request, 'pm_app/gantt_chart.html', {'project': project})