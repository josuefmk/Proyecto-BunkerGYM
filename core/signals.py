from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Cliente

@receiver(post_save, sender=Cliente)
def actualizar_estado_post_save(sender, instance, **kwargs):

    instance.actualizar_estado_plan()
