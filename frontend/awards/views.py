import re
from datetime import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from backend.awards.models import Awards, Nominees, Attachments, Awcategory, Criteria, Deliberation, AwGuidelines, \
    AwEligibility,Calibration,Points_calibration
from backend.models import Empprofile, Division
from frontend.models import PortalConfiguration,Workexperience
from django.db.models import Q
from dateutil.relativedelta import relativedelta
from backend.ipcr.models import IPC_Rating
from django.utils.timezone import now
import json




@login_required
def awards(request):
    context = {
        'categories': Awcategory.objects.filter(status=1),
        'name': awards,
        'tab_parent': 'Rewards & Recognition',
        'tab_title': 'Nominations',
        'title': 'rewards_and_recognition',
        'sub_title': 'nominations',
        'year': datetime.now().year
    }
    return render(request, 'frontend/awards/awards.html', context)




# @login_required
# def view_awards(request, year, category):
#     if category == "all":
#         awards = Awards.objects.filter(Q(year=year), Q(status=1)).order_by(
#             'name')
#     else:
#         awards = Awards.objects.filter(Q(year=year), Q(category_id=category), Q(status=1)).order_by(
#             'name')

#     nominees = Nominees.objects.filter(Q(awards__year=year)).order_by('-id')
#     latest = []
#     for nominee in nominees[:10]:
#         latest.append('<div class="row">'
#                       '<div class="col-xs-2">'
#                       '<img alt="image" class="img-circle" src="{}" '
#                       'style="object-fit:cover; height:48px; width:48px;">'
#                       '</div>'
#                       '<div class="col-xs-10">'
#                       '<strong><a href="javascript:;">{}</a></strong> has been nominated as '
#                       '<a class="btn-edit-modal" data-id="{}" href="javascript:;">{}</a>. <br>'
#                       '<small class="text-muted pull-right">{}</small>'
#                       '</div>'
#                       '</div>'
#                       .format(nominee.nominee.picture.url, nominee.nominee.pi.user.get_fullname,
#                               nominee.awards_id, nominee.awards.name, nominee.datetime.strftime('%b %d, %Y @ %I:%M %p')))

#     context = {
#         'awards': awards,
#         'latest': latest,
#         'others': len(nominees) - 10
#     }
#     return render(request, 'frontend/awards/view_awards.html', context)


@login_required
def view_awards(request, year, category):
    if category == "all":
        awards = Awards.objects.filter(Q(year=year), Q(status=1)).order_by('name')
    else:
        awards = Awards.objects.filter(Q(year=year), Q(category_id=category), Q(status=1)).order_by('name')

    nominees = Nominees.objects.filter(Q(awards__year=year)).order_by('-id')
    latest = []
    others_list = []

    for nominee in nominees[:10]:
        latest.append(
            '<div class="row">'
            '<div class="col-xs-2">'
            f'<img alt="image" class="img-circle" src="{nominee.nominee.picture.url}" '
            'style="object-fit:cover; height:48px; width:48px;">'
            '</div>'
            '<div class="col-xs-10">'
            f'<strong><a href="javascript:;">{nominee.nominee.pi.user.get_fullname}</a></strong> has been nominated as '
            f'<a class="btn-edit-modal" data-id="{nominee.awards_id}" href="javascript:;">{nominee.awards.name}</a>. <br>'
            f'<small class="text-muted pull-right">{nominee.datetime.strftime("%b %d, %Y @ %I:%M %p")}</small>'
            '</div>'
            '</div>'
        )

    for nominee in nominees[10:]:
        others_list.append(
            '<div class="row">'
            '<div class="col-xs-2">'
            f'<img alt="image" class="img-circle" src="{nominee.nominee.picture.url}" '
            'style="object-fit:cover; height:48px; width:48px;">'
            '</div>'
            '<div class="col-xs-10">'
            f'<strong><a href="javascript:;">{nominee.nominee.pi.user.get_fullname}</a></strong> has been nominated as '
            f'<a class="btn-edit-modal" data-id="{nominee.awards_id}" href="javascript:;">{nominee.awards.name}</a>. <br>'
            f'<small class="text-muted pull-right">{nominee.datetime.strftime("%b %d, %Y @ %I:%M %p")}</small>'
            '</div>'
            '</div>'
        )

    context = {
        'awards': awards,
        'latest': latest,
        'others': len(others_list),
        'others_list': others_list,
    }
    return render(request, 'frontend/awards/view_awards.html', context)


