from django.conf import settings
from supabase import create_client , Client
class SupabaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        access_token = request.session.get('supabase_access_token')
        
        if access_token:
            try:
                user = settings.SUPABASE.auth.get_user(access_token)
                request.supabase_user = user
            except:
                request.supabase_user = None
                del request.session['supabase_access_token']
        else:
            request.supabase_user = None
        
        return self.get_response(request)