

import requests
from backend.models import SMSLogs, Empprofile
from django.conf import settings
from django.template.loader import get_template
from django.core.mail import EmailMultiAlternatives
import os

ITXTMO_API_URL = os.getenv("ITXTMO_API_URL")
ITXTMO_EMAIL = os.getenv("ITXTMO_EMAIL")
ITXTMO_PASSWORD = os.getenv("ITXTMO_PASSWORD")
ITXTMO_API_CODE = os.getenv("ITXTMO_API_CODE") 
    

def send_sms_notification(message, contact_number, emp_id, receiver_id=None):
    if contact_number.startswith("09"):
        contact_number = "63" + contact_number[1:]

    payload = {
        "Email": ITXTMO_EMAIL,
        "Password": ITXTMO_PASSWORD,
        "ApiCode": ITXTMO_API_CODE,
        "Recipients": [contact_number],
        "Message": message
    }

    try:
        response = requests.post(ITXTMO_API_URL, json=payload)
        response_data = response.json()
        print(f"Response from SMS API: {response_data}")

        if response.status_code == 200 and not response_data.get("Error") and response_data.get("Failed") == 0:
            print(f"SMS sent successfully to {contact_number}")

            try:
                SMSLogs.objects.create(
                    message=message,
                    contact_number=contact_number,
                    emp_id=emp_id,
                    receiver_id=receiver_id
                )
            except Exception as e:
                print(f"Error creating SMS log: {str(e)}")
                
            return response_data
        else:
            print(f"Failed to send SMS: {response_data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error sending SMS: {str(e)}")
        return None


def send_notification(message, contact_number, emp_id, receiver_id=None):
    try:
        employee = Empprofile.objects.filter(pi__mobile_no=contact_number).first()
        if employee.pi.user.email:
            plain_text = get_template('email_template/notify_me.txt')
            html_body = get_template('email_template/notify_me.html')

            subject = 'HRPEARS'
            content = message
            email_from = settings.EMAIL_HOST_USER

            d = {
                'message': content,
            }
            message = EmailMultiAlternatives(
                subject,
                plain_text.render(d),
                email_from,
                [employee.pi.user.email]
            )

            message.attach_alternative(html_body.render(d), 'text/html')
            message.send(fail_silently=False)

            SMSLogs.objects.create(
                message=content,
                contact_number=contact_number,
                emp_id=emp_id,
                receiver_id=receiver_id if receiver_id else None
            )
    except Exception:
        pass