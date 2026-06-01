from django.urls import path

from . import views

urlpatterns = [
    path("", views.init, name="init"),
    path("upload", views.upload_doc, name="upload_doc"),
    path("ask", views.ask, name="ask"),
]
