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
from datetime import date, timedelta
import plotly.express as px
import plotly.offline as op
import pandas as pd
import traceback
from . import documents_helper
import csv
from django.http import HttpResponse
import base64
import plotly.graph_objects as go


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



def _duration_to_days(s, default=7):
    if not s: return default
    try:
        num, unit = s.split()
        num = int(num)
        return num * 7 if 'week' in unit.lower() else num
    except Exception:
        return default

def gantt_chart_data(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    qs = (Task.objects
            .filter(deliverableID__benefitID__outcomeID__projectID=project)
            .order_by('id'))
    if not qs.exists():
        return JsonResponse({"png": None, "message": "No tasks found."})

    rows, rolling = [], date.today()
    for t in qs:
        if t.start_date and t.end_date:
            #print(f"Task {t.name} has start and end dates: {t.start_date} to {t.end_date}")
            start, end = t.start_date, t.end_date
        else:
            #print('No start or end date for task:', t.name, 'duration:', t.duration)
            days = _duration_to_days(t.duration)
            start =  (t.start_date or rolling)
            end = start + timedelta(days=days)
            rolling = end + timedelta(days=1)
        rows.append({
            "Task": t.name or "Untitled Task",
            "Start": start, "Finish": end,
            "Team": t.responsible_team or "Unassigned",
        })

    
    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
    df["Finish"] = pd.to_datetime(df["Finish"], errors="coerce")
    df["Team"] = df["Team"].astype(str).str.strip().replace({"": "Unassigned"})
    # cast task column to first four characters to avoid long names
    # df["Task"] = df["Task"].astype(str).str.slice(0, 20).str.strip().replace({"": "Untitled Task"})
    df['TaskName'] = df['Task']
    df["Task"] = "Task " + (df.index + 1).astype(str)

    #print(df.to_string())
    # Stable palette (explicit map avoids grayscale fallbacks)
    palette = px.colors.qualitative.D3
    teams = list(dict.fromkeys(df["Team"]))  # preserve order
    color_map = {t: palette[i % len(palette)] for i, t in enumerate(teams)}

    assert (df["Finish"] > df["Start"]).all()
    df = df.reset_index(drop=True)
    df["ypos"] = len(df) - 1 - df.index  # top-to-bottom

    fig = go.Figure()
    for team in teams:
        sub = df[df["Team"] == team]
        fig.add_trace(go.Scatter(
            x=sum([[s, f, None] for s, f in zip(sub["Start"], sub["Finish"])], []),
            y=sum([[y, y, None] for y in sub["ypos"]], []),
            mode="lines",
            line=dict(width=18, color=color_map[team]),
            name=team,
            hovertext=sub["Task"],
            hoverinfo="text",
        ))
    
    # --- dynamic sizing (no hard-coded height) ---
    n_tasks = len(df)
    row_h   = 26                         # px per task row
    height  = max(360, min(140 + row_h*n_tasks, 1200))

    duration_days = max(1, (df["Finish"].max() - df["Start"].min()).days)
    ar = min(3.0, max(1.2, duration_days / max(n_tasks, 1)))  # aspect ~ time span / tasks
    width = int(height * ar)

    fig.update_yaxes(
        tickvals=df["ypos"], ticktext=df["Task"],
        autorange="reversed"
    )
    fig.update_xaxes(
        type="date", 
        range=[df["Start"].min(), df["Finish"].max()],
        # dtick="D1",                 # one tick per day (or use 86400000)
    # tickformat="%d %b %Y",      # e.g., 15 Aug 2025
    # tickangle=-45,    
    )
    fig.update_layout(
        title="Project Timeline", 
        margin=dict(l=10, r=10, b=10, t=48), 
        template="plotly_white",
        height=height, width=width)

    png_bytes = fig.to_image(format="png", scale=2)  # Kaleido
    b64 = base64.b64encode(png_bytes).decode("ascii")
    response = JsonResponse({"png": f"data:image/png;base64,{b64}"}) 

    task_map = dict(zip(df["Task"], df["TaskName"]))
    task_map_str = json.dumps(task_map, ensure_ascii=False)
    response["X-Task-Map"] = task_map_str  # Pass task map for client-side use
    
    return response   


def download_comm_plan_view(request, project_id):
    """
    Generates an AI-powered Communication Plan and returns it as a CSV file.
    """
    try:
        project = Project.objects.prefetch_related(
            'outcomes__benefits__deliverables'
        ).get(pk=project_id)
    except Project.DoesNotExist:
        return HttpResponse("Project not found.", status=404)

    # 1. Build the "Project Brief" string. This replaces the command-line wizard.
    # We create a detailed text description of the project for the AI.
    outcomes_str = ", ".join([o.description for o in project.outcomes.all()])
    project_brief = (
        f"Project Vision: {project.vision}. "
        f"Desired Outcomes: {outcomes_str}. "
        f"This project involves refining a project flow and generating detailed plans. "
        f"Key stakeholders likely include project managers, team leads, and executive sponsors."
    )

    # 2. Call the AI to generate the plan, with a fallback.
    try:
        # Call the AI helper function with the brief
        raw_comm_plan = documents_helper.generate_comm_plan(desc=project_brief)
    except Exception as e:
        print(f"AI call failed: {e}. Using default plan.")
        raw_comm_plan = {} # Set to empty dict to trigger the normalizer's fallback

    # 3. Normalize the AI output. This cleans the data and provides a default if needed.
    comm_plan = documents_helper.normalize_comm_obj(raw_comm_plan, project.vision)
    
    # 4. Create the CSV response from the structured 'comm_plan' dictionary.
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="project_{project_id}_comm_plan.csv"'},
    )

    writer = csv.writer(response)
    
    # Use the keys from the first stakeholder dict as headers
    stakeholders = comm_plan.get("Stakeholders", [])
    if not stakeholders:
        writer.writerow(["Note"])
        writer.writerow(["No stakeholder information was generated."])
        return response

    headers = stakeholders[0].keys()
    writer.writerow(headers)

    # Write the stakeholder data rows
    for stakeholder in stakeholders:
        writer.writerow([stakeholder.get(h, "") for h in headers])

    return response


def download_financial_plan_view(request, project_id):
    """
    Generates an AI-powered Financial Plan and returns it as a CSV file.
    """
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return HttpResponse("Project not found.", status=404)

    # 1. Build the project brief string for the AI.
    outcomes_str = ", ".join([o.description for o in project.outcomes.all()])
    project_brief = (
        f"Project Vision: {project.vision}. "
        f"Desired Outcomes: {outcomes_str}. "
        f"This project requires a detailed financial plan."
    )

    # 2. Call the AI to generate the full financial plan object.
    try:
        financial_plan_obj = documents_helper.generate_financial_plan(desc=project_brief)
    except Exception as e:
        return HttpResponse(f"Failed to generate financial plan from AI: {e}", status=500)

    # 3. Create the CSV response.
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="project_{project_id}_financial_plan.csv"'},
    )
    writer = csv.writer(response)

    # 4. Use `_rows_from_any` to format and write each section to the CSV.
    for section_title, section_data in financial_plan_obj.items():
        writer.writerow([f"--- {section_title.upper()} ---"]) # Section header

        rows = documents_helper._rows_from_any(section_data)
        if rows:
            for row in rows:
                writer.writerow(row)
        else:
            writer.writerow(["No data for this section."])
            
        writer.writerow([]) # Add a blank line for spacing

    return response

