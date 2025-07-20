from django.shortcuts import render, redirect, get_object_or_404
from .models import Project, Outcome, Benefit, Deliverable, Task
import json

# A mock function to simulate the LLM API call
def get_project_flow_from_llm(prompt):
    """
    In a real application, you would make an API call to your LLM here.
    You would also connect to your vector database to get relevant information.
    For now, we'll return some mock data based on the screenshots.
    """
    return {
        "outcomes": ["30% efficiency improvement", "Real-time data insights"],
        "benefits": ["$2M annual savings", "Enhanced customer experience"],
        "deliverables": ["New CRM system", "Analytics dashboard"],
        "tasks": [
            {"name": "Phase 1", "start": "2025-01-01", "end": "2025-02-15"},
            {"name": "Phase 2", "start": "2025-02-15", "end": "2025-03-10"},
            {"name": "Phase 3", "start": "2025-03-10", "end": "2025-04-20"},
            {"name": "Phase 4", "start": "2025-04-20", "end": "2025-05-30"},
        ]
    }

def index(request):
    """
    Handles the initial prompt submission page.
    """
    if request.method == 'POST':
        prompt = request.POST.get('prompt')
        
        # 1. Get project flow from the mock LLM function
        project_flow_data = get_project_flow_from_llm(prompt)

        # 2. Create Project and related objects in the database
        project = Project.objects.create(name="New Project from Vision", vision=prompt)
        
        for item in project_flow_data['outcomes']:
            Outcome.objects.create(project=project, description=item)
        
        for item in project_flow_data['benefits']:
            Benefit.objects.create(project=project, description=item)
        
        # Create deliverables and their associated tasks
        for deliverable_desc in project_flow_data['deliverables']:
            d = Deliverable.objects.create(project=project, description=deliverable_desc)
            # For this mock-up, we'll just assign all tasks to the first deliverable
            # In a real scenario, the LLM would specify which tasks belong to which deliverable
        
        # We need at least one deliverable to assign tasks to.
        first_deliverable = project.deliverables.first()
        if first_deliverable:
             for task_item in project_flow_data['tasks']:
                 Task.objects.create(
                     deliverable=first_deliverable, 
                     name=task_item['name'], 
                     start_date=task_item['start'], 
                     end_date=task_item['end']
                )

        # Redirect to the editable project flow page
        return redirect('project_flow', project_id=project.id)
        
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