@login_required
@csrf_exempt
def nomination_mark_as_winners(request):
    Nominees.objects.filter(id=request.POST.get('id')).update(
        is_winner=1
    )
    nominees_obj = Nominees.objects.filter(id=request.POST.get('id')).first()
    return JsonResponse({'success': True, 'award_name': nominees_obj.awards.name})


@login_required
@csrf_exempt
def nomination_unmark_as_winners(request):
    Nominees.objects.filter(id=request.POST.get('id')).update(
        is_winner=0
    )
    nominees_obj = Nominees.objects.filter(id=request.POST.get('id')).first()
    return JsonResponse({'success': True, 'award_name': nominees_obj.awards.name})





# @login_required
# def view_nominees(request, pk):
#     award = Awards.objects.filter(id=pk).first()
#     division = Division.objects.filter(div_chief_id=request.session['emp_id']).first()

#     if division or request.user.is_superuser:
#         nominees = Nominees.objects.filter(awards_id=pk).extra(
#             select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
#             order_by=['-is_winner', '-status', '-manual']
#         )
#     else:
#         nominees = Nominees.objects.filter(awards_id=pk, nominated_by_id=request.session['emp_id']).extra(
#             select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
#             order_by=['-is_winner', '-status', '-manual']
#         )

#     for nominee in nominees:
#         emp_profile = nominee.nominee

#         work_experiences = Workexperience.objects.filter(
#             Q(pi=emp_profile.pi) & 
#             (Q(company__icontains='DSWD') | Q(company__icontains='Department of Social Welfare and Development'))
#         ).order_by('-we_to')

#         total_years = 0
#         total_months = 0

#         for work_experience in work_experiences:
#             if work_experience.we_from and work_experience.we_to:
#                 delta = relativedelta(work_experience.we_to, work_experience.we_from)
#                 total_years += delta.years
#                 total_months += delta.months

#                 if total_months >= 12:
#                     total_years += total_months // 12
#                     total_months = total_months % 12  

#         if total_years > 0 and total_months > 0:
#             nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''} and {total_months} month{'s' if total_months > 1 else ''}"
#         elif total_years > 0:
#             nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''}"
#         elif total_months > 0:
#             nominee.years_of_service = f"{total_months} month{'s' if total_months > 1 else ''}"
#         else:
#             nominee.years_of_service = "Not Available"

#         if nominee.list_accomplishment:
#             nominee.list_accomplishment = nominee.list_accomplishment.split(',')
#         if nominee.list_remarks:
#             nominee.list_remarks = nominee.list_remarks.split(',')
#         if nominee.awards_received:
#             nominee.awards_received = nominee.awards_received.split(',')
#         if nominee.awards_received_remarks:
#             nominee.awards_received_remarks = nominee.awards_received_remarks.split(',')

#     today = datetime.now().date()
#     isnotdone = Awards.objects.filter(nomination_end__gte=today, id=pk)

#     context = {
#         'nominees': nominees if nominees else None,
#         'row': award,
#         'criteria': Criteria.objects.filter(awards_id=pk),
#         'eligibility': AwEligibility.objects.filter(awards_id=pk),
#         'attachments': Attachments.objects.filter(awards_id=pk),
#         'isnotdone': isnotdone,
#         'pk': pk
#     }   

#     return render(request, 'frontend/awards/view_nominees.html', context)


