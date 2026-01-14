from django.urls import path

from api.personnel.leave.views import LeaveViews, LeaveAdminViews, CTDOViews, LeaveCertificationTransactionViews, \
    CTDOAdminViews, CTDOBalanceViews,LeaveForApprovalView,LeaveCompenAttachmentList,AdminLeaveCompenAttachmentList
from frontend.leave.views import search_leave_tracking,get_tracking_numbers

urlpatterns = [
    path("application/", LeaveViews.as_view(), name='api_leave'),
    path("application/admin/", LeaveAdminViews.as_view(), name='api_leave_admin'),
    path("ctdo/", CTDOViews.as_view(), name='api_ctdo'),
    path("ctdo/admin/", CTDOAdminViews.as_view(), name='api_ctdo_admin'),
    path('certification/transaction/', LeaveCertificationTransactionViews.as_view(), name='api_lv_certification_transaction'),
    path('coc/balance/', CTDOBalanceViews.as_view(), name='api_coc_balance'),
    path('for-approval/', LeaveForApprovalView.as_view(), name='leave-for-approval'),
    path('leave-compensatory/', LeaveCompenAttachmentList.as_view(), name='leave-compensatory'),
    path('admin-leave-compensatory/',AdminLeaveCompenAttachmentList.as_view(), name='admin_leave_compensatory'),
    path("search-leave/", search_leave_tracking, name="search_leave_tracking"),
    path("get-tracking-numbers/", get_tracking_numbers, name="get_tracking_numbers"),
]