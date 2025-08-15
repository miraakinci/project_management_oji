from django.urls import path
from . import views

urlpatterns = [
    # The home page where the user enters a prompt
    path('', views.index, name='index'),
    
    # The page to edit the project flow, it needs a project_id
    path('project/<int:project_id>/', views.get_project_flow, name='project_flow'),

    path('project/<int:project_id>/update-flow-ajax/', views.update_flow_ajax, name='update_flow_ajax'),

    path('project/<int:project_id>/download-comm-plan/', views.download_comm_plan_view, name='download_comm_plan_ajax'),

    path('project/<int:project_id>/download-financial-plan/', views.download_financial_plan_view, name='download_financial_plan_ajax'),

    path('project/<int:project_id>/gantt-data/', views.gantt_chart_data, name='gantt_chart_data')
]