@login_required
def view_nominees(request, pk):
    award = Awards.objects.filter(id=pk).first()
    division = Division.objects.filter(div_chief_id=request.session['emp_id']).first()

    if division or request.user.is_superuser:
        nominees = Nominees.objects.filter(awards_id=pk).extra(
            select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
            order_by=['-is_winner', '-status', '-manual']
        )
    else:
        nominees = Nominees.objects.filter(awards_id=pk, nominated_by_id=request.session['emp_id']).extra(
            select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
            order_by=['-is_winner', '-status', '-manual']
        )

    for nominee in nominees:
        emp_profile = nominee.nominee

        work_experiences = Workexperience.objects.filter(
            Q(pi=emp_profile.pi) & 
            (Q(company__icontains='DSWD') | Q(company__icontains='Department of Social Welfare and Development'))
        ).order_by('we_from') 

        date_ranges = []
        for work_experience in work_experiences:
            we_from = work_experience.we_from
            we_to = work_experience.we_to
            if we_from and we_to:
                if we_from > we_to:
                    continue
                if we_from.year < 1970 or we_to.year < 1970: 
                    continue
                date_ranges.append((we_from, we_to))

        merged_ranges = []
        for start, end in sorted(date_ranges):
            if not merged_ranges:
                merged_ranges.append([start, end])
            else:
                last_start, last_end = merged_ranges[-1]
                if start <= last_end:
                    if end > last_end:
                        merged_ranges[-1][1] = end
                else:
                    merged_ranges.append([start, end])

        total_years = 0
        total_months = 0

        for start, end in merged_ranges:
            delta = relativedelta(end, start)
            total_years += delta.years
            total_months += delta.months
            if total_months >= 12:
                total_years += total_months // 12
                total_months = total_months % 12

        if total_years > 0 and total_months > 0:
            nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''} and {total_months} month{'s' if total_months > 1 else ''}"
        elif total_years > 0:
            nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''}"
        elif total_months > 0:
            nominee.years_of_service = f"{total_months} month{'s' if total_months > 1 else ''}"
        else:
            nominee.years_of_service = "Not Available"

        if nominee.list_accomplishment:
            nominee.list_accomplishment = nominee.list_accomplishment.split('||')
        if nominee.list_remarks:
            nominee.list_remarks = nominee.list_remarks.split('||')
        if nominee.awards_received:
            nominee.awards_received = nominee.awards_received.split('||')
        if nominee.awards_received_remarks:
            nominee.awards_received_remarks = nominee.awards_received_remarks.split('||')

        if nominee.supporting_link:
            nominee.link_display = nominee.supporting_link
        else:
            nominee.link_display = None

    today = datetime.now().date()
    isnotdone = Awards.objects.filter(nomination_end__gte=today, id=pk)

    context = {
        'nominees': nominees if nominees else None,
        'row': award,
        'criteria': Criteria.objects.filter(awards_id=pk),
        'eligibility': AwEligibility.objects.filter(awards_id=pk),
        'attachments': Attachments.objects.filter(awards_id=pk),
        'isnotdone': isnotdone,
        'pk': pk
    }   

    return render(request, 'frontend/awards/view_nominees.html', context)


# @login_required
# def view_nominees(request, pk):
#     award = Awards.objects.filter(id=pk).first()
#     division = Division.objects.filter(div_chief_id=request.session['emp_id']).first()

#     if division or request.user.is_superuser:
#         nominees = Nominees.objects.filter(awards_id=pk).extra(
#             select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
#             order_by=['-is_winner', '-status', '-manual']
#         )
#     else:
#         nominees = Nominees.objects.filter(awards_id=pk, nominated_by_id=request.session['emp_id']).extra(
#             select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
#             order_by=['-is_winner', '-status', '-manual']
#         )

#     for nominee in nominees:
#         emp_profile = nominee.nominee

#         work_experiences = Workexperience.objects.filter(
#             Q(pi=emp_profile.pi) & 
#             (Q(company__icontains='DSWD') | Q(company__icontains='Department of Social Welfare and Development'))
#         ).order_by('-we_to')

#         total_years = 0
#         total_months = 0

#         for work_experience in work_experiences:
#             if work_experience.we_from and work_experience.we_to:
#                 delta = relativedelta(work_experience.we_to, work_experience.we_from)
#                 total_years += delta.years
#                 total_months += delta.months

#                 if total_months >= 12:
#                     total_years += total_months // 12
#                     total_months = total_months % 12  

#         if total_years > 0 and total_months > 0:
#             nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''} and {total_months} month{'s' if total_months > 1 else ''}"
#         elif total_years > 0:
#             nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''}"
#         elif total_months > 0:
#             nominee.years_of_service = f"{total_months} month{'s' if total_months > 1 else ''}"
#         else:
#             nominee.years_of_service = "Not Available"

#         if nominee.list_accomplishment:
#             nominee.list_accomplishment = nominee.list_accomplishment.split(',')
#         if nominee.list_remarks:
#             nominee.list_remarks = nominee.list_remarks.split(',')
#         if nominee.awards_received:
#             nominee.awards_received = nominee.awards_received.split(',')
#         if nominee.awards_received_remarks:
#             nominee.awards_received_remarks = nominee.awards_received_remarks.split(',')

#     today = datetime.now().date()
#     isnotdone = Awards.objects.filter(nomination_end__gte=today, id=pk)

#     context = {
#         'nominees': nominees if nominees else None,
#         'row': award,
#         'criteria': Criteria.objects.filter(awards_id=pk),
#         'eligibility': AwEligibility.objects.filter(awards_id=pk),
#         'calibration': Calibration.objects.filter(awards_id=pk),

#         'attachments': Attachments.objects.filter(awards_id=pk),
#         'isnotdone': isnotdone,
#         'pk': pk
#     }   

#     return render(request, 'frontend/awards/view_nominees.html', context)



