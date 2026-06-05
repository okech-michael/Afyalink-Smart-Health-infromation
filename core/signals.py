from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal handler: Create a Profile instance whenever a new User is created.
    This ensures every user has a profile for the ProfileInline in the admin.
    """
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal handler: Ensure the user's profile is saved (for consistency).
    This is a safety measure to sync Profile with User updates.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
