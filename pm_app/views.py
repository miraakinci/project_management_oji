from django.shortcuts import render, redirect, get_object_or_404
from .models import Project, Outcome, Benefit, Deliverable, Task
import json
from .forms import InputForm
from django.http import JsonResponse
from .openapi_client import generate_flow_from_vision
from .helper import find_similar_projects


def index(request):
    """
    Handles the initial prompt submission page.
    """
    if request.method == 'POST':
        form = InputForm(request.POST)

        if form.is_valid():
            prompt = form.cleaned_data['prompt']

            print(prompt)

            #find relevant past projects
            similar_projects = find_similar_projects(prompt)
            
            project_flow_data = generate_flow_from_vision(prompt, similar_projects)

            project_title = project_flow_data.get('title', 'Untitled Project')

            project = Project.objects.create(name=project_title, vision=prompt)

            # 3. Create related objects in the database
            for item in project_flow_data.get('outcomes', []):
                Outcome.objects.create(project=project, description=item)
            
            for item in project_flow_data.get('benefits', []):
                Benefit.objects.create(project=project, description=item)
            
            for deliverable_desc in project_flow_data.get('deliverables', []):
                Deliverable.objects.create(project=project, description=deliverable_desc)
            
            first_deliverable = project.deliverables.first()
            if first_deliverable:
                for task_item in project_flow_data.get('tasks', []):
                    # Ensure task_item is a dictionary with the expected keys
                    if isinstance(task_item, dict):
                        Task.objects.create(
                            deliverable=first_deliverable, 
                            name=task_item.get('name', 'Unnamed Task'), 
                            start_date=task_item.get('start', None), 
                            end_date=task_item.get('end', None)
                        )

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
    
    if request.method == 'POST':
        # NOTE: The logic to handle user edits and propagate changes would go here.
        # For now, we'll just confirm and redirect to the Gantt chart.
        return redirect('gantt_chart', project_id=project.id)

    return render(request, 'pm_app/project_flow.html', {'project': project})


def gantt_chart(request, project_id):
    """
    Handles the final page with the non-editable flow and the Gantt chart.
    """
    project = get_object_or_404(Project, id=project_id)
    tasks = Task.objects.filter(deliverable__project=project)

    # Format the task data for the Frappe Gantt library
    chart_data = []
    for i, task in enumerate(tasks):
        chart_data.append({
            'id': f'task_{i}',
            'name': task.name,
            'start': task.start_date.strftime('%Y-%m-%d'),
            'end': task.end_date.strftime('%Y-%m-%d'),
            'progress': task.progress,
        })

    # Pass all project data to the template
    context = {
        'project': project,
        'chart_data': json.dumps(chart_data)
    }
    return render(request, 'pm_app/gantt_chart.html', context)