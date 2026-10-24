from django.urls import path
from .views import AssistantView, ReminderStatsView

urlpatterns = [
    path("", AssistantView.as_view(), name="assistant"),
    path("stats/", ReminderStatsView.as_view(), name="assistant-stats"),
]
