from django.db import models
from django.contrib.auth.models import AbstractBaseUser, UserManager

# add case insensitivity upon searching usernames in the user auth model
class CustomUserManager(UserManager):
    def get_by_natural_key(self, username):
        case_insensitive_username_field = '{}__iexact'.format(self.model.USERNAME_FIELD)
        return self.get(**{case_insensitive_username_field: username})

# use django's built in user authentication
class User(AbstractBaseUser):
    username = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=20)
    group_count = models.PositiveIntegerField(default=0)
    max_groups = models.PositiveIntegerField(default=5)
    # last login is included by default

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    
    def __str__(self):
        return self.username

class Group(models.Model):
    leader = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=32, unique=True)
    members_count = models.PositiveIntegerField(default=1)
    date_created = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.name

class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    contents = models.CharField(max_length=1024)
    datetime_posted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.author.username + ': ' + self.content

class Association(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    member = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.group.name + ': ' + self.member.username