# @login_required
# def view_nominees(request, pk):
#     award = Awards.objects.filter(id=pk).first()
#     division = Division.objects.filter(div_chief_id=request.session['emp_id']).first()
#     if division or request.user.is_superuser:
#         nominees = Nominees.objects.filter(awards_id=pk).extra(
#             select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
#             order_by=['-is_winner', '-status', '-manual']
#         )
#     else:
#         nominees = Nominees.objects.filter(awards_id=pk, nominated_by_id=request.session['emp_id']).extra(
#             select={'manual': 'FIELD(nominated_by_id,%s)' % ','.join(map(str, [request.session['emp_id']]))},
#             order_by=['-is_winner', '-status', '-manual']
#         )

#     today = datetime.now().date()
#     isnotdone = Awards.objects.filter(nomination_end__gte=today, id=pk)

#     context = {
#         'nominees': nominees if nominees else None,
#         'row': award,
#         'criteria': Criteria.objects.filter(awards_id=pk),
#         'eligibility': AwEligibility.objects.filter(awards_id=pk),
#         'attachments': Attachments.objects.filter(awards_id=pk),
#         'isnotdone': isnotdone,
#         'pk': pk
#     }
#     return render(request, 'frontend/awards/view_nominees.html', context)


@login_required
def nominee_count(request, pk):
    noms = Nominees.objects.filter(awards_id=pk).count()
    e = ["Number of Nominees: " + str(noms)]
    return JsonResponse({'data': e})


# @login_required
# def add_nominee(request, pk):
#     if request.method == "POST":
#         nominee = re.split('\[|\]', request.POST.get('nominee'))
#         name = Empprofile.objects.values('id').filter(id_number=nominee[1]).first()
#         details = Nominees(
#             awards_id=pk,
#             nominee_id=name['id'],
#             nominated_by_id=request.session['emp_id'],
#             datetime=datetime.now(),
#             why=request.POST.get('why'),
#             title=request.POST.get('title') if request.POST.get('title') else None,
#             status=0,
#             is_winner=0,
#         )

#         details.save()
#         return JsonResponse({'data': 'success'})
        
#         # xx = Nominees.objects.filter(Q(nominee_id=name['id']), Q(awards_id=pk)).count()
#         # 
#         # if xx == 0:
#         #     details.save()
#         #     return JsonResponse({'data': 'success'})
#         # else:
#         #     return JsonResponse({'data': 'failed', 'error': 'Duplicate nomination.'})

#     context = {
#         'awards_id': pk,
#         'award': Awards.objects.filter(id=pk).first(),
#     }
#     return render(request, 'frontend/awards/add_nominee.html', context)


@login_required
def add_nominee(request, pk):
    list_accomplishment = ""  
    list_remarks = ""  
    awards_received = ""
    awards_received_remarks = "" 

    if request.method == "POST":
        nominee = re.split('\[|\]', request.POST.get('nominee'))
        name = Empprofile.objects.values('id').filter(id_number=nominee[1]).first()

        # list_accomplishment = ",".join(request.POST.getlist('list_accomplishment[]')) 
        # list_remarks = ",".join(request.POST.getlist('remarks_accomplishment[]'))  
        # awards_received = ",".join(request.POST.getlist('awards_received[]')) 
        # awards_received_remarks = ",".join(request.POST.getlist('remarks_awards_received[]')) 

        list_accomplishment = "||".join(request.POST.getlist('list_accomplishment[]')) 
        list_remarks = "||".join(request.POST.getlist('remarks_accomplishment[]'))  
        awards_received = "||".join(request.POST.getlist('awards_received[]')) 
        awards_received_remarks = "||".join(request.POST.getlist('remarks_awards_received[]'))
        supporting_link = request.POST.get('supporting_link')


        details = Nominees(
            awards_id=pk,
            nominee_id=name['id'],
            nominated_by_id=request.session['emp_id'],
            datetime=datetime.now(),
            why=request.POST.get('why'),
            title=request.POST.get('title') if request.POST.get('title') else None,
            list_accomplishment=list_accomplishment, 
            list_remarks=list_remarks,  
            awards_received=awards_received,
            awards_received_remarks=awards_received_remarks, 
            status=0,
            is_winner=0,
            supporting_link=supporting_link, 

                    )
        details.save()
        return JsonResponse({'data': 'success'})

    context = {
        'awards_id': pk,
        'award': Awards.objects.filter(id=pk).first(),
        'list_accomplishments': list_accomplishment.split('||') if list_accomplishment else [],
        'list_remarks': list_remarks.split('||') if list_remarks else [],
        'awards_received_list': awards_received.split('||') if awards_received else [],
        'awards_received_remarks': awards_received_remarks.split('||') if awards_received_remarks else [],

    }
    return render(request, 'frontend/awards/add_nominee.html', context)



