import re
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from frontend.models import Workexperience
from backend.models import PasRfd, Rcompliance, Empprofile, Resignationreq, AuthUser, Personalinfo, PasTempseparation
from django.utils import timezone


@login_required
@permission_required("auth.resignation_request")
def deactivation_request(request):
    if request.method == "POST":
        user_id = re.split(r'\[|\]', request.POST.get('user_id'))
        emp = Empprofile.objects.filter(id_number=user_id[1]).first()

        date_effectivity_str = request.POST.get('date_effectivity')
        date_effectivity = datetime.strptime(date_effectivity_str, "%Y-%m-%d").date()
        today = timezone.now().date()

        tfs_id = request.POST.get('tempsep') 
        status = 0  
        date_approved = None

        if date_effectivity <= today:
            status = 1
            date_approved = timezone.now()

            if tfs_id != '5':  
                user = AuthUser.objects.filter(id=emp.pi.user.id).first()
                if user and user.is_active:
                    user.is_active = False
                    user.is_staff = False
                    user.save()

                    latest_we = Workexperience.objects.filter(
                        pi__user=user,
                        we_to__isnull=True
                    ).order_by('-we_from').first()

                    if latest_we:
                        latest_we.we_to = date_effectivity
                        latest_we.save()

        PasRfd.objects.create(
            user_id=emp.id,
            date_effectivity=date_effectivity_str,
            tfs_id=tfs_id,
            remarks=request.POST.get('remarks'),
            status=status,
            date_approved=date_approved,
            created_by=Empprofile.objects.get(pi__user=AuthUser.objects.get(username=request.user.username))
        )

        messages.success(request, "The resignation request was successfully added")
        return JsonResponse({'data': 'success'})


    rows = request.GET.get('rows', 20)
    page = request.GET.get('page', 1)
    search = request.GET.get('search', '')

    active_requests = PasRfd.objects.filter(
        Q(user__pi__user__first_name__icontains=search) |
        Q(user__pi__user__last_name__icontains=search) |
        Q(user__empstatus__name__icontains=search) |
        Q(user__empstatus__acronym__icontains=search) |
        Q(user__position__name__icontains=search) |
        Q(user__position__acronym__icontains=search) |
        Q(date_requested__icontains=search) |
        Q(tfs__name__icontains=search)
    ).order_by('-date_requested')

    inactive_users = Empprofile.objects.filter(pi__user__is_active=False)
    
    context = {
        'data': Paginator(active_requests, rows).page(page),
        'inactive_users': inactive_users,
        'tempsep': PasTempseparation.objects.all(),
        'title': 'employee',
        'sub_title': 'deactivation_request'
    }

    return render(request, 'backend/pas/resignation/deactivation_request.html', context)


# @login_required
# @csrf_exempt
# @permission_required("auth.resignation_request")
# def view_resignation_request(request, pk):
#     if request.method == "POST":
#         check = Rcompliance.objects.filter(user_id=request.POST.get('emp_id'), rreq_id=request.POST.get('req_id'))

#         if check is not None:
#             Rcompliance.objects.create(
#                 user_id=request.POST.get('emp_id'),
#                 rreq_id=request.POST.get('req_id')
#             )

#         return JsonResponse({'data': 'success'})

#     emp = Empprofile.objects.filter(id=pk).first()
#     context = {
#         'req': Resignationreq.objects.filter(empstatus_id=emp.empstatus_id),
#         'emp': emp,
#         'rfd': PasRfd.objects.filter(user_id=pk).first(),
#         'total_compliance': Rcompliance.objects.filter(user_id=pk).count(),
#     }
#     return render(request, 'backend/pas/resignation/view_resignation_detail.html', context)



