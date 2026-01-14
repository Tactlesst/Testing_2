import secrets
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import render
from api.personnel.employees.serializers import SectionHeadSerializer
from django.db.models import Q
from backend.models import Personalinfo, Empprofile, APISystemToken, APILogs, AuthUser, Section, Division


def api_log_token(token, activity):
    APILogs.objects.create(
        st=token,
        activity=activity
    )


@csrf_exempt
def api_login_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)

    token = request.headers.get('X-Token')
    if not token:
        return JsonResponse({'error_msg': 'Token is missing in headers'}, status=401)

    api_token = APISystemToken.objects.filter(token=token).first()
    if not api_token:
        return JsonResponse({'error_msg': 'Invalid token'}, status=401)

    if request.user.is_authenticated:
        return JsonResponse({'msg': 'User already logged in'}, status=200)

    username = request.POST.get('username')
    password = request.POST.get('password')
    if not username or not password:
        return JsonResponse({'error': 'Username and password are required'}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({'error': 'Invalid credentials'}, status=400)

    login(request, user)
    session_id = request.session.session_key
    auth_user = AuthUser.objects.get(id=user.id)

    try:
        personal_info = Personalinfo.objects.get(user_id=user.id)
        employee_info = Empprofile.objects.get(pi_id=personal_info.id)

        id_number = employee_info.id_number or None
        position = employee_info.position.name if employee_info.position else None
        section = employee_info.section.sec_name if employee_info.section else None
        division = employee_info.section.div.div_acronym if employee_info.section and employee_info.section.div else None
        section_id = employee_info.section.id if employee_info.section else None
        division_id = employee_info.section.div.id if employee_info.section and employee_info.section.div else None
        picture_url = employee_info.picture.url if employee_info.picture else None

    except (Personalinfo.DoesNotExist, Empprofile.DoesNotExist):
        id_number = position = section = division = section_id = division_id = picture_url = None

    api_log_token(api_token, f'{username} logged in')

    response_data = {
        'response': {
            'msg': 'Login successful'
        },
        'data': {
            "session_id": session_id,
            "username": user.username,
            "id_number": id_number,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "position": position,
            "section": section,
            "division": division,
            "section_id": section_id,
            "division_id": division_id,
            "user_type_id": auth_user.user_type_id,
            "picture": picture_url
        }
    }

    return JsonResponse(response_data, status=200)




def delete_user_sessions(user):
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    deleted_sessions = 0
    for session in sessions:
        session_data = session.get_decoded()
        if session_data.get('_auth_user_id') == str(user.id):
            session.delete()
            deleted_sessions += 1
    return deleted_sessions




@csrf_exempt
def api_logout_view(request):
    if request.method == "POST":
        token = request.headers.get('X-Token')

        if not token:
            return JsonResponse({'error_msg': 'Token is missing in headers'}, status=401)

        try:
            api_token = APISystemToken.objects.filter(token=token).first()
        except APISystemToken.DoesNotExist:
            return JsonResponse({'error_msg': 'Invalid token'}, status=401)

        username = request.POST.get('username')

        if not username:
            return JsonResponse({'error_msg': 'Username is required'}, status=400)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

        sessions_deleted = delete_user_sessions(user)
        api_log_token(api_token, f'{username} logged out')

        response_data = {
            'response': {
                'msg': f'User {username} logout successful'
            },
            'sessions_deleted': sessions_deleted
        }

        return JsonResponse(response_data, status=200)




@csrf_exempt
def api_system_generate_token(request):
    if request.method == 'POST':
        system_name = request.POST.get('system_name')

        if not system_name:
            return JsonResponse({'error': 'system_name is required'}, status=400)

        token_check = APISystemToken.objects.filter(system_name=system_name).first()

        if token_check:
            msg = 'Token already exists'
            token = None  
        else:
            token = secrets.token_urlsafe(32)
            APISystemToken.objects.create(
                token=token,
                system_name=system_name
            )
            msg = 'Token generated successfully'

        response_data = {
            'response': {
                'msg': msg
            },
            'data': {
                'system_name': system_name
            }
        }

        if token:
            response_data['data']['token'] = token

        return JsonResponse(response_data, status=200)

    return JsonResponse({'error': 'POST request required'}, status=405)

    
@csrf_exempt
def api_user_info(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET request required'}, status=405)

    token = request.headers.get('X-token')

    if not token:
        return JsonResponse({'error': 'Authorization token is required'}, status=403)

    if not APISystemToken.objects.filter(token=token).exists():
        return JsonResponse({'error': 'Invalid or expired token'}, status=403)

    position = request.GET.get('position')
    id_number = request.GET.get('id_number')
    designation = request.GET.get('designation')

    if not (position or id_number or designation):
        return JsonResponse({'error': 'At least one filter (position, id_number, or designation) is required'}, status=400)

    query = Q()
    if position:
        query &= Q(position__name__icontains=position)
    if id_number:
        query &= Q(id_number=id_number)
    if designation:
        query &= Q(designation=designation)

    employees = Empprofile.objects.filter(query).select_related(
        'pi__user', 'pi__ext', 'section__div', 'position'
    )

    if not employees.exists():
        return JsonResponse({'users': []}, status=200)

    user_data = []
    for emp in employees:
        pi = emp.pi  
        user = pi.user if pi else None

        user_data.append({
            "id_number": emp.id_number or None,
            "position": emp.position.name if emp.position else None,
            "name": f"{user.first_name} {user.last_name}".strip() if user else "Unknown",
            "designation": emp.designation or None,
            "lname": user.last_name if user else None,  
            "fname": user.first_name if user else None,
            "mname": user.middle_name if user and user.middle_name else None,
            "ext_name": pi.ext.name if pi and pi.ext else None,
            "birthdate": pi.dob.strftime("%Y-%m-%d") if pi and pi.dob else None,
            "sex": pi.get_gender if pi else None,
        })

    return JsonResponse({'users': user_data}, status=200)


#new_api


@csrf_exempt
def dtr_data(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'GET request required'}, status=405)

    token = request.headers.get('X-token')

    if not token:
        return JsonResponse({'success': False, 'error': 'Authorization token is required'}, status=403)

    if not APISystemToken.objects.filter(token=token).exists():
        return JsonResponse({'success': False, 'error': 'Invalid or expired token'}, status=403)

    position = request.GET.get('position')
    id_number = request.GET.get('id_number')
    designation = request.GET.get('designation')

    query = Q()
    if position:
        query &= Q(position__name__icontains=position)
    if id_number:
        query &= Q(id_number=id_number)
    if designation:
        query &= Q(designation=designation)

    if query:
        employees = Empprofile.objects.filter(query).select_related('pi__user')
    else:
        employees = Empprofile.objects.select_related('pi__user')

    user_data = []
    for emp in employees:
        pi = emp.pi
        user = pi.user if pi else None

        user_data.append({
            "employee_id": emp.id_number or None,
            "lastname": user.last_name if user else None,
            "firstname": user.first_name if user else None,
            "middlename": user.middle_name if user and user.middle_name else None,
        })

    return JsonResponse({'success': True, 'users': user_data}, status=200)






@csrf_exempt
def api_section_heads(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET request required'}, status=405)

    section_id = request.GET.get('section_id')
    if not section_id:
        return JsonResponse({'error': 'Missing section_id'}, status=400)

    emp = (
        Empprofile.objects
        .select_related('section')
        .filter(section_id=section_id)
        .first()
    )

    if emp and emp.section and emp.section.sec_head_id:
        section_head = (
            Empprofile.objects
            .select_related('pi__user', 'signature')
            .filter(id=emp.section.sec_head_id)
            .first()
        )
        if section_head:
            serializer = SectionHeadSerializer(section_head, context={'request': request})
            return JsonResponse({
                'section_name': emp.section.sec_name,
                **serializer.data
            }, status=200)

    return JsonResponse({'error': 'No valid Section Head assigned.'}, status=404)



@csrf_exempt
def api_preventive(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET request required'}, status=405)

    token = request.headers.get('X-token')
    if not token:
        return JsonResponse({'error': 'Authorization token is required'}, status=403)

    if not APISystemToken.objects.filter(token=token).exists():
        return JsonResponse({'error': 'Invalid or expired token'}, status=403)

    employees = Empprofile.objects.select_related('pi__user', 'section__div', 'position')

    if not employees.exists():
        return JsonResponse({'users': []}, status=200)

    user_data = []
    for emp in employees:
        personal_info = getattr(emp, 'pi', None)
        user = getattr(personal_info, 'user', None)

        user_data.append({
            "id_number": emp.id_number or None,
            "name": f"{user.first_name} {user.last_name}".strip() if user else "Unknown",
            "designation": emp.designation or None,
            "section": emp.section.sec_name if emp.section else None,
            "division": emp.section.div.div_name if emp.section and emp.section.div else None,
        })

    return JsonResponse({'users': user_data}, status=200)




@csrf_exempt
def api_division_sections(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET request required'}, status=405)

    # Token authentication
    token = request.headers.get('X-token')
    if not token:
        return JsonResponse({'error': 'Authorization token is required'}, status=403)

    if not APISystemToken.objects.filter(token=token).exists():
        return JsonResponse({'error': 'Invalid or expired token'}, status=403)

    # Get division ID (support both ?division_id and ?div_id)
    division_id = request.GET.get('division_id') or request.GET.get('div_id')

    # If no division selected yet → return list of all divisions
    if not division_id:
        divisions = Division.objects.values('id', 'div_name', 'div_acronym')
        return JsonResponse({'divisions': list(divisions)}, status=200)

    # If a division is selected → get sections with ACTIVE employee counts
    try:
        division = Division.objects.get(id=division_id)
    except Division.DoesNotExist:
        return JsonResponse({'error': 'Division not found'}, status=404)

    # Count only employees whose linked AuthUser is active
    sections = (
        Section.objects.filter(div=division)
        .annotate(
            employee_count=Count(
                'empprofile',
                filter=Q(empprofile__pi__user__is_active=1),  # only active users
                distinct=True
            )
        )
        .values('id', 'sec_name', 'sec_acronym', 'employee_count')
    )

    data = {
        "div_id": division.id,
        "div_name": division.div_name,
        "div_acronym": division.div_acronym,
        "sections": list(sections),
    }

    return JsonResponse(data, status=200)




# @api_view(['GET'])
# def api_list(request):
#     api_endpoints = {
#         'user_info': '/api/user-info/',
#         'section_heads': '/api/api-section-heads/',
#         'login': '/api/login/v2/',
#     }

#     if request.accepted_renderer.format == 'json':
#         return Response(api_endpoints)

#     return render(request, 'rest_framework/api_list.html', {'api_endpoints': api_endpoints})
