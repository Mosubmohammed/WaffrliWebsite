from django.contrib.auth import get_user_model
from firebase_admin import auth

User = get_user_model()

class FirebaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract the Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        if not auth_header:
            return self.get_response(request)

        # Extract the token from the Authorization header
        token = auth_header.split("Bearer ")[-1]

        try:
            # Verify the token using Firebase admin SDK
            decoded_token = auth.verify_id_token(token)
            uid = decoded_token["uid"]
            email = decoded_token.get("email")

            # Create or get the Django user based on the Firebase UID
            user, created = User.objects.get_or_create(username=uid, defaults={"email": email})

            # Attach the user to the request
            request.user = user

        except Exception as e:
            # Print the error for debugging (log if necessary)
            print("Invalid Firebase token:", str(e))
            request.user = None

        return self.get_response(request)