@login_required
def edit_nominee(request, pk):
    noms = Nominees.objects.filter(id=pk).first()
    
    if request.method == "POST":
        list_accomplishment = "||".join(request.POST.getlist('list_accomplishment[]'))
        list_remarks = "||".join(request.POST.getlist('remarks_accomplishment[]'))
        awards_received = "||".join(request.POST.getlist('awards_received[]'))
        awards_received_remarks = "||".join(request.POST.getlist('remarks_awards_received[]'))
        supporting_link = request.POST.get('supporting_link')



        Nominees.objects.filter(id=pk).update(
            datetime=datetime.now(),
            why=request.POST.get('why'),
            title=request.POST.get('title') if request.POST.get('title') else None,
            list_accomplishment=list_accomplishment,
            list_remarks=list_remarks,
            awards_received=awards_received,
            awards_received_remarks=awards_received_remarks,
            supporting_link=supporting_link,
        )
        return JsonResponse({'data': 'success'})

    list_accomplishment_list = list(zip(
        noms.list_accomplishment.split('||') if noms.list_accomplishment else [],
        noms.list_remarks.split('||') if noms.list_remarks else [],
    ))

    awards_received_list = list(zip(
        noms.awards_received.split('||') if noms.awards_received else [],
        noms.awards_received_remarks.split('||') if noms.awards_received_remarks else [],
    ))


    context = {
        'awards_id': noms.awards_id,
        'nominee': noms,
        'award': Awards.objects.filter(id=noms.awards.id).first(),
        'list_accomplishment_list': list_accomplishment_list,
        'awards_received_list': awards_received_list,
    }
    
    return render(request, 'frontend/awards/add_nominee.html', context)

# @login_required
# def edit_nominee(request, pk):
#     noms = Nominees.objects.filter(id=pk).first()
#     if request.method == "POST":
#         toupdate = Nominees.objects.filter(id=pk)
#         toupdate.update(datetime=datetime.now())
#         toupdate.update(why=request.POST.get('why'))
#         toupdate.update(title=request.POST.get('title') if request.POST.get('title') else None)
#         return JsonResponse({'data': 'success'})

#     context = {
#         'awards_id': noms.awards_id,
#         'nominee': noms,
#         'award': Awards.objects.filter(id=noms.awards.id).first(),
#     }
#     return render(request, 'frontend/awards/add_nominee.html', context)




@login_required
@csrf_exempt
def delete_nominee(request, pk):
    Nominees.objects.filter(Q(id=pk)).delete()
    return JsonResponse({'data': 'success'})


# @login_required
# @permission_required('auth.awards_deliberators')
# def deliberation(request):
#     if request.method == "POST":
#         if request.POST.get('action') == 'save':
#             criteria_id = request.POST.getlist('criteria_id[]')
#             nominee_id = request.POST.getlist('nominee_id[]')
#             grade = request.POST.getlist('grade[]')

#             grades = [
#                 {'c': c, 'n': n, 'g': g} for c, n, g in zip(criteria_id, nominee_id, grade)
#             ]

#             remarks_nominee_id = request.POST.getlist('remarks_nominee_id[]')
#             remarks = request.POST.getlist('remarks[]')

#             allremarks = [
#                 {'n': n, 'r': r}
#                 for n, r in zip(remarks_nominee_id, remarks)
#             ]

#             for row in grades:
#                 doesexist = Deliberation.objects.filter(Q(nominee_id=row['n']), Q(criteria_id=row['c']), Q(graded_by_id=request.session['emp_id'])).first()
#                 rm = ''
#                 for r in allremarks:
#                     if r['n'] == row['n']:
#                         rm = r['r']

#                 if row['g'] != '':
#                     if not doesexist:
#                         Deliberation.objects.create(
#                             criteria_id=row['c'],
#                             nominee_id=row['n'],
#                             grade=row['g'],
#                             remarks=rm,
#                             graded_by_id=request.session['emp_id'],
#                             graded_on=datetime.now()
#                         )
#                     else:
#                         Deliberation.objects.filter(Q(nominee_id=row['n']), Q(criteria_id=row['c']), Q(graded_by_id=request.session['emp_id']))\
#                             .update(grade=row['g'], graded_on=datetime.now(), remarks=rm)

