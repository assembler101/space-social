from django.shortcuts import render, redirect

from . import models
from . import forms

# http responses
from django.http import HttpResponse, HttpResponseRedirect

# display functionality
from django.views.generic.base import TemplateView

# signup and login functionality
from django.views.generic.edit import CreateView, UpdateView, DeleteView, View
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.hashers import make_password

# display views
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView

# url searching through their names
from django.urls import reverse, reverse_lazy

# validation
from django.core.exceptions import ValidationError

# python modules
import random

class HomePageView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        user = self.request.user

        # display the users information if logged in
        if user.is_authenticated:
            # display all the groups the user is in
            assns = models.Association.objects.filter(member=user)

            kwargs['object_list'] = assns

        return super().get_context_data(**kwargs)

class UserSignUp(CreateView):
    template_name = 'signup.html'

    model = models.User
    form_class = forms.SignUpForm

    def get(self, request):
        # redirect user to home page if already authenticated
        if request.user.is_authenticated:
            return redirect(reverse('basic_app:home'))

        return super().get(request)

    def form_valid(self, form):
        # hash the password. argon2 by default
        password = make_password(form.instance.password)
        form.instance.password = password

        # save the form data
        form.save()

        # display the success message on the same signup page
        return render(self.request, self.template_name, context={
            'signup_success': True,
            'form': form
        })

class UserLogin(LoginView):
    template_name = 'login.html'

    def get(self, request):
        # redirect the user to the home page if already authenticated
        if request.user.is_authenticated:
            return redirect(reverse('basic_app:home'))
        
        return super().get(request)

class UserLogout(LoginRequiredMixin, LogoutView):
    template_name = reverse_lazy('basic_app:user_logout')

class CreateGroup(LoginRequiredMixin, CreateView):
    template_name = 'create_group.html'

    model = models.Group
    fields = ['name']

    def form_valid(self, form):
        user = self.request.user

        # verify max group limit is not exceeded
        user.group_count += 1

        if user.group_count > 5:
            return redirect(reverse('basic_app:max_group_count'))

        # increase group count by 1
        user.save()

        # set group in database
        group = models.Group(name=form.cleaned_data['name'], leader=user)
        group.save()

        # set the user group relation
        assocation = models.Association(group=group, member=user)
        assocation.save()

        return redirect(reverse('basic_app:group_detail', kwargs={ 'pk': group.pk }))

class ListGroups(ListView):
    template_name = 'list_groups.html'
    
    model = models.Group

    def get(self, request, *args, **kwargs):
        # display all groups if user is anonymous
        if not request.user.is_authenticated:
            return super().get(request, *args, **kwargs)

        joinedGroupsIds = []

        # only display the groups the user is not in
        user = request.user

        # get all of the assocations
        assns = models.Association.objects.filter(member=user)

        # append each group id in the association
        for assn in assns:
            joinedGroupsIds.append(assn.group.id)

        # filter out all of the groups the user is in
        filteredGroups = models.Group.objects.exclude(id__in=joinedGroupsIds)

        # display the filtered groups
        return render(request, self.template_name, context={
            'object_list': filteredGroups
        })

class GroupDetailView(DetailView):
    template_name = 'group_detail.html'

    model = models.Group

    def get_context_data(self, **kwargs):
        # call the base implementation first to be able to set key values
        context = super().get_context_data(**kwargs)

        group = self.get_object()

        # render different details if user is anonymous
        if self.request.user.is_authenticated:
            # get the user and group
            user = self.request.user

            # verify if the user is not in the group. If not, display join group btn
            assn = models.Association.objects.filter(
                member=user,
                group=group
            ).first()

            if assn:
                context['already_joined'] = True

        # get all of the posts in the group
        groupPosts = models.Post.objects.filter(group=group)

        context['posts_list'] = groupPosts

        return context

