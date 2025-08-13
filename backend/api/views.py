from django.http import HttpResponse
from django.shortcuts import render

def dashboard(request):
    return render(request, 'api/dashboard.html')

def patient_list(request):
    return HttpResponse("List of patients")

def patient_add(request):
    return HttpResponse("Add a new patient")

def patient_detail(request, id):
    return HttpResponse(f"Patient details for ID {id}")

def appointment_list(request):
    return HttpResponse("List of appointments")

def appointment_book(request):
    return HttpResponse("Book an appointment")

def appointment_detail(request, id):
    return HttpResponse(f"Appointment details for ID {id}")

def login_view(request):
    return HttpResponse("Login page")

def logout_view(request):
    return HttpResponse("Logout page")
