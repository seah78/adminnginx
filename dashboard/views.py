import threading

from django.http import JsonResponse
from django.shortcuts import redirect

from .operation_store import create_operation, get_operation
from .provisioner import provision_site, provision_site_live, delete_site

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import SiteProvisionForm, DomainDiagnosticForm, VhostEditForm
from .generator import (
    write_project_files,
    generate_commands,
    list_vhosts,
    get_vhost_detail,
    get_dashboard_summary,
    update_vhost_file,
    nginx_test,
    nginx_reload,
)
from .diagnostics import run_domain_diagnostics

@login_required
def dashboard_home(request):
    summary = get_dashboard_summary()

    return render(
        request,
        "dashboard/index.html",
        {
            "summary": summary,
        }
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

            result = provision_site(data)

            return render(
                request,
                "dashboard/provision_result.html",
                {
                    "data": data,
                    "result": result,
                },
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
        }
    )


@login_required
def site_edit(request, filename):
    vhost = get_vhost_detail(filename)

    if vhost is None:
        return render(
            request,
            "dashboard/site_edit.html",
            {"vhost": None},
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

            vhost = get_vhost_detail(filename)

            return redirect("site_detail", filename=filename)

    return render(
        request,
        "dashboard/site_edit.html",
        {
            "vhost": vhost,
            "form": form,
            "saved": False,
        },
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
def site_delete(request, filename):
    if request.method != "POST":
        return redirect("site_detail", filename=filename)

    result = delete_site(filename)

    return render(
        request,
        "dashboard/delete_result.html",
        {
            "result": result,
            "filename": filename,
        },
    )