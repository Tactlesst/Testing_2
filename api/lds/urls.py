from django.urls import path

from api.lds.views import LdsRsoViews, LdsRsoViewsAdmin, LdsParticipantsViews, LdsFacilitatorsViews, LdsIDPViews, LdsTrainingTitlesDataTableViews, LdsLdiPlansByTrainingViews, LdsApprovedTrainingsDashboardDataTableViews, LdsTrainingNotificationView, LdsLatestApprovedTrainingView, LdsRsoParticipantsByRsoView

urlpatterns = [
    path('', LdsRsoViews.as_view(), name='api_lds_rso'),

    #nazef added
    path('training-titles/', LdsTrainingTitlesDataTableViews.as_view(), name='api_lds_training_titles'),
    path('approved-trainings/', LdsApprovedTrainingsDashboardDataTableViews.as_view(), name='api_lds_approved_trainings_dashboard'),
    path('latest-approved-training/', LdsLatestApprovedTrainingView.as_view(), name='api_lds_latest_approved_training'),
    path('participants-by-rso/<int:rso_id>/', LdsRsoParticipantsByRsoView.as_view(), name='api_lds_participants_by_rso'),
    path('training-notification/', LdsTrainingNotificationView.as_view(), name='api_lds_training_notification'),
    path('ldi-plans/training/<int:training_id>/', LdsLdiPlansByTrainingViews.as_view(), name='api_lds_ldi_plans_by_training'),

    #nazef end
    path('participants/', LdsParticipantsViews.as_view(), name='api_lds_participants'),
    path('facilitators/', LdsFacilitatorsViews.as_view(), name='api_lds_facilitators'),
    path('admin/', LdsRsoViewsAdmin.as_view(), name='api_lds_rso_admin'),
    path('idp/', LdsIDPViews.as_view(), name='api_lds_idp')
]