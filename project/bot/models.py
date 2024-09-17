from django.db import models


class Profile(models.Model):
    external_id = models.PositiveIntegerField(
        verbose_name='ID пользователя в соц сети',
        unique=True,
    )
    name = models.TextField(
        verbose_name='Имя пользователя',
    )
    status = models.TextField(
        default='Не пройдено'
    )
    question = models.IntegerField(
        default=1
    )
    points = models.IntegerField(
        default=0
    )
    totem = models.TextField(
        verbose_name='Тотемное животное',
        default='Не определено'
    )

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'
