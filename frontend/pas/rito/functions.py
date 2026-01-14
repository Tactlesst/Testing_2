from frontend.models import RitoSignatories


def check_signatories_rito_workflow(rito_id):
    requested_by = RitoSignatories.objects.filter(rito_id=rito_id, status=1, signatory_type=0)
    noted_by = RitoSignatories.objects.filter(rito_id=rito_id, status=1, signatory_type=1)
    approved_by = RitoSignatories.objects.filter(rito_id=rito_id, status=1, signatory_type=2)

    count = 0
    if requested_by:
        count += 1

    if noted_by:
        count += 1

    if approved_by:
        count += 1

    if count == 3:
        return True, abs(count - 3)
    else:
        return False, abs(count - 3)