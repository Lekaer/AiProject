from django.urls import path

from . import views

urlpatterns = [
    path("", views.init, name="init"),

    # 知识库 CRUD
    path("api/kb", views.kb_view, name="kb_list_create"),
    path("api/kb/<str:kb_name>", views.kb_delete, name="kb_delete"),

    # 文档管理（知识库内）
    path("api/kb/<str:kb_name>/docs", views.docs_view, name="docs_upload_list_delete"),

    # 问答
    path("api/kb/<str:kb_name>/ask", views.ask, name="ask"),
]
