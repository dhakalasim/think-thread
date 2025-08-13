from django.urls import path
from . import views

urlpatterns = [
    # Dashboard or landing page
    path('', views.dashboard, name='dashboard'),

    # Patient management
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/add/', views.patient_add, name='patient_add'),
    path('patients/<int:id>/', views.patient_detail, name='patient_detail'),

    # Appointment management
    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/book/', views.appointment_book, name='appointment_book'),
    path('appointments/<int:id>/', views.appointment_detail, name='appointment_detail'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
