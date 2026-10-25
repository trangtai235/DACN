"""Account creation is isolated from project invitations and administrator roles."""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(label='Họ và tên', max_length=150)
    email = forms.EmailField(label='Email', max_length=254)

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'first_name', 'email')

    def clean_username(self):
        username = super().clean_username()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Tên đăng nhập đã được sử dụng.')
        return username