#         toggle = PortalConfiguration.objects.filter(key_name='Deliberation').first()
#         if toggle.key_acronym == '1':
#             context = {
#                 'title': 'human_resource_transactions',
#                 'sub_title': 'awardsf',
#                 'sub_sub_title': 'deliberation',
#                 'criteria': Criteria.objects.filter(Q(awards_id=request.POST.get('awards')), Q(is_active=1)).order_by('-percentage', 'id', 'name'),
#                 'awards': Awards.objects.filter(id=request.POST.get('awards'), year=request.POST.get('year')).first(),
#                 'data': Nominees.objects.filter(awards_id=request.POST.get('awards'), awards__year=request.POST.get('year')),
#                 'category': Awcategory.objects.filter(status=1),
#                 'notpost': False,
#                 'toggle': True,
#                 'year': request.POST.get('year'),
#                 'ctgy': request.POST.get('category'),
#                 'awrd': request.POST.get('awards'),
#             }
#         else:
#             a = list()
#             b = Deliberation.objects.values('graded_by_id') \
#                 .filter(Q(nominee__awards_id=request.POST.get('awards')), Q(criteria__is_active=1)) \
#                 .annotate(total_grade=Sum('grade'))
#             for x in b:
#                 a.append(x['graded_by_id'])
#             c = Empprofile.objects.filter(Q(id__in=a))

#             context = {
#                 'title': 'human_resource_transactions',
#                 'sub_title': 'awardsf',
#                 'sub_sub_title': 'deliberation',
#                 'graders': c,
#                 'awards': Awards.objects.filter(id=request.POST.get('awards'), year=request.POST.get('year')).first(),
#                 'data': Nominees.objects.filter(awards_id=request.POST.get('awards'),
#                                                 awards__year=request.POST.get('year')),
#                 'category': Awcategory.objects.filter(status=1),
#                 'notpost': False,
#                 'toggle': False,
#                 'year': request.POST.get('year'),
#                 'ctgy': request.POST.get('category'),
#                 'awrd': request.POST.get('awards'),
#             }
#         return render(request, 'frontend/awards/deliberation.html', context)

#     context = {
#         'tab_title': 'Deliberation',
#         'title': 'rewards_and_recognition',
#         'sub_title': 'awardsf',
#         'sub_sub_title': 'deliberation',
#         'notpost': True,
#         'category': Awcategory.objects.filter(status=1),
#     }
#     return render(request, 'frontend/awards/deliberation.html', context)