@login_required
@csrf_exempt
@permission_required("auth.resignation_request")
def view_resignation_request(request, pk):
    if request.method == "POST":
        emp_id = request.POST.get('emp_id')
        req_id = request.POST.get('req_id')

        pas_rfd = PasRfd.objects.filter(id=req_id, user_id=emp_id).first()
        if pas_rfd and pas_rfd.status == 0:  
            pas_rfd.status = 1  
            pas_rfd.date_approved = timezone.now()  
            pas_rfd.save()

        check = Rcompliance.objects.filter(
            user_id=emp_id,
            rreq_id=req_id
        )
        if not check.exists():
            Rcompliance.objects.create(
                user_id=emp_id,
                rreq_id=req_id
            )

        return JsonResponse({'data': 'success'})

    emp = Empprofile.objects.filter(id=pk).first()

    # Retrieve resignation request details
    rfd_id = request.GET.get('rfd_id')  
    if rfd_id:
        pas_rfd = PasRfd.objects.filter(id=rfd_id, user_id=pk).first()
    else:
        pas_rfd = PasRfd.objects.filter(user_id=pk).order_by('-id').first() 

    context = {
        'req': Resignationreq.objects.filter(empstatus_id=emp.empstatus_id),
        'emp': emp,
        'rfd': pas_rfd,
        'total_compliance': Rcompliance.objects.filter(user_id=pk).count(),
    }

    return render(request, 'backend/pas/resignation/view_resignation_detail.html', context)


# @permission_required("auth.resignation_request")
# def deactivate_user(request):
#     if request.method == "POST":
#         user = AuthUser.objects.filter(id=request.POST.get('user_id')).first()

#         if user and user.is_active:
#             user.is_active = 0
#             user.is_staff = 0  
#             user.save()
#             PasRfd.objects.filter(user_id=request.POST.get('emp_id')).update(
#                 status=1,
#                 date_approved=datetime.now()
#             )
#             return JsonResponse({'status': 'success', 'message': 'User account has been deactivated!'})

#     return JsonResponse({'status': 'error', 'message': 'User is already inactive!'})



@csrf_exempt
@permission_required("auth.resignation_request")
def deactivate_user(request):
    if request.method == "POST":
        user_id = request.POST.get('user_id')
        emp_id = request.POST.get('emp_id')
        rfd_id = request.POST.get('rfd_id')

        user = AuthUser.objects.filter(id=user_id).first()

        if user and user.is_active:
            user.is_active = False
            user.is_staff = False
            user.save()

     
            pas_rfd = PasRfd.objects.filter(user_id=emp_id).order_by('-date_requested').first()


            if pas_rfd:
                pas_rfd.status = 1
                pas_rfd.date_approved = timezone.now()
                pas_rfd.save()

                latest_we = Workexperience.objects.filter(
                    pi__user=user,
                    we_to__isnull=True
                ).order_by('-we_from').first()

                if latest_we and pas_rfd.date_effectivity:
                    latest_we.we_to = pas_rfd.date_effectivity
                    latest_we.save()

            return JsonResponse({'status': 'success', 'message': 'User account has been deactivated!'})

    return JsonResponse({'status': 'error', 'message': 'User is already inactive!'})





@login_required
@csrf_exempt
@permission_required("auth.resignation_request")
def activate_user(request, pk):
    if request.method == "POST":
        user = AuthUser.objects.filter(id=pk).first()
        
        if user and not user.is_active:
            user.is_active = True
            user.is_staff = True  
            user.save()
            return JsonResponse({'status': 'success', 'message': 'User activated successfully and set as staff!'})

        return JsonResponse({'status': 'error', 'message': 'User is already active!'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method!'}, status=400)

@login_required
@csrf_exempt
@permission_required("auth.resignation_request")
def delete_compliance(request):
    Rcompliance.objects.filter(Q(user_id=request.POST.get('emp_id')) & Q(rreq_id=request.POST.get('req_id'))).delete()
    return JsonResponse({'data': 'success'})




@login_required
@permission_required("auth.resignation_request")
def rfd(request):
    if request.method == "POST":
        PasRfd.objects.create(
            user_id=request.POST.get('user_id'),
            date_effectivity=request.POST.get('date_effectivity'),
            tfs_id=request.POST.get('tempsep'),
            remarks=request.POST.get('remarks'),
            status=0,
        )
        return JsonResponse({'data': 'success'})
