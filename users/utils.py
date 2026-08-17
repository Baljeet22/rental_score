from django.core import signing


def generate_email_verification_token(user):
    return signing.dumps(
        {"user_id": user.id},
        salt="email-verification",
    )
