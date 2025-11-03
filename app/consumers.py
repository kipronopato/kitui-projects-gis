import json
from channels.generic.websocket import AsyncWebSocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Project, ProjectUpdate, CitizenReport
from django.utils import timezone

class ProjectTimelineConsumer(AsyncWebSocketConsumer):
    async def connect(self):
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.room_group_name = f'project_timeline_{self.project_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send existing timeline data when client connects
        timeline_data = await self.get_timeline_data()
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'data': timeline_data
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'new_update':
            # Handle new project update
            await self.handle_new_update(text_data_json)
        elif message_type == 'new_report':
            # Handle new citizen report
            await self.handle_new_report(text_data_json)
        elif message_type == 'typing':
            # Handle typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_message',
                    'user': text_data_json.get('user', 'Anonymous'),
                    'is_typing': text_data_json.get('is_typing', False)
                }
            )

    async def handle_new_update(self, data):
        update = await self.create_project_update(data)
        if update:
            # Send to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'new_update_message',
                    'update': await self.serialize_update(update)
                }
            )

    async def handle_new_report(self, data):
        report = await self.create_citizen_report(data)
        if report:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'new_report_message',
                    'report': await self.serialize_report(report)
                }
            )

    # Receive message from room group
    async def new_update_message(self, event):
        update = event['update']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_update',
            'update': update
        }))

    async def new_report_message(self, event):
        report = event['report']
        
        await self.send(text_data=json.dumps({
            'type': 'new_report',
            'report': report
        }))

    async def typing_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user': event['user'],
            'is_typing': event['is_typing']
        }))

    @database_sync_to_async
    def get_timeline_data(self):
        """Get all timeline items for the project"""
        project = Project.objects.get(id=self.project_id)
        
        # Get project updates
        updates = ProjectUpdate.objects.filter(project=project).select_related('reported_by').order_by('created_at')
        # Get citizen reports
        reports = CitizenReport.objects.filter(project=project).select_related('reported_by').order_by('created_at')
        
        # Combine and sort all timeline items
        timeline_items = []
        
        for update in updates:
            timeline_items.append({
                'type': 'update',
                'id': update.id,
                'title': update.title,
                'description': update.description,
                'progress_percentage': update.progress_percentage,
                'photo': update.photo.url if update.photo else None,
                'created_at': update.created_at.isoformat(),
                'created_by': update.reported_by.username if update.reported_by else 'System',
                'user_avatar': self.get_user_avatar(update.reported_by)
            })
        
        for report in reports:
            timeline_items.append({
                'type': 'report',
                'id': report.id,
                'report_type': report.report_type,
                'description': report.description,
                'photo': report.photo.url if report.photo else None,
                'created_at': report.created_at.isoformat(),
                'created_by': report.reported_by.username if report.reported_by else 'Anonymous',
                'is_approved': report.is_approved,
                'user_avatar': self.get_user_avatar(report.reported_by)
            })
        
        # Sort by creation date
        timeline_items.sort(key=lambda x: x['created_at'])
        
        return {
            'project': {
                'id': project.id,
                'name': project.name,
                'status': project.status
            },
            'timeline': timeline_items
        }

    @database_sync_to_async
    def create_project_update(self, data):
        """Create a new project update"""
        try:
            project = Project.objects.get(id=self.project_id)
            user = self.scope['user'] if not isinstance(self.scope['user'], AnonymousUser) else None
            
            update = ProjectUpdate.objects.create(
                project=project,
                title=data.get('title', 'Update'),
                description=data.get('description', ''),
                progress_percentage=data.get('progress_percentage', 0),
                reported_by=user
            )
            
            # Handle file upload if present
            # Note: File uploads through WebSocket need special handling
            # For now, we'll handle them through separate HTTP requests
            
            return update
        except Exception as e:
            print(f"Error creating update: {e}")
            return None

    @database_sync_to_async
    def create_citizen_report(self, data):
        """Create a new citizen report"""
        try:
            project = Project.objects.get(id=self.project_id)
            user = self.scope['user'] if not isinstance(self.scope['user'], AnonymousUser) else None
            
            report = CitizenReport.objects.create(
                project=project,
                report_type=data.get('report_type', 'progress'),
                description=data.get('description', ''),
                reported_by=user,
                is_approved=False  # Default to not approved
            )
            
            return report
        except Exception as e:
            print(f"Error creating report: {e}")
            return None

    @database_sync_to_async
    def serialize_update(self, update):
        """Serialize project update for JSON"""
        return {
            'type': 'update',
            'id': update.id,
            'title': update.title,
            'description': update.description,
            'progress_percentage': update.progress_percentage,
            'photo': update.photo.url if update.photo else None,
            'created_at': update.created_at.isoformat(),
            'created_by': update.reported_by.username if update.reported_by else 'System',
            'user_avatar': self.get_user_avatar(update.reported_by)
        }

    @database_sync_to_async
    def serialize_report(self, report):
        """Serialize citizen report for JSON"""
        return {
            'type': 'report',
            'id': report.id,
            'report_type': report.report_type,
            'description': report.description,
            'photo': report.photo.url if report.photo else None,
            'created_at': report.created_at.isoformat(),
            'created_by': report.reported_by.username if report.reported_by else 'Anonymous',
            'is_approved': report.is_approved,
            'user_avatar': self.get_user_avatar(report.reported_by)
        }

    def get_user_avatar(self, user):
        """Get user avatar URL - you can extend this based on your user model"""
        if not user or isinstance(user, AnonymousUser):
            return '/static/images/default-avatar.png'
        
        # Example: if you have an avatar field in your User model
        # return user.avatar.url if user.avatar else '/static/images/default-avatar.png'
        return '/static/images/default-avatar.png'