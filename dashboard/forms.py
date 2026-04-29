from django import forms


class SiteProvisionForm(forms.Form):

    domain = forms.CharField(
        label="Domaine principal",
        max_length=255,
        help_text="Exemple : mondomaine.com"
    )

    include_www = forms.BooleanField(
        label="Inclure www",
        required=False,
        initial=True
    )

    github_repo = forms.CharField(
        label="Repository GitHub",
        max_length=120,
        help_text="Format : usergithub/monrepo"
    )

    internal_port = forms.IntegerField(
        label="Port interne",
        initial=80,
        min_value=1,
        max_value=65535
    )

    certbot_email = forms.EmailField(
        label="Email Certbot"
    )

    def clean_github_repo(self):
        repo = self.cleaned_data["github_repo"]

        if "/" not in repo:
            raise forms.ValidationError(
                "Utiliser le format owner/repository"
            )

        return repo.lower()
    
class DomainDiagnosticForm(forms.Form):
    domain = forms.CharField(
        label="Nom de domaine",
        max_length=255,
        help_text="Exemple : mondomaine.com"
    )