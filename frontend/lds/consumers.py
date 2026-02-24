from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from backend.models import Empprofile


class LdsTrainingNotificationsConsumer(AsyncJsonWebsocketConsumer):
    admin_group_name = 'lds_admins'

    async def connect(self):
        user = self.scope.get('user')
        if not user or getattr(user, 'is_anonymous', True):
            await self.close()
            return

        emp_id = await self._get_emp_id_for_user(user.id)
        self.user_group_name = f"lds_user_{emp_id}" if emp_id else f"lds_user_{user.id}"

        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        try:
            if user.has_perm('auth.ld_manager'):
                await self.channel_layer.group_add(self.admin_group_name, self.channel_name)
        except Exception:
            pass

        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        except Exception:
            pass

        try:
            await self.channel_layer.group_discard(self.admin_group_name, self.channel_name)
        except Exception:
            pass

    async def lds_notification(self, event):
        await self.send_json(event.get('data', {}))

    @database_sync_to_async
    def _get_emp_id_for_user(self, user_id):
        try:
            return (
                Empprofile.objects
                .filter(pi__user_id=user_id)
                .values_list('id', flat=True)
                .first()
            )
        except Exception:
            return None