class DeleteGroup(LoginRequiredMixin, DeleteView):
    template_name = 'group_confirm_delete.html'

    model = models.Group
    success_url = reverse_lazy('basic_app:groups_list')

    def get(self, request, *args, **kwargs):
        # confirm the get request was sent by the leader
        groupLeader = self.get_object().leader

        if groupLeader != request.user:
            # show a standard 401 access denied page
            return HttpResponse('<h1>Access Denied.</h1>', status=401)

        # continue everything as usual if correct authentication
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # confirm the post request was sent by the leader
        groupLeader = self.get_object().leader
        
        if groupLeader != request.user:
            # show a standard 401 unauthorized access page
            return HttpResponse('<h1>Something went wrong.</h1>', status=401)

        # reduce the users group count
        groupLeader.group_count -= 1
        groupLeader.save()

        # all posts and associations referring to this group are automatically
        # removed due to models.CASCADE

        # continue everything as usual if correct authentication
        return super().post(request, *args, **kwargs)

class JoinGroup(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        # set the group to user assocation
        user = request.user

        # verify max group limit is not exceeded
        user.group_count += 1

        if user.group_count > 5:
            return redirect(reverse('basic_app:max_group_count'))

        # increase group count by 1
        user.save()

        group = models.Group.objects.get(pk=kwargs['pk'])

        # verify the association already exists to avoid duplicates
        assnCheck = models.Association.objects.filter(member=user, group=group)
        
        if not assnCheck.exists():
            # increment the members count on the group
            group.members_count += 1
            group.save()

            # save the instance
            assn = models.Association(member=user, group=group)
            assn.save()

        # redirect the user to the group he/she joined
        return redirect(reverse('basic_app:group_detail', kwargs={ 'pk': group.pk }))

class LeaveGroup(LoginRequiredMixin, TemplateView):
    template_name = 'group_confirm_leave.html'

    def post(self, request, *args, **kwargs):
        # get the user and group info
        user = request.user
        group = models.Group.objects.get(pk=kwargs['pk'])

        # only non-leaders can leave groups. Owners can only delete groups
        if group.leader == user:
            return HttpResponse('<h1>Only non-owners of the group can leave!</h1>')

        # decrement the users group count
        user.group_count -= 1
        user.save()

        # remove the user to group assocation
        assn = models.Association.objects.get(member=user, group=group)
        assn.delete()

        # decrement the group member count
        group.members_count -= 1
        group.save()

        return redirect(reverse('basic_app:groups_list'))

class CreatePost(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        group_pk = kwargs['pk']

        groupDetailPath = reverse('basic_app:group_detail', kwargs={
            'pk': group_pk
        })

        # get the post data
        author = request.user
        group = models.Group.objects.filter(pk=group_pk).first()
        post_contents = request.POST['post_contents']

        # verify the post contents length is greater than 0
        if len(post_contents) == 0:
            return redirect(groupDetailPath)

        # save the post data in the model
        post = models.Post(author=author, group=group, contents=post_contents)
        post.save()

        return redirect(groupDetailPath)

class DeletePost(LoginRequiredMixin, DeleteView):
    template_name = 'post_confirm_delete.html'

    model = models.Post

    def get(self, request, *args, **kwargs):
        # verify the post author is the authenticated user or 
        # the authenticated user is the leader of the group
        user = request.user
        postAuthor = self.get_object().author
        leader = self.get_object().group.leader

        if user != postAuthor and user != leader:
            return HttpResponse('<h1>Access Denied.</h1>', status=401)

        return super().get(request, *args, **kwargs)
        
    def post(self, request, *args, **kwargs):
        # verify the post author is the authenticated user or 
        # the authenticated user is the leader of the group
        user = request.user
        postAuthor = self.get_object().author
        leader = self.get_object().group.leader

        if user != postAuthor and user != leader:
            return HttpResponse('<h1>Something went wrong.</h1>', status=401)

        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        # redirect back to the group containing the deleted post
        return reverse('basic_app:group_detail',
            kwargs={ 'pk': self.object.group.id }
        )

class MaxGroupCount(TemplateView):
    template_name = 'group_count_exceeded.html'