@login_required
@permission_required('auth.awards_deliberators')
def deliberation(request):
    if request.method == "POST":
        if request.POST.get('action') == 'save':
            criteria_id = request.POST.getlist('criteria_id[]')
            nominee_id = request.POST.getlist('nominee_id[]')
            grade = request.POST.getlist('grade[]')

            grades = [{'c': c, 'n': n, 'g': g} for c, n, g in zip(criteria_id, nominee_id, grade)]

            remarks_nominee_id = request.POST.getlist('remarks_nominee_id[]')
            remarks = request.POST.getlist('remarks[]')

            allremarks = [{'n': n, 'r': r} for n, r in zip(remarks_nominee_id, remarks)]

            for row in grades:
                doesexist = Deliberation.objects.filter(
                    Q(nominee_id=row['n']),
                    Q(criteria_id=row['c']),
                    Q(graded_by_id=request.session['emp_id'])
                ).first()

                rm = ''
                for r in allremarks:
                    if r['n'] == row['n']:
                        rm = r['r']

                if row['g'] != '':
                    if not doesexist:
                        Deliberation.objects.create(
                            criteria_id=row['c'],
                            nominee_id=row['n'],
                            grade=row['g'],
                            remarks=rm,
                            graded_by_id=request.session['emp_id'],
                            graded_on=datetime.now()
                        )
                    else:
                        doesexist.grade = row['g']
                        doesexist.remarks = rm
                        doesexist.graded_on = datetime.now()
                        doesexist.save()

        toggle = PortalConfiguration.objects.filter(key_name='Deliberation').first()
        awards_id = request.POST.get('awards')
        year = request.POST.get('year')

        nominees = Nominees.objects.filter(
            awards_id=awards_id,
            awards__year=year
        ).select_related('nominee__pi__user', 'nominee__empstatus')

        for nominee in nominees:
            if nominee.list_accomplishment:
                nominee.list_accomplishment = nominee.list_accomplishment.split('||')      
            else:
                nominee.list_accomplishment = [] 
            if nominee.list_remarks:
                nominee.list_remarks = nominee.list_remarks.split('||') 
            else:
                nominee.list_remarks = [] 

            if nominee.awards_received:
                nominee.awards_received = nominee.awards_received.split('||')
            else:
                nominee.awards_received = []  

            if nominee.awards_received_remarks:
                nominee.awards_received_remarks = nominee.awards_received_remarks.split('||')
            else:
                nominee.awards_received_remarks = []  
        
        current_year = now().year

        for row in nominees:
            row.ipcr_ratings = json.dumps(list( 
                IPC_Rating.objects.filter(
                    emp=row.nominee,
                    year__gte=current_year - 3,
                    year__lt=current_year
                ).order_by('-year', '-semester').values('year', 'semester', 'ipcr')
            ))
            # print(f"Nominee: {row.nominee}, IPCR: {row.ipcr_ratings}")  
        
        for nominee in nominees:
            emp_profile = nominee.nominee

            work_experiences = Workexperience.objects.filter(
                Q(pi=emp_profile.pi) & 
                (Q(company__icontains='DSWD') | Q(company__icontains='Department of Social Welfare and Development'))
            ).order_by('-we_to')

            nominee.supporting_link = nominee.supporting_link or ''

            # --- Begin Modified Years of Service Calculation ---

            # Step 1: Collect date ranges as tuples
            date_ranges = []
            for work_experience in work_experiences:
                we_from = work_experience.we_from
                we_to = work_experience.we_to
                if we_from and we_to:
                    if we_from > we_to:
                        continue
                    if we_from.year < 1970 or we_to.year < 1970: 
                        continue
                    date_ranges.append((we_from, we_to))

            # Step 2: Merge overlapping or contiguous date ranges
            merged_ranges = []
            for start, end in sorted(date_ranges):
                if not merged_ranges:
                    merged_ranges.append([start, end])
                else:
                    last_start, last_end = merged_ranges[-1]
                    if start <= last_end:  # overlapping or contiguous
                        if end > last_end:
                            merged_ranges[-1][1] = end
                    else:
                        merged_ranges.append([start, end])

            # Step 3: Calculate total years and months from merged ranges
            total_years = 0
            total_months = 0
            for start, end in merged_ranges:
                delta = relativedelta(end, start)
                total_years += delta.years
                total_months += delta.months

                if total_months >= 12:
                    total_years += total_months // 12
                    total_months = total_months % 12

            # Step 4: Format years_of_service string
            if total_years > 0 and total_months > 0:
                nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''} and {total_months} month{'s' if total_months > 1 else ''}"
            elif total_years > 0:
                nominee.years_of_service = f"{total_years} year{'s' if total_years > 1 else ''}"
            elif total_months > 0:
                nominee.years_of_service = f"{total_months} month{'s' if total_months > 1 else ''}"
            else:
                nominee.years_of_service = "Not Available"

            print(f"Nominee: {emp_profile.pi.user.first_name} {emp_profile.pi.user.last_name}, Years of Service: {nominee.years_of_service}")

            # --- End Modified Years of Service Calculation ---

        if toggle and toggle.key_acronym == '1':
            context = {
                'title': 'human_resource_transactions',
                'sub_title': 'awardsf',
                'sub_sub_title': 'deliberation',
                'criteria': Criteria.objects.filter(Q(awards_id=awards_id), Q(is_active=1)).order_by('-percentage', 'id', 'name'),
                'awards': Awards.objects.filter(id=awards_id, year=year).first(),
                'data': nominees,
                'category': Awcategory.objects.filter(status=1),
                'notpost': False,
                'toggle': True,
                'year': year,
                'ctgy': request.POST.get('category'),
                'awrd': awards_id,
            }
        else:
            graders_ids = Deliberation.objects.values('graded_by_id')\
                .filter(Q(nominee__awards_id=awards_id), Q(criteria__is_active=1))\
                .annotate(total_grade=Sum('grade'))
            
            graders = Empprofile.objects.filter(id__in=[x['graded_by_id'] for x in graders_ids])

            context = {
                'title': 'human_resource_transactions',
                'sub_title': 'awardsf',
                'sub_sub_title': 'deliberation',
                'graders': graders,
                'awards': Awards.objects.filter(id=awards_id, year=year).first(),
                'data': nominees,
                'category': Awcategory.objects.filter(status=1),
                'notpost': False,
                'toggle': False,
                'year': year,
                'ctgy': request.POST.get('category'),
                'awrd': awards_id,
            }

        return render(request, 'frontend/awards/deliberation.html', context)

    context = {
        'tab_title': 'Deliberation',
        'title': 'rewards_and_recognition',
        'sub_title': 'awardsf',
        'sub_sub_title': 'deliberation',
        'notpost': True,
        'category': Awcategory.objects.filter(status=1),
    }
    return render(request, 'frontend/awards/deliberation.html', context)





