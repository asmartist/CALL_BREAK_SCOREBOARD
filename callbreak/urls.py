"""
URL configuration for callbreak project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.matches.views import PlayerViewSet, MatchViewSet
from apps.rounds.views import RoundViewSet
from apps.stats.views import StatsListView
from apps.exports.views import MatchExportView

router = DefaultRouter()
router.register(r'players', PlayerViewSet, basename='player')
router.register(r'matches', MatchViewSet, basename='match')
router.register(r'rounds', RoundViewSet, basename='round')

from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('lite/', TemplateView.as_view(template_name='lite.html'), name='lite-home'),
    path('mobile/', TemplateView.as_view(template_name='mobile.html'), name='mobile-home'),
    path('match/<uuid:match_id>/', TemplateView.as_view(template_name='game.html'), name='game'),
    path('match/<uuid:match_id>/complete/', TemplateView.as_view(template_name='complete.html'), name='complete'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/stats/', StatsListView.as_view(), name='stats-list'),
    path('api/matches/<str:match_id>/export/', MatchExportView.as_view(), name='match-export'),
]
