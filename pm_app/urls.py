from django.urls import path
from . import views

urlpatterns = [
    # The home page where the user enters a prompt
    path('', views.index, name='index'),
    
    # The page to edit the project flow, it needs a project_id
    path('project/<int:project_id>/', views.get_project_flow, name='project_flow'),

    path('project/<int:project_id>/update-flow-ajax/', views.update_flow_ajax, name='update_flow_ajax'),

    # The final page with the gantt chart, it also needs a project_id
    path('gantt/<int:project_id>/', views.gantt_chart, name='gantt_chart')
]