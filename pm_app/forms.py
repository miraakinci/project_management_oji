from django import forms 


class InputForm(forms.Form):
    prompt = forms.CharField(
        label='',
        max_length=500,
        widget=forms.Textarea(attrs={'placeholder': 'e.g., Transform our organization into a data-driven, digitally-enabled enterprise...',
        'class': 'chat-input'}),
        required=True
    )