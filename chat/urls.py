from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_page, name='chat_page'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/agent/control/', views.agent_control_api, name='agent_control'),
    path('api/chats/', views.chat_sessions_api, name='chat_sessions'),
    path('api/chats/<int:session_id>/', views.chat_session_detail_api, name='chat_session_detail'),
    path('api/files/', views.list_directory_files_api, name='list_directory_files'),
    path('api/graph/', views.agent_graph_api, name='agent_graph'),
    path('api/test-error/', views.test_error_api, name='test_error'),
    path('api/shutdown/', views.shutdown_server, name='shutdown_server'),
    path('logo.png', views.serve_logo, name='serve_logo'),
]