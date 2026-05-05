from django import forms


class SiteProvisionForm(forms.Form):
    github_repo = forms.CharField(
        label="Repo GitHub",
        help_text="Format : owner/repository",
    )

    domain = forms.CharField(
        label="Domaine principal",
        help_text="Exemple : example.com",
    )

    include_www = forms.BooleanField(
        label="Inclure www",
        required=False,
        initial=True,
    )

    internal_port = forms.IntegerField(
        label="Port interne du conteneur",
        initial=80,
    )

    certbot_email = forms.EmailField(
        label="Email Certbot",
    )


class DomainDiagnosticForm(forms.Form):
    domain = forms.CharField(
        label="Domaine",
        help_text="Exemple : example.com",
    )


class VhostEditForm(forms.Form):
    content = forms.CharField(
        label="Contenu du fichier",
        widget=forms.Textarea(
            attrs={
                "rows": 24,
                "class": "code-textarea",
            }
        ),
    )

class TwoFactorVerifyForm(forms.Form):
    token = forms.CharField(
        label="Code de vérification",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "placeholder": "123456",
            }
        ),
    )