import threading
import base64
import qrcode

from io import BytesIO
from django.contrib import messages
from django_otp.plugins.otp_totp.models import TOTPDevice

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect

from .forms import (
    SiteProvisionForm,
    DomainDiagnosticForm,
    VhostEditForm,
    TwoFactorVerifyForm,
)

from .generator import (
    update_vhost_file,
    list_vhosts,
    get_vhost_detail,
    get_dashboard_summary,
    nginx_test,
    nginx_reload,
)

from .diagnostics import run_domain_diagnostics
from .operation_store import create_operation, get_operation
from .provisioner import provision_site_live, delete_site_live


@login_required
def dashboard_home(request):
    summary = get_dashboard_summary()

    return render(
        request,
        "dashboard/index.html",
        {
            "summary": summary,
        },
    )


@login_required
def site_create(request):
    form = SiteProvisionForm()

    if request.method == "POST":
        form = SiteProvisionForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data.copy()

            owner, repo = data["github_repo"].split("/")

            data["project_name"] = repo
            data["container_name"] = repo
            data["server_path"] = f"/opt/{repo}"
            data["ghcr_image"] = f"ghcr.io/{owner}/{repo}:latest"

            operation_id = create_operation("provision_site")

            thread = threading.Thread(
                target=provision_site_live,
                args=(data, operation_id),
                daemon=True,
            )
            thread.start()

            return redirect(
                "operation_progress",
                operation_id=operation_id,
            )

    return render(
        request,
        "dashboard/site_create.html",
        {
            "form": form,
        },
    )


@login_required
def site_list(request):
    vhosts = list_vhosts()

    return render(
        request,
        "dashboard/site_list.html",
        {
            "vhosts": vhosts,
        },
    )


@login_required
def site_detail(request, filename):
    vhost = get_vhost_detail(filename)

    if vhost is None:
        return render(
            request,
            "dashboard/site_detail.html",
            {
                "vhost": None,
                "diagnostics": [],
            },
            status=404,
        )

    diagnostics = []

    if vhost["primary_domain"] != "Non détecté":
        diagnostics = run_domain_diagnostics(
            vhost["primary_domain"]
        )

    return render(
        request,
        "dashboard/site_detail.html",
        {
            "vhost": vhost,
            "diagnostics": diagnostics,
        },
    )


@login_required
def site_edit(request, filename):
    vhost = get_vhost_detail(filename)

    if vhost is None:
        return render(
            request,
            "dashboard/site_edit.html",
            {
                "vhost": None,
                "form": None,
            },
            status=404,
        )

    form = VhostEditForm(
        initial={
            "content": vhost["content"],
        }
    )

    if request.method == "POST":
        form = VhostEditForm(request.POST)

        if form.is_valid():
            update_vhost_file(
                filename,
                form.cleaned_data["content"],
            )

            return redirect(
                "site_detail",
                filename=filename,
            )

    return render(
        request,
        "dashboard/site_edit.html",
        {
            "vhost": vhost,
            "form": form,
        },
    )


@login_required
def site_delete(request, filename):
    if request.method != "POST":
        return redirect("site_detail", filename=filename)

    operation_id = create_operation("delete_site")

    thread = threading.Thread(
        target=delete_site_live,
        args=(filename, operation_id),
        daemon=True,
    )
    thread.start()

    return redirect(
        "operation_progress",
        operation_id=operation_id,
    )


@login_required
def nginx_test_view(request, filename):
    success, output = nginx_test()

    request.session["nginx_test"] = {
        "success": success,
        "output": output,
    }

    return redirect("site_detail", filename=filename)


@login_required
def nginx_reload_view(request, filename):
    success, output = nginx_reload()

    request.session["nginx_reload"] = {
        "success": success,
        "output": output,
    }

    return redirect("site_detail", filename=filename)


@login_required
def diagnostics_view(request):
    form = DomainDiagnosticForm()
    results = None
    domain = None

    if request.method == "POST":
        form = DomainDiagnosticForm(request.POST)

        if form.is_valid():
            domain = form.cleaned_data["domain"].strip().lower()
            results = run_domain_diagnostics(domain)

    return render(
        request,
        "dashboard/diagnostics.html",
        {
            "form": form,
            "results": results,
            "domain": domain,
        },
    )


@login_required
def operation_progress(request, operation_id):
    return render(
        request,
        "dashboard/operation_progress.html",
        {
            "operation_id": operation_id,
        },
    )


@login_required
def operation_status(request, operation_id):
    return JsonResponse(get_operation(operation_id))


@login_required
def security_view(request):
    device = TOTPDevice.objects.filter(
        user=request.user,
        confirmed=True,
    ).first()

    return render(
        request,
        "dashboard/security.html",
        {
            "two_factor_enabled": device is not None,
        },
    )


@login_required
def two_factor_setup(request):
    device, created = TOTPDevice.objects.get_or_create(
        user=request.user,
        name="default",
        defaults={
            "confirmed": False,
        },
    )

    if device.confirmed:
        return redirect("security")

    form = TwoFactorVerifyForm()

    if request.method == "POST":
        form = TwoFactorVerifyForm(request.POST)

        if form.is_valid():
            token = form.cleaned_data["token"]

            if device.verify_token(token):
                device.confirmed = True
                device.save()

                messages.success(
                    request,
                    "La double authentification est activée.",
                )

                return redirect("security")

            messages.error(
                request,
                "Code invalide. Réessaie avec un nouveau code.",
            )

    qr = qrcode.make(device.config_url)

    stream = BytesIO()
    qr.save(stream, format="PNG")

    qr_base64 = base64.b64encode(
        stream.getvalue()
    ).decode("utf-8")

    return render(
        request,
        "dashboard/two_factor_setup.html",
        {
            "form": form,
            "device": device,
            "qr_base64": qr_base64,
        },
    )


@login_required
def two_factor_disable(request):
    if request.method == "POST":
        TOTPDevice.objects.filter(user=request.user).delete()

        messages.success(
            request,
            "La double authentification est désactivée.",
        )

    return redirect("security")