# @login_required
# @permission_required('auth.awards_deliberators')
# def save_deliberation(request):
#     if request.method == "POST":
#         criteria_id = request.POST.getlist('criteria_id[]')
#         nominee_id = request.POST.getlist('nominee_id[]')
#         grade = request.POST.getlist('grade[]')

#         grades = [
#             {'c': c, 'n': n, 'g': g}
#             for c, n, g in zip(criteria_id, nominee_id, grade)
#         ]

#         remarks_nominee_id = request.POST.getlist('remarks_nominee_id[]')
#         remarks = request.POST.getlist('remarks[]')

#         allremarks = [
#             {'n': n, 'r': r}
#             for n, r in zip(remarks_nominee_id, remarks)
#         ]

#         for row in grades:
#             doesexist = Deliberation.objects.filter(Q(nominee_id=row['n']), Q(criteria_id=row['c']),
#                                                     Q(graded_by_id=request.session['emp_id'])).first()
#             rm = ''
#             for r in allremarks:
#                 if r['n'] == row['n']:
#                     rm = r['r']

#             if row['g'] != '':
#                 if not doesexist:
#                     Deliberation.objects.create(
#                         criteria_id=row['c'],
#                         nominee_id=row['n'],
#                         grade=row['g'],
#                         remarks=rm,
#                         graded_by_id=request.session['emp_id'],
#                         graded_on=datetime.now()
#                     )
#                 else:
#                     Deliberation.objects.filter(Q(nominee_id=row['n']), Q(criteria_id=row['c']),
#                                                 Q(graded_by_id=request.session['emp_id'])) \
#                         .update(grade=row['g'], graded_on=datetime.now(), remarks=rm)

#         return JsonResponse({'data': 'success'})




@login_required
@permission_required('auth.awards_deliberators')
def save_deliberation(request):
    if request.method == "POST":
        criteria_id = request.POST.getlist('criteria_id[]')
        nominee_id = request.POST.getlist('nominee_id[]')
        grade = request.POST.getlist('grade[]')

        grades = [{'c': c, 'n': n, 'g': g} for c, n, g in zip(criteria_id, nominee_id, grade)]

        remarks_nominee_id = request.POST.getlist('remarks_nominee_id[]')
        remarks = request.POST.getlist('remarks[]')
        allremarks = [{'n': n, 'r': r} for n, r in zip(remarks_nominee_id, remarks)]

        for row in grades:
            doesexist = Deliberation.objects.filter(
                nominee_id=row['n'],
                criteria_id=row['c'],
                graded_by_id=request.session['emp_id']
            ).first()

            rm = next((r['r'] for r in allremarks if r['n'] == row['n']), '')

            if row['g'] != '':
                if not doesexist:
                    Deliberation.objects.create(
                        criteria_id=row['c'],
                        nominee_id=row['n'],
                        grade=row['g'],
                        remarks=rm,
                        graded_by_id=request.session['emp_id'],
                        graded_on=datetime.now()
                    )
                else:
                    doesexist.grade = row['g']
                    doesexist.remarks = rm
                    doesexist.graded_on = datetime.now()
                    doesexist.save()

        # Handle calibration descriptions and points
        calibration_ids = request.POST.getlist('calibration_criteria_id[]')
        nominee_ids = request.POST.getlist('calibration_nominee_id[]')

        for cid in calibration_ids:
            cdesc = request.POST.get(f'calibration_desc_{cid}', '').strip()

            Calibration.objects.update_or_create(
                crit_id=cid,
                defaults={'desc': cdesc}
            )

            for nominee_id in nominee_ids:
                key = f'calibration_points_{nominee_id}_{cid}'
                cal_points = request.POST.get(key)

                if cal_points is not None:
                    cal_points = cal_points.strip()

                    if cal_points == '':
                        Points_calibration.objects.filter(
                            crit_id=cid,
                            nominee_id=nominee_id
                        ).delete()
                    else:
                        Points_calibration.objects.update_or_create(
                            crit_id=cid,
                            nominee_id=nominee_id,
                            defaults={'points_cal': cal_points}
                        )

        return JsonResponse({'data': 'success'})




@login_required
@permission_required('auth.awards_deliberators')
def get_guidelines(request, year):
    guidelines = AwGuidelines.objects.filter(year=year)

    if guidelines.exists():
        data = [
            {'title': guideline.title, 'file': guideline.file.url} for guideline in guidelines
        ]
        return JsonResponse({'guidelines': data})
    else:
        return JsonResponse({'error': True, 'msg': 'No attachment available.'})
    


